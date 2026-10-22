#[compute]
#version 450

// Turns each texel's capture sums into means and sorts the texel into one of three kinds. A texel covered by at least
// half a texel of world surface is a probe of its own. A texel with less joins a neighbouring probe of its chart if it
// has one. The rest belong to sub-texel charts and group per instance by world cell and normal class: their keys go
// to a list that the CPU sorts, so that the probes come out in the same order on every load.

#define ATLAS_SET 0
#include "cshd_atlas.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

// The sums come in; the means go out in their place.
layout(set = 1, binding = 0, rgba32f) uniform image2D positions; // w: samples, then their covered share
layout(set = 1, binding = 1, rgba32f) uniform image2D normals; // w: world area
layout(set = 1, binding = 2, rgba32f) uniform image2D albedos; // w: the instance
layout(set = 1, binding = 3, rgba32f) uniform image2D emissions;
layout(set = 1, binding = 4, std430) buffer Counts { uint solid_count; uint key_count; uint outside_count; uint covered_count; };
layout(set = 1, binding = 5, std430) writeonly buffer Solids { uint solids[]; };
layout(set = 1, binding = 6, std430) writeonly buffer Keys { uvec2 keys[]; };

#include "cshd_probes.glslinc"

layout(push_constant, std430) uniform Parameters {
	float texel_size;
	float samples; // per texel
} parameters;

void main() {
	ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(texel, atlas_size))) {
		return;
	}

	vec4 position_sum = imageLoad(positions, texel);
	float count = position_sum.w;
	if (count == 0.0) {
		return;
	}

	atomicAdd(covered_count, 1u);

	// Neighbours read only the area and whether a texel is covered, which the means keep.
	vec4 normal_sum = imageLoad(normals, texel);
	vec3 position = position_sum.xyz / count;
	vec3 normal = normalize(normal_sum.xyz);
	imageStore(positions, texel, vec4(position, count / parameters.samples));
	imageStore(normals, texel, vec4(normal, normal_sum.w));
	vec4 albedo = imageLoad(albedos, texel);
	imageStore(albedos, texel, vec4(albedo.rgb / count, albedo.w));
	imageStore(emissions, texel, imageLoad(emissions, texel) / count);

	float solid_area = PROBE_SOLID_SHARE * parameters.texel_size * parameters.texel_size;
	if (normal_sum.w >= solid_area) {
		solids[atomicAdd(solid_count, 1u)] = atlas_index(texel);
		return;
	}

	if (probe_solid_neighbour(texel, solid_area) != ATLAS_NO_PROBE) {
		return;
	}

	ivec3 cell = probe_cell(position, parameters.texel_size);
	if (!probe_cell_inside(cell)) {
		atomicAdd(outside_count, 1u);
		return;
	}
	keys[atomicAdd(key_count, 1u)] = probe_group_key(uint(albedo.w), cell, normal);
}
