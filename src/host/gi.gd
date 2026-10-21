class_name GI
extends Node
## The scene's GI. A mesh instance takes part when every surface uses one of the GI shaders; its surfaces must then
## have UV2. At load the GI builds the tracer over the instances that take part.
##
## An instance that casts no shadow, such as a lamp's fixture, takes no part: Godot's shadow maps and the reference path
## tracer let light through it, and its emission belongs to the Godot light inside it.

## What the GI materials show, through the global shader parameter `gi_view`. NO_INDIRECT and UNIT_INDIRECT hand Godot
## an irradiance of 0 and 1, so that the final image can be composed for any irradiance. REFERENCE reads `gi_irradiance`
## per screen pixel, as a path-traced reference stores it. POSITION shows each surface's world position.
enum View { SHADED, IRRADIANCE, NO_INDIRECT, UNIT_INDIRECT, REFERENCE, POSITION }

@export var one_sided_shader: Shader = null
@export var two_sided_shader: Shader = null
@export var alpha_tested_shader: Shader = null
@export var two_sided_alpha_tested_shader: Shader = null
@export var triangles_shader: RDShaderFile = null

var _tracer: Tracer = null


func _ready() -> void:
	var instances: Array[MeshInstance3D] = []
	for node: Node in get_parent().find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node
		if _takes_part(instance):
			instances.append(instance)

	if instances.is_empty():
		return

	var scene := TracerScene.new(instances, self)
	RenderingServer.call_on_render_thread(_build_tracer.bind(scene))


func _exit_tree() -> void:
	if is_instance_valid(_tracer):
		RenderingServer.call_on_render_thread(_tracer.free_rids)


## The tracer, once the render thread has built it.
func get_tracer() -> Tracer:
	return _tracer


func is_two_sided(shader: Shader) -> bool:
	return shader == two_sided_shader || shader == two_sided_alpha_tested_shader


func is_alpha_tested(shader: Shader) -> bool:
	return shader == alpha_tested_shader || shader == two_sided_alpha_tested_shader


func _takes_part(instance: MeshInstance3D) -> bool:
	var mesh: Mesh = instance.mesh
	if !is_instance_valid(mesh) || instance.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
		return false

	var shaders: Array[Shader] = [one_sided_shader, two_sided_shader, alpha_tested_shader, two_sided_alpha_tested_shader]
	for surface: int in mesh.get_surface_count():
		var material: ShaderMaterial = instance.get_active_material(surface) as ShaderMaterial
		if !is_instance_valid(material) || !shaders.has(material.shader):
			push_warning("%s takes no part in the GI: surface %d has no GI material." % [instance.get_path(), surface])
			return false

	for surface: int in mesh.get_surface_count():
		if !(mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_TEX_UV2):
			push_error("%s has no UV2 on surface %d: import it with light baking set to Static Lightmaps."
					% [instance.get_path(), surface])
			return false
	return true


func _build_tracer(scene: TracerScene) -> void:
	var tracer := Tracer.new(RenderingServer.get_rendering_device())
	tracer.build(scene, triangles_shader)
	_tracer = tracer
