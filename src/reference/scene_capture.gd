extends Node
## Captures the scene when launched with `-- --capture=<dir>`: render timings, then for each camera, in a folder named
## after it, `final.png`, the frame as the game shows it, and as linear EXR files the final image and the irradiance E/π
## that the GI materials hand to Godot. `--animation=<name>` plays that animation of the scene's AnimationPlayers, and
## `--time=<seconds>` holds it at that time. `--benchmark=<texel spacing in metres>` traces the tracer's benchmark rays
## from the current camera every frame, and `--check` with it checks the BVH against brute force first; their counts go
## into the report under `tracer`.
##
## `--reference` captures the path-traced reference in place of the GI, denoised by DLSS Ray Reconstruction:
## `irradiance.exr`, the path tracer's E/π, and the path-traced frame as `path_traced.exr` and `path_traced.png`. `--accumulate=<frames>` instead averages that many raw
## frames of one sample per pixel into `irradiance.exr`, and the even ones into `irradiance_half.exr`. Either way the
## folder also holds Godot's frame with an irradiance of 0 and of 1, the surfaces' world positions, and as `final.exr`
## and `final.png` Godot's frame with the reference's E/π.

const CAPTURE_PREFIX: String = "--capture="
const ANIMATION_PREFIX: String = "--animation="
const TIME_PREFIX: String = "--time="
const BENCHMARK_PREFIX: String = "--benchmark="
const CHECK_ARGUMENT: String = "--check"
const REFERENCE_ARGUMENT: String = "--reference"
const ACCUMULATE_PREFIX: String = "--accumulate="
const REPORT_FILE: String = "capture.json"
const FINAL_FILE: String = "final.exr"
const FINAL_IMAGE_FILE: String = "final.png"
const IRRADIANCE_FILE: String = "irradiance.exr"
const IRRADIANCE_HALF_FILE: String = "irradiance_half.exr"
const NO_INDIRECT_FILE: String = "no_indirect.exr"
const UNIT_INDIRECT_FILE: String = "unit_indirect.exr"
const POSITION_FILE: String = "position.exr"
const PATH_TRACED_FILE: String = "path_traced.exr"
const PATH_TRACED_IMAGE_FILE: String = "path_traced.png"
const WARMUP_FRAMES: int = 60
const MEASURED_FRAMES: int = 120
const SETTLE_FRAMES: int = 2
## The engine patch's cap. Russian roulette ends the paths long before it.
const MAX_BOUNCES: int = 255
## Ray Reconstruction smears colour bleeding and indirect shadows at one sample per pixel and keeps them at this many
## (design/evaluation.md#reference).
const DENOISED_SAMPLES: int = 16
## Ray Reconstruction's history settles within this many frames of its start.
const DENOISED_SETTLE_FRAMES: int = 64

var _directory: String = ""
var _frames_drawn: int = 0
var _gpu_ms: PackedFloat64Array = []
var _cpu_ms: PackedFloat64Array = []
var _gi_ms: Dictionary[StringName, PackedFloat64Array] = {}
var _gi_effect: GIEffect = null
var _gi_timed_frame: int = -1
# gdstyle-ignore[load]: an autoload script has no export slots
var _benchmark_shader: RDShaderFile = load("res://src/tracer/cshd_trace_benchmark.glsl")
var _benchmark: TracerBenchmark = null
var _tracer_report: Dictionary[String, Variant] = {}
# gdstyle-ignore[load]: an autoload script has no export slots
var _accumulate_shader: RDShaderFile = load("res://src/reference/cshd_accumulate.glsl")
var _accumulator: FrameAccumulator = null
var _reference: bool = false
var _accumulated_frames: int = 0
var _display_settings: DisplaySettings = null
var _path_tracing: PathTracing = null
var _error_log: ErrorLog = null
var _aborted: bool = false


# The logger goes in before the main scene loads, so its script errors are caught.
func _init() -> void:
	_directory = _argument(CAPTURE_PREFIX)
	if _directory:
		_error_log = ErrorLog.new(_abort)
		OS.add_logger(_error_log)


func _ready() -> void:
	if !_directory:
		return

	_reference = OS.get_cmdline_user_args().has(REFERENCE_ARGUMENT)
	_accumulated_frames = _argument(ACCUMULATE_PREFIX).to_int()
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
	if is_instance_valid(_benchmark):
		RenderingServer.call_on_render_thread(_benchmark.trace.bind(CameraRays.basis(get_viewport().get_camera_3d())))
	if _frames_drawn <= WARMUP_FRAMES:
		return

	_record_render_times()
	if _frames_drawn == WARMUP_FRAMES + MEASURED_FRAMES:
		_finish()


