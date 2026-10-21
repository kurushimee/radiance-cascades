class_name FrameAccumulator
extends RefCounted
## Running means of a viewport's frames on the GPU, one over every frame added and one over the even frames, through
## cshd_accumulate.glsl. Call it on the render thread.

const GROUP_SIZE: int = 256
const PIXEL_BYTES: int = 16

var _device: RenderingDevice = null
var _shader: ComputeShader = null
var _viewport_texture: RID = RID()
var _size: Vector2i = Vector2i.ZERO
var _all_frames: RID = RID()
var _even_frames: RID = RID()
var _sampler: RID = RID()
var _frame_texture: RID = RID()
var _uniform_set: RID = RID()
var _frame_count: int = 0


## `viewport_texture` is the viewport's texture as RenderingServer knows it.
func _init(device: RenderingDevice, file: RDShaderFile, viewport_texture: RID, size: Vector2i) -> void:
	_device = device
	_shader = ComputeShader.new(device, file)
	_viewport_texture = viewport_texture
	_size = size
	var bytes: int = PIXEL_BYTES * size.x * size.y
	_all_frames = device.storage_buffer_create(bytes)
	_even_frames = device.storage_buffer_create(bytes)
	device.buffer_clear(_all_frames, 0, bytes)
	device.buffer_clear(_even_frames, 0, bytes)
	_sampler = device.sampler_create(RDSamplerState.new())


## Adds the frame the viewport last drew.
func add() -> void:
	# The viewport's texture changes when its format does, and its uniform set goes with the old one.
	var texture: RID = RenderingServer.texture_get_rd_texture(_viewport_texture)
	if texture != _frame_texture || !_device.uniform_set_is_valid(_uniform_set):
		_frame_texture = texture
		_uniform_set = _shader.create_uniform_set(_uniforms(texture))

	var parameters: PackedByteArray = PackedInt32Array([_size.x, _size.y, _frame_count]).to_byte_array()
	_shader.dispatch([_uniform_set], parameters, ComputeShader.group_count(_size.x * _size.y, GROUP_SIZE))
	_frame_count += 1


## The mean over every frame added. Reading it stalls the GPU.
func get_mean() -> Image:
	return _image(_all_frames)


## The mean over the even frames. Reading it stalls the GPU.
func get_even_mean() -> Image:
	return _image(_even_frames)


func free_rids() -> void:
	_shader.free_rids()
	for owned: RID in [_all_frames, _even_frames, _sampler]:
		_device.free_rid(owned)


func _uniforms(texture: RID) -> Array[RDUniform]:
	var frame := RDUniform.new()
	frame.uniform_type = RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE
	frame.binding = 0
	frame.add_id(_sampler)
	frame.add_id(texture)
	var uniforms: Array[RDUniform] = [frame]
	uniforms.append_array(ComputeShader.storage_uniforms([_all_frames, _even_frames], 1))
	return uniforms


func _image(buffer: RID) -> Image:
	return Image.create_from_data(_size.x, _size.y, false, Image.FORMAT_RGBAF, _device.buffer_get_data(buffer))
