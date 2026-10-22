class_name Tracer
extends RefCounted
## The tracer's scene on the GPU: the static triangles in a hardware acceleration structure built at load
## (design/scene_and_tracer.md), with the triangles' attributes and the materials with their textures. A shader that
## traces includes cshd_trace.glslinc and binds get_uniforms() as one uniform set.

const BUILD_PASS: StringName = &"Acceleration structure build"
const GROUP_SIZE: int = 256
const TRIANGLE_BYTES: int = 48
const CORNER_BYTES: int = 16
const ATTRIBUTE_BYTES: int = 56
const CORNER_NORMAL_BYTES: int = 4
const STATISTICS_BYTES: int = 4
## Ray queries never read the hit shader table, but tlas_build refuses an instance without a range of it. This is one
## hit group at offset 0.
const UNUSED_HIT_RANGE: int = 1 << 32

var triangle_count: int = 0
## Bytes the tracer keeps after the build, the acceleration structures' included.
var resident_bytes: int = 0
## The most bytes the build held at once.
var peak_bytes: int = 0

var _device: RenderingDevice = null
var _buffer_bytes: Dictionary[RID, int] = {}
var _structure_bytes: int = 0
var _triangles: RID = RID()
var _attributes: RID = RID()
var _statistics: RID = RID()
var _corner_normals: RID = RID()
var _materials: RID = RID()
var _blas: RID = RID()
var _tlas: RID = RID()
var _white_texture: RID = RID()
var _sampler: RID = RID()
var _textures: Array[RID] = []


func _init(device: RenderingDevice) -> void:
	_device = device


## `triangles_shader` is cshd_triangles.glsl.
func build(scene: TracerScene, triangles_shader: RDShaderFile) -> void:
	triangle_count = scene.triangle_count
	GpuPass.begin(_device, BUILD_PASS)
	_gather_triangles(scene, triangles_shader)
	_build_structures(scene.opaque_triangle_count)
	GpuPass.end(_device, BUILD_PASS)
	_create_materials(scene)
	resident_bytes = _total_bytes()


## The uniforms of cshd_trace.glslinc, bindings 0 to 5.
func get_uniforms() -> Array[RDUniform]:
	var scene := RDUniform.new()
	scene.uniform_type = RenderingDevice.UNIFORM_TYPE_ACCELERATION_STRUCTURE
	scene.binding = 0
	scene.add_id(_tlas)
	var uniforms: Array[RDUniform] = [scene]
	uniforms.append_array(ComputeShader.storage_uniforms([_triangles, _attributes, _materials], 1))

	var textures := RDUniform.new()
	textures.uniform_type = RenderingDevice.UNIFORM_TYPE_TEXTURE
	textures.binding = 4
	for index: int in TracerScene.MAX_TEXTURES:
		textures.add_id(_textures[index] if index < _textures.size() else _white_texture)
	uniforms.append(textures)

	var sampler := RDUniform.new()
	sampler.uniform_type = RenderingDevice.UNIFORM_TYPE_SAMPLER
	sampler.binding = 5
	sampler.add_id(_sampler)
	uniforms.append(sampler)
	return uniforms


## Triangles whose winding disagrees with their vertex normals. Reading it stalls the GPU.
func get_winding_disagreements() -> int:
	return _device.buffer_get_data(_statistics).decode_u32(0)


## The world-space vertex normals of every triangle's corners, packed by cshd_normals.glslinc, which the atlas capture
## reads until free_corner_normals().
func get_corner_normals() -> RID:
	return _corner_normals


func free_corner_normals() -> void:
	_free_buffer(_corner_normals)
	_corner_normals = RID()
	resident_bytes = _total_bytes()


func free_rids() -> void:
	for owned: RID in [_tlas, _blas]:
		if owned.is_valid():
			_device.free_rid(owned)
	for buffer: RID in _buffer_bytes.keys():
		_device.free_rid(buffer)
	_buffer_bytes.clear()
	for owned: RID in [_white_texture, _sampler]:
		if owned.is_valid():
			_device.free_rid(owned)


