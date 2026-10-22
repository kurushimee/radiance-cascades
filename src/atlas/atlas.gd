class_name Atlas
extends RefCounted
## The surface atlas and its probes (design/atlas.md). Each GI instance's UV2 gets a rectangle at its mesh's lightmap
## size, packed into one atlas, and instances with two-sided surfaces get a second one for the backs. A raster capture
## finds each texel's surface at `samples × samples` points. A texel covered by at least half a texel of world surface
## becomes a probe of its own; a texel with less joins a neighbouring probe of its chart, or else a probe that groups its
## instance's sub-texel charts by world cell and normal class. The map then sends every texel to the probe it reads.

enum View { ALBEDO, NORMAL, POSITION, EMISSION, PROBES, KINDS, DIRECT }

const CAPTURE_PASS: StringName = &"Atlas capture"
const PROBES_PASS: StringName = &"Atlas probes"
## Geometry2D.make_atlas tries widths up to this many texels and fails on a wider rectangle.
const MAX_RECT_WIDTH: int = 4096
## The key's 18 instance bits (cshd_probes.glslinc).
const MAX_INSTANCES: int = 1 << 18
const PADDING: int = 1
const TILE: int = 8
const PROBE_GROUP_SIZE: int = 64
const HEADER_BYTES: int = 16
const RECT_BYTES: int = 32
const PROBE_BYTES: int = 64
const DIRECT_BYTES: int = 16
const GROUP_BYTES: int = 64
const COUNT_BYTES: int = 16

var size: Vector2i = Vector2i.ZERO
var rect_count: int = 0
var covered_texels: int = 0
## Texels that are probes of their own.
var solid_count: int = 0
## Texels that belong to groups, and the groups.
var grouped_texels: int = 0
var group_count: int = 0
var probe_count: int = 0
## Grouped texels outside the cells a key holds, which belong to no probe.
var outside_texels: int = 0
## Probes that sat behind a one-sided surface and moved out through it, and the groups among them.
var moved_probes: int = 0
var moved_groups: int = 0
var resident_bytes: int = 0
## CPU time of the build, the GPU's waits for the readbacks included.
var build_milliseconds: float = 0.0

var _device: RenderingDevice = null
var _shaders: GIShaders = null
var _texel_size: float = 0.0
var _rects: RID = RID()
var _map: RID = RID()
var _probes: RID = RID()
var _direct: RID = RID()
var _view_shader: ComputeShader = null
var _texel_view_shader: ComputeShader = null
var _transient: Array[RID] = []


func _init(device: RenderingDevice, shaders: GIShaders) -> void:
	_device = device
	_shaders = shaders


## `texel_size` is the import's, in metres.
func build(scene: TracerScene, tracer: Tracer, texel_size: float, samples: int) -> bool:
	var start: int = Time.get_ticks_usec()
	_texel_size = texel_size
	if !_pack(scene):
		return false

	var captures: Array[RID] = _capture(tracer, samples)
	_form_probes(tracer, captures, samples)
	for transient: RID in _transient:
		_device.free_rid(transient)
	_transient.clear()
	resident_bytes = (HEADER_BYTES + RECT_BYTES * rect_count + 4 * size.x * size.y
			+ (PROBE_BYTES + DIRECT_BYTES) * probe_count)
	_view_shader = ComputeShader.new(_device, _shaders.atlas_view)
	_texel_view_shader = ComputeShader.new(_device, _shaders.texel_view)
	build_milliseconds = (Time.get_ticks_usec() - start) * 0.001
	return true


## The rectangles and the map, bindings 0 and 1 of cshd_atlas.glslinc.
func get_uniforms() -> Array[RDUniform]:
	return ComputeShader.storage_uniforms([_rects, _map])


## The probes and their direct light, bindings 0 and 1 of cshd_probe.glslinc.
func get_probe_uniforms() -> Array[RDUniform]:
	return ComputeShader.storage_uniforms([_probes, _direct])


## The atlas as the GI reads it, one probe value per texel, with alpha 0 where no probe is. Reading it stalls the GPU.
func get_view(view: View) -> Image:
	var target: RID = _view_target(size)
	var sets: Array[RID] = [
		_view_shader.create_uniform_set(get_uniforms(), 0),
		_view_shader.create_uniform_set(get_probe_uniforms(), 1),
		_view_shader.create_uniform_set([_image_uniform(target, 0)], 2),
	]
	var tiles: Vector2i = _tiles(size)
	_view_shader.dispatch(sets, PackedInt32Array([view]).to_byte_array(), tiles.x, tiles.y)
	return _read_view(target, sets, size)


