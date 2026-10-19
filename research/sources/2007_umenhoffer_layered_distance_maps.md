# Robust Multiple Specular Reflections and Refractions (GPU Gems 3, ch. 17)

| | |
|---|---|
| Authors | Umenhoffer, Patow, Szirmay-Kalos |
| Date | GPU Gems 3, 2007 |
| Kind | Book chapter |
| Link | https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-17-robust-multiple-specular-reflections-and-refractions |

The chapter ray-traces reflections and refractions against cube maps that store distance from a reference point, searching each ray in the map's texture space. RC discussions link it as "distance impostors for a spherical radiance field" ([sparse 3D RC](2026_sparse_and_3d_rc.md)); the chapter itself says layered distance maps, and the phrase "distance impostors" appears only in its reference to Szirmay-Kalos et al. 2005. Section numbers are the chapter's.

## Representation (sec. 17.2)

- Each layer is a cube map rendered from a reference point. A texel holds the material (reflected radiance for diffuse surfaces, or the Fresnel factor at normal incidence for specular ones), a refractive index whose sign gives the type (negative reflector, zero diffuse, positive refractor), the normal, and the distance from the reference point.
- Layers come from depth peeling with a capped count, far objects collapsing into one layer. A single reflective object puts its front and back faces in two layers, with empty texels cleared to a negative distance. Per-map minimum and maximum distances bound the search ("Acceleration with Min-Max Distance Values").

## Tracing (sec. 17.2.2)

- For the ray `x + R·d`, the point `l` is compared with the stored distance `|l'|` in its direction: `|l|/|l'| < 1` is in front of the surface and `> 1` behind it.
- The linear search is uniform on the segment between the projections of the start and the direction onto the unit sphere, `r'(t) = s·(1 − t) + e·t` with `s = x/|x|` and `e = R/|R|`, so steps are even in texels; the ray parameter is `d = a·t/(1 − t)` with `a = |x|/|R|` (Listing 17-1). The step `dt` scales with the segment length and the map resolution, and a step longer than a texel can miss thin objects. Every layer is searched, and the one with the smallest overshoot holds the first hit.
- Secant refinement (Listing 17-2): `d_new = d_l + (d_p − d_l)·(1 − llp)/(ppp − llp)` from the last undershoot and overshoot and their ratios, exact for planes. Fig. 17-6 compares linear/secant step limits of 15/1, 15/10, 80/1 and 80/10.

## Shading and results (sec. 17.3-17.5)

- Schlick Fresnel `F = F_p + (1 − F_p)·(1 − N·R)^5`, with `F_p` from the refractive index and extinction coefficient computed on the CPU. A loop up to `MAXDEPTH` reflects or refracts by the sign of the index, falls back to reflection on total internal reflection, multiplies by the Fresnel factor at each specular hit and by the diffuse radiance at the end (Listing 17-5).
- DirectX 9 HLSL on a GeForce 8800 GTX at 800×600, with 6 × 512² cube maps rebuilt every frame and three layers (two for the reflective object, one for diffuse surfaces); depth peeling was not implemented. The video runs at 25 FPS without and 50 FPS with min/max acceleration, with at most two reflections, and the frame rate barely falls with reflection depth (Figs. 17-7, 17-8).
- Limits: thin objects missed when steps exceed texels; abrupt distance changes need fine steps; few layers leave reflected regions empty (under a table in Fig. 17-6); one diffuse layer blurs where occlusion depends on the view; maps must be rebuilt when objects move.

## For RC

- A distance cube map is one probe's hit-distance texels, so the chapter's search is a way to trace rays near a probe through that probe's stored distances instead of the scene, as light field probes later did with octahedral maps ([2017_mcguire_light_field_probes.md](2017_mcguire_light_field_probes.md)). It works only for rays near the reference point and for what the reference point sees, the same limit as tracing through screen-space depth (inference).
