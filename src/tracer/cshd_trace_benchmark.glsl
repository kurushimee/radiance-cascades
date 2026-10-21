#[compute]
#version 460

// The tracer's benchmark and check, one thread per pixel. Primary rays find the surfaces the camera sees; from them,
// segments over one cascade interval in cosine-distributed directions, or shadow rays toward the sun. With a check
// stride, a sparse subset of the same rays is traced against brute force over every triangle instead, and the
// disagreements are counted.

#extension GL_EXT_ray_query : require
#extension GL_KHR_shader_subgroup_ballot : require

#define TRACE_SET 1

layout(local_size_x = 64) in;

#include "res://src/tracer/cshd_trace.glslinc"
#include "res://src/tracer/cshd_camera.glslinc"
#include "res://src/tracer/cshd_sampling.glslinc"

layout(set = 0, binding = 0, std430) buffer Origins { vec4 origins[]; }; // w: 1 where the primary ray hit
layout(set = 0, binding = 1, std430) buffer Normals { vec4 normals[]; };
layout(set = 0, binding = 2, std430) writeonly buffer Results { uint results[]; };
layout(set = 0, binding = 3, std430) buffer Counters {
	uint primary_hits;
	uint closest_mismatches;
	uint any_mismatches;
	uint checked_rays;
};

layout(push_constant, std430) uniform Parameters {
	vec4 camera_origin;
	vec4 camera_right;
	vec4 camera_up;
	vec4 camera_forward;
	vec4 sun; // toward the sun
	vec2 segment; // t_min, t_max
	uvec2 size;
	uint mode;
	uint check_stride; // 0 for the benchmark
	uint seed;
	uint triangle_count;
} parameters;

const uint MODE_PRIMARY = 0u;
const uint MODE_SEGMENT = 1u;
const uint MODE_SHADOW = 2u;

struct Ray {
	vec3 origin;
	vec3 direction;
	float t_min;
	float t_max;
	uint flags;
};

vec2 random2(uint pixel) {
	uint first = hash(pixel ^ hash(parameters.seed));
	return vec2(first >> 8u, hash(first) >> 8u) / 16777216.0;
}

bool make_ray(uint pixel, out Ray ray) {
	if (parameters.mode == MODE_PRIMARY) {
		uvec2 coordinates = uvec2(pixel % parameters.size.x, pixel / parameters.size.x);
		vec3 direction = camera_direction(parameters.camera_right.xyz, parameters.camera_up.xyz,
				parameters.camera_forward.xyz, coordinates, parameters.size);
		ray = Ray(parameters.camera_origin.xyz, direction, 0.0, TRACE_FAR, TRACE_CULL);
		return true;
	}

	vec4 origin = origins[pixel];
	vec3 normal = normals[pixel].xyz;
	vec3 direction = parameters.mode == MODE_SHADOW ? parameters.sun.xyz : cosine_direction(normal, random2(pixel));
	ray = Ray(origin.xyz, direction, parameters.segment.x, parameters.segment.y,
			parameters.mode == MODE_SHADOW ? TRACE_ANY : 0u);
	return origin.w != 0.0;
}

// Möller and Trumbore (1997): updates `hit` if the ray meets the triangle nearer, past its culling and alpha test.
bool test_triangle(uint triangle, Ray ray, inout TraceHit hit) {
	vec3 corner = trace_triangles[3u * triangle].xyz;
	vec4 second = trace_triangles[3u * triangle + 1u];
	vec3 edge1 = second.xyz - corner;
	vec3 edge2 = trace_triangles[3u * triangle + 2u].xyz - corner;
	vec3 h = cross(ray.direction, edge2);
	float determinant = dot(edge1, h);
	float f = 1.0 / determinant;
	vec3 s = ray.origin - corner;
	float u = f * dot(s, h);
	vec3 q = cross(s, edge1);
	float v = f * dot(ray.direction, q);
	float t = f * dot(edge2, q);
	if (!(u >= 0.0 && v >= 0.0 && u + v <= 1.0 && t > ray.t_min && t < hit.t)) {
		return false;
	}

	uint material_word = floatBitsToUint(second.w);
	uint material_flags = material_word >> 24u;
	bool back = determinant < 0.0;
	if (back && (ray.flags & TRACE_CULL) != 0u && (material_flags & MATERIAL_TWO_SIDED) == 0u) {
		return false;
	}
	if ((material_flags & MATERIAL_ALPHA_TESTED) != 0u && !trace_opaque(triangle, material_word & 0xFFFFFFu, vec2(u, v))) {
		return false;
	}

	hit = TraceHit(t, vec2(u, v), triangle, back);
	return true;
}

TraceHit brute_force(Ray ray) {
	TraceHit hit = TraceHit(ray.t_max, vec2(0.0), TRACE_MISS, false);
	for (uint triangle = 0u; triangle < parameters.triangle_count; triangle++) {
		if (test_triangle(triangle, ray, hit) && (ray.flags & TRACE_ANY) != 0u) {
			break;
		}
	}
	return hit;
}

void check(Ray ray) {
	TraceHit expected = brute_force(ray);
	TraceHit found = trace(ray.origin, ray.direction, ray.t_min, ray.t_max, ray.flags);
	atomicAdd(checked_rays, 1u);
	bool expected_hit = expected.triangle != TRACE_MISS;
	bool found_hit = found.triangle != TRACE_MISS;
	if ((ray.flags & TRACE_ANY) != 0u) {
		if (expected_hit != found_hit) {
			atomicAdd(any_mismatches, 1u);
		}
		return;
	}

	// Triangles that share an edge or overlap may both claim the same distance.
	bool same_hit = expected.triangle == found.triangle ? expected.back == found.back
			: abs(expected.t - found.t) <= 1e-5 * max(expected.t, 1.0);
	if (expected_hit != found_hit || (expected_hit && !same_hit)) {
		atomicAdd(closest_mismatches, 1u);
	}
}

void main() {
	uint pixel = gl_GlobalInvocationID.x * max(parameters.check_stride, 1u);
	Ray ray;
	if (pixel >= parameters.size.x * parameters.size.y || !make_ray(pixel, ray)) {
		return;
	}

	if (parameters.check_stride != 0u) {
		check(ray);
		return;
	}

	TraceHit hit = trace(ray.origin, ray.direction, ray.t_min, ray.t_max, ray.flags);
	results[pixel] = hit.triangle;
	if (parameters.mode != MODE_PRIMARY) {
		return;
	}

	bool surface = hit.triangle != TRACE_MISS;
	vec3 normal = surface ? trace_front_normal(hit.triangle) : vec3(0.0, 1.0, 0.0);
	normal = hit.back ? -normal : normal;
	vec3 position = ray.origin + ray.direction * hit.t;
	origins[pixel] = vec4(trace_offset(position, normal), surface ? 1.0 : 0.0);
	normals[pixel] = vec4(normal, 0.0);
	if (surface) {
		atomicAdd(primary_hits, 1u);
	}
}