## The probes as a camera sees them: each pixel shows a value of the probe its primary ray reads, with alpha 0 where
## the ray finds none. `camera_basis` is CameraRays.basis's. Reading it stalls the GPU.
func get_texel_view(view: View, tracer: Tracer, camera_basis: PackedFloat32Array, view_size: Vector2i) -> Image:
	var target: RID = _view_target(view_size)
	var sets: Array[RID] = [
		_texel_view_shader.create_uniform_set(tracer.get_uniforms(), 0),
		_texel_view_shader.create_uniform_set(get_uniforms(), 1),
		_texel_view_shader.create_uniform_set(get_probe_uniforms(), 2),
		_texel_view_shader.create_uniform_set([_image_uniform(target, 0)], 3),
	]
	var parameters: PackedByteArray = camera_basis.to_byte_array()
	parameters.append_array(PackedInt32Array([view_size.x, view_size.y, view]).to_byte_array())
	var tiles: Vector2i = _tiles(view_size)
	_texel_view_shader.dispatch(sets, parameters, tiles.x, tiles.y)
	return _read_view(target, sets, view_size)


func free_rids() -> void:
	for view_shader: ComputeShader in [_view_shader, _texel_view_shader]:
		if is_instance_valid(view_shader):
			view_shader.free_rids()
	for owned: RID in [_rects, _map, _probes, _direct]:
		if owned.is_valid():
			_device.free_rid(owned)


# One rectangle per instance and one more per instance with two-sided surfaces, each with a texel of padding on every
# side. xatlas leaves its charts two empty texels apart, and the padding keeps rectangles as far apart.
func _pack(scene: TracerScene) -> bool:
	var instance_count: int = scene.lightmap_sizes.size()
	if instance_count > MAX_INSTANCES:
		push_error("The GI has %d instances; the atlas holds %d." % [instance_count, MAX_INSTANCES])
		return false

	var sizes := PackedVector2Array()
	for instance: int in instance_count:
		var lightmap_size: Vector2i = scene.lightmap_sizes[instance]
		if lightmap_size.x <= 0 || lightmap_size.y <= 0 || lightmap_size.x + 2 * PADDING > MAX_RECT_WIDTH:
			push_error("Instance %d has a lightmap size of %s, which the atlas cannot hold." % [instance, lightmap_size])
			return false

		for side: int in (2 if scene.two_sided[instance] else 1):
			sizes.append(Vector2(lightmap_size + Vector2i(2 * PADDING, 2 * PADDING)))
	rect_count = sizes.size()

	# gdstyle-ignore[untyped-collection]: the engine returns the packing as an untyped Dictionary
	var packing: Dictionary = Geometry2D.make_atlas(sizes)
	var points: PackedVector2Array = packing["points"]
	size = packing["size"]
	var data := PackedByteArray()
	data.resize(HEADER_BYTES + RECT_BYTES * instance_count)
	data.encode_s32(0, size.x)
	data.encode_s32(4, size.y)
	var rect: int = 0
	for instance: int in instance_count:
		var offset: int = HEADER_BYTES + RECT_BYTES * instance
		var front: Vector2i = Vector2i(points[rect]) + Vector2i(PADDING, PADDING)
		var back: Vector2i = Vector2i(-1, -1)
		rect += 1
		if scene.two_sided[instance]:
			back = Vector2i(points[rect]) + Vector2i(PADDING, PADDING)
			rect += 1
		for value: int in [front.x, front.y, back.x, back.y, scene.lightmap_sizes[instance].x,
				scene.lightmap_sizes[instance].y]:
			data.encode_s32(offset, value)
			offset += 4
	_rects = _device.storage_buffer_create(data.size(), data)
	_map = _device.storage_buffer_create(4 * size.x * size.y)
	return true