func _gather_triangles(scene: TracerScene, file: RDShaderFile) -> void:
	var inputs: Array[RID] = []
	for data: PackedByteArray in [scene.positions, scene.normals, scene.uvs, scene.uv2s, scene.indices, scene.surfaces]:
		inputs.append(_create_buffer(data.size(), data))

	# The acceleration structure reads the triangles' corners as vertices.
	_triangles = _device.vertex_buffer_create(TRIANGLE_BYTES * triangle_count, PackedByteArray(),
			RenderingDevice.BUFFER_CREATION_AS_STORAGE_BIT | RenderingDevice.BUFFER_CREATION_DEVICE_ADDRESS_BIT
			| RenderingDevice.BUFFER_CREATION_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT)
	_track(_triangles, TRIANGLE_BYTES * triangle_count)
	_attributes = _create_buffer(ATTRIBUTE_BYTES * triangle_count)
	_statistics = _create_buffer(STATISTICS_BYTES)
	_device.buffer_clear(_statistics, 0, STATISTICS_BYTES)
	_corner_normals = _create_buffer(3 * CORNER_NORMAL_BYTES * triangle_count)

	var shader := ComputeShader.new(_device, file)
	var buffers: Array[RID] = inputs.duplicate()
	buffers.append_array([_triangles, _attributes, _statistics, _corner_normals])
	var uniform_set: RID = shader.create_uniform_set(ComputeShader.storage_uniforms(buffers))
	var parameters: PackedByteArray = PackedInt32Array([scene.triangle_count, scene.surface_count]).to_byte_array()
	shader.dispatch([uniform_set], parameters, ComputeShader.group_count(triangle_count, GROUP_SIZE))

	shader.free_rids()
	for input: RID in inputs:
		_free_buffer(input)


# One BLAS holds the opaque triangles as one geometry and the alpha-tested ones as another, so that only the second
# reach the shader as candidates. The instance's custom index, the first alpha-tested triangle, turns a geometry's
# primitive index back into the triangle's.
func _build_structures(opaque_count: int) -> void:
	var memory_before: int = _device.get_memory_usage(RenderingDevice.MEMORY_TOTAL)
	var geometries: Array[RDAccelerationStructureGeometry] = []
	if opaque_count > 0:
		geometries.append(_geometry(0, opaque_count, RenderingDevice.ACCELERATION_STRUCTURE_GEOMETRY_OPAQUE_BIT))
	if opaque_count < triangle_count:
		geometries.append(_geometry(opaque_count, triangle_count - opaque_count, 0))
	_blas = _device.blas_create(geometries, RenderingDevice.ACCELERATION_STRUCTURE_PREFER_FAST_TRACE_BIT)
	_device.blas_build(_blas)

	var instance := RDAccelerationStructureInstance.new()
	instance.blas = _blas
	instance.id = opaque_count
	instance.hit_sbt_range = UNUSED_HIT_RANGE
	_tlas = _device.tlas_create(1, RenderingDevice.ACCELERATION_STRUCTURE_PREFER_FAST_TRACE_BIT)
	_device.tlas_build(_tlas, [instance])

	# The structures' storage and their build scratch, which Godot keeps as long as a structure lives.
	_structure_bytes = _device.get_memory_usage(RenderingDevice.MEMORY_TOTAL) - memory_before
	peak_bytes = maxi(peak_bytes, _total_bytes())


func _geometry(first: int, count: int, flags: int) -> RDAccelerationStructureGeometry:
	var geometry := RDAccelerationStructureGeometry.new()
	geometry.flags = flags
	geometry.vertex_buffer = _triangles
	geometry.vertex_offset = TRIANGLE_BYTES * first
	geometry.vertex_stride = CORNER_BYTES
	geometry.vertex_count = 3 * count
	geometry.vertex_format = RenderingDevice.DATA_FORMAT_R32G32B32_SFLOAT
	return geometry


func _create_materials(scene: TracerScene) -> void:
	_materials = _create_buffer(scene.materials.size(), scene.materials)

	var format := RDTextureFormat.new()
	format.format = RenderingDevice.DATA_FORMAT_R8G8B8A8_UNORM
	format.width = 1
	format.height = 1
	format.usage_bits = RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT
	_white_texture = _device.texture_create(format, RDTextureView.new(), [PackedByteArray([255, 255, 255, 255])])
	_textures = [_white_texture]
	for texture: Texture2D in scene.textures:
		# The GI material samples both of its textures as source colours, through their sRGB views.
		_textures.append(RenderingServer.texture_get_rd_texture(texture.get_rid(), true))

	var sampler := RDSamplerState.new()
	sampler.min_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	sampler.mag_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	sampler.mip_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	sampler.repeat_u = RenderingDevice.SAMPLER_REPEAT_MODE_REPEAT
	sampler.repeat_v = RenderingDevice.SAMPLER_REPEAT_MODE_REPEAT
	_sampler = _device.sampler_create(sampler)


func _create_buffer(size: int, data: PackedByteArray = PackedByteArray()) -> RID:
	var buffer: RID = _device.storage_buffer_create(size, data)
	_track(buffer, size)
	return buffer


func _track(buffer: RID, size: int) -> void:
	_buffer_bytes[buffer] = size
	peak_bytes = maxi(peak_bytes, _total_bytes())


func _free_buffer(buffer: RID) -> void:
	_device.free_rid(buffer)
	_buffer_bytes.erase(buffer)


func _total_bytes() -> int:
	var total: int = _structure_bytes
	for size: int in _buffer_bytes.values():
		total += size
	return total
