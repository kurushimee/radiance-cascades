extends Node
## Captures the scene when launched with `-- --capture=<dir>`: a screenshot and render timings, then for each camera
## the final image and the irradiance E/π that the GI materials hand to Godot, as linear EXR files in a folder named
## after the camera. `--animation=<name>` plays that animation of the scene's AnimationPlayers, and
## `--time=<seconds>` holds it at that time.

const CAPTURE_PREFIX: String = "--capture="
const ANIMATION_PREFIX: String = "--animation="
const TIME_PREFIX: String = "--time="
const SCREENSHOT_FILE: String = "screenshot.png"
const REPORT_FILE: String = "capture.json"
const FINAL_FILE: String = "final.exr"
const IRRADIANCE_FILE: String = "irradiance.exr"
const WARMUP_FRAMES: int = 60
const MEASURED_FRAMES: int = 120
const SETTLE_FRAMES: int = 2

var _directory: String = ""
var _frames_drawn: int = 0
var _gpu_ms: PackedFloat64Array = []
var _cpu_ms: PackedFloat64Array = []
var _gi_ms: Dictionary[StringName, PackedFloat64Array] = {}
var _gi_effect: GIEffect = null
var _gi_timed_frame: int = -1
var _error_log: ErrorLog = ErrorLog.new()


# The logger goes in before the main scene loads, so its script errors are caught.
func _init() -> void:
	_directory = _argument(CAPTURE_PREFIX)
	if _directory:
		OS.add_logger(_error_log)


func _ready() -> void:
	if !_directory:
		return

	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	RenderingServer.frame_post_draw.connect(_on_frame_post_draw)


func _argument(prefix: String) -> String:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with(prefix):
			return argument.trim_prefix(prefix)
	return ""


func _on_frame_post_draw() -> void:
	_frames_drawn += 1
	if _frames_drawn == 1:
		_prepare_scene()
	if _frames_drawn <= WARMUP_FRAMES:
		return

	_record_render_times()
	if _frames_drawn == WARMUP_FRAMES + MEASURED_FRAMES:
		_finish()


# The main scene enters the tree after the autoloads are ready.
func _prepare_scene() -> void:
	var scene: Node = get_tree().current_scene
	_gi_effect = _find_gi_effect(scene)
	var animation: String = _argument(ANIMATION_PREFIX)
	if !animation:
		return

	var time: String = _argument(TIME_PREFIX)
	for node: Node in scene.find_children("*", "AnimationPlayer", true, false):
		var player: AnimationPlayer = node
		if !player.has_animation(animation):
			continue

		player.play(animation)
		if time:
			player.seek(time.to_float(), true)
			player.pause()


func _find_gi_effect(scene: Node) -> GIEffect:
	for node: Node in scene.find_children("*", "WorldEnvironment", true, false):
		var compositor: Compositor = (node as WorldEnvironment).compositor
		if !is_instance_valid(compositor):
			continue

		for effect: CompositorEffect in compositor.compositor_effects:
			if effect is GIEffect:
				return effect
	return null


func _record_render_times() -> void:
	var viewport_rid: RID = get_viewport().get_viewport_rid()
	_gpu_ms.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport_rid))
	_cpu_ms.append(RenderingServer.viewport_get_measured_render_time_cpu(viewport_rid))
	if !is_instance_valid(_gi_effect) || _gi_effect.get_timed_frame() == _gi_timed_frame:
		return

	_gi_timed_frame = _gi_effect.get_timed_frame()
	var pass_milliseconds: Dictionary[StringName, float] = _gi_effect.get_pass_milliseconds()
	for pass_name: StringName in pass_milliseconds:
		var samples: PackedFloat64Array = _gi_ms.get(pass_name, PackedFloat64Array())
		samples.append(pass_milliseconds[pass_name])
		_gi_ms[pass_name] = samples


func _finish() -> void:
	RenderingServer.frame_post_draw.disconnect(_on_frame_post_draw)
	DirAccess.make_dir_recursive_absolute(_directory)
	_save_screenshot()
	await _capture_cameras()
	OS.remove_logger(_error_log)
	_save_report()
	get_tree().quit()


func _save_screenshot() -> void:
	var path: String = _directory.path_join(SCREENSHOT_FILE)
	var error: Error = get_viewport().get_texture().get_image().save_png(path)
	if error != OK:
		push_error("Screenshot not saved to %s: %s" % [path, error_string(error)])


# An HDR viewport reads back linear, unclamped values, and a transparent background marks the pixels without a
# surface with alpha 0.
func _capture_cameras() -> void:
	var viewport: Viewport = get_viewport()
	viewport.use_hdr_2d = true
	for node: Node in get_tree().current_scene.find_children("*", "Camera3D", true, false):
		var camera: Camera3D = node
		var directory: String = _directory.path_join(camera.name)
		DirAccess.make_dir_recursive_absolute(directory)
		camera.make_current()
		await _settle()
		_save_exr(directory.path_join(FINAL_FILE))

		RenderingServer.global_shader_parameter_set(&"gi_view", GI.View.IRRADIANCE)
		viewport.transparent_bg = true
		await _settle()
		_save_exr(directory.path_join(IRRADIANCE_FILE))
		RenderingServer.global_shader_parameter_set(&"gi_view", GI.View.SHADED)
		viewport.transparent_bg = false


func _settle() -> void:
	for _frame: int in SETTLE_FRAMES:
		await RenderingServer.frame_post_draw


func _save_exr(path: String) -> void:
	var error: Error = get_viewport().get_texture().get_image().save_exr(path)
	if error != OK:
		push_error("Image not saved to %s: %s" % [path, error_string(error)])


func _save_report() -> void:
	var gi_ms: Dictionary[String, Dictionary] = {}  # Dictionary[String, float]
	for pass_name: StringName in _gi_ms:
		gi_ms[String(pass_name)] = _summarize(_gi_ms[pass_name])
	var report: Dictionary[String, Variant] = {
		"gpu_ms": _summarize(_gpu_ms),
		"cpu_ms": _summarize(_cpu_ms),
		"gi_ms": gi_ms,
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
