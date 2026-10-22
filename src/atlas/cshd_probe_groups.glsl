#[compute]
#version 450

// Sums each group's texels in fixed point, weighted by the world area each covers, so that the sums are the same
// whatever order the atomics run in. The first pass finds each group's brightest emission, which scales its emission
// in the second.

#define ATLAS_SET 0
#include "cshd_atlas.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

layout(set = 1, binding = 0, rgba32f) uniform readonly image2D positions; // w: covered share of the samples
layout(set = 1, binding = 1, rgba32f) uniform readonly image2D normals; // w: world area
layout(set = 1, binding = 2, rgba32f) uniform readonly image2D albedos;
layout(set = 1, binding = 3, rgba32f) uniform readonly image2D emissions;

#include "cshd_probes.glslinc"

layout(set = 1, binding = 4, std430) buffer Groups { ProbeGroup groups[]; };

layout(push_constant, std430) uniform Parameters {
	float texel_size;
	uint solid_count;
	uint sums; // 1 in the second pass
} parameters;

uint quantized(float value) {
	return uint(round(clamp(value, 0.0, 1.0) * PROBE_GROUP_STEPS));
}

void main() {
	ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(texel, atlas_size)) || !probe_covered(texel)) {
		return;
	}

	uint probe = atlas_map[atlas_index(texel)];
	if (probe == ATLAS_NO_PROBE || probe < parameters.solid_count) {
		return;
	}

	uint group = probe - parameters.solid_count;
	vec3 emission = imageLoad(emissions, texel).rgb;
	if (parameters.sums == 0u) {
		atomicAdd(groups[group].members, 1u);
		atomicMax(groups[group].emission_scale, floatBitsToUint(max(max(emission.r, emission.g), emission.b)));
		return;
	}

	vec4 normal = imageLoad(normals, texel);
	uint weight = probe_group_weight(normal.w, parameters.texel_size);
	vec3 position = imageLoad(positions, texel).xyz;
	vec3 offset = position / parameters.texel_size - vec3(probe_cell(position, parameters.texel_size) - PROBE_CELL_OFFSET);
	float emission_scale = uintBitsToFloat(groups[group].emission_scale);
	vec3 values[4] = vec3[4](offset, normal.xyz * 0.5 + 0.5, imageLoad(albedos, texel).rgb,
			emission_scale > 0.0 ? emission / emission_scale : vec3(0.0));
	atomicAdd(groups[group].weight, weight);
	for (uint value = 0u; value < 4u; value++) {
		for (uint channel = 0u; channel < 3u; channel++) {
			atomicAdd(groups[group].sums[3u * value + channel], weight * quantized(values[value][channel]));
		}
	}
}
