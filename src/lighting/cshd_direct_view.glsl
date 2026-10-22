#[compute]
#version 460
#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

// The direct light, E/π, at each pixel's primary hit, as the engine's direct irradiance view computes it: a white
// Lambertian surface with the raster's normal, every light's cone sampled by many directions, and no
// indirect energy. Alpha 0 marks a pixel without a surface, or one whose traced hit lies elsewhere along the pixel's ray
// than the raster's, as where alpha-tested leaves overlap.

#define TRACE_SET 0
#include "../tracer/cshd_trace.glslinc"
#include "../tracer/cshd_sampling.glslinc"
#include "../tracer/cshd_camera.glslinc"
#define LIGHT_SET 1
#include "cshd_lights.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

// The relative difference in distance that a float's rounding along the ray explains.
const float MATCH_TOLERANCE = 1.0 / 4096.0;

layout(set = 2, binding = 0, rgba32f) uniform readonly image2D distances;
layout(set = 2, binding = 1, rgba32f) uniform readonly image2D normals;
layout(set = 2, binding = 2, rgba32f) uniform writeonly image2D view;

layout(push_constant, std430) uniform Parameters {
	vec4 camera_origin;
	vec4 camera_right;
	vec4 camera_up;
	vec4 camera_forward;
	uvec2 size;
	uint directions;
} parameters;

vec3 hit_position(TraceHit hit) {
	vec3 corner = trace_triangles[3u * hit.triangle].xyz;
	return corner + (trace_triangles[3u * hit.triangle + 1u].xyz - corner) * hit.barycentrics.x
			+ (trace_triangles[3u * hit.triangle + 2u].xyz - corner) * hit.barycentrics.y;
}

void main() {
	ivec2 pixel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(uvec2(pixel), parameters.size))) {
		return;
	}

	vec4 raster_distance = imageLoad(distances, pixel);
	vec4 raster_normal = imageLoad(normals, pixel);
	vec3 direction = camera_direction(parameters.camera_right.xyz, parameters.camera_up.xyz,
			parameters.camera_forward.xyz, uvec2(pixel), parameters.size);
	TraceHit hit = trace(parameters.camera_origin.xyz, direction, 0.0, TRACE_FAR, TRACE_CULL);
	if (raster_distance.a == 0.0 || hit.triangle == TRACE_MISS) {
		imageStore(view, pixel, vec4(0.0));
		return;
	}

	if (abs(hit.t - raster_distance.r - raster_distance.g) > hit.t * MATCH_TOLERANCE) {
		imageStore(view, pixel, vec4(0.0));
		return;
	}

	vec3 position = hit_position(hit);

	vec3 normal = normalize(raster_normal.xyz);
	vec3 origin = trace_offset(position, normal);
	vec3 direct = vec3(0.0);
	for (uint index = 0u; index < light_count; index++) {
		Light light = lights[index];
		LightCone cone = light_cone(light, origin);
		direct += light.emission.rgb * light_attenuation(light, cone)
				* light_visible_cosine(light, cone, origin, normal, parameters.directions);
	}
	imageStore(view, pixel, vec4(direct, 1.0));
}
