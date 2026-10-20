extends SceneTree
## Gives each scene's import the texel size that the budget model (design/checks/budget.py) gets from the scene's
## surface area, with UV2 unwrapping and the GI material import script, then reimports:
##
##     godot --headless --path . --script res://src/editor/texel_size.gd -- res://assets/models/<scene>.gltf ...
##
## The scene must have been imported once, so that its .import file exists.

const BUDGET_SCRIPT: String = "res://design/checks/budget.py"
const IMPORT_SCRIPT: String = "res://src/composite/gi_material_import.gd"
const STATIC_LIGHTMAPS: int = 2
const TEXEL_STEPS_PER_METRE: float = 1000.0  # the import option's 0.001 m step

var _two_sided: Shader = load("res://assets/shaders/shd_gi_double_sided.gdshader")


func _initialize() -> void:
	for source: String in OS.get_cmdline_user_args():
		_configure(source)
	_reimport()
	quit()


func _configure(source: String) -> void:
	var scene: Node = (load(source) as PackedScene).instantiate()
	var surface := Surface.new()
	for node: Node in scene.find_children("*", "MeshInstance3D", true, false):
		surface.add(node as MeshInstance3D, _scene_transform(node, scene), _two_sided)
	scene.free()

	var diameter: float = surface.bounds.size.length()
	var spacing: float = _budget_spacing(surface.area, diameter)
	if spacing <= 0.0:
		return

	# Rounding up keeps the texel count within the record budget.
	var texel_size: float = ceilf(spacing * TEXEL_STEPS_PER_METRE) / TEXEL_STEPS_PER_METRE
	_write_import_options(source, texel_size)
	print("%s: %.1f m² of surface, %.1f m across, texel size %.3f m" % [source, surface.area, diameter, texel_size])


# The scene is not in the tree, so its nodes have no global transforms.
func _scene_transform(node: Node, scene: Node) -> Transform3D:
	var transform: Transform3D = Transform3D.IDENTITY
	var ancestor: Node = node
	while is_instance_valid(ancestor):
		if ancestor is Node3D:
			transform = (ancestor as Node3D).transform * transform
		ancestor = null if ancestor == scene else ancestor.get_parent()
	return transform


func _budget_spacing(area: float, diameter: float) -> float:
	var output: Array[String] = []
	var arguments: PackedStringArray = [ProjectSettings.globalize_path(BUDGET_SCRIPT), str(area), str(diameter)]
	if OS.execute("python", arguments, output, true) != 0:
		push_error("%s failed: %s" % [BUDGET_SCRIPT, "".join(output)])
		return 0.0
	return output[0].strip_edges().to_float()


func _write_import_options(source: String, texel_size: float) -> void:
	var path: String = source + ".import"
	var config := ConfigFile.new()
	var error: Error = config.load(path)
	if error != OK:
		push_error("%s not read: %s" % [path, error_string(error)])
		return

	config.set_value("params", "meshes/light_baking", STATIC_LIGHTMAPS)
	config.set_value("params", "meshes/lightmap_texel_size", texel_size)
	config.set_value("params", "import_script/path", IMPORT_SCRIPT)
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


	func add(instance: MeshInstance3D, transform: Transform3D, two_sided_shader: Shader) -> void:
		var mesh: Mesh = instance.mesh
		if !is_instance_valid(mesh):
			return

		for surface: int in mesh.get_surface_count():
			var sides: int = 2 if _is_two_sided(instance.get_active_material(surface), two_sided_shader) else 1
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


	func _is_two_sided(material: Material, two_sided_shader: Shader) -> bool:
		if material is BaseMaterial3D:
			return (material as BaseMaterial3D).cull_mode == BaseMaterial3D.CULL_DISABLED
		return material is ShaderMaterial && (material as ShaderMaterial).shader == two_sided_shader