# Each of the samples² passes rasterizes every triangle at one sample point per texel, then adds what it found there to
# the sums. Returns the sums: positions, normals, albedos and emissions.
func _capture(tracer: Tracer, samples: int) -> Array[RID]:
	GpuPass.begin(_device, CAPTURE_PASS)
	var codes: RID = _create_texture(RenderingDevice.DATA_FORMAT_R32_UINT,
			RenderingDevice.TEXTURE_USAGE_COLOR_ATTACHMENT_BIT | RenderingDevice.TEXTURE_USAGE_STORAGE_BIT)
	var captures: Array[RID] = []
	for capture: int in 4:
		var texture: RID = _create_texture(RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT,
				RenderingDevice.TEXTURE_USAGE_STORAGE_BIT | RenderingDevice.TEXTURE_USAGE_CAN_COPY_TO_BIT)
		_device.texture_clear(texture, Color(0.0, 0.0, 0.0, 0.0), 0, 1, 0, 1)
		captures.append(texture)
	_transient.append(codes)
	_transient.append_array(captures)

	var raster := CaptureRaster.new(_device, _shaders.capture, codes)
	var raster_sets: Array[RID] = [
		raster.create_uniform_set(_raster_trace_uniforms(tracer), 0),
		raster.create_uniform_set(get_uniforms(), 1),
	]
	var sampler := ComputeShader.new(_device, _shaders.capture_samples)
	var image_uniforms: Array[RDUniform] = [_image_uniform(codes, 0)]
	for capture: int in captures.size():
		image_uniforms.append(_image_uniform(captures[capture], capture + 1))
	image_uniforms.append_array(ComputeShader.storage_uniforms([tracer.get_corner_normals()], captures.size() + 1))
	var sample_sets: Array[RID] = [
		sampler.create_uniform_set(tracer.get_uniforms(), 0),
		sampler.create_uniform_set(get_uniforms(), 1),
		sampler.create_uniform_set(image_uniforms, 2),
	]

	var footprint: float = 1.0 / samples
	for row: int in samples:
		for column: int in samples:
			_capture_sample(raster, raster_sets, sampler, sample_sets, Vector2(column + 0.5, row + 0.5) * footprint,
					footprint, tracer.triangle_count)

	raster.free_rids()
	sampler.free_rids()
	return captures


func _capture_sample(raster: CaptureRaster, raster_sets: Array[RID], sampler: ComputeShader,
		sample_sets: Array[RID], offset: Vector2, footprint: float, triangle_count: int) -> void:
	raster.draw(raster_sets, offset, 3 * triangle_count)
	var parameters: PackedByteArray = PackedFloat32Array([offset.x, offset.y, footprint]).to_byte_array()
	sampler.dispatch(sample_sets, parameters, _tiles(size).x, _tiles(size).y)


func _form_probes(tracer: Tracer, captures: Array[RID], samples: int) -> void:
	var texel_count: int = size.x * size.y
	var counts: RID = _transient_buffer(COUNT_BYTES)
	_device.buffer_clear(counts, 0, COUNT_BYTES)
	var solids: RID = _transient_buffer(4 * texel_count)
	var keys: RID = _transient_buffer(8 * texel_count)
	var classify := ComputeShader.new(_device, _shaders.probe_classify)
	var classify_uniforms: Array[RDUniform] = _images(captures)
	classify_uniforms.append_array(ComputeShader.storage_uniforms([counts, solids, keys], captures.size()))
	var parameters: PackedByteArray = PackedFloat32Array([_texel_size, samples * samples]).to_byte_array()
	classify.dispatch([classify.create_uniform_set(get_uniforms(), 0), classify.create_uniform_set(classify_uniforms, 1)],
			parameters, _tiles(size).x, _tiles(size).y)
	classify.free_rids()
	GpuPass.end(_device, CAPTURE_PASS)

	# Sorting on the CPU puts the probes in an order that does not depend on the order the atomics ran in.
	var count_values: PackedInt32Array = _device.buffer_get_data(counts).to_int32_array()
	solid_count = count_values[0]
	grouped_texels = count_values[1]
	outside_texels = count_values[2]
	covered_texels = count_values[3]
	var solid_texels: PackedInt32Array = _device.buffer_get_data(solids, 0, maxi(4 * solid_count, 4)).to_int32_array()
	solid_texels.resize(solid_count)
	solid_texels.sort()
	var group_keys: PackedInt64Array = _unique_keys(keys, grouped_texels)
	group_count = group_keys.size()
	probe_count = solid_count + group_count
	if outside_texels > 0:
		push_error("%d texels lie too far from the origin for a group key." % outside_texels)
	if solid_count > 0:
		_device.buffer_update(solids, 0, 4 * solid_count, solid_texels.to_byte_array())
	if group_count > 0:
		_device.buffer_update(keys, 0, 8 * group_count, group_keys.to_byte_array())

	GpuPass.begin(_device, PROBES_PASS)
	var groups: RID = _transient_buffer(maxi(GROUP_BYTES * group_count, GROUP_BYTES))
	_device.buffer_clear(groups, 0, maxi(GROUP_BYTES * group_count, GROUP_BYTES))
	_device.buffer_clear(counts, 0, COUNT_BYTES)
	_probes = _device.storage_buffer_create(maxi(PROBE_BYTES * probe_count, PROBE_BYTES))
	_direct = _device.storage_buffer_create(maxi(DIRECT_BYTES * probe_count, DIRECT_BYTES))
	_map_texels(captures, solids, keys)
	_sum_groups(captures, groups)
	_write_probes(tracer, captures, solids, keys, groups, counts)
	GpuPass.end(_device, PROBES_PASS)

	count_values = _device.buffer_get_data(counts).to_int32_array()
	moved_probes = count_values[0]
	moved_groups = count_values[1]
	if count_values[2] > 0:
		push_error("%d probe groups hold more texels than their sums can." % count_values[2])


