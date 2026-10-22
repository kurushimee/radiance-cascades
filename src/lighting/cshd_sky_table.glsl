#[compute]
#version 450

// The sky's mean radiance over each bin of the top cascade, from the baked panorama at samples² stratified points per
// bin. The bins are equal-area and the points uniform in the map, so the plain mean weighs the bin's solid angle evenly.

#include "../cascades/cshd_directions.glslinc"

layout(local_size_x = 64) in;

layout(set = 0, binding = 0) uniform sampler2D panorama;
layout(set = 0, binding = 1, std430) writeonly buffer SkyTable { vec4 sky_table[]; };

layout(push_constant, std430) uniform Parameters {
	uint bins_per_side;
	uint samples;
} parameters;

// Godot's panorama puts (−sin φ sin θ, cos θ, −cos φ sin θ) at (φ / 2π, θ / π) of its pixels' corners.
vec3 sky_radiance(vec3 direction) {
	float azimuth = atan(-direction.x, -direction.z);
	vec2 point = vec2(fract(azimuth / 6.28318530718), acos(clamp(direction.y, -1.0, 1.0)) / 3.14159265359);
	return textureLod(panorama, point + 0.5 / vec2(textureSize(panorama, 0)), 0.0).rgb;
}

void main() {
	uint bin = gl_GlobalInvocationID.x;
	uint m = parameters.bins_per_side;
	if (bin >= 2u * m * m) {
		return;
	}

	vec2 corner = vec2(bin / m, bin % m);
	vec3 sum = vec3(0.0);
	for (uint index = 0u; index < parameters.samples * parameters.samples; index++) {
		vec2 offset = (vec2(index % parameters.samples, index / parameters.samples) + 0.5) / float(parameters.samples);
		sum += sky_radiance(directions_world(corner + offset, m));
	}
	sky_table[bin] = vec4(sum / float(parameters.samples * parameters.samples), 0.0);
}
