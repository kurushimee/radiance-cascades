// The GI material, shared by its shaders: one- or two-sided, and alpha-tested when ALPHA_TESTED is defined. Godot's
// default Lambert diffuse matches the solve's. Occlusion maps stay out: the GI and the path tracer trace occlusion.
// For the same reason the indirect specular reflects the GI's E/π in place of the open sky, and Godot's specular
// occlusion, a guess from the irradiance's luminance in absolute units, stays off.
render_mode specular_occlusion_disabled;

const int VIEW_IRRADIANCE = 1;
const int VIEW_NO_INDIRECT = 2;
const int VIEW_UNIT_INDIRECT = 3;
const int VIEW_REFERENCE = 4;
const int VIEW_POSITION = 5;
const int VIEW_NORMAL = 6;
const int VIEW_DISTANCE = 7;
const int VIEW_NORMAL_REMAINDER = 8;

// Not named "albedo": NVIDIA's path tracer takes a material with a colour parameter of that name for a
// StandardMaterial3D and skips this shader.
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float alpha_scissor = 0.5;
uniform float roughness = 1.0;
// Each texture's channel is picked by a mask, as StandardMaterial3D's channel settings do.
uniform sampler2D roughness_texture : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 roughness_channel = vec4(1.0, 0.0, 0.0, 0.0);
uniform float metallic = 0.0;
uniform sampler2D metallic_texture : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 metallic_channel = vec4(1.0, 0.0, 0.0, 0.0);
uniform float specular = 0.5;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float normal_scale = 1.0;
// DirectX normal maps point their green channel down.
uniform bool normal_green_down = false;
uniform vec3 emission : source_color = vec3(0.0);
uniform float emission_energy = 1.0;
uniform sampler2D emission_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;

global uniform sampler2D gi_irradiance : hint_default_black, filter_linear;
global uniform int gi_view;

// The value with its float's top 10 mantissa bits, which a half float keeps exactly.
vec3 half_part(vec3 value) {
	return uintBitsToFloat(floatBitsToUint(value) & uvec3(0xFFFFE000u));
}

void fragment() {
	vec4 base = albedo_color * texture(albedo_texture, UV);
	vec3 irradiance = texture(gi_irradiance, gi_view == VIEW_REFERENCE ? SCREEN_UV : UV2).rgb;
	if (gi_view == VIEW_NO_INDIRECT || gi_view == VIEW_UNIT_INDIRECT) {
		irradiance = vec3(gi_view == VIEW_UNIT_INDIRECT ? 1.0 : 0.0);
	}

#ifdef ALPHA_TESTED
	ALPHA = base.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_scissor;
#endif

	// With no albedo and no specular, the pixel shows only its emission: here, the irradiance, the world position, the
	// world normal, which Godot turns toward the camera on a two-sided surface's back, or the distance from the camera.
	// The half-float frame keeps the distance and the normal to a float's precision as their half-float parts and the
	// remainders, the normal's remainders in a view of their own.
	if (gi_view == VIEW_IRRADIANCE || gi_view == VIEW_POSITION || gi_view == VIEW_NORMAL
			|| gi_view == VIEW_NORMAL_REMAINDER || gi_view == VIEW_DISTANCE) {
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		EMISSION = irradiance;
		if (gi_view == VIEW_POSITION) {
			EMISSION = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
		} else if (gi_view == VIEW_NORMAL || gi_view == VIEW_NORMAL_REMAINDER) {
			vec3 normal = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
			EMISSION = gi_view == VIEW_NORMAL ? half_part(normal) : normal - half_part(normal);
		} else if (gi_view == VIEW_DISTANCE) {
			float distance = length(VERTEX);
			float half_distance = half_part(vec3(distance)).x;
			EMISSION = vec3(half_distance, distance - half_distance, 0.0);
		}
	} else {
		vec3 normal_map = texture(normal_texture, UV).rgb;
		if (normal_green_down) {
			normal_map.g = 1.0 - normal_map.g;
		}

		ALBEDO = base.rgb;
		ROUGHNESS = roughness * dot(texture(roughness_texture, UV), roughness_channel);
		METALLIC = metallic * dot(texture(metallic_texture, UV), metallic_channel);
		SPECULAR = specular;
		NORMAL_MAP = normal_map;
		NORMAL_MAP_DEPTH = normal_scale;
		EMISSION = emission * emission_energy * texture(emission_texture, UV).rgb;
		IRRADIANCE = vec4(irradiance, 1.0);
		RADIANCE = vec4(irradiance, 1.0);
	}
}