# Sorted keys without repeats, as 64-bit numbers whose top bit is clear.
func _unique_keys(keys: RID, count: int) -> PackedInt64Array:
	if count == 0:
		return PackedInt64Array()

	var sorted: PackedInt64Array = _device.buffer_get_data(keys, 0, 8 * count).to_int64_array()
	sorted.sort()
	var unique := PackedInt64Array()
	unique.resize(count)
	var unique_count: int = 0
	var previous: int = -1
	for key: int in sorted:
		if key != previous:
			unique[unique_count] = key
			unique_count += 1
			previous = key
	unique.resize(unique_count)
	return unique


func _map_texels(captures: Array[RID], solids: RID, keys: RID) -> void:
	var shader := ComputeShader.new(_device, _shaders.probe_map)
	var uniforms: Array[RDUniform] = _images(captures.slice(0, 3))
	uniforms.append_array(ComputeShader.storage_uniforms([solids, keys], 3))
	var sets: Array[RID] = [shader.create_uniform_set(get_uniforms(), 0), shader.create_uniform_set(uniforms, 1)]
	for padding: int in 2:
		var parameters := PackedByteArray()
		parameters.resize(16)
		parameters.encode_float(0, _texel_size)
		parameters.encode_u32(4, solid_count)
		parameters.encode_u32(8, group_count)
		parameters.encode_u32(12, padding)
		shader.dispatch(sets, parameters, _tiles(size).x, _tiles(size).y)
	shader.free_rids()


func _sum_groups(captures: Array[RID], groups: RID) -> void:
	if group_count == 0:
		return

	var shader := ComputeShader.new(_device, _shaders.probe_groups)
	var uniforms: Array[RDUniform] = _images(captures)
	uniforms.append_array(ComputeShader.storage_uniforms([groups], captures.size()))
	var sets: Array[RID] = [shader.create_uniform_set(get_uniforms(), 0), shader.create_uniform_set(uniforms, 1)]
	for sums: int in 2:
		var parameters := PackedByteArray()
		parameters.resize(12)
		parameters.encode_float(0, _texel_size)
		parameters.encode_u32(4, solid_count)
		parameters.encode_u32(8, sums)
		shader.dispatch(sets, parameters, _tiles(size).x, _tiles(size).y)
	shader.free_rids()


func _write_probes(tracer: Tracer, captures: Array[RID], solids: RID, keys: RID, groups: RID, counts: RID) -> void:
	if probe_count == 0:
		return

	var shader := ComputeShader.new(_device, _shaders.probe_data)
	var uniforms: Array[RDUniform] = _images(captures)
	uniforms.append_array(ComputeShader.storage_uniforms([solids, keys, groups, counts], captures.size()))
	var sets: Array[RID] = [
		shader.create_uniform_set(tracer.get_uniforms(), 0),
		shader.create_uniform_set(get_uniforms(), 1),
		shader.create_uniform_set(get_probe_uniforms(), 2),
		shader.create_uniform_set(uniforms, 3),
	]
	var parameters := PackedByteArray()
	parameters.resize(12)
	parameters.encode_float(0, _texel_size)
	parameters.encode_u32(4, solid_count)
	parameters.encode_u32(8, probe_count)
	shader.dispatch(sets, parameters, ComputeShader.group_count(probe_count, PROBE_GROUP_SIZE))
	shader.free_rids()


func _create_texture(format: RenderingDevice.DataFormat, usage: int, texture_size: Vector2i = Vector2i.ZERO) -> RID:
	var extent: Vector2i = texture_size if texture_size else size
	var texture_format := RDTextureFormat.new()
	texture_format.format = format
	texture_format.width = extent.x
	texture_format.height = extent.y
	texture_format.usage_bits = usage
	return _device.texture_create(texture_format, RDTextureView.new())