# The main scene enters the tree after the autoloads are ready.
func _prepare_scene() -> void:
	var scene: Node = get_tree().current_scene
	_gi_effect = _find_gi_effect(scene)
	_play_animation(scene)
	var spacing: String = _argument(BENCHMARK_PREFIX)
	if spacing:
		_start_benchmark(scene, spacing.to_float())


func _play_animation(scene: Node) -> void:
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


func _start_benchmark(scene: Node, spacing: float) -> void:
	var tracer: Tracer = _find_tracer(scene)
	if !is_instance_valid(tracer):
		return

	var sun: Vector3 = Vector3.ZERO
	for node: Node in scene.find_children("*", "DirectionalLight3D", true, false):
		var light: DirectionalLight3D = node
		if light.is_visible_in_tree():
			sun = light.global_transform.basis.z.normalized()
	var camera_basis: PackedFloat32Array = CameraRays.basis(get_viewport().get_camera_3d())
	var check: bool = OS.get_cmdline_user_args().has(CHECK_ARGUMENT)
	RenderingServer.call_on_render_thread(func() -> void:
		var device: RenderingDevice = RenderingServer.get_rendering_device()
		var benchmark: TracerBenchmark = TracerBenchmark.new(device, tracer, _benchmark_shader, get_viewport().size,
				spacing, sun)
		if check:
			benchmark.check(camera_basis)
		_benchmark = benchmark)


func _find_tracer(scene: Node) -> Tracer:
	var gis: Array[Node] = scene.find_children("*", "GI", true, false)
	if gis.is_empty() || !is_instance_valid((gis[0] as GI).get_tracer()):
		push_error("The scene has no GI node with a tracer.")
		return null

	return (gis[0] as GI).get_tracer()


func _stop_benchmark() -> void:
	var benchmark: TracerBenchmark = _benchmark
	_benchmark = null
	RenderingServer.call_on_render_thread(func() -> void:
		_tracer_report = benchmark.get_report()
		benchmark.free_rids())


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
	if is_instance_valid(_benchmark):
		_stop_benchmark()
	DirAccess.make_dir_recursive_absolute(_directory)
	await _capture_cameras()
	OS.remove_logger(_error_log)
	_save_report()
	get_tree().quit(1 if _error_log.get_errors() else 0)


# Any logged error invalidates the capture, and a script error can stop the capture from ever finishing.
func _abort() -> void:
	if _aborted:
		return

	_aborted = true
	DirAccess.make_dir_recursive_absolute(_directory)
	_save_report()
	get_tree().quit(1)


func _capture_cameras() -> void:
	var world_environment: Environment = get_viewport().find_world_3d().environment
	if !is_instance_valid(world_environment):
		push_error("The capture needs a WorldEnvironment.")
		return

	for node: Node in get_tree().current_scene.find_children("*", "Camera3D", true, false):
		var camera: Camera3D = node
		var directory: String = _directory.path_join(camera.name)
		DirAccess.make_dir_recursive_absolute(directory)
		camera.make_current()
		# A camera's own environment, such as one with its own exposure, takes the WorldEnvironment's place.
		var environment: Environment = camera.environment if is_instance_valid(camera.environment) else world_environment
		_display_settings = DisplaySettings.new(get_viewport(), environment)
		_display_settings.set_linear(true)
		_display_settings.set_anti_aliased(false)
		_path_tracing = PathTracing.new(get_viewport(), environment)
		await _capture_camera(directory)
		# The next camera reads its display settings from the viewport and from an environment it may share.
		_display_settings.set_linear(false)
		_display_settings.set_anti_aliased(true)


func _capture_camera(directory: String) -> void:
	if _reference || _accumulated_frames:
		await _capture_reference(directory)
		return

	await _save_view(GI.View.SHADED, directory.path_join(FINAL_FILE))
	# A transparent background marks the pixels without a surface with alpha 0.
	get_viewport().transparent_bg = true
	await _save_view(GI.View.IRRADIANCE, directory.path_join(IRRADIANCE_FILE))
	get_viewport().transparent_bg = false
	await _save_final_image(directory.path_join(FINAL_IMAGE_FILE))


