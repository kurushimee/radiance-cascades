class_name GpuPass
## A named span of GPU work: a debug label for GPU debuggers and a pair of timestamps that `GIEffect` reads back.
## Timestamps cannot be captured inside a compute list that has dispatched, so a span begins before its first list and
## ends after its last.

const END_SUFFIX: String = " end"
const LABEL_COLOR: Color = Color(0.3, 0.8, 1.0)


static func begin(device: RenderingDevice, pass_name: StringName) -> void:
	device.draw_command_begin_label(pass_name, LABEL_COLOR)
	device.capture_timestamp(pass_name)


static func end(device: RenderingDevice, pass_name: StringName) -> void:
	device.capture_timestamp(pass_name + END_SUFFIX)
	device.draw_command_end_label()
