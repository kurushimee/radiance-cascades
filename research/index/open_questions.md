# Open questions

Every open question the topics end with, grouped by theme. Each links to the topic section that states it with its context and evidence. The ranked list of open problems for single-frame 3D RC, with hypotheses, is in [single-frame 3D RC](../topics/single_frame_3d_rc.md#open-problems-ranked).

## Contents

- [Tracing and scene representation](#tracing-and-scene-representation)
- [Cost, throughput and atomics](#cost-throughput-and-atomics)
- [Merging, ringing and interpolation](#merging-ringing-and-interpolation)
- [Leaks and visibility](#leaks-and-visibility)
- [Intervals, directions and parameters](#intervals-directions-and-parameters)
- [Probe placement, density and levels of detail](#probe-placement-density-and-levels-of-detail)
- [Noise, stability and quality without history](#noise-stability-and-quality-without-history)
- [Near field, screen space and hybrids](#near-field-screen-space-and-hybrids)
- [Moving and skinned geometry](#moving-and-skinned-geometry)
- [Hit lighting, direct light, sky and the composite](#hit-lighting-direct-light-sky-and-the-composite)
- [Bounces](#bounces)
- [Volumetrics, transparency and spectral transport](#volumetrics-transparency-and-spectral-transport)
- [Holographic RC in 3D](#holographic-rc-in-3d)
- [Sampling and guiding with cascades](#sampling-and-guiding-with-cascades)
- [Godot integration](#godot-integration)
- [Facts about existing work](#facts-about-existing-work)

## Tracing and scene representation

- Which empty-space skipping scheme (occupancy pyramid, block masks, distance field) is fastest for long upper intervals at equal correctness? ([2d_implementations](../topics/2d_implementations.md#open-questions))
- What is the right per-length opacity convention when cascades march different mip levels of one scene? ([2d_implementations](../topics/2d_implementations.md#open-questions))
- Can sector casting or another amortized march give SPWI rays the shared-cost advantage SSRC has, for example by marching a world structure along screen lines? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- Which compute tracer gives the highest throughput for short coherent SPWI rays under `RenderingDevice`: BVH2, wide BVH, voxels or an SDF? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- Would a surfel tracing proxy built per mesh (Love and Deepspace) make long software rays cheap enough for ray splitting under `RenderingDevice`? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- Does ray splitting pay with a compute tracer, and at what scene complexity does a per-probe tracer over filtered proxies win? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Can a 3D sweep over a voxel clipmap replace tracing for the upper cascades in a single frame, and where does the crossover sit in 3D, given that it fell at cascade 3 in 2D? ([light_transport_alternatives](../topics/light_transport_alternatives.md#open-questions))
- Can an LPV-like propagation or VCT mips provide RC's far cascades cheaply in a single frame, and how much leak would the prefiltering add there (light transport alternatives)? ([related_probe_gi](../topics/related_probe_gi.md#open-questions))
- Which pairing gives the best single-frame quality per millisecond: a triangle BVH for cascades 0 and 1 with voxel mips above, an HDDA over bitmasks for all cascades, or a narrow-band SDF with a skip structure? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))
- Can a per-frame GPU LBVH (Wicked Engine's four passes) build and trace a typical Godot scene within 1 to 2 ms on mid-range hardware, and how does BVH2 traversal in GLSL compare with an HDDA at RC's segment lengths? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))
- Does a narrow band of ±4 voxels in 8 bits keep enough precision for RC's short cascade 0 segments, or does cascade 0 need a finer field near the camera? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))

## Cost, throughput and atomics

- What does a measured comparison of the teaching demos' layouts at equal resolution show, given that none of them reports a timing? ([2d_articles_and_demos](../topics/2d_articles_and_demos.md#open-questions))
- Can IceKontroI's sparse task lists keep their speed with interpolation, which the author says would add parent tasks? ([2d_implementations](../topics/2d_implementations.md#open-questions))
- Is gathering every cascade per pixel (tf2XRc) ever cheaper than a top-down merge when only a few cascades exist? ([2d_shadertoys](../topics/2d_shadertoys.md#open-questions))
- What does extended gathering (NfVXRc, sfVSzd) cost against a merged cascade stack at equal penumbra quality? ([2d_shadertoys](../topics/2d_shadertoys.md#open-questions))
- How much of the per-ray fixed cost Dell'Ova's data imply survives in a compute tracer, where there is no ray launch but also no hardware traversal? ([3d_screen_space_theses](../topics/3d_screen_space_theses.md#open-questions))
- Can deposits avoid atomic contention without 64-bit or float atomics: subgroup deduplication, sort-based binning (1.5 ms for 10M texels in one build), or per-probe tracing for cascade 0 with splitting only above it? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Does the length-weighted cost model hold for the tracers available in compute shaders (sphere tracing a distance field, voxel DDA), or does the fix cost track ray count? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Is the 3D direction-first layout with hardware trilinear merging faster than a shader trilinear blend on current GPUs, given that GM Shaders' 2D speedup did not survive measurement? ([cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#open-questions))
- How much of gomezzz's frame is tracing? ([godot_projects](../topics/godot_projects.md#open-questions))
- What rate does a `RenderingDevice` compute tracer reach on RC rays? ([performance](../topics/performance.md#open-questions))
- How does the per-ray rate fall from cascade 0 to the top cascade for each tracer class? ([performance](../topics/performance.md#open-questions))
- How much of Split RC's 7 ms of non-trace work survives without atomics, with sort-based binning or per-probe tracing at cascade 0? ([performance](../topics/performance.md#open-questions))
- Are the hardware-RT single-frame results reproducible at the same ray counts with a compute tracer at 3.5 to 4× the trace time? ([performance](../topics/performance.md#open-questions))
- How much of HSGI's 2.65 ms denoiser and Lumen's fixed gather costs would a single-frame RC spend instead on rays, at the same quality? ([related_engine_gi](../topics/related_engine_gi.md#open-questions))
- Compute tracer throughput under `RenderingDevice` ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))
- Deposits without float or 64-bit atomics ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Merging, ringing and interpolation

- How much quality does the one-fetch merge lose against the bilinear fix in 2D at equal cost, measured against a path tracer such as CoreCascade's? ([2d_implementations](../topics/2d_implementations.md#open-questions))
- Does the Switch game's `pow(2, i²)` weighting of single fetches on a downsampled scene generalize, and what does it approximate? ([2d_implementations](../topics/2d_implementations.md#open-questions))
- Does the Dolkar mask (clVcD3, 4ctXD8, MfXyRj) remove the ringing that the bilinear fix removes, at one trace per ray, when its bracket and the merge use the same probes and weights? ([2d_shadertoys](../topics/2d_shadertoys.md#open-questions))
- How large is the error of NfBSz1's perspective-correct min/max interpolation on real G-buffers, against bilinear 3D and selective subsets? ([3d_screen_space_implementations](../topics/3d_screen_space_implementations.md#open-questions))
- Does the hit-distance hand-over of M3ycWt (rays to the first hit, blended between two levels) beat interval splitting for seams, and at what cost? ([3d_world_space_implementations](../topics/3d_world_space_implementations.md#open-questions))
- How large is vanilla merging's error in 3D, measured against a reference? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Is the circle-fix checkerboard on cascades 0 and 1 caused by rays starting outside the circle? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Can a nearest fix with forking in 3D avoid visibly blocky penumbras if cascade 0 is dense or replaced by cascade −1? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Does a simplex (tetrahedral) probe grid keep its 4× fix cost advantage once its merge indexing and direction interpolation are written out? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Does pre-averaging cost quality in 3D, where a parent's 4 children are farther apart in angle at low direction counts? ([cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#open-questions))
- Can a 3D lattice make the extend identity exact, as HRC does in 2D, without HRC's `O(N⁴)` memory for an `N³` volume? ([core_theory](../topics/core_theory.md#open-questions))
- How large is vanilla merging's error in 3D? ([core_theory](../topics/core_theory.md#open-questions))
- Can interpolation order be raised cheaply (GradientRC's slopes, cubic kernels) to remove blocky patches, and does that interact with the band-limit argument? ([core_theory](../topics/core_theory.md#open-questions))
- Is Split RC's 3D scaling (`K = 4, l = 4`) enough to drop reprojected parent lookups altogether, as the bin-shift scaling predicts, and does the leftover constant shift still need correcting? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- Irradiance gradients come almost free from a record's hemisphere samples. Could each RC probe compute translational gradients from its own rays and use them in the merge's spatial interpolation, the way first-order interpolation removed Radiance's seams? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- PoE1's GI used mips of depth and colour for distant samples. What is the exact relation between that prefiltering and RC's pre-averaged upper cascades? ([related_screen_space_gi](../topics/related_screen_space_gi.md#open-questions))

## Leaks and visibility

- How much does Peixoto's re-tracing of lower intervals from upper probes change the image against contiguous intervals, and does it hide or create leaks? ([2d_articles_and_demos](../topics/2d_articles_and_demos.md#open-questions))
- Does bilinear 3D with the bilinear fix (scy3Dd) remove depth-edge leaks as well as min/max probes, at lower cost? ([3d_screen_space_implementations](../topics/3d_screen_space_implementations.md#open-questions))
- Can the Unreal plugin's per-sector β be carried into SPWI, where rays are world segments rather than screen slices? ([3d_screen_space_implementations](../topics/3d_screen_space_implementations.md#open-questions))
- Is the hit-distance parent test enough to stop leaks in a 3D sparse grid, where parents are not on the same surface as the child? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- Which leak defence gives the best quality per millisecond in one frame: hit bits, parent hit distances, surface-class keys, or a few visibility rays? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Would erhe's gate failures (quarter-spacing leak, floor-embedded probes, 0.25 m emitter, corridor far field) pass with `l = 4`, equal-error `t0`, probe relocation and an analytic small-emitter term? ([3d_world_space_implementations](../topics/3d_world_space_implementations.md#open-questions))
- How many of the 8 parent validation segments does a 3D merge need, and can stored hit distances replace them as the free test does in world-space builds? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- Does a single-frame RC need Chebyshev visibility at its final gather when cascade-0 intervals are short, or do short intervals already confine the leak to within one probe spacing? ([related_probe_gi](../topics/related_probe_gi.md#open-questions))
- Does GI-1.0's ray-length bit, or an equivalent, have a cascade form, such as keying merged values by whether the child interval was blocked? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- How thin can walls be before each structure leaks at cascade 0, and do six-direction opacity mips keep upper cascades leak-free in one frame? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))
- A leak-free merge at bounded cost ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))
- Which mip rule loses least for thin walls in a single-frame 3D budget: six directional opacities, a variance limit like DexRT's, or max-filtering for binary occluders with averaging only in media? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))

## Intervals, directions and parameters

- Is `modifierHack`'s `√B` scale above base 16 a tuning of interval length against angular resolution that the interval scaling criteria would predict, or a patch over a layout bug, as jason.today suspected? ([2d_articles_and_demos](../topics/2d_articles_and_demos.md#open-questions))
- Do pixel-unit or depth-scaled intervals (Unreal plugin) remove the depth-dependent penumbra violation of world-unit intervals without new artifacts at large depth? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- Does the 2× interval rule for SPWI hold up against ×4 intervals in a measured comparison, and how many cascades does it cost to reach scene scale? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- Does an interval length that scales with surfel size (Split RC's `t0` per LOD) fix Coppen's depth-dependent error balance? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- Which nested equal-area map gives the best quality at 16 to 32 cascade 0 directions? ([cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#open-questions))
- Which interval scaling minimizes perceived error in 3D? ([core_theory](../topics/core_theory.md#open-questions))
- Does supersampling each stored direction (many rays per cone) change the equal-error `t0`, since it removes the aliasing that made shorter intervals preferable? ([core_theory](../topics/core_theory.md#open-questions))
- Which direction spacing (equal tangent, equal angle, equal area) minimizes cone-weight error and crosses in 3D cube-face layouts, and at what cost in lookups? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- Can an adaptive per-region angular density, driven by measured anisotropy as in the JQSRT method, keep RC's single-frame cost bounded? ([light_transport_alternatives](../topics/light_transport_alternatives.md#open-questions))
- Can interval-boundary bias be removed in one frame by overlapping or blended intervals at a cost below block jitter's history? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- daGI2 lengthens screen-probe rays from 3 to 6 grid probe sizes as probes settle. In a single frame there is no settling: which fixed interval-to-spacing ratio best trades the far level's coarseness against tracing cost? ([related_engine_gi](../topics/related_engine_gi.md#open-questions))

## Probe placement, density and levels of detail

- Would tmpvar's planned ring of outside probes beat clamping at domain edges, and what is its memory cost for a 3D volume? ([2d_articles_and_demos](../topics/2d_articles_and_demos.md#open-questions))
- How far do adaptive screen probes (Lumen, Godot's draft, daGI2) reduce depth-edge error compared with min/max pairs at equal ray count? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- Does Kaméus's Min+Max advantage grow with a cascade −1 gather and finer final interpolation, which remove the halos from 2×2 averaging? ([3d_screen_space_theses](../topics/3d_screen_space_theses.md#open-questions))
- Can surfel probes be spawned fast enough for a single frame, for example one per pixel block every frame as Split RC inserts probes, without the coverage test's dependence on last frame's grid? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- Can LOD transitions be hidden without the 25% interval cost of an overlap zone, for example with axis-aligned cubic boundaries and 4× interval scaling, which one build found needed no blending? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Would storing sparse intervals instead of probes (about 10× less waste in enclosed scenes) keep the merge cheap enough, given the extra indirection? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- At what scene size does a dense grid like gomezzz's lose to sparse probes near surfaces, in memory and in rays per frame? ([godot_projects](../topics/godot_projects.md#open-questions))
- Can DDGI-style relocation move RC's cascade-0 probes without breaking the regular parent interpolation of the merge, or must relocation be limited to the final gather? ([related_probe_gi](../topics/related_probe_gi.md#open-questions))
- Can neighbour clamping or a Weber-law test, as in adaptive radiance caching, set a single-frame RC's probe density per region without history? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- Can kajiya's output-sensitive origins, with one query point per cell picked from this frame's queries, place RC probes in a single frame without the history its votes rely on? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- How much of the energy loss Solari saw in its voxelized cache comes from fixed cell positions and normals, and does a world-space RC grid lose energy the same way? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- A generated surface atlas as the world part ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Noise, stability and quality without history

- Can a min/max or two-surface probe construction be made stable enough under camera motion without accumulation, and at what cost in mobile-class hardware? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- What is the quality-per-millisecond curve of SPWI across spacing and ray count, measured against a path-traced reference? ([3d_screen_space_theses](../topics/3d_screen_space_theses.md#open-questions))
- What probe footprint and rays per pixel give acceptable single-frame noise in cascade 0, and how much of the near field can a screen-space or world-space cascade −1 take over? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- How large is gomezzz's error per level against a path-traced reference, and how much does it drop with a parallax-correct parent lookup or with `l = 4` intervals? ([godot_projects](../topics/godot_projects.md#open-questions))
- Which parts of Love and Deepspace's temporal machinery (frame-spread tracing, cached hit distances, 28-frame convergence) does its surfel RC need, and which could a desktop single-frame version drop? ([history_and_landscape](../topics/history_and_landscape.md#open-questions))
- Lumen spends a quarter ray per pixel on its base screen probes and ships at 1/16 on High. What does a single-frame RC need at cascade 0 to match Lumen High's quality without the temporal filter, and does that fit the 4 ms budget Lumen holds at 60 fps? ([related_engine_gi](../topics/related_engine_gi.md#open-questions))
- At an equal per-frame ray budget, how does single-frame RC's noise compare with DDGI at its default hysteresis in the same scene? ([related_probe_gi](../topics/related_probe_gi.md#open-questions))
- Which of Enshrouded's tricks (fixed ray budget, ray sorting, stochastic cascade selection) survive without its temporal importance sampling? ([related_probe_gi](../topics/related_probe_gi.md#open-questions))
- Cascade 0 noise and stability in one frame ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))
- Quality against cost ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Near field, screen space and hybrids

- Can a screen-space cascade −1 restore the contact shadows that a 10 to 25 cm atlas texel loses, without the screen-space family's disocclusion problems? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- Is a clipmap of world probes over a distance field (EggyStudio) a usable far field under a single-frame screen-probe near field, with directions growing 4× per level? ([3d_world_space_implementations](../topics/3d_world_space_implementations.md#open-questions))
- Can cascade −1 in 3D be traced against the same scene representation as the cascades, or does it need screen-space marching as in Split RC, and how does that choice affect leaks at contact? ([cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#open-questions))
- Does the pull-back distance (half a probe for screen rays, √3 coarser probes for grid rays) generalize into an RC merge rule tied to the parent probe's spacing? ([related_engine_gi](../topics/related_engine_gi.md#open-questions))
- Can LSAO's sweep stack carry a sector bitmask instead of one largest occluder, giving bitmask GI at O(K) per pixel for any radius, the caching Therrien names as future work? ([related_screen_space_gi](../topics/related_screen_space_gi.md#open-questions))
- Can a screen-space RC interval use the bitmask's slab model with thickness from a min/max depth pyramid instead of a constant `t`? ([related_screen_space_gi](../topics/related_screen_space_gi.md#open-questions))
- How many slices per pixel does the bitmask's GI need to be acceptable in one frame at 1080p without temporal jitter, and how does that cost compare with a screen-space cascade 0 of the same angular resolution? ([related_screen_space_gi](../topics/related_screen_space_gi.md#open-questions))
- The hand-off in a hybrid ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Moving and skinned geometry

- How do on-surface charts handle dynamic and skinned meshes, given that their islands and triangle ID maps are built per mesh? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- How would a generated atlas handle moving and skinned meshes, and can it be rebuilt per change at Godot's mesh counts? ([3d_surface_probes](../topics/3d_surface_probes.md#open-questions))
- How should moving and skinned geometry enter the tracer and the probe set when the hash map is rebuilt every frame? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Can the analytic-primitive path (64 per frame, 112 bytes each) grow into a per-frame proxy scene for moving objects, as a cheap same-frame alternative to rebuilding a BVH? ([godot_projects](../topics/godot_projects.md#open-questions))
- Can screen-space marking and removal of the visible depth (daGI2's scheme) run every frame over the whole screen, so that visible moving objects enter the world structure without lag? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))
- Moving geometry in the same frame ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Hit lighting, direct light, sky and the composite

- What is the best irradiance tile size per probe for single-frame shading, and should tiles be built per probe or per pixel group? ([cascade_layout_and_merging](../topics/cascade_layout_and_merging.md#open-questions))
- What is the right 3D sky integral for non-equal-area direction maps, and can a prefiltered environment lookup per direction cell replace it exactly? ([core_theory](../topics/core_theory.md#open-questions))
- How should direct light be split from RC without double counting light that RC also reaches through its intervals? ([core_theory](../topics/core_theory.md#open-questions))
- What is the cheapest same-frame radiance source for screen-space hits at PRE_OPAQUE: a direct-light-only pass, voxel light injection, or direct light evaluated at each hit? ([godot_integration](../topics/godot_integration.md#open-questions))
- Can direct light at a hit come from Godot's shadow maps in the same frame, through the PRE_OPAQUE hook, so that a single-frame RC has first-bounce light at off-screen hits without last frame's lit image? ([related_engine_gi](../topics/related_engine_gi.md#open-questions))
- What is the cheapest same-frame hit shading that does not carry history: shadow maps sampled at hits, one shadow ray per hit, or a light injected into voxels each frame from the current shadow maps? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))
- Same-frame radiance at hits ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))
- Small lights and the direct split ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Bounces

- What replaces history for off-screen second bounces: a world cache rebuilt each frame, or world cascades under the screen ones? ([3d_screen_space](../topics/3d_screen_space.md#open-questions))
- What does a single-frame second bounce cost in a sparse hierarchy, and does a coarse secondary solve at `lod + 2` within the same frame suffice? ([3d_world_space](../topics/3d_world_space.md#open-questions))
- Can several bounces be computed within one frame from stored hit distances or repeated RC passes at acceptable cost? ([core_theory](../topics/core_theory.md#open-questions))
- What does a single-frame multi-bounce cost when each bounce is a full solve, and is one bounce plus an ambient term enough? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- How many lag-free bounces, by stored hit distances or by repeated RC iterations, fit in a frame budget, and how close do they get to the infinite-bounce fixed point at typical albedos? ([light_transport_alternatives](../topics/light_transport_alternatives.md#open-questions))
- What is the cheapest single-frame source of second-bounce light once last frame's lit result is ruled out? ([related_radiance_caches](../topics/related_radiance_caches.md#open-questions))
- A second bounce in one frame ([single_frame_3d_rc](../topics/single_frame_3d_rc.md#open-problems-ranked))

## Volumetrics, transparency and spectral transport

- Which fix, if any, stays watertight with participating media, where hit distances are not defined? ([artifacts_and_fixes](../topics/artifacts_and_fixes.md#open-questions))
- Does TypeGPU's 0.1 opacity gate in the integrate pass blur across thin occluders whose opacity differs by less than that? ([holographic_rc_implementations](../topics/holographic_rc_implementations.md#open-questions))
- Does a short-characteristics step with a linear source in each interval improve RC's merge of volumetric intervals over the constant-source form? ([light_transport_alternatives](../topics/light_transport_alternatives.md#open-questions))
- Can the Jensen-gap bound be used directly to pick per block between density averaging and coverage averaging, by the orientation of the structure? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))
- Does sparse RC work for volumetrics if probes are activated along camera rays through fog, and how many probes does that add per frame? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))
- What does single-frame multiple scattering cost, and is one scattering event from the same solve plus an ambient term enough for fog? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))
- Can a spectral cascade keep transmittance in a few bins and radiance in moments, and does the merge stay accurate? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))
- How much do the darker surfaces in Rulkens's comparison shrink once cones are weighted by projected solid angle? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))

## Holographic RC in 3D

- Can extensions be made to work in 3D, and is their bend tolerable when the extended rays feed a 3D merge? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- Is there a 3D layout that keeps HRC's transverse resolution below `N⁴` memory: frusta only where occluders are, HRC for the near field and vanilla RC for the far field, or the polygonal block layout with sparse extensions? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- How much memory would an extension structure cost as a tracing accelerator for vanilla 3D RC, and does it beat marching a distance field per interval? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- How should b-type rays be weighted in scenes with transparency? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- Can polygonal cascades carry shadows, by splitting polygons at occluders or estimating partial coverage as EnergyConservingHRC does for lights? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- Does vanilla 3D RC have an equivalent of HRC's 8-probe minimum light size, and would region integrals remove it? ([holographic_rc](../topics/holographic_rc.md#open-questions))
- How large is the accuracy gap between extending from cascade 0 and tracing the lowest three levels, measured on the same code against a reference? ([holographic_rc_implementations](../topics/holographic_rc_implementations.md#open-questions))

## Sampling and guiding with cascades

- Does a deterministic form of the RIS merge (all four or eight parents kept, weighted by validated `β·J`) keep Reservoir Cascades' leak reduction without its selection noise, and does Proposition 3's `O(ε_n)` bias bound still hold for it? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- What is merge-as-RIS's per-frame error with no temporal reuse, against vanilla RC at equal rays? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- Can RCPG's cell-and-texel average come from one cone or beam trace through a prefiltered voxel or distance-field scene within a few milliseconds? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- How does a culled dense volume like RCPG's build on a compute tracer under `RenderingDevice`, and does its cost still follow surface area? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))
- Can a merged cascade's descent sampler importance-sample cascade 0 or near-field rays inside the same frame, and does that reduce single-frame noise at equal rays? ([rc_for_sampling_and_guiding](../topics/rc_for_sampling_and_guiding.md#open-questions))

## Godot integration

- Does a `call_on_render_thread` callable queued from `_process` run before that frame's scene render, so a world-space solve lands in the same frame? ([godot_integration](../topics/godot_integration.md#open-questions))
- Does a `Texture3DRD` work as a `sampler3D` global shader parameter? ([godot_integration](../topics/godot_integration.md#open-questions))
- How should an RC integration handle users who enable SSAO, given that the opaque shader applies it to `IRRADIANCE` unconditionally? ([godot_integration](../topics/godot_integration.md#open-questions))
- How much of SDFGI's or HDDAGI's per-frame time is tracing, and how much is upkeep (voxelization, light injection, scrolling)? ([godot_integration](../topics/godot_integration.md#open-questions))
- Can a FogVolume shader sample an RC probe texture through a global uniform and write it as emission, so the engine's fog carries RC light without engine changes? ([godot_integration](../topics/godot_integration.md#open-questions))
- How much of a dense 128³ to 256³ occupancy or distance volume fits Godot's storage-buffer and texture limits once cascades, probes and the scene share the GPU? ([scene_representation_and_tracing](../topics/scene_representation_and_tracing.md#open-questions))

## Facts about existing work

- Which RC did Gerassimov test, and what causes its over-brightening in daylight? ([3d_screen_space_theses](../topics/3d_screen_space_theses.md#open-questions))
- How does wroughtinator's native build perform with history off, and how much of its look comes from the running average? ([3d_world_space_implementations](../topics/3d_world_space_implementations.md#open-questions))
- Does Phreakyx's design compile and run, and how full do its probe pools get in a real scene? ([godot_projects](../topics/godot_projects.md#open-questions))
- What does PoE2 ship: the cascade count, probe spacing, interval lengths, the 128-bit occlusion layout and the resolution? ([history_and_landscape](../topics/history_and_landscape.md#open-questions))
- How does Sannikov's sparse 3D RC handle tile interpolation, the cascade seam, memory and per-stage cost? ([history_and_landscape](../topics/history_and_landscape.md#open-questions))
- Does Blackline Interactive's Spatium run in a single frame, bounces included, and is it the surface-atlas design its HUDs and settings point to? ([history_and_landscape](../topics/history_and_landscape.md#open-questions))
- The academic record has no 3D single-frame world-space RC for games. Is that because it is too costly, or because no one has written it up? ([history_and_landscape](../topics/history_and_landscape.md#open-questions))
- What are TypeGPU's, folkjs's and cute_framework's timings on one GPU at one size, so the codes can be compared without the cross-hardware normalization used in holographic RC? ([holographic_rc_implementations](../topics/holographic_rc_implementations.md#open-questions))
- Most reported timings give no ray count, resolution or hardware. Which of the unnormalizable rows (Sannikov's sparse videos, the forum stacks, the README claims) can be rerun under known settings? ([performance](../topics/performance.md#open-questions))
- What is DexRT's actual 3D block-map size, given that the stated 669 words fit neither 8³ nor 16³ blocks at 512³? ([volumetric_and_radiative_transfer](../topics/volumetric_and_radiative_transfer.md#open-questions))