func _transient_buffer(bytes: int) -> RID:
	var buffer: RID = _device.storage_buffer_create(bytes)
	_transient.append(buffer)
	return buffer


func _images(textures: Array[RID]) -> Array[RDUniform]:
	var uniforms: Array[RDUniform] = []
	for binding: int in textures.size():
		uniforms.append(_image_uniform(textures[binding], binding))
	return uniforms


func _image_uniform(texture: RID, binding: int) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	uniform.binding = binding
	uniform.add_id(texture)
	return uniform


# The tracer's triangle and attribute buffers, bindings 1 and 2 of its set, are bindings 0 and 1 of the raster's.
func _raster_trace_uniforms(tracer: Tracer) -> Array[RDUniform]:
	var uniforms: Array[RDUniform] = []
	for uniform: RDUniform in tracer.get_uniforms().slice(1, 3):
		var moved := RDUniform.new()
		moved.uniform_type = uniform.uniform_type
		moved.binding = uniform.binding - 1
		for id: RID in uniform.get_ids():
			moved.add_id(id)
		uniforms.append(moved)
	return uniforms


func _view_target(view_size: Vector2i) -> RID:
	return _create_texture(RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT,
			RenderingDevice.TEXTURE_USAGE_STORAGE_BIT | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT, view_size)


func _read_view(target: RID, sets: Array[RID], view_size: Vector2i) -> Image:
	var image: Image = Image.create_from_data(view_size.x, view_size.y, false, Image.FORMAT_RGBAF,
			_device.texture_get_data(target, 0))
	for uniform_set: RID in sets:
		_device.free_rid(uniform_set)
	_device.free_rid(target)
	return image


func _tiles(extent: Vector2i) -> Vector2i:
	return Vector2i(ComputeShader.group_count(extent.x, TILE), ComputeShader.group_count(extent.y, TILE))


## The capture's raster pass: every triangle drawn procedurally into an R32_UINT target the size of the atlas.
class CaptureRaster:
	var _device: RenderingDevice = null
	var _shader: RID = RID()
	var _pipeline: RID = RID()
	var _framebuffer: RID = RID()


	func _init(device: RenderingDevice, file: RDShaderFile, target: RID) -> void:
		_device = device
		var spirv: RDShaderSPIRV = file.get_spirv()
		if spirv.compile_error_vertex || spirv.compile_error_fragment:
			push_error("%s does not compile: %s%s" % [file.resource_path, spirv.compile_error_vertex,
					spirv.compile_error_fragment])
			return

		_shader = device.shader_create_from_spirv(spirv, file.resource_path.get_file())
		_framebuffer = device.framebuffer_create([target])
		var blend := RDPipelineColorBlendState.new()
		blend.attachments = [RDPipelineColorBlendStateAttachment.new()]
		_pipeline = device.render_pipeline_create(_shader, device.framebuffer_get_format(_framebuffer),
				RenderingDevice.INVALID_FORMAT_ID, RenderingDevice.RENDER_PRIMITIVE_TRIANGLES,
				RDPipelineRasterizationState.new(), RDPipelineMultisampleState.new(), RDPipelineDepthStencilState.new(),
				blend)


	func create_uniform_set(uniforms: Array[RDUniform], set_index: int) -> RID:
		return _device.uniform_set_create(uniforms, _shader, set_index)


	## Clears the target, then draws the fronts of every triangle and the backs of the two-sided ones.
	func draw(uniform_sets: Array[RID], sample_offset: Vector2, vertex_count: int) -> void:
		var list: int = _device.draw_list_begin(_framebuffer, RenderingDevice.DRAW_CLEAR_COLOR_0,
				PackedColorArray([Color(0.0, 0.0, 0.0, 0.0)]))
		_device.draw_list_bind_render_pipeline(list, _pipeline)
		for set_index: int in uniform_sets.size():
			_device.draw_list_bind_uniform_set(list, uniform_sets[set_index], set_index)
		for back: int in 2:
			var parameters := PackedByteArray()
			parameters.resize(12)
			parameters.encode_float(0, sample_offset.x)
			parameters.encode_float(4, sample_offset.y)
			parameters.encode_u32(8, back)
			_device.draw_list_set_push_constant(list, parameters, parameters.size())
			_device.draw_list_draw(list, false, 1, vertex_count)
		_device.draw_list_end()


	# Freeing the shader frees its pipeline and uniform sets with it.
	func free_rids() -> void:
		if _framebuffer.is_valid():
			_device.free_rid(_framebuffer)
		if _shader.is_valid():
			_device.free_rid(_shader)
