@tool
extends EditorScenePostImport
## Replaces every imported mesh material with a GI material that keeps its albedo, roughness, metalness, normal map,
## emission, two-sidedness and alpha test. Alpha-scissor materials are cards, so they render from both sides.
## Transparent materials are out of the GI's scope, so blended ones become alpha-tested. Glass is left out with its
## surfaces: neither the GI nor the path tracer transmits light, and thin panes pass nearly all of it.

const GLASS: String = "glass"
## Falcor's texture convention: next to a "_BaseColor" map, a "_Specular" map holds occlusion, roughness and
## metalness in red, green and blue, and the normal maps are DirectX's.
const FALCOR_BASE_COLOR: String = "_BaseColor."
const FALCOR_SPECULAR: String = "_Specular."
const CHANNEL_GREEN: Vector4 = Vector4(0.0, 1.0, 0.0, 0.0)
const CHANNEL_BLUE: Vector4 = Vector4(0.0, 0.0, 1.0, 0.0)

# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _one_sided: Shader = load("res://assets/shaders/shd_gi.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _two_sided: Shader = load("res://assets/shaders/shd_gi_double_sided.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _one_sided_alpha_tested: Shader = load("res://assets/shaders/shd_gi_alpha_tested.gdshader")
# gdstyle-ignore[load]: an import script is instanced by the importer and has no export slots
var _two_sided_alpha_tested: Shader = load("res://assets/shaders/shd_gi_double_sided_alpha_tested.gdshader")
var _converted: Dictionary[Material, ShaderMaterial] = {}
# Instances share meshes, whose materials are converted once.
var _converted_meshes: Dictionary[Mesh, bool] = {}


func _post_import(scene: Node) -> Object:
	for node: Node in scene.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node
		if !is_instance_valid(instance.mesh):
			continue
		if !_converted_meshes.has(instance.mesh):
			_convert(instance.mesh)
		if instance.mesh.get_surface_count() == 0:
			instance.mesh = null
	return scene


func _convert(mesh: ArrayMesh) -> void:
	_converted_meshes[mesh] = true
	for surface: int in range(mesh.get_surface_count() - 1, -1, -1):
		var source: Material = mesh.surface_get_material(surface)
		if is_instance_valid(source) && source.resource_name.containsn(GLASS):
			mesh.surface_remove(surface)
			# Godot draws each surface's depth and shadows from the shadow mesh's surface of the same index.
			if is_instance_valid(mesh.shadow_mesh):
				mesh.shadow_mesh.surface_remove(surface)
		else:
			mesh.surface_set_material(surface, _gi_material(source))


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
		_copy_falcor_textures(base, material)
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
	material.set_shader_parameter(&"albedo_color", base.albedo_color)
	material.set_shader_parameter(&"albedo_texture", base.albedo_texture)
	if base.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
		material.set_shader_parameter(&"alpha_scissor", base.alpha_scissor_threshold)

	material.set_shader_parameter(&"roughness", base.roughness)
	material.set_shader_parameter(&"roughness_texture", base.roughness_texture)
	material.set_shader_parameter(&"roughness_channel", _channel_mask(base.roughness_texture_channel))
	material.set_shader_parameter(&"metallic", base.metallic)
	material.set_shader_parameter(&"metallic_texture", base.metallic_texture)
	material.set_shader_parameter(&"metallic_channel", _channel_mask(base.metallic_texture_channel))
	# Godot imports no glTF specular, so a scene gives it in the material's extras.
	# gdstyle-ignore[untyped-collection]: the importer keeps the extras as parsed JSON
	var extras: Dictionary = base.get_meta(&"extras", {})
	material.set_shader_parameter(&"specular", extras.get("specular", base.metallic_specular))
	if base.normal_enabled:
		material.set_shader_parameter(&"normal_texture", base.normal_texture)
		material.set_shader_parameter(&"normal_scale", base.normal_scale)

	if base.emission_enabled:
		material.set_shader_parameter(&"emission", _emission_color(base))
		material.set_shader_parameter(&"emission_energy", base.emission_energy_multiplier)
		material.set_shader_parameter(&"emission_texture", base.emission_texture)


# Falcor's FBX materials are Phong, so the importer reads neither their roughness nor their metalness, and the
# "_Specular" map they come from sits in a slot Godot ignores.
func _copy_falcor_textures(base: BaseMaterial3D, material: ShaderMaterial) -> void:
	if !is_instance_valid(base.albedo_texture) || !base.albedo_texture.resource_path.contains(FALCOR_BASE_COLOR):
		return

	material.set_shader_parameter(&"normal_green_down", true)
	var specular_path: String = base.albedo_texture.resource_path.replace(FALCOR_BASE_COLOR, FALCOR_SPECULAR)
	if !ResourceLoader.exists(specular_path):
		return

	# gdstyle-ignore[load]: the map's path follows from the base colour's, and an import script has no export slots
	var specular: Texture2D = load(specular_path)
	material.set_shader_parameter(&"roughness", 1.0)
	material.set_shader_parameter(&"roughness_texture", specular)
	material.set_shader_parameter(&"roughness_channel", CHANNEL_GREEN)
	material.set_shader_parameter(&"metallic", 1.0)
	material.set_shader_parameter(&"metallic_texture", specular)
	material.set_shader_parameter(&"metallic_channel", CHANNEL_BLUE)


# The mask of the dot product with which the GI shader reads one channel, as StandardMaterial3D's shader does.
func _channel_mask(channel: BaseMaterial3D.TextureChannel) -> Vector4:
	match channel:
		BaseMaterial3D.TEXTURE_CHANNEL_GREEN:
			return CHANNEL_GREEN
		BaseMaterial3D.TEXTURE_CHANNEL_BLUE:
			return CHANNEL_BLUE
		BaseMaterial3D.TEXTURE_CHANNEL_ALPHA:
			return Vector4(0.0, 0.0, 0.0, 1.0)
		BaseMaterial3D.TEXTURE_CHANNEL_GRAYSCALE:
			return Vector4(1.0, 1.0, 1.0, 0.0) / 3.0
	return Vector4(1.0, 0.0, 0.0, 0.0)


# The GI shader multiplies the emission colour by its texture. Godot's other operator adds them, which equals white
# times the texture when the colour is black.
func _emission_color(base: BaseMaterial3D) -> Color:
	if base.emission_operator == BaseMaterial3D.EMISSION_OP_MULTIPLY || !is_instance_valid(base.emission_texture):
		return base.emission

	if base.emission != Color.BLACK:
		push_warning("Material %s adds its emission texture to a colour; its GI material keeps the texture alone."
				% base.resource_name)
	return Color.WHITE
