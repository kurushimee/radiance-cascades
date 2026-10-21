class_name TracerBenchmark
extends RefCounted
## Measures and checks the tracer on rays like the GI's (design/scene_and_tracer.md): from the surfaces the camera sees,
## segments over each cascade's interval in cosine-distributed directions, and shadow rays toward the sun. Each kind of
## ray is a GPU pass of its own, which GIEffect times.

const GROUP_SIZE: int = 64
const FIRST_INTERVAL: float = 1.6  # t0 in texel spacings
const CASCADES: int = 4  # cascades 0 to 2 and the top, whose rays have no end
const FAR: float = 1e30
const CHECK_STRIDE: int = 257  # about 3,600 rays of each kind at 1280×720
const COUNTER_BYTES: int = 16
const MODE_PRIMARY: int = 0
const MODE_SEGMENT: int = 1
const MODE_SHADOW: int = 2
const PRIMARY_PASS: StringName = &"Trace primary"
const SHADOW_PASS: StringName = &"Trace shadows"
const SEGMENT_PASS: String = "Trace cascade %d"

var _device: RenderingDevice = null
var _tracer: Tracer = null
var _shader: ComputeShader = null
var _uniform_sets: Array[RID] = []
var _buffers: Array[RID] = []
var _counters: RID = RID()
var _size: Vector2i = Vector2i.ZERO
var _segments: Array[Vector2] = []
var _sun: Vector3 = Vector3.ZERO
var _primary_dispatches: int = 0
var _report: Dictionary[String, Variant] = {}


## `spacing` is the scene's texel spacing in metres; a zero `sun` leaves out the shadow rays.
func _init(device: RenderingDevice, tracer: Tracer, file: RDShaderFile, size: Vector2i, spacing: float,
		sun: Vector3) -> void:
	_device = device
	_tracer = tracer
	_size = size
	_sun = sun
	var pixels: int = size.x * size.y
	var origins: RID = device.storage_buffer_create(16 * pixels)
	var normals: RID = device.storage_buffer_create(16 * pixels)
	var results: RID = device.storage_buffer_create(4 * pixels)
	_counters = device.storage_buffer_create(COUNTER_BYTES)
	device.buffer_clear(_counters, 0, COUNTER_BYTES)
	_buffers = [origins, normals, results, _counters]

	_shader = ComputeShader.new(device, file)
	_uniform_sets = [
		_shader.create_uniform_set(ComputeShader.storage_uniforms(_buffers), 0),
		_shader.create_uniform_set(tracer.get_uniforms(), 1),
	]

	var first: float = FIRST_INTERVAL * spacing
	_segments = [Vector2(0.0, first)]
	for cascade: int in range(1, CASCADES):
		var end: float = first * pow(4.0, cascade) if cascade < CASCADES - 1 else FAR
		_segments.append(Vector2(first * pow(4.0, cascade - 1), end))


## Traces every kind of ray once from the camera described by `camera_basis` (CameraRays.basis()).
func trace(camera_basis: PackedFloat32Array) -> void:
	_timed(PRIMARY_PASS, _parameters(camera_basis, MODE_PRIMARY, Vector2.ZERO, 0, 0))
	_primary_dispatches += 1
	for cascade: int in _segments.size():
		_timed(StringName(SEGMENT_PASS % cascade),
				_parameters(camera_basis, MODE_SEGMENT, _segments[cascade], cascade, 0))
	if _sun:
		_timed(SHADOW_PASS, _parameters(camera_basis, MODE_SHADOW, Vector2(0.0, FAR), 0, 0))


## Compares the tracer's hits with brute force over every triangle on a sparse subset of the benchmark's rays.
func check(camera_basis: PackedFloat32Array) -> void:
	_run(_parameters(camera_basis, MODE_PRIMARY, Vector2.ZERO, 0, 0), 1)
	_run(_parameters(camera_basis, MODE_PRIMARY, Vector2.ZERO, 0, CHECK_STRIDE), CHECK_STRIDE)
	for cascade: int in _segments.size():
		_run(_parameters(camera_basis, MODE_SEGMENT, _segments[cascade], cascade, CHECK_STRIDE), CHECK_STRIDE)
	if _sun:
		_run(_parameters(camera_basis, MODE_SHADOW, Vector2(0.0, FAR), 0, CHECK_STRIDE), CHECK_STRIDE)

	var counters: PackedInt32Array = _device.buffer_get_data(_counters).to_int32_array()
	_report["checked_rays"] = counters[3]
	_report["closest_mismatches"] = counters[1]
	_report["any_mismatches"] = counters[2]
	_device.buffer_clear(_counters, 0, COUNTER_BYTES)


## Counts and sizes for capture.json. The rays of each segment and shadow pass are the primary hits.
func get_report() -> Dictionary[String, Variant]:
	var counters: PackedInt32Array = _device.buffer_get_data(_counters).to_int32_array()
	var report: Dictionary[String, Variant] = _report.duplicate()
	report["triangles"] = _tracer.triangle_count
	report["resident_bytes"] = _tracer.resident_bytes
	report["peak_build_bytes"] = _tracer.peak_bytes
	report["primary_rays"] = _size.x * _size.y
	if _primary_dispatches > 0:
		@warning_ignore("integer_division")
		report["primary_hits"] = counters[0] / _primary_dispatches
	report["segments"] = _segments.map(func(segment: Vector2) -> PackedFloat64Array: return [segment.x, segment.y])
	report["winding_disagreements"] = _tracer.get_winding_disagreements()
	return report


func free_rids() -> void:
	_shader.free_rids()
	for buffer: RID in _buffers:
		_device.free_rid(buffer)


func _timed(pass_name: StringName, parameters: PackedByteArray) -> void:
	GpuPass.begin(_device, pass_name)
	_run(parameters, 1)
	GpuPass.end(_device, pass_name)


# A thread traces every `stride`-th pixel.
func _run(parameters: PackedByteArray, stride: int) -> void:
	var threads: int = ComputeShader.group_count(_size.x * _size.y, stride)
	_shader.dispatch(_uniform_sets, parameters, ComputeShader.group_count(threads, GROUP_SIZE))


func _parameters(camera_basis: PackedFloat32Array, mode: int, segment: Vector2, direction_seed: int,
		check_stride: int) -> PackedByteArray:
	var floats: PackedFloat32Array = camera_basis.duplicate()
	floats.append_array([_sun.x, _sun.y, _sun.z, 0.0, segment.x, segment.y])
	var parameters: PackedByteArray = floats.to_byte_array()
	parameters.append_array(PackedInt32Array([_size.x, _size.y, mode, check_stride, direction_seed,
			_tracer.triangle_count]).to_byte_array())
	return parameters
