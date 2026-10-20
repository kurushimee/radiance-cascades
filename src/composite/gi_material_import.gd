@tool
extends EditorScenePostImport
## Replaces every imported mesh material with a GI material that keeps its albedo, emission and two-sidedness.
## A material whose name starts with the fixture prefix becomes a fixture.

const FIXTURE_PREFIX: String = "fixture"

# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _one_sided: Shader = load("res://assets/shaders/shd_gi.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _two_sided: Shader = load("res://assets/shaders/shd_gi_double_sided.gdshader")
var _converted: Dictionary[Material, ShaderMaterial] = {}


func _post_import(scene: Node) -> Object:
	for node: Node in scene.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for surface: int in mesh.get_surface_count():
			mesh.surface_set_material(surface, _gi_material(mesh.surface_get_material(surface)))
	return scene


func _gi_material(source: Material) -> ShaderMaterial:
	if !is_instance_valid(source):
		var plain := ShaderMaterial.new()
		plain.shader = _one_sided
		return plain

	if _converted.has(source):
		return _converted[source]

	var base: BaseMaterial3D = source as BaseMaterial3D
	var two_sided: bool = is_instance_valid(base) && base.cull_mode == BaseMaterial3D.CULL_DISABLED
	var material := ShaderMaterial.new()
	material.resource_name = source.resource_name
	material.shader = _two_sided if two_sided else _one_sided
	material.set_shader_parameter(&"fixture", source.resource_name.begins_with(FIXTURE_PREFIX))
	if is_instance_valid(base):
		_copy_parameters(base, material)
	else:
		push_warning("Material %s is not a BaseMaterial3D; its GI material keeps the defaults." % source.resource_name)

	_converted[source] = material
	return material


func _copy_parameters(base: BaseMaterial3D, material: ShaderMaterial) -> void:
	material.set_shader_parameter(&"albedo", base.albedo_color)
	material.set_shader_parameter(&"albedo_texture", base.albedo_texture)
	if base.emission_enabled:
		material.set_shader_parameter(&"emission", base.emission)
		material.set_shader_parameter(&"emission_energy", base.emission_energy_multiplier)
		material.set_shader_parameter(&"emission_texture", base.emission_texture)
