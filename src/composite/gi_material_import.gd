@tool
extends EditorScenePostImport
## Replaces every imported mesh material with a GI material that keeps its albedo, emission, two-sidedness and
## alpha test. Alpha-scissor materials are cards, so they render from both sides. Transparent materials are out of the
## GI's scope, so blended ones become alpha-tested.

# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _one_sided: Shader = load("res://assets/shaders/shd_gi.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _two_sided: Shader = load("res://assets/shaders/shd_gi_double_sided.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _one_sided_alpha_tested: Shader = load("res://assets/shaders/shd_gi_alpha_tested.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _two_sided_alpha_tested: Shader = load("res://assets/shaders/shd_gi_double_sided_alpha_tested.gdshader")
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

	var material := ShaderMaterial.new()
	material.resource_name = source.resource_name
	var base: BaseMaterial3D = source as BaseMaterial3D
	if is_instance_valid(base):
		material.shader = _shader(base)
		_copy_parameters(base, material)
	else:
		material.shader = _one_sided
		push_warning("Material %s is not a BaseMaterial3D; its GI material keeps the defaults." % source.resource_name)

	_converted[source] = material
	return material


func _shader(base: BaseMaterial3D) -> Shader:
	if base.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
		return _two_sided_alpha_tested

	var two_sided: bool = base.cull_mode == BaseMaterial3D.CULL_DISABLED
	if base.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
		return _two_sided_alpha_tested if two_sided else _one_sided_alpha_tested
	return _two_sided if two_sided else _one_sided


func _copy_parameters(base: BaseMaterial3D, material: ShaderMaterial) -> void:
	material.set_shader_parameter(&"albedo", base.albedo_color)
	material.set_shader_parameter(&"albedo_texture", base.albedo_texture)
	if base.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
		material.set_shader_parameter(&"alpha_scissor", base.alpha_scissor_threshold)
	if base.emission_enabled:
		material.set_shader_parameter(&"emission", _emission_color(base))
		material.set_shader_parameter(&"emission_energy", base.emission_energy_multiplier)
		material.set_shader_parameter(&"emission_texture", base.emission_texture)


# The GI shader multiplies the emission colour by its texture. Godot's other operator adds them, which equals white
# times the texture when the colour is black.
func _emission_color(base: BaseMaterial3D) -> Color:
	if base.emission_operator == BaseMaterial3D.EMISSION_OP_MULTIPLY || !is_instance_valid(base.emission_texture):
		return base.emission

	if base.emission != Color.BLACK:
		push_warning("Material %s adds its emission texture to a colour; its GI material keeps the texture alone."
				% base.resource_name)
	return Color.WHITE
