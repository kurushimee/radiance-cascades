class_name SkyTable
extends RefCounted
## The sky's radiance over each direction bin of the top cascade, which the top cascade's misses read
## (design/lighting.md#sky): Godot's baked panorama, averaged over stratified points in each bin.

const PASS: StringName = &"Sky table"
## Godot's panorama: twice as wide as tall, and twice as fine along each side as the points of a table of 128×64 bins.
const PANORAMA_SIZE: Vector2i = Vector2i(1024, 512)
## Stratified points along each side of a bin.
const SAMPLES: int = 4
const GROUP_SIZE: int = 64
const BIN_BYTES: int = 16

var cascade: int = 0
var bins_per_side: int = 0

var _device: RenderingDevice = null
var _table: RID = RID()


func _init(device: RenderingDevice) -> void:
	_device = device


## `panorama` is the environment's radiance from environment_bake_panorama() at PANORAMA_SIZE.
func build(file: RDShaderFile, panorama: Image, top_cascade: int) -> void:
	cascade = top_cascade
	bins_per_side = CascadeLayout.bins_per_side(top_cascade)
	var bin_count: int = 2 * bins_per_side * bins_per_side
	_table = _device.storage_buffer_create(BIN_BYTES * bin_count)

	var format := RDTextureFormat.new()
	format.format = RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	format.width = panorama.get_width()
	format.height = panorama.get_height()
	format.usage_bits = RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT
	var data: Image = panorama.duplicate()
	data.convert(Image.FORMAT_RGBAF)
	var texture: RID = _device.texture_create(format, RDTextureView.new(), [data.get_data()])
	var sampler_state := RDSamplerState.new()
	sampler_state.min_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	sampler_state.mag_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	sampler_state.repeat_u = RenderingDevice.SAMPLER_REPEAT_MODE_REPEAT
	sampler_state.repeat_v = RenderingDevice.SAMPLER_REPEAT_MODE_CLAMP_TO_EDGE
	var sampler: RID = _device.sampler_create(sampler_state)

	var shader := ComputeShader.new(_device, file)
	var panorama_uniform := RDUniform.new()
	panorama_uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE
	panorama_uniform.binding = 0
	panorama_uniform.add_id(sampler)
	panorama_uniform.add_id(texture)
	var uniforms: Array[RDUniform] = [panorama_uniform]
	uniforms.append_array(ComputeShader.storage_uniforms([_table], 1))
	GpuPass.begin(_device, PASS)
	shader.dispatch([shader.create_uniform_set(uniforms)], PackedInt32Array([bins_per_side, SAMPLES]).to_byte_array(),
			ComputeShader.group_count(bin_count, GROUP_SIZE))
	GpuPass.end(_device, PASS)
	shader.free_rids()
	_device.free_rid(texture)
	_device.free_rid(sampler)


## The table, one radiance per bin at index j · m + k.
func get_uniforms(binding: int) -> Array[RDUniform]:
	return ComputeShader.storage_uniforms([_table], binding)


## E/π on a surface facing `normal` under the table's sky alone, summed over the bins' centres. Reading it stalls the
## GPU.
func get_irradiance(normal: Vector3) -> Color:
	var table: PackedFloat32Array = _device.buffer_get_data(_table).to_float32_array()
	var sum := Color(0.0, 0.0, 0.0, 0.0)
	for column: int in 2 * bins_per_side:
		for row: int in bins_per_side:
			var cosine: float = normal.dot(CascadeLayout.direction(Vector2(column, row) + Vector2(0.5, 0.5),
					bins_per_side))
			if cosine <= 0.0:
				continue

			var bin: int = 4 * (column * bins_per_side + row)
			sum += Color(table[bin], table[bin + 1], table[bin + 2]) * cosine
	# Each bin spans 4π / (2m²) of the sphere, and E/π divides by π.
	return sum * (2.0 / (bins_per_side * bins_per_side))


func free_rids() -> void:
	if _table.is_valid():
		_device.free_rid(_table)
