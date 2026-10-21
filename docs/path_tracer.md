# NVIDIA's path tracer

Read in NVIDIA-RTX/godot at `135dff3887` (branch `nvidia-pt-dlss`) with this project's engine patch ([README](../README.md#engine)); paths are relative to that repository.

## Settings

The path tracer is set on the Environment the camera renders with, so a camera's own environment takes the WorldEnvironment's place:

- `pathtracing_enabled`, `pathtracing_samples_per_pixel` and `pathtracing_max_bounces`, which the patch lets reach 255.
- `pathtracing_denoiser`: `RenderingServer.PT_DENOISER_NONE` or `PT_DENOISER_DLSS_RAY_RECONSTRUCTION`.
- `pathtracing_debug_mode`, an `Environment.PathtracingDebugMode`. It is a float parameter of the pipeline, not a specialization constant, so changing it compiles nothing.

Two project settings keep it working on this project:

- `rendering/pathtracing/async_shader_compilation=false`. A ShaderMaterial compiles into a hit group of its own, by default in the background, and until it is ready its instances render with the standard hit group or not at all.
- `rendering/pathtracing/use_shader_execution_reordering=false`. Reordering is on by default with no check that the GPU supports it, and Turing does not (NVIDIA-RTX/godot issue #12).

## Frames

Each frame overwrites the output, since the fork keeps no accumulation of its own. The raw frame's alpha is 1 everywhere (`scene_raytracing_raygen.glsl`).

Primary rays leave each pixel's centre, through the camera's projection. With DLSS scaling Godot jitters that projection, and without it a raw frame samples the same points as a raster frame without anti-aliasing.

`init_rng` seeds each path from the pixel, the frame index and the sample (`raytracing_inc.glsl`), and the frame index advances every frame. The fork's seed, `pcg_hash(pixel.x + 65536·pixel.y + 10⁶·frame + 10⁸·sample)`, is linear before the hash: frame `f + 27` at pixel `(x, y)` has the seed of frame `f` at `(x − 832, y + 412)`, so the means of two such pixels over many frames are correlated. The patch hashes the frame and sample first, `pcg_hash((pixel.x + 65536·pixel.y) ^ pcg_hash(256·frame + sample))`.

Bounce and shadow rays start at a Wächter–Binder offset from the surface along its normal (`offset_ray_origin` in `raytracing_inc.glsl`), and the fork also skips any hit closer than 1 mm. A ray that leaves a surface within a millimetre of a corner then passes through the surface on the corner's other side. Where single-plane walls meet, light from outside reaches the inside along every seam, as thin bright lines in both views. The patch starts these rays at a distance of 0, which the offset alone makes safe.

The viewport's frame is half float, and storing to it rounds toward zero: a radiance of 18.387 reads back as 18.375. A mean over many frames therefore sits about 0.034% low. The raster frames the GI is compared on pass through the same format.

## DLSS Ray Reconstruction

Ray Reconstruction runs only with `Viewport.scaling_3d_mode = SCALING_3D_MODE_DLSS`, and at `scaling_3d_scale = 1.0` it denoises at full resolution (DLAA). `rendering/streamline/dlss_ray_reconstruction_preset` picks the model.

The fork never resets its history: `reset_accumulation` is always false (`render_forward_clustered.cpp`, with a FIXME). After a camera cut or a change of view, the output carries the earlier frames until the history settles. Turning path tracing off for a frame does not reset it either.

Godot deletes a viewport's DLSS context when it reconfigures the viewport's render buffers, as on a change of `scaling_3d_mode`, and hands its Streamline viewport handle to the next context (`dlss.cpp`). The fork never frees the Ray Reconstruction instance on that handle, so the next context inherits it in a stale state that a history reset does not clear. In the unlit leak house, a frame denoised after the viewport left DLSS and came back carried a soft dark patch on the ground, 15% below the raw path tracer's mean, which grew from the eighth frame and remained at the 64th. The patch frees a handle's instances before the handle is reused, once the GPU is done with the frames that used them, so a new context starts with a new instance and no history.

- From a start the output settles within 64 frames, and after a change of debug view within 128.
- More frames do not sharpen it once it settles; more samples per pixel per frame do. In the Cornell box's irradiance view, one sample smears colour bleeding and indirect shadows, 16 keep them, and 255 match the converged image. A frame of 255 samples takes about 0.45 s on the Cornell box and 5 to 10 s on Crytek Sponza, on an RTX 2070.
- Without the camera jitter the irradiance view degrades with every frame.

## Materials

- A material with a colour parameter named `albedo` is taken for a StandardMaterial3D and shaded by the standard hit group, which skips the shader's own code (`render_raytracing.cpp`).
- The standard hit group adds emission only when the material has an emission texture.
- In a ShaderMaterial's hit group, Godot's built-ins are renamed: `IRRADIANCE` becomes `custom_irradiance`, which no path tracer shader reads. The patch declares it and `custom_radiance`, so shaders that write them compile.
- The BRDF is Lambertian diffuse with a GGX specular lobe (`brdf_inc.glsl`). The two are combined with Fresnel, so the diffuse is weighted by `1 − F`, and `SPECULAR` sets the dielectric F0: 0.04 at Godot's default of 0.5.
- Nothing transmits: `transmissivness` is hard-coded to 0. StandardMaterial3D's alpha scissor is a fixed 0.5.
- A global sampler parameter without a texture binds the first bindless texture, not its hint's default as in the raster (`render_raytracing.cpp`).

Single-scattering GGX loses energy at high roughness, so a rough dielectric reflects less than its albedo. In the Cornell box at roughness 1 and specular 0.5, the irradiance over π is 3.7% lower than with Lambertian surfaces of the same albedo: 5.4% in red, 2.3% in green and 1.1% in blue, growing with the albedo. At specular 0 it matches a Lambertian path tracer to 0.04%.

Roughness has no floor, and the sun is sampled without MIS, so a metal whose roughness map reaches 0 reflects the sun into rare samples millions of times the mean. In Crytek Sponza's Atrium they hold 98% of the variance of a mean over raw frames. Ray Reconstruction at 16 samples shows none of them.

## Lights

- Directional and omni lights are sampled as cones, up to 64 of them, with no multiple importance sampling. Every ray that misses samples the sky's radiance, so a sun disk drawn in the sky adds the sun's light a second time. `DirectionalLight3D.sky_mode = SKY_MODE_LIGHT_ONLY` keeps it out of the sky.
- The sky's radiance comes from the top level of the radiance map that Godot prefilters for reflections, also for camera rays (`scene_raytracing_raygen.glsl`). That map is `Sky.radiance_size` on a side, 256 by default, so a panorama's detail shows only as far as its size allows: at 256, the buildings in Bistro's 4K panorama blurred into smears behind the plaza.
- Emissive meshes are not sampled as lights. They add light only when a path hits them, so a scene lit by an emissive panel converges slowly without denoising.
- Omni lights use Godot's window, `(1 − (d/r)⁴)²` times `d^−attenuation`. The fork caps the `d^−attenuation` factor at 1, which the patch removes, so a light closer than a metre is as bright as the raster's.
- Non-physical light energy is multiplied by π, as in Godot's raster. Without camera attributes, `emissive_exposure_normalization` is 1.
- A light's `light_specular` scales its sampled specular lobe, as it scales the raster's highlights: Godot's default of 0.5 halves it. Its `light_indirect_energy` scales it for every path past its first diffuse bounce, so in the irradiance view it scales all of a light's sampled contribution (`raytracing_lights_inc.glsl`).

## The engine patch

- **Irradiance view**, `Environment.RT_DEBUG_INDIRECT_IRRADIANCE`. At the primary hit the surface is white and diffuse, adds no emission, samples no lights and sends one cosine-distributed ray; the rest of the path is unchanged. The radiance then estimates the irradiance over π arriving there, the quantity the GI hands Godot. Ray Reconstruction's guides are a white diffuse albedo with the geometry normal.
- **Bounces.** The cap is a pipeline parameter of up to 255 instead of a 3-bit specialization constant of up to 8, and the separate limit of two diffuse bounces is gone. From the fourth bounce on, Russian roulette ends a path with a probability of one less its largest throughput channel, capped at 0.95 survival, and divides the survivors' throughput by their survival.
- **Camera-only instances.** An instance with `cast_shadow = SHADOW_CASTING_SETTING_OFF` gets an instance mask that only primary rays include. A lamp's fixture then neither shadows its own light nor adds its emission to the light's, as in the raster, where an instance that casts no shadow stays out of every shadow map.
- **Omni attenuation** without the cap at 1.
- **Seed.** The frame and sample are hashed before they meet the pixel ([Frames](#frames)).
- **Minimum ray distance** of 0 for bounce and shadow rays ([Frames](#frames)).
- **Streamline viewport handles** freed before reuse ([DLSS Ray Reconstruction](#dlss-ray-reconstruction)).
- **`Environment.pathtracing_max_bounces`** reaches 255; the fork clamps it to 8.
