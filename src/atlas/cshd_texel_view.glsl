#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// Shows the probes as a camera sees them: each pixel's primary ray finds a surface, and the pixel takes a value of the
// probe that surface's texel reads, with alpha 0 where the ray finds no surface or no probe.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#include "../tracer/cshd_camera.glslinc"
#define ATLAS_SET 1
#include "cshd_atlas.glslinc"
#define PROBE_SET 2
#include "cshd_probe.glslinc"
#include "cshd_probe_view.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

layout(set = 3, binding = 0, rgba32f) uniform writeonly image2D view;

layout(push_constant, std430) uniform Parameters {
	vec4 camera_origin;
	vec4 camera_right;
	vec4 camera_up;
	vec4 camera_forward;
	uvec2 size;
	uint mode;
} parameters;

void main() {
	uvec2 pixel = gl_GlobalInvocationID.xy;
	if (any(greaterThanEqual(pixel, parameters.size))) {
		return;
	}

	vec3 direction = camera_direction(parameters.camera_right.xyz, parameters.camera_up.xyz,
			parameters.camera_forward.xyz, pixel, parameters.size);
	TraceHit hit = trace(parameters.camera_origin.xyz, direction, 0.0, TRACE_FAR, TRACE_CULL);
	uint index = hit.triangle == TRACE_MISS ? ATLAS_NO_PROBE : atlas_hit_probe(hit);
	imageStore(view, ivec2(pixel),
			index == ATLAS_NO_PROBE ? vec4(0.0) : vec4(view_value(index, parameters.mode), 1.0));
}
