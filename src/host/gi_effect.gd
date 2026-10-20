class_name GIEffect
extends CompositorEffect
## Runs the GI's frame before the opaque pass reads its irradiance. The callback runs once per viewport, and the
## solve is in world space, so only the first callback of a frame does the work.

const FRAME_PASS: StringName = &"GI"
const END_SUFFIX: String = " end"
const LABEL_COLOR: Color = Color(0.3, 0.8, 1.0)

var _solved_frame: int = -1
var _pass_milliseconds: Dictionary[StringName, float] = {}
var _timed_frame: int = -1


func _init() -> void:
	effect_callback_type = EFFECT_CALLBACK_TYPE_PRE_OPAQUE


func _render_callback(_effect_callback_type: int, _render_data: RenderData) -> void:
	var frame: int = Engine.get_frames_drawn()
	if frame == _solved_frame:
		return

	_solved_frame = frame
	var device: RenderingDevice = RenderingServer.get_rendering_device()
	_read_timestamps(device)
	_begin_pass(device, FRAME_PASS)
	_end_pass(device, FRAME_PASS)


## GPU milliseconds of each pass in the frame `get_timed_frame()` returns.
func get_pass_milliseconds() -> Dictionary[StringName, float]:
	return _pass_milliseconds


func get_timed_frame() -> int:
	return _timed_frame


# Timestamps cannot be captured inside a compute list that has dispatched, so each pass is a list of its own.
func _begin_pass(device: RenderingDevice, pass_name: StringName) -> void:
	device.draw_command_begin_label(pass_name, LABEL_COLOR)
	device.capture_timestamp(pass_name)


func _end_pass(device: RenderingDevice, pass_name: StringName) -> void:
	device.capture_timestamp(pass_name + END_SUFFIX)
	device.draw_command_end_label()


# The main device's timestamps become readable two frames after their frame, and only for one frame.
func _read_timestamps(device: RenderingDevice) -> void:
	var starts: Dictionary[String, int] = {}
	var milliseconds: Dictionary[StringName, float] = {}
	for index: int in device.get_captured_timestamps_count():
		var timestamp_name: String = device.get_captured_timestamp_name(index)
		var nanoseconds: int = device.get_captured_timestamp_gpu_time(index)
		var pass_name: String = timestamp_name.trim_suffix(END_SUFFIX)
		if pass_name == timestamp_name:
			starts[pass_name] = nanoseconds
		elif starts.has(pass_name):
			milliseconds[StringName(pass_name)] = (nanoseconds - starts[pass_name]) * 1e-6

	_pass_milliseconds = milliseconds
	_timed_frame = device.get_captured_timestamps_frame()
