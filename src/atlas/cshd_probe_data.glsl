#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// Writes each probe: a texel of its own copies its capture, and a group turns its fixed-point sums into means. The mean
// of a curved surface lies behind it, inside a column or a prop, where the probe's rays would meet back faces and
// return black. So a probe whose ray along its normal meets the back of a one-sided surface within half a texel moves
// out to it. The probe then sits a twentieth of a texel off the surface.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#define ATLAS_SET 1
#include "cshd_atlas.glslinc"
#define PROBE_SET 2
#define PROBE_WRITES
#include "cshd_probe.glslinc"

layout(local_size_x = 64) in;

layout(set = 3, binding = 0, rgba32f) uniform readonly image2D positions; // w: covered share of the samples
layout(set = 3, binding = 1, rgba32f) uniform readonly image2D normals; // w: world area
layout(set = 3, binding = 2, rgba32f) uniform readonly image2D albedos; // w: the instance
layout(set = 3, binding = 3, rgba32f) uniform readonly image2D emissions;

#include "cshd_probes.glslinc"

layout(set = 3, binding = 4, std430) readonly buffer Solids { uint solids[]; };
layout(set = 3, binding = 5, std430) readonly buffer GroupKeys { uvec2 group_keys[]; };
layout(set = 3, binding = 6, std430) readonly buffer Groups { ProbeGroup groups[]; };
layout(set = 3, binding = 7, std430) buffer Counts { uint moved_count; uint moved_group_count; uint crowded_count; };

layout(push_constant, std430) uniform Parameters {
	float texel_size;
	uint solid_count;
	uint probe_count;
} parameters;

ivec3 key_cell(uvec2 key) {
	return ivec3(key.x & 0x3FFFu, (key.x >> 14u) & 0x3FFFu, (key.x >> 28u) | ((key.y & 0x3FFu) << 4u));
}

Probe solid_probe(uint index) {
	ivec2 texel = ivec2(index % uint(atlas_size.x), index / uint(atlas_size.x));
	vec4 normal = imageLoad(normals, texel);
	vec4 albedo = imageLoad(albedos, texel);
	return Probe(vec4(imageLoad(positions, texel).xyz, normal.w), vec4(normal.xyz, 0.0), albedo,
			vec4(imageLoad(emissions, texel).rgb, 0.0));
}

Probe group_probe(uint group) {
	ProbeGroup sums = groups[group];
	if (sums.members > PROBE_GROUP_MEMBER_LIMIT) {
		atomicAdd(crowded_count, 1u);
	}

	vec3 means[4];
	for (uint value = 0u; value < 4u; value++) {
		for (uint channel = 0u; channel < 3u; channel++) {
			means[value][channel] = float(sums.sums[3u * value + channel]) / (float(sums.weight) * PROBE_GROUP_STEPS);
		}
	}

	uvec2 key = group_keys[group];
	vec3 corner = vec3(key_cell(key) - PROBE_CELL_OFFSET) * parameters.texel_size;
	float area = float(sums.weight) / 256.0 * parameters.texel_size * parameters.texel_size;
	return Probe(vec4(corner + means[0] * parameters.texel_size, area),
			vec4(normalize(means[1] * 2.0 - 1.0), float(PROBE_GROUP)),
			vec4(means[2], float(key.y >> 13u)), vec4(means[3] * uintBitsToFloat(sums.emission_scale), 0.0));
}

void main() {
	uint index = gl_GlobalInvocationID.x;
	if (index >= parameters.probe_count) {
		return;
	}

	Probe probe = index < parameters.solid_count ? solid_probe(solids[index]) : group_probe(index - parameters.solid_count);
	vec3 normal = probe.normal.xyz;
	vec3 origin = trace_offset(probe.position.xyz, normal);
	TraceHit hit = trace(origin, normal, 0.0, 0.5 * parameters.texel_size, 0u);
	if (hit.triangle != TRACE_MISS && hit.back
			&& (materials[trace_attributes[hit.triangle].material].data.z & MATERIAL_TWO_SIDED) == 0u) {
		probe.position.xyz = origin + normal * hit.t;
		probe.normal.w += float(PROBE_MOVED);
		atomicAdd(moved_count, 1u);
		if (index >= parameters.solid_count) {
			atomicAdd(moved_group_count, 1u);
		}
	}
	probe.position.xyz += normal * parameters.texel_size / 20.0;
	probes[index] = probe;
}
