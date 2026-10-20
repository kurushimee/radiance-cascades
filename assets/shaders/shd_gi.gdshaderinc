// The GI material, shared by its shaders: one- or two-sided, and alpha-tested when ALPHA_TESTED is defined. Godot's
// default Lambert diffuse matches the solve's.

const int VIEW_IRRADIANCE = 1;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float alpha_scissor = 0.5;
uniform vec3 emission : source_color = vec3(0.0);
uniform float emission_energy = 1.0;
uniform sampler2D emission_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;

global uniform sampler2D gi_irradiance : hint_default_black, filter_linear;
global uniform int gi_view;

void fragment() {
	vec4 base = albedo * texture(albedo_texture, UV);
	vec3 irradiance = texture(gi_irradiance, UV2).rgb;

#ifdef ALPHA_TESTED
	ALPHA = base.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_scissor;
#endif

	// With no albedo and no specular, the pixel shows only its emission: here, the irradiance.
	if (gi_view == VIEW_IRRADIANCE) {
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		EMISSION = irradiance;
	} else {
		ALBEDO = base.rgb;
		EMISSION = emission * emission_energy * texture(emission_texture, UV).rgb;
		IRRADIANCE = vec4(irradiance, 1.0);
	}
}
