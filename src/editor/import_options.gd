extends SceneTree
## Sets the import options of each scene's models and textures, then reimports:
##
##     godot --headless --path . --script res://src/editor/import_options.gd -- res://assets/scenes/<scene>.tscn ...
##
## The models get UV2 unwrapping, the GI material import script and the texel size that the budget model
## (design/checks/budget.py) gets from the scene's surface area. The textures their materials use get Godot's 3D import,
## VRAM compression with mipmaps, which the editor sets when it first draws a texture in 3D and a headless import never
## does. The models must have been imported once, so that their .import files exist.

const BUDGET_SCRIPT: String = "res://design/checks/budget.py"
const IMPORT_SCRIPT: String = "res://src/composite/gi_material_import.gd"
const STATIC_LIGHTMAPS: int = 2
const TEXEL_STEPS_PER_METRE: float = 1000.0  # the import option's 0.001 m step
const VRAM_COMPRESSED: int = 2  # ResourceImporterTexture's COMPRESS_VRAM_COMPRESSED
const NORMAL_TEXTURE: StringName = &"normal_texture"

var _two_sided: Array[Shader] = [
	load("res://assets/shaders/shd_gi_double_sided.gdshader"),
	load("res://assets/shaders/shd_gi_double_sided_alpha_tested.gdshader"),
]


func _initialize() -> void:
	for scene_path: String in OS.get_cmdline_user_args():
		_configure(scene_path)
	_reimport()
	quit()


func _configure(scene_path: String) -> void:
	var scene: Node = (load(scene_path) as PackedScene).instantiate()
	var surface := Surface.new()
	var textures: Dictionary[String, bool] = {}
	for node: Node in scene.find_children("*", "MeshInstance3D", true, false):
		surface.add(node as MeshInstance3D, _scene_transform(node, scene), _two_sided)
		_add_textures(node as MeshInstance3D, textures)
	var models: PackedStringArray = _models(scene)
	scene.free()

	for texture: String in textures:
		_write_import_options(texture, _texture_options(textures[texture]))

	var diameter: float = surface.bounds.size.length()
	var spacing: float = _budget_spacing(surface.area, diameter)
	if spacing <= 0.0:
		return

	# Rounding up keeps the texel count within the record budget.
	var texel_size: float = ceilf(spacing * TEXEL_STEPS_PER_METRE) / TEXEL_STEPS_PER_METRE
	for model: String in models:
		_write_import_options(model, _model_options(texel_size))
	print("%s: %.1f m² of surface, %.1f m across, texel size %.3f m, %d textures" % [scene_path, surface.area, diameter,
			texel_size, textures.size()])


# The import's texel size is in the model's own units, so the scene must not scale a model.
func _models(scene: Node) -> PackedStringArray:
	var models: PackedStringArray = []
	for node: Node in scene.find_children("*", "Node3D", true, false):
		if !node.scene_file_path:
			continue

		models.append(node.scene_file_path)
		if !(node as Node3D).scale.is_equal_approx(Vector3.ONE):
			push_error("%s scales its model %s." % [scene.scene_file_path, node.scene_file_path])
	return models


# The scene is not in the tree, so its nodes have no global transforms.
func _scene_transform(node: Node, scene: Node) -> Transform3D:
	var transform: Transform3D = Transform3D.IDENTITY
	var ancestor: Node = node
	while is_instance_valid(ancestor):
		if ancestor is Node3D:
			transform = (ancestor as Node3D).transform * transform
		ancestor = null if ancestor == scene else ancestor.get_parent()
	return transform


## Adds to `textures` the path of each imported texture the instance's materials use, mapped to whether one of them
## uses it as a normal map.
func _add_textures(instance: MeshInstance3D, textures: Dictionary[String, bool]) -> void:
	if !is_instance_valid(instance.mesh):
		return

	for surface: int in instance.mesh.get_surface_count():
		var material: ShaderMaterial = instance.get_active_material(surface) as ShaderMaterial
		if !is_instance_valid(material):
			continue

		# gdstyle-ignore[untyped-collection]: the engine describes each uniform in an untyped Dictionary
		for uniform: Dictionary in material.shader.get_shader_uniform_list():
			var value: Variant = material.get_shader_parameter(uniform["name"])
			if value is not Texture2D || !FileAccess.file_exists((value as Texture2D).resource_path + ".import"):
				continue

			var path: String = (value as Texture2D).resource_path
			textures[path] = textures.get(path, false) || uniform["name"] == NORMAL_TEXTURE


