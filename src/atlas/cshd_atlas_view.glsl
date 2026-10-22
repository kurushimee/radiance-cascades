#[compute]
#version 450

// Shows the atlas as the GI reads it: every texel takes a value of the probe its map sends it to, with alpha 0 where
// the map sends it nowhere.

#define ATLAS_SET 0
#include "cshd_atlas.glslinc"
#define PROBE_SET 1
#include "cshd_probe.glslinc"
#include "cshd_probe_view.glslinc"

layout(local_size_x = 8, local_size_y = 8) in;

layout(set = 2, binding = 0, rgba32f) uniform writeonly image2D view;

layout(push_constant, std430) uniform Parameters {
	uint mode;
} parameters;

void main() {
	ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(texel, atlas_size))) {
		return;
	}

	uint index = atlas_map[atlas_index(texel)];
	imageStore(view, texel, index == ATLAS_NO_PROBE ? vec4(0.0) : vec4(view_value(index, parameters.mode), 1.0));
}
