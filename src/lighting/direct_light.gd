class_name DirectLight
extends RefCounted
## Each frame's direct light from Godot's omni and directional lights at every probe, E/π (design/lighting.md). A
## static light's visibility at each probe is found once at load, as the mean of cos · visibility over the light's
## cone, a byte per probe; every other light traces one shadow ray per probe toward its centre each frame.

const DIRECT_PASS: StringName = &"GI direct light"
const VISIBILITY_PASS: StringName = &"Light visibility"
## The path tracer's light limit (RT_LIGHTS_MAX), past which it leaves lights out.
const MAX_LIGHTS: int = 64
## Directions across a static light's cone.
const CACHE_DIRECTIONS: int = 64
const HEADER_BYTES: int = 16
const LIGHT_BYTES: int = 64
const SLOT_OFFSET: int = 52
const GROUP_SIZE: int = 64
const TILE: int = 8
const OMNI: int = 0
const SUN: int = 1
const NO_SLOT: int = 0xFFFFFFFF

var _device: RenderingDevice = null
var _probe_count: int = 0
var _lights: RID = RID()
var _cache: RID = RID()
var _direct_shader: ComputeShader = null
var _direct_sets: Array[RID] = []
var _view_shader: ComputeShader = null
var _tracer: Tracer = null


## Packs `lights` for cshd_lights.glslinc. A light outside the tree's visible part keeps its place with no emission, so
## that a static light switched off at load still gets its visibility. `static_lights` gives the static lights' slots.
static func pack(lights: Array[Light3D], static_lights: Array[Light3D]) -> PackedByteArray:
	var data := PackedByteArray()
	data.resize(HEADER_BYTES + LIGHT_BYTES * lights.size())
	data.encode_u32(0, lights.size())
	data.encode_u32(4, static_lights.size())
	for index: int in lights.size():
		var light: Light3D = lights[index]
		var colour: Color = light.light_color.srgb_to_linear() * light.light_energy
		if !light.is_visible_in_tree():
			colour = Color.BLACK

		var sun: bool = light is DirectionalLight3D
		var position: Vector3 = light.global_basis.z.normalized() if sun else light.global_position
		var radius: float = deg_to_rad(light.light_angular_distance * 0.5) if sun else light.light_size
		var falloff := Vector2.ZERO
		if light is OmniLight3D:
			falloff = Vector2((light as OmniLight3D).omni_attenuation, 1.0 / (light as OmniLight3D).omni_range)
		var slot: int = static_lights.find(light)
		var values := PackedFloat32Array([position.x, position.y, position.z, radius, colour.r, colour.g, colour.b,
				light.light_indirect_energy, falloff.x, falloff.y, 0.0, 0.0])
		var offset: int = HEADER_BYTES + LIGHT_BYTES * index
		for value: int in values.size():
			data.encode_float(offset + 4 * value, values[value])
		data.encode_u32(offset + 48, SUN if sun else OMNI)
		data.encode_u32(offset + SLOT_OFFSET, NO_SLOT if slot < 0 else slot)
	return data


func _init(device: RenderingDevice) -> void:
	_device = device


## Caches the static lights' visibility at the atlas's probes. `lights` is pack()'s.
func build(shaders: GIShaders, tracer: Tracer, atlas: Atlas, lights: PackedByteArray) -> void:
	_tracer = tracer
	_probe_count = atlas.probe_count
	_lights = _device.storage_buffer_create(HEADER_BYTES + LIGHT_BYTES * MAX_LIGHTS)
	set_lights(lights)
	var cache_words: int = ceili(_probe_count * lights.decode_u32(4) / 4.0)
	_cache = _device.storage_buffer_create(4 * maxi(cache_words, 1))
	_device.buffer_clear(_cache, 0, 4 * maxi(cache_words, 1))

	var light_uniforms: Array[RDUniform] = ComputeShader.storage_uniforms([_lights, _cache])
	var visibility := ComputeShader.new(_device, shaders.light_visibility)
	var visibility_sets: Array[RID] = [
		visibility.create_uniform_set(tracer.get_uniforms(), 0),
		visibility.create_uniform_set(atlas.get_probe_uniforms(), 1),
		visibility.create_uniform_set(light_uniforms, 2),
	]
	GpuPass.begin(_device, VISIBILITY_PASS)
	for light: int in lights.decode_u32(0):
		if lights.decode_u32(HEADER_BYTES + LIGHT_BYTES * light + SLOT_OFFSET) == NO_SLOT:
			continue

		var parameters: PackedByteArray = PackedInt32Array([light, _probe_count, CACHE_DIRECTIONS]).to_byte_array()
		visibility.dispatch(visibility_sets, parameters, ComputeShader.group_count(_probe_count, GROUP_SIZE))
	GpuPass.end(_device, VISIBILITY_PASS)
	visibility.free_rids()

	_direct_shader = ComputeShader.new(_device, shaders.direct)
	_direct_sets = [
		_direct_shader.create_uniform_set(tracer.get_uniforms(), 0),
		_direct_shader.create_uniform_set(atlas.get_probe_uniforms(), 1),
		_direct_shader.create_uniform_set(light_uniforms, 2),
	]
	_view_shader = ComputeShader.new(_device, shaders.direct_view)


