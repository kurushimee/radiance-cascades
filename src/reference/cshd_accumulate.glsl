#[compute]
#version 450

// Adds a frame to two running means of its pixels, one over every frame added and one over the even frames, one thread
// per pixel.

layout(local_size_x = 256) in;

layout(set = 0, binding = 0) uniform sampler2D frame;
layout(set = 0, binding = 1, std430) restrict buffer AllFrames { vec4 all_mean[]; };
layout(set = 0, binding = 2, std430) restrict buffer EvenFrames { vec4 even_mean[]; };

layout(push_constant, std430) uniform Parameters {
	uvec2 size;
	uint frame_index; // counted from 0 over the frames added
} parameters;

void main() {
	uint pixel = gl_GlobalInvocationID.x;
	if (pixel >= parameters.size.x * parameters.size.y) {
		return;
	}

	vec4 value = texelFetch(frame, ivec2(pixel % parameters.size.x, pixel / parameters.size.x), 0);
	all_mean[pixel] += (value - all_mean[pixel]) / float(parameters.frame_index + 1u);
	if (parameters.frame_index % 2u == 0u) {
		even_mean[pixel] += (value - even_mean[pixel]) / float(parameters.frame_index / 2u + 1u);
	}
}
