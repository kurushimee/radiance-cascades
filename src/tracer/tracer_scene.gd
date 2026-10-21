class_name TracerScene
extends RefCounted
## The static triangles of the GI's mesh instances, gathered on the CPU for the tracer: the meshes' local vertex arrays
## packed one buffer per attribute, a table of surfaces with their world transforms, and the materials with their
## textures. The layouts match the structs of cshd_triangles.glsl and cshd_trace.glslinc.

const MAX_TEXTURES: int = 512  # the length of the texture array in cshd_trace.glslinc
const MAX_MATERIALS: int = 1 << 24  # material indices share a word with the flags
const WHITE_TEXTURE: int = 0
const TWO_SIDED: int = 1
const ALPHA_TESTED: int = 2
const SURFACE_BYTES: int = 80
const MATERIAL_BYTES: int = 48

var triangle_count: int = 0
## The opaque surfaces' triangles come first and the alpha-tested ones' after them, so that the acceleration structure
## holds each kind as one geometry.
var opaque_triangle_count: int = 0
var vertex_count: int = 0
var index_count: int = 0
var surface_count: int = 0
var positions: PackedByteArray = []
var normals: PackedByteArray = []
var uvs: PackedByteArray = []
var uv2s: PackedByteArray = []
var indices: PackedByteArray = []
var surfaces: PackedByteArray = []
var materials: PackedByteArray = []
## Texture `i + 1` of the material table; texture 0 is white.
var textures: Array[Texture2D] = []

var _material_indices: Dictionary[ShaderMaterial, int] = {}
var _material_flags: PackedInt32Array = []
var _texture_indices: Dictionary[Texture2D, int] = {}


func _init(instances: Array[MeshInstance3D], gi: GI) -> void:
	for alpha_tested: bool in [false, true]:
		for instance_index: int in instances.size():
			var instance: MeshInstance3D = instances[instance_index]
			for surface: int in instance.mesh.get_surface_count():
				var material: int = _add_material(instance.get_active_material(surface) as ShaderMaterial, gi)
				if bool(_material_flags[material] & ALPHA_TESTED) == alpha_tested:
					_add_surface(instance, instance_index, surface, material)
		if !alpha_tested:
			opaque_triangle_count = triangle_count


func _add_surface(instance: MeshInstance3D, instance_index: int, surface: int, material: int) -> void:
	# gdstyle-ignore[untyped-collection]: the engine returns the surface's arrays of mixed types untyped
	var arrays: Array = instance.mesh.surface_get_arrays(surface)
	var surface_positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var surface_vertices: int = surface_positions.size()
	var surface_indices: PackedInt32Array = _indices(arrays[Mesh.ARRAY_INDEX], surface_vertices)

	var record := PackedByteArray()
	record.resize(SURFACE_BYTES)
	var transform: Transform3D = instance.global_transform
	for row: int in 3:
		record.encode_float(16 * row, transform.basis.x[row])
		record.encode_float(16 * row + 4, transform.basis.y[row])
		record.encode_float(16 * row + 8, transform.basis.z[row])
		record.encode_float(16 * row + 12, transform.origin[row])
	record.encode_u32(48, triangle_count)
	record.encode_u32(52, vertex_count)
	record.encode_u32(56, index_count)
	record.encode_u32(60, material)
	record.encode_u32(64, instance_index)
	record.encode_u32(68, int(transform.basis.determinant() < 0.0))
	record.encode_u32(72, _material_flags[material])
	surfaces.append_array(record)

	positions.append_array(surface_positions.to_byte_array())
	normals.append_array(_vectors3(arrays[Mesh.ARRAY_NORMAL], surface_vertices).to_byte_array())
	uvs.append_array(_vectors2(arrays[Mesh.ARRAY_TEX_UV], surface_vertices).to_byte_array())
	uv2s.append_array(_vectors2(arrays[Mesh.ARRAY_TEX_UV2], surface_vertices).to_byte_array())
	indices.append_array(surface_indices.to_byte_array())
	index_count += surface_indices.size()
	@warning_ignore("integer_division")
	triangle_count = index_count / 3
	vertex_count += surface_vertices
	surface_count += 1


# A surface without indices lists its triangles' vertices in order.
func _indices(values: Variant, count: int) -> PackedInt32Array:
	if values is PackedInt32Array:
		return values

	var sequence := PackedInt32Array()
	sequence.resize(count)
	for index: int in count:
		sequence[index] = index
	return sequence


func _vectors3(values: Variant, count: int) -> PackedVector3Array:
	if values is PackedVector3Array:
		return values

	var zeros := PackedVector3Array()
	zeros.resize(count)
	return zeros


func _vectors2(values: Variant, count: int) -> PackedVector2Array:
	if values is PackedVector2Array:
		return values

	var zeros := PackedVector2Array()
	zeros.resize(count)
	return zeros


func _add_material(material: ShaderMaterial, gi: GI) -> int:
	if _material_indices.has(material):
		return _material_indices[material]

	var flags: int = 0
	if gi.is_two_sided(material.shader):
		flags |= TWO_SIDED
	if gi.is_alpha_tested(material.shader):
		flags |= ALPHA_TESTED

	# Godot converts source-colour parameters from sRGB when it uploads them.
	var albedo: Color = _parameter(material, &"albedo_color", Color.WHITE).srgb_to_linear()
	var emission: Color = _parameter(material, &"emission", Color.BLACK).srgb_to_linear()
	var emission_energy: float = _parameter(material, &"emission_energy", 1.0)
	var record := PackedByteArray()
	record.resize(MATERIAL_BYTES)
	record.encode_float(0, albedo.r)
	record.encode_float(4, albedo.g)
	record.encode_float(8, albedo.b)
	record.encode_float(12, albedo.a)
	record.encode_float(16, emission.r * emission_energy)
	record.encode_float(20, emission.g * emission_energy)
	record.encode_float(24, emission.b * emission_energy)
	record.encode_float(28, _parameter(material, &"alpha_scissor", 0.5))
	record.encode_u32(32, _texture(material.get_shader_parameter(&"albedo_texture")))
	record.encode_u32(36, _texture(material.get_shader_parameter(&"emission_texture")))
	record.encode_u32(40, flags)

	var index: int = _material_flags.size()
	assert(index < MAX_MATERIALS, "Too many materials for the tracer's material index.")
	materials.append_array(record)
	_material_flags.append(flags)
	_material_indices[material] = index
	return index


func _parameter(material: ShaderMaterial, parameter: StringName, default: Variant) -> Variant:
	var value: Variant = material.get_shader_parameter(parameter)
	return default if typeof(value) == TYPE_NIL else value


func _texture(texture: Texture2D) -> int:
	if !is_instance_valid(texture):
		return WHITE_TEXTURE

	if !_texture_indices.has(texture):
		if textures.size() + 1 == MAX_TEXTURES:
			push_error("The scene has more than %d textures, the tracer's limit." % (MAX_TEXTURES - 1))
			return WHITE_TEXTURE

		textures.append(texture)
		_texture_indices[texture] = textures.size()
	return _texture_indices[texture]
