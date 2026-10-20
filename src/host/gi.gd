class_name GI
extends Node
## The scene's GI. A mesh instance takes part when every surface uses one of the GI shaders; its surfaces must then
## have UV2.

enum View { SHADED, IRRADIANCE }

@export var shaders: Array[Shader] = []


func _ready() -> void:
	for node: Node in get_parent().find_children("*", "MeshInstance3D", true, false):
		_check_instance(node as MeshInstance3D)


func _check_instance(instance: MeshInstance3D) -> void:
	var mesh: Mesh = instance.mesh
	if !is_instance_valid(mesh):
		return

	for surface: int in mesh.get_surface_count():
		var material: ShaderMaterial = instance.get_active_material(surface) as ShaderMaterial
		if !is_instance_valid(material) || !shaders.has(material.shader):
			push_warning("%s takes no part in the GI: surface %d has no GI material." % [instance.get_path(), surface])
			return

	for surface: int in mesh.get_surface_count():
		if !(mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_TEX_UV2):
			push_error("%s has no UV2 on surface %d: import it with light baking set to Static Lightmaps."
					% [instance.get_path(), surface])
