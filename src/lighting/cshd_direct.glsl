#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// Each frame's direct light at every probe, E/π, scaled by each light's indirect energy since it feeds the bounces. A
// static light reads its cached visibility; any other light traces one shadow ray toward its centre, or, for a
// measurement of what that ray misses, many rays across its cone.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#include "../tracer/cshd_sampling.glslinc"
#define PROBE_SET 1
#define PROBE_WRITES_DIRECT
#include "../atlas/cshd_probe.glslinc"
#define LIGHT_SET 2
#include "cshd_lights.glslinc"

layout(local_size_x = 64) in;

layout(push_constant, std430) uniform Parameters {
	uint probe_count;
	uint directions; // 0: the one ray toward the centre
} parameters;

float visible_cosine(Light light, LightCone cone, uint probe, vec3 position, vec3 normal) {
	if (light.data.y != LIGHT_NO_SLOT) {
		uint byte_index = light.data.y * parameters.probe_count + probe;
		return float((light_cache[byte_index / 4u] >> (8u * (byte_index % 4u))) & 0xFFu) / 255.0;
	}

	if (parameters.directions > 0u) {
		return light_visible_cosine(light, cone, position, normal, parameters.directions);
	}

	float cosine = dot(normal, cone.axis);
	return cosine > 0.0 && light_visible(light, cone, position, cone.axis) ? cosine : 0.0;
}

void main() {
	uint probe = gl_GlobalInvocationID.x;
	if (probe >= parameters.probe_count) {
		return;
	}

	vec3 position = probes[probe].position.xyz;
	vec3 normal = probes[probe].normal.xyz;
	vec3 direct = vec3(0.0);
	for (uint index = 0u; index < light_count; index++) {
		Light light = lights[index];
		LightCone cone = light_cone(light, position);
		direct += light.emission.rgb * light.emission.w * light_attenuation(light, cone)
				* visible_cosine(light, cone, probe, position, normal);
	}
	probe_direct[probe] = vec4(direct, 0.0);
}
