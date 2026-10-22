class_name ComputeShader
extends RefCounted
## A compute shader and its pipeline on one RenderingDevice. Each dispatch runs in a compute list of its own, so the
## render graph orders it after the dispatches whose output it reads.

var _device: RenderingDevice = null
var _shader: RID = RID()
var _pipeline: RID = RID()


func _init(device: RenderingDevice, file: RDShaderFile) -> void:
	_device = device
	var spirv: RDShaderSPIRV = file.get_spirv()
	if spirv.compile_error_compute:
		push_error("%s does not compile: %s" % [file.resource_path, spirv.compile_error_compute])
		return

	_shader = device.shader_create_from_spirv(spirv, file.resource_path.get_file())
	_pipeline = device.compute_pipeline_create(_shader)


static func storage_uniforms(buffers: Array[RID], first_binding: int = 0) -> Array[RDUniform]:
	var uniforms: Array[RDUniform] = []
	for index: int in buffers.size():
		var uniform := RDUniform.new()
		uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
		uniform.binding = first_binding + index
		uniform.add_id(buffers[index])
		uniforms.append(uniform)
	return uniforms


static func group_count(threads: int, group_size: int) -> int:
	return ceili(float(threads) / group_size)


func create_uniform_set(uniforms: Array[RDUniform], set_index: int = 0) -> RID:
	return _device.uniform_set_create(uniforms, _shader, set_index)


## Binds `uniform_sets` as sets 0, 1, ... in order.
func dispatch(uniform_sets: Array[RID], push_constant: PackedByteArray, groups: int, groups_y: int = 1) -> void:
	var list: int = _device.compute_list_begin()
	_device.compute_list_bind_compute_pipeline(list, _pipeline)
	for set_index: int in uniform_sets.size():
		_device.compute_list_bind_uniform_set(list, uniform_sets[set_index], set_index)
	if !push_constant.is_empty():
		_device.compute_list_set_push_constant(list, push_constant, push_constant.size())
	_device.compute_list_dispatch(list, groups, groups_y, 1)
	_device.compute_list_end()


# Freeing the shader frees its pipeline and uniform sets with it.
func free_rids() -> void:
	if _shader.is_valid():
		_device.free_rid(_shader)