func _capture_reference(directory: String) -> void:
	await _save_view(GI.View.NO_INDIRECT, directory.path_join(NO_INDIRECT_FILE))
	await _save_view(GI.View.UNIT_INDIRECT, directory.path_join(UNIT_INDIRECT_FILE))
	get_viewport().transparent_bg = true
	var positions: Image = await _view_image(GI.View.POSITION)
	get_viewport().transparent_bg = false
	_save_exr(positions, directory.path_join(POSITION_FILE))

	var irradiance: Image = null
	if _accumulated_frames:
		irradiance = await _accumulate(positions, directory)
	else:
		irradiance = await _trace_denoised(positions, directory)
	_save_exr(irradiance, directory.path_join(IRRADIANCE_FILE))
	await _save_reference_final(irradiance, directory)


func _view_image(view: GI.View) -> Image:
	RenderingServer.global_shader_parameter_set(&"gi_view", view)
	await _settle(SETTLE_FRAMES)
	var image: Image = get_viewport().get_texture().get_image()
	RenderingServer.global_shader_parameter_set(&"gi_view", GI.View.SHADED)
	return image


func _save_view(view: GI.View, path: String) -> void:
	_save_exr(await _view_image(view), path)


func _trace_denoised(mask: Image, directory: String) -> Image:
	_path_tracing.enable(true, Environment.RT_DEBUG_INDIRECT_IRRADIANCE)
	await _settle(DENOISED_SETTLE_FRAMES)
	var irradiance: Image = _masked(get_viewport().get_texture().get_image(), mask)

	# Leaving DLSS gives the next view a new Ray Reconstruction instance, which the irradiance view left nothing in.
	_path_tracing.disable()
	await _settle(SETTLE_FRAMES)
	_path_tracing.enable(true, Environment.RT_DEBUG_DISABLED)
	await _settle(DENOISED_SETTLE_FRAMES)
	_save_exr(get_viewport().get_texture().get_image(), directory.path_join(PATH_TRACED_FILE))
	# Ray Reconstruction anti-aliases the frame itself.
	await _save_display_image(directory.path_join(PATH_TRACED_IMAGE_FILE), DENOISED_SETTLE_FRAMES)
	_path_tracing.disable()
	return irradiance


func _accumulate(mask: Image, directory: String) -> Image:
	_path_tracing.enable(false, Environment.RT_DEBUG_INDIRECT_IRRADIANCE)
	await _settle(SETTLE_FRAMES)
	var viewport_texture: RID = get_viewport().get_texture().get_rid()
	var size: Vector2i = get_viewport().size
	RenderingServer.call_on_render_thread(func() -> void:
		_accumulator = FrameAccumulator.new(RenderingServer.get_rendering_device(), _accumulate_shader,
				viewport_texture, size))
	for _frame: int in _accumulated_frames:
		await RenderingServer.frame_post_draw
		RenderingServer.call_on_render_thread(func() -> void: _accumulator.add())
	_path_tracing.disable()

	var means: Array[Image] = []
	RenderingServer.call_on_render_thread(func() -> void:
		means.append_array([_accumulator.get_mean(), _accumulator.get_even_mean()])
		_accumulator.free_rids())
	await RenderingServer.frame_post_draw
	_save_exr(_masked(means[1], mask), directory.path_join(IRRADIANCE_HALF_FILE))
	return _masked(means[0], mask)


# The path tracer sees no alpha, so the pixels without a surface take theirs from `mask`.
func _masked(image: Image, mask: Image) -> Image:
	# An opaque viewport reads back without alpha.
	if image.get_format() == Image.FORMAT_RGBH:
		image.convert(Image.FORMAT_RGBAH)
	var masked: Image = Image.create_empty(image.get_width(), image.get_height(), false, image.get_format())
	masked.blit_rect_mask(image, mask, Rect2i(Vector2i.ZERO, image.get_size()), Vector2i.ZERO)
	return masked


# Godot's frame with the reference's irradiance in place of the GI's.
func _save_reference_final(irradiance: Image, directory: String) -> void:
	RenderingServer.global_shader_parameter_set(&"gi_irradiance", ImageTexture.create_from_image(irradiance))
	RenderingServer.global_shader_parameter_set(&"gi_view", GI.View.REFERENCE)
	await _settle(SETTLE_FRAMES)
	_save_exr(get_viewport().get_texture().get_image(), directory.path_join(FINAL_FILE))
	await _save_final_image(directory.path_join(FINAL_IMAGE_FILE))
	RenderingServer.global_shader_parameter_set(&"gi_view", GI.View.SHADED)
	RenderingServer.global_shader_parameter_set(&"gi_irradiance", null)


func _save_final_image(path: String) -> void:
	_display_settings.set_anti_aliased(true)
	await _save_display_image(path, SETTLE_FRAMES)
	_display_settings.set_anti_aliased(false)


