extends Node
## Captures the scene when launched with `-- --capture=<dir>`.

const ARG_PREFIX: String = "--capture="
const SCREENSHOT_FILE: String = "screenshot.png"
const REPORT_FILE: String = "capture.json"
const WARMUP_FRAMES: int = 60
const MEASURED_FRAMES: int = 120

var _directory: String = ""
var _frames_drawn: int = 0
var _gpu_ms: PackedFloat64Array = []
var _cpu_ms: PackedFloat64Array = []
var _error_log: ErrorLog = ErrorLog.new()


# The logger goes in before the main scene loads, so its script errors are caught.
func _init() -> void:
	_directory = _directory_from_args()
	if _directory:
		OS.add_logger(_error_log)


func _ready() -> void:
	if !_directory:
		return

	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	RenderingServer.frame_post_draw.connect(_on_frame_post_draw)


func _directory_from_args() -> String:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with(ARG_PREFIX):
			return argument.trim_prefix(ARG_PREFIX)
	return ""


func _on_frame_post_draw() -> void:
	_frames_drawn += 1
	if _frames_drawn <= WARMUP_FRAMES:
		return

	_record_render_times()
	if _frames_drawn == WARMUP_FRAMES + MEASURED_FRAMES:
		_finish()


func _record_render_times() -> void:
	var viewport_rid: RID = get_viewport().get_viewport_rid()
	_gpu_ms.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport_rid))
	_cpu_ms.append(RenderingServer.viewport_get_measured_render_time_cpu(viewport_rid))


func _finish() -> void:
	RenderingServer.frame_post_draw.disconnect(_on_frame_post_draw)
	DirAccess.make_dir_recursive_absolute(_directory)
	_save_screenshot()
	OS.remove_logger(_error_log)
	_save_report()
	get_tree().quit()


func _save_screenshot() -> void:
	var path: String = _directory.path_join(SCREENSHOT_FILE)
	var error: Error = get_viewport().get_texture().get_image().save_png(path)
	if error != OK:
		push_error("Screenshot not saved to %s: %s" % [path, error_string(error)])


func _save_report() -> void:
	var report: Dictionary[String, Variant] = {
		"gpu_ms": _summarize(_gpu_ms),
		"cpu_ms": _summarize(_cpu_ms),
		"errors": _error_log.get_errors(),
		"warnings": _error_log.get_warnings(),
	}
	var path: String = _directory.path_join(REPORT_FILE)
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if !is_instance_valid(file):
		push_error("Report not saved to %s: %s" % [path, error_string(FileAccess.get_open_error())])
		return

	file.store_string(JSON.stringify(report, "\t", false))


func _summarize(samples: PackedFloat64Array) -> Dictionary[String, float]:
	var sorted: PackedFloat64Array = samples.duplicate()
	sorted.sort()
	return {
		"p50": _percentile(sorted, 0.5),
		"p95": _percentile(sorted, 0.95),
		"max": _percentile(sorted, 1.0),
	}


func _percentile(sorted: PackedFloat64Array, fraction: float) -> float:
	var index: int = ceili(fraction * sorted.size()) - 1
	return snappedf(sorted[index], 0.001)


class ErrorLog extends Logger:
	var _mutex: Mutex = Mutex.new()
	var _errors: PackedStringArray = []
	var _warnings: PackedStringArray = []


	func _log_error(
		function: String,
		file: String,
		line: int,
		code: String,
		rationale: String,
		_editor_notify: bool,
		error_type: int,
		script_backtraces: Array[ScriptBacktrace],
	) -> void:
		var message: String = rationale if rationale else code
		var entry: String = "%s at %s" % [message, _source_location(function, file, line, script_backtraces)]
		_mutex.lock()
		if error_type == ERROR_TYPE_WARNING:
			_warnings.append(entry)
		else:
			_errors.append(entry)
		_mutex.unlock()


	func get_errors() -> PackedStringArray:
		_mutex.lock()
		var errors: PackedStringArray = _errors.duplicate()
		_mutex.unlock()
		return errors


	func get_warnings() -> PackedStringArray:
		_mutex.lock()
		var warnings: PackedStringArray = _warnings.duplicate()
		_mutex.unlock()
		return warnings


	func _source_location(function: String, file: String, line: int, backtraces: Array[ScriptBacktrace]) -> String:
		if backtraces.is_empty() || backtraces[0].get_frame_count() == 0:
			return "%s (%s:%d)" % [function, file, line]

		var backtrace: ScriptBacktrace = backtraces[0]
		return "%s (%s:%d)" % [
			backtrace.get_frame_function(0), backtrace.get_frame_file(0), backtrace.get_frame_line(0),
		]
