#[compute]
#version 450

// Sends every texel to the probe whose light it reads. In the first pass a covered texel reads its own probe, its
// neighbour's or its group's; the probes are the sorted texels that are probes of their own, then the sorted groups. In
// the second pass a texel without a sample copies the nearest covered texel within two texels, ties going to the lower
// index, so that bilinear reads at a chart's edge stay within its light.

#define ATLAS_SET 0
#define ATLAS_WRITES_MAP
#include "cshd_atlas.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

layout(set = 1, binding = 0, rgba32f) uniform readonly image2D positions; // w: covered share of the samples
layout(set = 1, binding = 1, rgba32f) uniform readonly image2D normals; // w: world area
layout(set = 1, binding = 2, rgba32f) uniform readonly image2D albedos; // w: the instance
layout(set = 1, binding = 3, std430) readonly buffer Solids { uint solids[]; };
layout(set = 1, binding = 4, std430) readonly buffer Groups { uvec2 group_keys[]; };

#include "cshd_probes.glslinc"

layout(push_constant, std430) uniform Parameters {
	float texel_size;
	uint solid_count;
	uint group_count;
	uint padding; // 1 in the second pass
} parameters;

uint find_solid(uint index) {
	uint low = 0u;
	uint high = parameters.solid_count;
	while (low < high) {
		uint middle = (low + high) / 2u;
		if (solids[middle] < index) {
			low = middle + 1u;
		} else {
			high = middle;
		}
	}
	return low;
}

bool key_less(uvec2 a, uvec2 b) {
	return a.y < b.y || (a.y == b.y && a.x < b.x);
}

uint find_group(uvec2 key) {
	uint low = 0u;
	uint high = parameters.group_count;
	while (low < high) {
		uint middle = (low + high) / 2u;
		if (key_less(group_keys[middle], key)) {
			low = middle + 1u;
		} else {
			high = middle;
		}
	}
	return low;
}

uint covered_probe(ivec2 texel) {
	float solid_area = PROBE_SOLID_SHARE * parameters.texel_size * parameters.texel_size;
	if (imageLoad(normals, texel).w >= solid_area) {
		return find_solid(atlas_index(texel));
	}

	uint neighbour = probe_solid_neighbour(texel, solid_area);
	if (neighbour != ATLAS_NO_PROBE) {
		return find_solid(neighbour);
	}

	vec3 position = imageLoad(positions, texel).xyz;
	ivec3 cell = probe_cell(position, parameters.texel_size);
	if (!probe_cell_inside(cell)) {
		return ATLAS_NO_PROBE;
	}
	uvec2 key = probe_group_key(uint(imageLoad(albedos, texel).w), cell, imageLoad(normals, texel).xyz);
	return parameters.solid_count + find_group(key);
}

uint padding_probe(ivec2 texel) {
	uint nearest = ATLAS_NO_PROBE;
	int nearest_distance = 9;
	for (int y = -2; y <= 2; y++) {
		for (int x = -2; x <= 2; x++) {
			ivec2 neighbour = texel + ivec2(x, y);
			int distance = x * x + y * y;
			if (distance < nearest_distance && probe_in_atlas(neighbour) && probe_covered(neighbour)) {
				nearest = atlas_map[atlas_index(neighbour)];
				nearest_distance = distance;
			}
		}
	}
	return nearest;
}

void main() {
	ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(texel, atlas_size))) {
		return;
	}

	bool covered = probe_covered(texel);
	if (parameters.padding == 0u && covered) {
		atlas_map[atlas_index(texel)] = covered_probe(texel);
	} else if (parameters.padding != 0u && !covered) {
		atlas_map[atlas_index(texel)] = padding_probe(texel);
	}
}