func _save_display_image(path: String, settle_frames: int) -> void:
	_display_settings.set_linear(false)
	await _settle(settle_frames)
	var error: Error = get_viewport().get_texture().get_image().save_png(path)
	if error != OK:
		push_error("Image not saved to %s: %s" % [path, error_string(error)])
	_display_settings.set_linear(true)


func _settle(frames: int) -> void:
	for _frame: int in frames:
		await RenderingServer.frame_post_draw


func _save_exr(image: Image, path: String) -> void:
	var error: Error = image.save_exr(path)
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
	if !_tracer_report.is_empty():
		report["tracer"] = _tracer_report

	var path: String = _directory.path_join(REPORT_FILE)
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if !is_instance_valid(file):
		push_error("Report not saved to %s: %s" % [path, error_string(FileAccess.get_open_error())])
		return

	file.store_string(JSON.stringify(report, "\t", false))


func _summarize(samples: PackedFloat64Array) -> Dictionary[String, float]:
	if samples.is_empty():
		return {}

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


## The settings that turn a frame into the game's image: tonemapping, exposure, debanding and anti-aliasing. A linear
## frame without anti-aliasing holds in each pixel the exact linear value of the one surface at its centre, as
## metrics.py needs.
class DisplaySettings:
	var _viewport: Viewport = null
	var _environment: Environment = null
	var _msaa: Viewport.MSAA = Viewport.MSAA_DISABLED
	var _screen_space_aa: Viewport.ScreenSpaceAA = Viewport.SCREEN_SPACE_AA_DISABLED
	var _debanding: bool = false
	var _tone_mapper: Environment.ToneMapper = Environment.TONE_MAPPER_LINEAR
	var _exposure: float = 1.0


	func _init(viewport: Viewport, environment: Environment) -> void:
		_viewport = viewport
		_environment = environment
		_msaa = viewport.msaa_3d
		_screen_space_aa = viewport.screen_space_aa
		_debanding = viewport.use_debanding
		_tone_mapper = environment.tonemap_mode
		_exposure = environment.tonemap_exposure


	## An HDR viewport reads back linear, unclamped values.
	func set_linear(linear: bool) -> void:
		_viewport.use_hdr_2d = linear
		_viewport.use_debanding = !linear && _debanding
		_environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR if linear else _tone_mapper
		_environment.tonemap_exposure = 1.0 if linear else _exposure


	func set_anti_aliased(anti_aliased: bool) -> void:
		_viewport.msaa_3d = _msaa if anti_aliased else Viewport.MSAA_DISABLED
		_viewport.screen_space_aa = _screen_space_aa if anti_aliased else Viewport.SCREEN_SPACE_AA_DISABLED


## The path tracer's settings, on the environment the camera renders with, and the viewport's scaling: DLSS Ray
## Reconstruction runs only with DLSS scaling, here at full resolution.
class PathTracing:
	var _viewport: Viewport = null
	var _environment: Environment = null
	var _scaling_mode: Viewport.Scaling3DMode = Viewport.SCALING_3D_MODE_BILINEAR
	var _scaling_scale: float = 1.0


	func _init(viewport: Viewport, environment: Environment) -> void:
		_viewport = viewport
		_environment = environment
		_scaling_mode = viewport.scaling_3d_mode
		_scaling_scale = viewport.scaling_3d_scale


	## Without denoising, each frame is one raw sample per pixel.
	func enable(denoised: bool, view: Environment.PathtracingDebugMode) -> void:
		_environment.pathtracing_enabled = true
		_environment.pathtracing_samples_per_pixel = DENOISED_SAMPLES if denoised else 1
		_environment.pathtracing_max_bounces = MAX_BOUNCES
		_environment.pathtracing_debug_mode = view
		if denoised:
			_environment.pathtracing_denoiser = RenderingServer.PT_DENOISER_DLSS_RAY_RECONSTRUCTION
			_viewport.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
			_viewport.scaling_3d_scale = 1.0
		else:
			_environment.pathtracing_denoiser = RenderingServer.PT_DENOISER_NONE


	func disable() -> void:
		_environment.pathtracing_enabled = false
		_environment.pathtracing_debug_mode = Environment.RT_DEBUG_DISABLED
		_viewport.scaling_3d_mode = _scaling_mode
		_viewport.scaling_3d_scale = _scaling_scale


class ErrorLog extends Logger:
	var _mutex: Mutex = Mutex.new()
	var _errors: PackedStringArray = []
	var _warnings: PackedStringArray = []
	var _on_error: Callable = Callable()


	## `on_error` runs on the main thread after each error, since errors arrive from any thread.
	func _init(on_error: Callable) -> void:
		_on_error = on_error


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
			_on_error.call_deferred()
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
