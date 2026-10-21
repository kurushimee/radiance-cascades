#[compute]
#version 450

// Puts the scene's triangles in world space with their attributes, one thread per triangle, as the acceleration
// structure's vertices. Each triangle is stored so that cross(v1 − v0, v2 − v0) is its front normal: Godot's front faces
// wind clockwise, and a mirroring transform turns that around.

layout(local_size_x = 256) in;

struct Surface {
	vec4 rows[3];
	uvec4 offsets; // first triangle, first vertex, first index, material
	uvec4 instance; // instance index, mirrored, material flags
};

struct Attributes {
	vec2 uv[3];
	vec2 uv2[3];
	uint material;
	uint instance;
};

layout(set = 0, binding = 0, std430) readonly buffer Positions { float positions[]; };
layout(set = 0, binding = 1, std430) readonly buffer Normals { float normals[]; };
layout(set = 0, binding = 2, std430) readonly buffer Uvs { vec2 uvs[]; };
layout(set = 0, binding = 3, std430) readonly buffer Uv2s { vec2 uv2s[]; };
layout(set = 0, binding = 4, std430) readonly buffer Indices { uint indices[]; };
layout(set = 0, binding = 5, std430) readonly buffer Surfaces { Surface surfaces[]; };
layout(set = 0, binding = 6, std430) writeonly buffer Triangles { vec4 triangles[]; };
layout(set = 0, binding = 7, std430) writeonly buffer TriangleAttributes { Attributes attributes[]; };
layout(set = 0, binding = 8, std430) buffer Statistics { uint winding_disagreements; };

layout(push_constant, std430) uniform Parameters {
	uint triangle_count;
	uint surface_count;
} parameters;

uint find_surface(uint triangle) {
	uint low = 0u;
	uint high = parameters.surface_count - 1u;
	while (low < high) {
		uint middle = (low + high + 1u) / 2u;
		if (surfaces[middle].offsets.x <= triangle) {
			low = middle;
		} else {
			high = middle - 1u;
		}
	}
	return low;
}

vec3 local_position(uint vertex) {
	return vec3(positions[3u * vertex], positions[3u * vertex + 1u], positions[3u * vertex + 2u]);
}

vec3 local_normal(uint vertex) {
	return vec3(normals[3u * vertex], normals[3u * vertex + 1u], normals[3u * vertex + 2u]);
}

void main() {
	uint triangle = gl_GlobalInvocationID.x;
	if (triangle >= parameters.triangle_count) {
		return;
	}

	Surface surface = surfaces[find_surface(triangle)];
	uint first_index = surface.offsets.z + 3u * (triangle - surface.offsets.x);
	uvec3 vertex = uvec3(indices[first_index], indices[first_index + 1u], indices[first_index + 2u]);
	vertex += surface.offsets.y;

	// In local space the front faces wind clockwise whatever the transform.
	vec3 corner0 = local_position(vertex.x);
	vec3 local_front = cross(local_position(vertex.z) - corner0, local_position(vertex.y) - corner0);
	vec3 vertex_normals = local_normal(vertex.x) + local_normal(vertex.y) + local_normal(vertex.z);
	if (dot(local_front, vertex_normals) < 0.0) {
		atomicAdd(winding_disagreements, 1u);
	}

	bool mirrored = surface.instance.y != 0u;
	uvec3 order = mirrored ? vertex : vertex.xzy;
	mat3x4 to_world = mat3x4(surface.rows[0], surface.rows[1], surface.rows[2]);
	vec3 world[3];
	Attributes corner_attributes;
	for (uint corner = 0u; corner < 3u; corner++) {
		world[corner] = vec4(local_position(order[corner]), 1.0) * to_world;
		corner_attributes.uv[corner] = uvs[order[corner]];
		corner_attributes.uv2[corner] = uv2s[order[corner]];
	}
	corner_attributes.material = surface.offsets.w;
	corner_attributes.instance = surface.instance.x;
	attributes[triangle] = corner_attributes;

	uint material_word = surface.offsets.w | (surface.instance.z << 24u);
	triangles[3u * triangle] = vec4(world[0], 0.0);
	triangles[3u * triangle + 1u] = vec4(world[1], uintBitsToFloat(material_word));
	triangles[3u * triangle + 2u] = vec4(world[2], 0.0);
}