## `lights` is pack()'s, with the lights in the order and slots of build()'s.
func set_lights(lights: PackedByteArray) -> void:
	_device.buffer_update(_lights, 0, lights.size(), lights)


## Writes this frame's direct light at every probe.
func update() -> void:
	GpuPass.begin(_device, DIRECT_PASS)
	update_sampled(0)
	GpuPass.end(_device, DIRECT_PASS)


## Writes the direct light at every probe with the lights that have no cache sampled by `directions` rays across their
## cones, or by the one ray toward their centres when `directions` is 0. The next frame's update() overwrites it.
func update_sampled(directions: int) -> void:
	var parameters: PackedByteArray = PackedInt32Array([_probe_count, directions]).to_byte_array()
	_direct_shader.dispatch(_direct_sets, parameters, ComputeShader.group_count(_probe_count, GROUP_SIZE))


## The direct light, E/π, at each pixel's primary hit, as the path tracer's direct irradiance view computes it: every
## light's cone sampled by `directions` rays, around the raster's normal. `distances` is the raster's GI.View.DISTANCE
## and `normals` its GI.View.NORMAL plus GI.View.NORMAL_REMAINDER, with alpha 0 where no surface is; alpha 0 also marks
## a pixel whose traced hit lies elsewhere along its ray than the raster's. `camera_basis` is CameraRays.basis's.
## Reading it stalls the GPU.
func get_pixel_view(camera_basis: PackedFloat32Array, distances: Image, normals: Image, directions: int) -> Image:
	var size: Vector2i = distances.get_size()
	var distance_texture: RID = _create_texture(size, distances)
	var normal_texture: RID = _create_texture(size, normals)
	var target: RID = _create_texture(size)
	var images: Array[RDUniform] = []
	for texture: RID in [distance_texture, normal_texture, target]:
		var uniform := RDUniform.new()
		uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
		uniform.binding = images.size()
		uniform.add_id(texture)
		images.append(uniform)
	var sets: Array[RID] = [
		_view_shader.create_uniform_set(_tracer.get_uniforms(), 0),
		_view_shader.create_uniform_set(ComputeShader.storage_uniforms([_lights, _cache]), 1),
		_view_shader.create_uniform_set(images, 2),
	]
	var parameters: PackedByteArray = camera_basis.to_byte_array()
	parameters.append_array(PackedInt32Array([size.x, size.y, directions]).to_byte_array())
	_view_shader.dispatch(sets, parameters, ComputeShader.group_count(size.x, TILE),
			ComputeShader.group_count(size.y, TILE))

	var image: Image = Image.create_from_data(size.x, size.y, false, Image.FORMAT_RGBAF,
			_device.texture_get_data(target, 0))
	for owned: RID in sets + [distance_texture, normal_texture, target]:
		_device.free_rid(owned)
	return image


func free_rids() -> void:
	for shader: ComputeShader in [_direct_shader, _view_shader]:
		if is_instance_valid(shader):
			shader.free_rids()
	for owned: RID in [_lights, _cache]:
		if owned.is_valid():
			_device.free_rid(owned)


# A float texture the size of a view, filled from `image` when one is given.
func _create_texture(size: Vector2i, image: Image = null) -> RID:
	var format := RDTextureFormat.new()
	format.format = RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	format.width = size.x
	format.height = size.y
	format.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	if !is_instance_valid(image):
		return _device.texture_create(format, RDTextureView.new())

	var data: Image = image.duplicate()
	data.convert(Image.FORMAT_RGBAF)
	return _device.texture_create(format, RDTextureView.new(), [data.get_data()])
