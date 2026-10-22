class_name GI
extends Node
## The scene's GI. A mesh instance takes part when every surface uses one of the GI shaders; its surfaces must then
## have UV2. At load the GI builds the tracer over the instances that take part, then the atlas and its probes, caches
## the static lights' visibility and bakes the sky into the top cascade's bins; each frame its effect lights the probes
## with the scene's lights.
##
## An instance that casts no shadow, such as a lamp's fixture, takes no part: Godot's shadow maps and the reference path
## tracer let light through it, and its emission belongs to the Godot light inside it.

## What the GI materials show, through the global shader parameter `gi_view`. NO_INDIRECT and UNIT_INDIRECT hand Godot
## an irradiance of 0 and 1, so that the final image can be composed for any irradiance. REFERENCE reads `gi_irradiance`
## per screen pixel, as a path-traced reference stores it. POSITION and NORMAL show each surface's world position and
## its world normal before normal mapping. DISTANCE shows its distance from the camera to a float's precision, as the
## sum of the red and green channels.
enum View { SHADED, IRRADIANCE, NO_INDIRECT, UNIT_INDIRECT, REFERENCE, POSITION, NORMAL, DISTANCE, NORMAL_REMAINDER }

@export var one_sided_shader: Shader = null
@export var two_sided_shader: Shader = null
@export var alpha_tested_shader: Shader = null
@export var two_sided_alpha_tested_shader: Shader = null
@export var shaders: GIShaders = null
## The compositor effect that runs the GI's frame.
@export var effect: GIEffect = null
## The import's texel size in metres, which src/editor/import_options.gd writes into the scene.
@export var texel_size: float = 0.0
## The atlas capture's sample points along each side of a texel.
@export var atlas_samples: int = 4

var _tracer: Tracer = null
var _atlas: Atlas = null
var _direct_light: DirectLight = null
var _sky_table: SkyTable = null
var _lights: Array[Light3D] = []
var _static_lights: Array[Light3D] = []


func _ready() -> void:
	var instances: Array[MeshInstance3D] = []
	for node: Node in get_parent().find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node
		if _takes_part(instance):
			instances.append(instance)

	if instances.is_empty():
		set_process(false)
		return

	if texel_size <= 0.0:
		push_error("The GI has no texel size: run src/editor/import_options.gd on the scene.")
		return

	_gather_lights()
	var scene := TracerScene.new(instances, self)
	RenderingServer.call_on_render_thread(_build.bind(scene, DirectLight.pack(_lights, _static_lights)))

	# Godot fills the sky's radiance map as it draws the first frame, and bakes a black panorama before that.
	var top_cascade: int = CascadeLayout.top_cascade(_bounds(instances).size.length(), texel_size)
	await RenderingServer.frame_post_draw
	RenderingServer.call_on_render_thread(_build_sky.bind(_bake_sky(), top_cascade))


func _process(_delta: float) -> void:
	RenderingServer.call_on_render_thread(_set_lights.bind(DirectLight.pack(_lights, _static_lights)))


func _exit_tree() -> void:
	RenderingServer.call_on_render_thread(_free_rids)


## The tracer, once the render thread has built it.
func get_tracer() -> Tracer:
	return _tracer


## The atlas, once the render thread has built it.
func get_atlas() -> Atlas:
	return _atlas


## The direct light, once the render thread has built it.
func get_direct_light() -> DirectLight:
	return _direct_light


## The sky table, once the render thread has built it.
func get_sky_table() -> SkyTable:
	return _sky_table


## The environment's radiance as Godot bakes it: E/π from its irradiance map with `irradiance`, or null without an
## environment.
func bake_panorama(irradiance: bool) -> Image:
	var environment: Environment = get_viewport().find_world_3d().environment
	if !is_instance_valid(environment):
		return null
	return RenderingServer.environment_bake_panorama(environment.get_rid(), irradiance, SkyTable.PANORAMA_SIZE)


func is_two_sided(shader: Shader) -> bool:
	return shader == two_sided_shader || shader == two_sided_alpha_tested_shader


func is_alpha_tested(shader: Shader) -> bool:
	return shader == alpha_tested_shader || shader == two_sided_alpha_tested_shader


