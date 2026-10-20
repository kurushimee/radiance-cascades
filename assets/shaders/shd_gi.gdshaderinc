// The GI material, shared by its one- and two-sided shaders. Godot's default Lambert diffuse matches the solve's.

const int VIEW_IRRADIANCE = 1;

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 emission : source_color = vec3(0.0);
uniform float emission_energy = 1.0;
uniform sampler2D emission_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// A fixture's emission stays out of the solve, because its Godot light already carries that light.
uniform bool fixture = false;

global uniform sampler2D gi_irradiance : hint_default_black, filter_linear;
global uniform int gi_view;

void fragment() {
	vec3 irradiance = texture(gi_irradiance, UV2).rgb;

	// With no albedo and no specular, the pixel shows only its emission: here, the irradiance.
	if (gi_view == VIEW_IRRADIANCE) {
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		EMISSION = irradiance;
	} else {
		ALBEDO = albedo.rgb * texture(albedo_texture, UV).rgb;
		EMISSION = emission * emission_energy * texture(emission_texture, UV).rgb;
		IRRADIANCE = vec4(irradiance, 1.0);
	}
}
