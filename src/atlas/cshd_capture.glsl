#[vertex]
#version 450

// Draws every triangle of the tracer's scene into its instance's atlas rectangle at its UV2, shifted so that each pixel
// centre falls on one sample point of its texel. A pixel keeps the triangle that covers its sample point, plus one, with
// the top bit set on the back of a two-sided surface; zero means no triangle.

#define ATLAS_SET 1
#include "cshd_atlas.glslinc"

const uint MATERIAL_TWO_SIDED = 1u; // as in cshd_trace.glslinc

struct TraceAttributes { // as in cshd_trace.glslinc
	vec2 uv[3];
	vec2 uv2[3];
	uint material;
	uint instance;
};

layout(set = 0, binding = 0, std430) readonly buffer TraceTriangles { vec4 trace_triangles[]; };
layout(set = 0, binding = 1, std430) readonly buffer TraceAttributeBuffer { TraceAttributes trace_attributes[]; };

layout(push_constant, std430) uniform Parameters {
	vec2 sample_offset; // the sample point inside its texel, in [0, 1)
	uint back; // 1 draws the backs of the two-sided triangles into the back rectangles
} parameters;

layout(location = 0) flat out uint triangle_code;

void main() {
	uint triangle = uint(gl_VertexIndex) / 3u;
	uint corner = uint(gl_VertexIndex) % 3u;
	bool back = parameters.back != 0u;
	uint material_flags = floatBitsToUint(trace_triangles[3u * triangle + 1u].w) >> 24u;
	if (back && (material_flags & MATERIAL_TWO_SIDED) == 0u) {
		gl_Position = vec4(-2.0, -2.0, 0.0, 1.0); // outside the view, so the triangle draws nothing
		triangle_code = 0u;
		return;
	}

	TraceAttributes attributes = trace_attributes[triangle];
	vec2 point = atlas_point(attributes.instance, attributes.uv2[corner], back) + 0.5 - parameters.sample_offset;
	gl_Position = vec4(point / vec2(atlas_size) * 2.0 - 1.0, 0.0, 1.0);
	triangle_code = (triangle + 1u) | (back ? 0x80000000u : 0u);
}

#[fragment]
#version 450

layout(location = 0) flat in uint triangle_code;
layout(location = 0) out uint pixel_code;

void main() {
	pixel_code = triangle_code;
}