func _takes_part(instance: MeshInstance3D) -> bool:
	var mesh: Mesh = instance.mesh
	if !is_instance_valid(mesh) || instance.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
		return false

	if mesh is not ArrayMesh:
		push_warning("%s takes no part in the GI: its mesh has no lightmap size." % instance.get_path())
		return false

	var material_shaders: Array[Shader] = [one_sided_shader, two_sided_shader, alpha_tested_shader,
			two_sided_alpha_tested_shader]
	for surface: int in mesh.get_surface_count():
		var material: ShaderMaterial = instance.get_active_material(surface) as ShaderMaterial
		if !is_instance_valid(material) || !material_shaders.has(material.shader):
			push_warning("%s takes no part in the GI: surface %d has no GI material." % [instance.get_path(), surface])
			return false

	for surface: int in mesh.get_surface_count():
		if !(mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_TEX_UV2):
			push_error("%s has no UV2 on surface %d: import it with light baking set to Static Lightmaps."
					% [instance.get_path(), surface])
			return false
	return true


# Omni and directional lights with shadows, in non-physical units, are the ones the GI supports. Any other light that
# gives no light at load, such as a model's light that the scene's own lights replace, is left out. Static omni lights
# get the visibility cache's slots.
func _gather_lights() -> void:
	if ProjectSettings.get_setting("rendering/lights_and_shadows/use_physical_light_units"):
		push_error("The GI does not support physical light units.")

	for node: Node in get_parent().find_children("*", "Light3D", true, false):
		var light: Light3D = node
		if light is SpotLight3D || !light.shadow_enabled:
			if light.is_visible_in_tree() && light.light_energy > 0.0:
				push_error("%s: the GI supports only omni and directional lights with shadows." % light.get_path())
			continue

		_lights.append(light)
		if light is OmniLight3D && light.light_bake_mode == Light3D.BAKE_STATIC:
			_static_lights.append(light)

	if _lights.size() > DirectLight.MAX_LIGHTS:
		push_error("The scene has %d lights; the GI takes %d." % [_lights.size(), DirectLight.MAX_LIGHTS])
		_lights.resize(DirectLight.MAX_LIGHTS)
		_static_lights = _static_lights.filter(func(light: Light3D) -> bool: return _lights.has(light))


func _bounds(instances: Array[MeshInstance3D]) -> AABB:
	var bounds: AABB = instances[0].global_transform * instances[0].get_aabb()
	for instance: MeshInstance3D in instances:
		bounds = bounds.merge(instance.global_transform * instance.get_aabb())
	return bounds


func _bake_sky() -> Image:
	var panorama: Image = bake_panorama(false)
	if !is_instance_valid(panorama):
		push_error("The GI has no environment to take its sky from.")
	return panorama


func _build(scene: TracerScene, lights: PackedByteArray) -> void:
	var device: RenderingDevice = RenderingServer.get_rendering_device()
	var tracer := Tracer.new(device)
	tracer.build(scene, shaders.triangles)
	_tracer = tracer
	var atlas := Atlas.new(device, shaders)
	if atlas.build(scene, tracer, texel_size, atlas_samples):
		_atlas = atlas
		var direct_light := DirectLight.new(device)
		direct_light.build(shaders, tracer, atlas, lights)
		_direct_light = direct_light
		effect.set_direct_light(direct_light)
	tracer.free_corner_normals()


func _build_sky(panorama: Image, top_cascade: int) -> void:
	if !is_instance_valid(panorama):
		return

	var sky_table := SkyTable.new(RenderingServer.get_rendering_device())
	sky_table.build(shaders.sky_table, panorama, top_cascade)
	_sky_table = sky_table


func _set_lights(lights: PackedByteArray) -> void:
	if is_instance_valid(_direct_light):
		_direct_light.set_lights(lights)


func _free_rids() -> void:
	effect.set_direct_light(null)
	if is_instance_valid(_direct_light):
		_direct_light.free_rids()
	if is_instance_valid(_sky_table):
		_sky_table.free_rids()
	if is_instance_valid(_atlas):
		_atlas.free_rids()
	if is_instance_valid(_tracer):
		_tracer.free_rids()
