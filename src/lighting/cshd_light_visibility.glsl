#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// Caches one static light's visibility at every probe: the mean of cos · visibility over the given directions
// across the light's cone, a byte per probe at the light's slot. The slots start cleared.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#include "../tracer/cshd_sampling.glslinc"
#define PROBE_SET 1
#include "../atlas/cshd_probe.glslinc"
#define LIGHT_SET 2
#define LIGHT_WRITES_CACHE
#include "cshd_lights.glslinc"

layout(local_size_x = 64) in;

layout(push_constant, std430) uniform Parameters {
	uint light;
	uint probe_count;
	uint directions;
} parameters;

void main() {
	uint probe = gl_GlobalInvocationID.x;
	if (probe >= parameters.probe_count) {
		return;
	}

	Light light = lights[parameters.light];
	vec3 position = probes[probe].position.xyz;
	vec3 normal = probes[probe].normal.xyz;
	float share = light_visible_cosine(light, light_cone(light, position), position, normal, parameters.directions);
	uint byte_index = light.data.y * parameters.probe_count + probe;
	atomicOr(light_cache[byte_index / 4u], uint(round(share * 255.0)) << (8u * (byte_index % 4u)));
}