func _budget_spacing(area: float, diameter: float) -> float:
	var output: Array[String] = []
	var arguments: PackedStringArray = [ProjectSettings.globalize_path(BUDGET_SCRIPT), str(area), str(diameter)]
	if OS.execute("python", arguments, output, true) != 0:
		push_error("%s failed: %s" % [BUDGET_SCRIPT, "".join(output)])
		return 0.0
	return output[0].strip_edges().to_float()


func _model_options(texel_size: float) -> Dictionary[String, Variant]:
	return {
		"meshes/light_baking": STATIC_LIGHTMAPS,
		"meshes/lightmap_texel_size": texel_size,
		"import_script/path": IMPORT_SCRIPT,
	}


# The options the editor's 3D detection sets (ResourceImporterTexture::update_imports). A normal map keeps only its red
# and green channels, which is all Godot reads of one.
func _texture_options(normal_map: bool) -> Dictionary[String, Variant]:
	var options: Dictionary[String, Variant] = {
		"compress/mode": VRAM_COMPRESSED,
		"mipmaps/generate": true,
		"detect_3d/compress_to": 0,
	}
	if normal_map:
		options["compress/normal_map"] = 1
	return options


func _write_import_options(source: String, options: Dictionary[String, Variant]) -> void:
	var path: String = source + ".import"
	var config := ConfigFile.new()
	var error: Error = config.load(path)
	if error != OK:
		push_error("%s not read: %s" % [path, error_string(error)])
		return

	# Saving rewrites the file, which reimports the source even when no option changed.
	if options.keys().all(func(key: String) -> bool: return config.get_value("params", key) == options[key]):
		return

	for key: String in options:
		config.set_value("params", key, options[key])
	error = config.save(path)
	if error != OK:
		push_error("%s not written: %s" % [path, error_string(error)])


# A changed .import file makes the editor's scan reimport its source.
func _reimport() -> void:
	var arguments: PackedStringArray = ["--headless", "--path", ProjectSettings.globalize_path("res://"), "--import"]
	if OS.execute(OS.get_executable_path(), arguments) != 0:
		push_error("Reimport failed.")


## Surface area in world units, counting two-sided surfaces twice since each side gets its own texels.
class Surface:
	var area: float = 0.0
	var bounds: AABB = AABB()
	var _empty: bool = true


	func add(instance: MeshInstance3D, transform: Transform3D, two_sided_shaders: Array[Shader]) -> void:
		var mesh: Mesh = instance.mesh
		if !is_instance_valid(mesh):
			return

		for surface: int in mesh.get_surface_count():
			var sides: int = 2 if _is_two_sided(instance.get_active_material(surface), two_sided_shaders) else 1
			# gdstyle-ignore[untyped-collection]: the engine returns the surface arrays with mixed element types
			var arrays: Array = mesh.surface_get_arrays(surface)
			var local_vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var vertices: PackedVector3Array = transform * local_vertices
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			if indices.is_empty():
				indices = PackedInt32Array(range(vertices.size()))
			for corner: int in range(0, indices.size(), 3):
				var a: Vector3 = vertices[indices[corner]]
				area += sides * 0.5 * (vertices[indices[corner + 1]] - a).cross(vertices[indices[corner + 2]] - a).length()
			for vertex: Vector3 in vertices:
				bounds = AABB(vertex, Vector3.ZERO) if _empty else bounds.expand(vertex)
				_empty = false


	func _is_two_sided(material: Material, two_sided_shaders: Array[Shader]) -> bool:
		if material is BaseMaterial3D:
			return (material as BaseMaterial3D).cull_mode == BaseMaterial3D.CULL_DISABLED
		return material is ShaderMaterial && two_sided_shaders.has((material as ShaderMaterial).shader)
