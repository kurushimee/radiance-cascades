#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// Adds one sample point of every texel to the capture's sums: the surface the raster pass found there, its world
// position, normal, albedo and emission, and the world area the sample stands for. An alpha-tested surface counts only
// where its alpha reaches the material's scissor. The passes run one after another, so the sums come out the same on
// every load.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#include "../tracer/cshd_normals.glslinc"
#define ATLAS_SET 1
#include "cshd_atlas.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

layout(set = 2, binding = 0, r32ui) uniform readonly uimage2D triangle_codes;
layout(set = 2, binding = 1, rgba32f) uniform image2D position_sums; // w: samples
layout(set = 2, binding = 2, rgba32f) uniform image2D normal_sums; // w: world area
layout(set = 2, binding = 3, rgba32f) uniform image2D albedo_sums; // w: the instance
layout(set = 2, binding = 4, rgba32f) uniform image2D emission_sums;
layout(set = 2, binding = 5, std430) readonly buffer CornerNormals { uint corner_normals[]; }; // Tracer's

layout(push_constant, std430) uniform Parameters {
	vec2 sample_offset; // the sample point inside its texel, in [0, 1)
	float footprint; // a sample's share of a texel's side
} parameters;

// The interpolated vertex normal, as the path tracer and Godot's lightmapper shade with, or the face's normal where the
// vertex normals turn to its back.
vec3 vertex_normal(uint triangle, vec2 barycentrics) {
	vec3 face = trace_front_normal(triangle);
	vec3 normal = normal_unpack(corner_normals[3u * triangle]) * (1.0 - barycentrics.x - barycentrics.y)
			+ normal_unpack(corner_normals[3u * triangle + 1u]) * barycentrics.x
			+ normal_unpack(corner_normals[3u * triangle + 2u]) * barycentrics.y;
	return dot(normal, face) > 0.0 ? normalize(normal) : face;
}

void main() {
	ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(texel, atlas_size))) {
		return;
	}

	uint code = imageLoad(triangle_codes, texel).x;
	if (code == 0u) {
		return;
	}

	uint triangle = (code & 0x7FFFFFFFu) - 1u;
	bool back = code >= 0x80000000u;
	TraceAttributes attributes = trace_attributes[triangle];
	vec2 corner0 = atlas_point(attributes.instance, attributes.uv2[0], back);
	mat2 from_atlas = inverse(mat2(atlas_point(attributes.instance, attributes.uv2[1], back) - corner0,
			atlas_point(attributes.instance, attributes.uv2[2], back) - corner0));
	vec2 barycentrics = from_atlas * (vec2(texel) + parameters.sample_offset - corner0);

	// The change of world position across one atlas texel.
	vec3 world0 = trace_triangles[3u * triangle].xyz;
	mat2x3 world_edges = mat2x3(trace_triangles[3u * triangle + 1u].xyz - world0,
			trace_triangles[3u * triangle + 2u].xyz - world0);
	mat2x3 world_per_texel = world_edges * from_atlas;

	uint material = attributes.material;
	vec2 uv = trace_interpolate(attributes.uv, barycentrics);
	vec4 albedo = material_albedo(material, uv);
	bool alpha_tested = (materials[material].data.z & MATERIAL_ALPHA_TESTED) != 0u;
	if (alpha_tested && albedo.a < materials[material].emission.w) {
		return;
	}

	vec3 position = world0 + world_edges * barycentrics;
	vec3 normal = vertex_normal(triangle, barycentrics) * (back ? -1.0 : 1.0);
	float area = length(cross(world_per_texel[0], world_per_texel[1])) * parameters.footprint * parameters.footprint;
	imageStore(position_sums, texel, imageLoad(position_sums, texel) + vec4(position, 1.0));
	imageStore(normal_sums, texel, imageLoad(normal_sums, texel) + vec4(normal, area));
	imageStore(albedo_sums, texel, vec4(imageLoad(albedo_sums, texel).rgb + albedo.rgb, float(attributes.instance)));
	imageStore(emission_sums, texel, imageLoad(emission_sums, texel)
			+ vec4(material_emission(material, uv), 0.0));
}
