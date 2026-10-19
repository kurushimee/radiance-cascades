---
id: 001
title: Close every open question in research/
status: in_progress
created: 2026-10-19
updated: 2026-10-19
---

# Close every open question in research/

Every open question in `research/` is either answered as a fact in the section that owns it, or removed because its premise is false or because nothing in the research rests on it. Questions about what to build, measurements no source made, and untried combinations are not gaps in the research: they go, after any fact they carry is confirmed in its owning section. Answers come from derivation, CPU computation, re-reading cited sources and code, and the Godot source; closed work is bounded by public evidence.

## Phases

### 1. Clean project mentions out of research/

Done when the sweep finds no wording that mentions the project or its aims and the fact guard passes.

- [x] README, `single_frame_3d_rc.md`, `performance.md`, topics, sources and indexes reworded
- [x] Memory corrected
- [x] Committed

### 2. Ledger

Done when every item below has a provisional disposition.

- [x] Explicit questions classified
- [x] Implicit research-voice items classified

### 3. Remove wrong-premise and goal-less questions

Done when every confident removal is applied, with the facts each removed question carries confirmed in its owning section.

- [x] Facts carried by removed questions confirmed or moved
- [x] Removals applied in topics
- [x] Premise corrections written
- [x] Committed

### 4. Facts about existing work

Done when each `read`, `engine` and `public` row is answered or closed at the limit of public evidence.

- [x] `read` rows
- [x] `engine` rows
- [x] `public` rows
- [x] Committed

### 5. Derivations

Done when each `derive` row is answered, with a check script for each computed number.

- [x] `derive` rows
- [ ] Committed

### 6. Fold-in and verification

Done when the verification in the approved plan passes.

- [ ] Empty "Open questions" sections and the ranked list removed; `index/open_questions.md` deleted; README rows updated
- [ ] Links repointed; index entries added for new sections
- [ ] Verification passed
- [ ] Committed; plan moved to `finished/`

## Ledger

Dispositions: `derive`, `read` (cited source or code), `engine` (Godot source), `public` (bounded by public evidence), `premise` (premise false, corrected where stated), `goes` with a reason, `dup` (answered under another row). Reasons for `goes`: **design** (asks what a build should choose; no statement in the research rests on it), **measure** (asks for a measurement no source made; no statement rests on it), **frontier** (asks whether an untried combination or new theory works; answering it is new research and no statement rests on it), **paper** (an open theory problem, no statement rests on it).

### Explicit questions

Each `goes` row names what the research keeps in place of the question: the reported fact, record or inference stays in its section, and nothing else in `research/` rests on the answer. Inventory items Q136 to Q138 are the ranked items R10 to R12.

| ID | Question (short) | Where | Disposition |
|---|---|---|---|
| Q001 | modifierHack's `√B` above base 16: interval tuning or layout bug | 2d_articles_and_demos | read + derive: jason.today's suspicion and `artifacts_and_fixes` "no source tested" rest on it; `index/goals_artifacts.md` misstates the base-16 spatial ratio as halving (it is ×0.25); answered in `artifacts_and_fixes#base-ray-counts-other-than-4` and the modifierHack note of `2d_articles_and_demos` |
| Q002 | Peixoto's re-tracing of lower intervals | 2d_articles_and_demos | derive: the Peixoto section derives that a re-traced hit reaches the result, the conclusions say the image is unchanged; the overlap rows in `artifacts_and_fixes` settle it; answered in `2d_articles_and_demos#otavio-peixoto-opengine` |
| Q003 | tmpvar's outside-probe ring | 2d_articles_and_demos | derive: memory share of a one-probe ring per level in 3D, behind "edge handling matters more in 3D"; the quality comparison goes (frontier); answered in `2d_articles_and_demos#single-frame-assessment` |
| Q004 | teaching demos' layouts at equal resolution | 2d_articles_and_demos | derive: texels and merge fetches per demo at one resolution, behind "the cheapest merge"; premise partly false (GM Shaders' stress test is a timing); answered in `2d_articles_and_demos#single-frame-assessment` |
| Q005 | one-fetch merge against the bilinear fix, 2D | 2d_implementations | goes: measure; "must choose between hardware interpolation and a visibility-correct merge" stays |
| Q006 | the Switch game's `pow(2, i²)` | 2d_implementations | derive: what the weights approximate; "does it generalize" goes (frontier); answered in `2d_implementations#setups-that-worked-in-2d` |
| Q007 | fastest empty-space skipping | 2d_implementations | goes: measure; the skipping schemes and IceKontroI's timings stay |
| Q008 | IceKontroI's sparse lists with interpolation | 2d_implementations | goes: frontier; the author's note and the 3D 4× interpolation cost stay |
| Q009 | per-length opacity across mip levels | 2d_implementations | derive: the step conversion is already stated (`supporting_techniques_transport_and_math`, `volumetric`); the mip half is I15; answered in `2d_implementations#scene-representations` |
| Q010 | Dolkar mask with matched probes | 2d_shadertoys | goes: frontier; the mismatch record stays |
| Q011 | per-pixel gather against a top-down merge | 2d_shadertoys | derive: fetch counts from tf2XRc's section; answered in `2d_shadertoys#single-frame-assessment` |
| Q012 | extended gathering against a merged stack | 2d_shadertoys | derive: one cascade must have cascade 0 spacing and top-cascade directions at once; answered in `2d_shadertoys#single-frame-assessment` |
| Q013 | stable min/max probes without accumulation | 3d_screen_space | goes: design; Kaméus's single-frame Min+Max data stay |
| Q014 | pixel or depth-scaled intervals against the penumbra violation | 3d_screen_space | derive: the section states the fix; what remains is a fixed wall thickness against intervals growing with depth; answered in `3d_screen_space#interval-units-and-view-depth` |
| Q015 | 2× against ×4 intervals for SPWI | 3d_screen_space | goes: answered by the existing derivation ("the two findings are consistent") and the 9-against-5 cascade count |
| Q016 | sector casting for SPWI | 3d_screen_space | goes: frontier |
| Q017 | fastest compute tracer for SPWI | 3d_screen_space | goes: design; tracer rates are Q096 |
| Q018 | off-screen second bounce without history | 3d_screen_space | goes: design |
| Q019 | adaptive screen probes against min/max | 3d_screen_space | goes: measure; the counterpart inference stays |
| Q020 | bilinear 3D with the fix against min/max | 3d_screen_space_implementations | goes: measure |
| Q021 | per-sector β in SPWI | 3d_screen_space_implementations | goes: frontier |
| Q022 | NfBSz1's error on real G-buffers | 3d_screen_space_implementations | goes: measure |
| Q023 | SPWI quality per millisecond | 3d_screen_space_theses | goes: measure; "the curve is missing" stays |
| Q024 | Dell'Ova's per-ray fixed cost in a compute tracer | 3d_screen_space_theses | goes: measure |
| Q025 | Min+Max with a cascade −1 gather | 3d_screen_space_theses | goes: frontier; the author's next steps stay |
| Q026 | which RC Gerassimov tested | 3d_screen_space_theses | goes: answered by the records that paper and data name none; "unknown" restated as that record |
| Q027 | surfel probes spawned in one frame | 3d_surface_probes | goes: frontier; the derived 32-frame fill stays |
| Q028 | surfel-size intervals against Coppen's error balance | 3d_surface_probes | derive with Q014: Coppen's radius grows with depth while its intervals do not; answered in `3d_surface_probes#read-against-the-theory-derived` |
| Q029 | per-mesh surfel proxies for splitting | 3d_surface_probes | goes: design |
| Q030 | on-surface charts with dynamic meshes | 3d_surface_probes | read: Tatzgern et al.; answered: neither the slides nor the paper's notes cover moving or skinned meshes; recorded with an inference in `3d_surface_probes#on-surface-radiance-caches-tatzgern-et-al-2024` and the source note |
| Q031 | hit-distance parent test with off-surface parents | 3d_surface_probes | derive: geometry of what the test detects; ranked 4 and an index line rest on it; answered in `3d_surface_probes#connections`: the hit-distance test needs child-to-parent visibility in 3D |
| Q032 | generated atlas with moving meshes | 3d_surface_probes | goes: design |
| Q033 | screen-space cascade −1 for atlas contact shadows | 3d_surface_probes | derive: disocclusion and flicker come from history and moving probes, which a per-pixel cascade −1 lacks; answered in `3d_surface_probes#single-frame-assessment` |
| Q034 | cascade 0 footprint for single-frame noise | 3d_world_space | goes: design; the samples-per-direction table stays |
| Q035 | deposits without wide atomics | 3d_world_space | goes: design; ranked 6 keeps the hypothesis |
| Q036 | whether splitting pays with a compute tracer | 3d_world_space | goes: design |
| Q037 | LOD transitions without an overlap zone | 3d_world_space | goes: answered by the reported build that needed no blending |
| Q038 | best leak defence per millisecond | 3d_world_space | goes: measure |
| Q039 | sparse intervals instead of sparse probes | 3d_world_space | goes: frontier |
| Q040 | moving geometry with a per-frame hash map | 3d_world_space | goes: design; ranked 7 keeps the hypothesis |
| Q041 | single-frame second bounce in a sparse hierarchy | 3d_world_space | derive with Q094: probe and ray share of a solve two LODs up; answered in `3d_world_space#single-frame-assessment`; whether `lod + 2` suffices goes (measure) |
| Q042 | wroughtinator with history off | 3d_world_space_implementations | goes: measure |
| Q043 | erhe's gates under other settings | 3d_world_space_implementations | goes: frontier; the placement-and-scaling inference stays |
| Q044 | M3ycWt's hand-over against splitting | 3d_world_space_implementations | goes: measure |
| Q045 | EggyStudio's clipmap as a far field | 3d_world_space_implementations | goes: design (its "4× directions per level" matches no preset) |
| Q046 | vanilla merging's error in 3D | artifacts_and_fixes | goes: dup Q059 |
| Q047 | the length-weighted fix cost model | artifacts_and_fixes | derive: steps per interval for each tracer class; "between the two models" rests on it; answered in `artifacts_and_fixes#cost`: fix time `k·(1 − s_top) + s_top` by tracer class; the l = 2 figure corrected from 6.7× to 6.6×, also in `performance` |
| Q048 | cause of the circle-fix checkerboard | artifacts_and_fixes | derive + CPU check; answered in `artifacts_and_fixes#straight-ray-fixes`: a forward exit needs every ray to start inside the circle, so contiguous ×4 in 2D and Split RC-style 3D also fail on cascade 1; the table and the single-frame line corrected |
| Q049 | nearest fix with forking in 3D | artifacts_and_fixes | derive: forking gives every cascade the spacing of the one above; answered in `artifacts_and_fixes#cheaper-fixes` |
| Q050 | simplex grid's 4× fix cost | artifacts_and_fixes | derive; answered in `artifacts_and_fixes#cost`: 2 or 3 upper probes (2.75 on average) for cell-centred probes on a Kuhn split, not 4 |
| Q051 | a fix watertight in media | artifacts_and_fixes | derive: which fixes need hit distances; answered in `artifacts_and_fixes#fixes-compared` |
| Q052 | hardware trilinear merge against a shader blend | cascade_layout_and_merging | goes: measure; the GM Shaders retraction stays |
| Q053 | nested equal-area map at 16 to 32 directions | cascade_layout_and_merging | derive + CPU: two sources disagree without metrics; answered in `cascade_layout_and_merging#direction-maps-in-3d`; premise partly false: the screen-space and sparse builds compared Clarberg with the plain octahedral map; "best" goes (design) |
| Q054 | pre-averaging's cost in 3D | cascade_layout_and_merging | derive: premise false for nested maps, whose four children tile the parent cell; answered in `cascade_layout_and_merging#pre-averaging` |
| Q055 | irradiance tile size | cascade_layout_and_merging | derive + CPU: irradiance carries 9 SH coefficients; per-pixel-group tiles go (design); answered in `cascade_layout_and_merging#final-gather` |
| Q056 | cascade −1 against the cascades' scene structure | cascade_layout_and_merging | goes: design |
| Q057 | interval scaling that minimizes error in 3D | core_theory | derive: drift of the error ratio for any constant or per-cascade `l`; answered in `core_theory#two-criteria-for-interval-scaling-derived` |
| Q058 | exact extend identity below `O(N⁴)` | core_theory | derive: lines in 3D are a four-parameter family; answered in `core_theory#where-the-merge-is-exact-derived`; the below-`N⁴` half goes (paper) |
| Q059 | vanilla merging's error in 3D | core_theory | goes: measure; Osborne's worst case stays |
| Q060 | higher interpolation order | core_theory | goes: frontier; "suggested but not tested" stays |
| Q061 | 3D sky integral for non-equal-area maps | core_theory | derive (with I03); answered in `core_theory#sky-and-environment` |
| Q062 | direct light split without double counting | core_theory | derive (with I14, R09); answered in `core_theory#splitting-direct-light-derived` and `single_frame_3d_rc#lighting-the-hits-and-the-composite` |
| Q063 | several bounces in one frame | core_theory | goes: design; the energy share is Q094 |
| Q064 | supersampling and the equal-error `t0` | core_theory | derive; answered in `core_theory#choosing-cascade-0-derived-and-reported` |
| Q065 | `call_on_render_thread` from `_process` | godot_integration | engine: answered (`main.cpp`, `rendering_server_default.h`); answered in `godot_integration#running-the-compute-work`, `#single-frame-assessment`, `#engine-source-locations`; `docs/rendering_device.md#render-thread` |
| Q066 | `Texture3DRD` as a global `sampler3D` | godot_integration | engine: answered (`texture_rd.cpp`, `material_storage.cpp`, `variant.cpp`); answered in `godot_integration#running-the-compute-work`, `#engine-source-locations`; `docs/rendering_device.md#texture3drd` |
| Q067 | cheapest same-frame radiance at PRE_OPAQUE | godot_integration | goes: design |
| Q068 | users who enable SSAO | godot_integration | goes: design; the SSAO gating found in the source is added |
| Q069 | SDFGI and HDDAGI time split | godot_integration | goes: measure; the combined 2.43 and 0.93 ms stay |
| Q070 | FogVolume shader reading a global texture | godot_integration | engine: answered (`fog.cpp`); answered in `godot_integration#volumetric-fog`, `#engine-source-locations` |
| Q071 | gomezzz's error per level | godot_projects | goes: measure; the derived bin error stays |
| Q072 | gomezzz's trace share | godot_projects | goes: measure |
| Q073 | whether Phreakyx compiles | godot_projects | goes: measure; "untested design" stays |
| Q074 | dense grid against sparse probes by scene size | godot_projects | goes: design |
| Q075 | analytic primitives as a moving-object proxy | godot_projects | goes: frontier |
| Q076 | what PoE2 ships | history_and_landscape | public; closed at public evidence in `history_and_landscape#poe2-cost-figures` |
| Q077 | Sannikov's sparse 3D internals | history_and_landscape | goes: answered by the world-space section (no tile interpolation, a visible seam, a hash map, no timings published) |
| Q078 | Spatium single-frame and atlas-based | history_and_landscape | public (with Q146 to Q152); closed at public evidence: `history_and_landscape` landscape row, Blackline note `#not-shown-publicly` |
| Q079 | Love and Deepspace's temporal parts | history_and_landscape | goes: design |
| Q080 | no single-frame 3D world-space RC in the academic record | history_and_landscape | premise false: Split RC's preprint is one; the academic-work paragraph corrected |
| Q081 | HRC extensions in 3D | holographic_rc | goes: frontier; "unsolved in 3D" stays as reported |
| Q082 | 3D HRC layout below `N⁴` | holographic_rc | derive with Q058; answered in `holographic_rc#3d`; occluder-only frusta and sparse polygonal layouts go (paper) |
| Q083 | extension structure as a tracing accelerator | holographic_rc | goes: frontier |
| Q084 | b-type weights with transparency | holographic_rc | goes: frontier; "the main unsolved problem" stays as reported |
| Q085 | direction spacing for cube faces | holographic_rc | goes: frontier |
| Q086 | shadows in polygonal cascades | holographic_rc | goes: frontier; "no version has shadows yet" stays |
| Q087 | vanilla 3D minimum light size | holographic_rc | derive: the 3D ray-end gap at the equal-error `t0`; region integrals go (frontier); answered in `holographic_rc#where-it-works` |
| Q088 | single-frame multi-bounce cost | holographic_rc | goes: design |
| Q089 | extending from cascade 0 against tracing three levels | holographic_rc_implementations | goes: measure; the disagreement stays as reported |
| Q090 | TypeGPU's 0.1 opacity gate | holographic_rc_implementations | goes: the code fact answers it by definition |
| Q091 | three HRC codes on one GPU | holographic_rc_implementations | goes: measure; the bandwidth normalization stays |
| Q092 | 3D sweep for upper cascades | light_transport_alternatives | goes: frontier |
| Q093 | linear source in the merge | light_transport_alternatives | goes: frontier; the inference stays |
| Q094 | lag-free bounces against the fixed point | light_transport_alternatives | derive: energy share per bounce, assumptions stated; answered in `light_transport_alternatives#multi-bounce`; the frame-budget half goes (design) |
| Q095 | adaptive angular density | light_transport_alternatives | goes: frontier |
| Q096 | rate of a `RenderingDevice` compute tracer | performance | premise: RD dispatches plain SPIR-V (`rendering_device_driver_vulkan.cpp`), so published compute rates apply; "1 to 3 G rays/s" restated as an assumption; premise corrected in `performance#normalized-throughput-derived`, the README main findings and `scene_representation_and_tracing#single-frame-assessment` (`rendering_device_driver_vulkan.cpp:4418, 6700-6703, 6741`) |
| Q097 | per-ray rate by cascade | performance | dup Q047; answered with Q047 in `artifacts_and_fixes#cost` and `performance#what-the-numbers-show` |
| Q098 | Split RC's non-trace work without atomics | performance | goes: design |
| Q099 | hardware-RT results with a compute tracer | performance | goes: answered by the derived 4.5 to 18.0 ms projection |
| Q100 | which unnormalizable rows can be rerun | performance | goes: measure |
| Q101 | deterministic RIS merge | rc_for_sampling_and_guiding | goes: paper; the carry-over inference stays |
| Q102 | merge-as-RIS error without temporal reuse | rc_for_sampling_and_guiding | goes: measure; "not reported" and the extrapolation stay |
| Q103 | parent validation segments in 3D | rc_for_sampling_and_guiding | goes: frontier |
| Q104 | `K = 4, l = 4` and reprojected lookups | rc_for_sampling_and_guiding | derive: the section already derives it; the hedge in `single_frame_3d_rc` is replaced; answered in `rc_for_sampling_and_guiding#single-frame-assessment` and `single_frame_3d_rc`: the shift is constant at 1.7 to 5.2 parent bins |
| Q105 | interval-boundary bias without history | rc_for_sampling_and_guiding | goes: frontier; the inference stays |
| Q106 | RCPG's average from one cone trace | rc_for_sampling_and_guiding | goes: frontier |
| Q107 | RCPG's volume on a compute tracer | rc_for_sampling_and_guiding | goes: design |
| Q108 | descent sampler within a frame | rc_for_sampling_and_guiding | goes: frontier |
| Q109 | cascade 0 to match Lumen High | related_engine_gi | goes: design |
| Q110 | a fixed interval-to-spacing ratio | related_engine_gi | goes: design; the equal-error `t0` stays |
| Q111 | Godot's shadow maps at PRE_OPAQUE | related_engine_gi | goes: answered by the frame order in `godot_integration` |
| Q112 | pull-back as a merge rule | related_engine_gi | goes: frontier; the inferences stay |
| Q113 | HSGI's denoiser spent on rays | related_engine_gi | goes: design; the inference stays |
| Q114 | DDGI relocation of cascade 0 probes | related_probe_gi | goes: frontier |
| Q115 | Chebyshev visibility with short intervals | related_probe_gi | derive: the gather leak runs from shading point to probe, not along probe rays; answered in `related_probe_gi#single-frame-assessment` |
| Q116 | single-frame RC noise against DDGI hysteresis | related_probe_gi | goes: answered by the derived 34 M-ray equivalence |
| Q117 | LPV or VCT mips as far cascades | related_probe_gi | goes: frontier |
| Q118 | Enshrouded's tricks without history | related_probe_gi | goes: design |
| Q119 | irradiance gradients in the merge | related_radiance_caches | goes: paper (its "removed Radiance's seams" is not in the sources) |
| Q120 | Weber-law test for probe density | related_radiance_caches | goes: frontier |
| Q121 | kajiya's origins without votes | related_radiance_caches | goes: frontier |
| Q122 | cascade form of the ray-length bit | related_radiance_caches | goes: frontier |
| Q123 | Solari's energy loss | related_radiance_caches | read: the post's attribution (its cache is hashed, not voxelized); the RC-grid half goes (frontier); answered: the post names no cause; `related_radiance_caches#bevy-solari` and the source note |
| Q124 | cheapest second-bounce source | related_radiance_caches | goes: design |
| Q125 | LSAO's stack with a bitmask | related_screen_space_gi | goes: frontier; Therrien's future work stays |
| Q126 | slab thickness from a min/max pyramid | related_screen_space_gi | goes: frontier |
| Q127 | slices per pixel without jitter | related_screen_space_gi | goes: measure; the inference stays |
| Q128 | PoE1's mips against pre-averaged cascades | related_screen_space_gi | derive; answered in `related_screen_space_gi#connections` |
| Q129 | best tracer pairing | scene_representation_and_tracing | goes: design |
| Q130 | per-frame GPU LBVH in 1 to 2 ms | scene_representation_and_tracing | goes: measure |
| Q131 | wall thickness at which each structure leaks | scene_representation_and_tracing | goes: measure |
| Q132 | cheapest same-frame hit shading | scene_representation_and_tracing | goes: design; ranked 2 keeps the hypothesis |
| Q133 | daGI2's marking every frame | scene_representation_and_tracing | goes: design |
| Q134 | 8-bit ±4-voxel band for cascade 0 | scene_representation_and_tracing | derive: quantization step against the march step; answered in `scene_representation_and_tracing#connections` |
| Q135 | dense volume within the storage limits | scene_representation_and_tracing | derive: the scene volume fits; the dense cascade stack does not; answered in `scene_representation_and_tracing#single-frame-assessment` |
| Q139 | mip rule for thin walls | volumetric_and_radiative_transfer | goes: measure; the directional-opacity report stays |
| Q140 | Jensen-gap bound per block | volumetric_and_radiative_transfer | goes: frontier; the variance-test inference stays |
| Q141 | probes activated along camera rays | volumetric_and_radiative_transfer | goes: frontier |
| Q142 | single-frame multiple scattering | volumetric_and_radiative_transfer | goes: design |
| Q143 | spectral cascade | volumetric_and_radiative_transfer | goes: frontier |
| Q144 | DexRT's 3D block-map size | volumetric_and_radiative_transfer | read: DexRT code; else the derived mismatch is recorded; answered from the code: 12,484 words; `volumetric_and_radiative_transfer#dexrt` and the source note |
| Q145 | Rulkens's darker surfaces | volumetric_and_radiative_transfer | goes: answered by the source note's derivation (0.52 and 0.91 of exact) |
| Q146 to Q152 | Spatium's atlas, HUD, layout, bounces, directional GI, moving meshes, far field | Blackline note | public; closed at public evidence in the Blackline note `#not-shown-publicly` |
| R01 | ranked 1: tracer throughput | single_frame_3d_rc | becomes a stated result with Q096 |
| R02 | ranked 2: same-frame radiance at hits | single_frame_3d_rc | becomes a stated assessment; its hypothesis and evidence stay |
| R03 | ranked 3: cascade 0 noise | single_frame_3d_rc | becomes a stated assessment |
| R04 | ranked 4: leak-free merge | single_frame_3d_rc | becomes a stated result with Q104 and Q031 |
| R05 | ranked 5: quality against cost | single_frame_3d_rc | becomes a stated assessment (no 3D quality-per-ms study) |
| R06 | ranked 6: deposits without wide atomics | single_frame_3d_rc | becomes a stated assessment |
| R07 | ranked 7: moving geometry | single_frame_3d_rc | becomes a stated assessment |
| R08 | ranked 8: a second bounce | single_frame_3d_rc | becomes a stated result with Q094 and Q041 |
| R09 | ranked 9: small lights and the direct split | single_frame_3d_rc | becomes a stated result with Q062 and Q087 |
| R10 | ranked 10: the hybrid hand-off | single_frame_3d_rc | becomes a stated assessment |
| R11 | ranked 11: a generated atlas | single_frame_3d_rc | becomes a stated assessment |
| R12 | theory paragraph | single_frame_3d_rc | answered by Q057 and Q058; the gradient and RIS items go with Q119 and Q101 |

### Implicit research-voice items

| ID | Item | Where | Disposition |
|---|---|---|---|
| I01 | circle-fix explanation "remains untested" | artifacts_and_fixes | with Q048; answered with Q048 |
| I02 | base 16: "No source tested whether that imbalance, or a bug, causes the artifacts" | artifacts_and_fixes | with Q001 |
| I03 | "unexplained 6" | core_theory, sources/2023_rc_shadertoys.md | derive: `2π/6 = 1.047` cancels the gather's ×2π to within 5%; answered in `core_theory#sky-and-environment` and the Shadertoys note |
| I04 | INSIDE talk's coverage of depth-aware upsampling | 3d_screen_space_implementations, sources/2021_pixelmager_depth_aware_upscaling.md | read; answered in `3d_screen_space_implementations` and the pixelmager note |
| I05 | Gavras's untested light-count claim | 3d_screen_space_theses | derive: RC's cost is independent of light count by construction; answered in `3d_screen_space_theses` |
| I06 | fixes at branch tips not checked | 3d_world_space_implementations_grids, sources/2026_rc_repository_survey.md | read; answered: both fixes at all four tips; grids topic and the survey note |
| I07 | `rb_ssao/final` with the pre-pass off | godot_integration, sources/2026_godot_indirect_diffuse_paths.md | engine: answered (`render_forward_clustered.cpp`, `scene_forward_clustered.glsl`); answered in `godot_integration#getting-gi-into-shading`, `#engine-source-locations` and the indirect-diffuse note |
| I08 | Phreakyx reduce path not checked | godot_projects, sources/2026_phreakyx_godot_rc_gdextension.md | read; answered in `godot_projects` and the Phreakyx note |
| I09 | Half HRC authorship | holographic_rc_implementations | read, else restated as the public record; answered: Yaazarai's; `holographic_rc_implementations#half-hrc`, `holographic_rc#half-hrc`, the reference-codes note |
| I10 | GTAO formula not checked against the memo | supporting_techniques_structures_and_tracing | read; answered: the memo's Eq. 7; `supporting_techniques_structures_and_tracing` |
| I11 | Dell'Ova's figures not checked against eq 4.2 | sources/2025_dellova_rc_performance_scaling_thesis.md | restate: the figure gives no sizes; restated in the Dell'Ova note |
| I12 | ascii-gi's bilinear-fix uniform not traced | sources/2026_merging_and_ringing.md | read; answered in the merging notes |
| I13 | mdxish pages not rendered | sources/2026_merging_and_ringing.md | restate as the note's provenance; restated in the merging notes (the page renders a gist) |
| I14 | "Double counting is unresolved" | single_frame_3d_rc | with Q062; answered with Q062 |
| I15 | "What to average is disputed" | volumetric_and_radiative_transfer, sources/2026_volumetric_rc.md | the dispute record stays; the section's slab result ("density averaging is exact across slabs and over-occludes partial coverage") is linked from it |
| I16 | "the relation is not established" | sources/2026_blackline_interactive_spatium_rc.md | public, with the Blackline rows; restated as a derived bound in the Blackline note `#derived-numbers` |
| I17 | index lines that restate questions ("untested", "open", "unknown" trade-offs) | index/goals_*.md, index/open_questions.md | phase 6: restated from the answers or removed with their questions |

Records that stay as they are: reported open problems and disputes ("disputed" for cubic interpolation with the bilinear fix, "Reports disagree" on HRC extension starts), "unclear in source" items, provenance qualifiers, and authors' own listed limitations.

## Facts / research

- `index/open_questions.md` matched the topics exactly at the start: 142 topic bullets plus the 11 ranked problems.
- Split RC was published on arXiv in July 2026 (v2); it gives one diffuse bounce in a single frame with no temporal reuse, timed per stage on an RTX 3080 Laptop (`sources/2026_freeman_split_radiance_cascades.md`).
- `docs/rendering_device.md#ray-tracing` records a Vulkan ray tracing pipeline in Godot 4.7.2 that works with non-indexed BLAS triangles, and `#limits` the 128 MiB storage-buffer guarantee.
- Corrections made during phase 5: the circle-fix condition is an interval-length bound, not `t_end ≥` the probe distance alone (`checks/circle_fix_failures.py`); the trilinear fix at `l = 2` is 6.6×, not 6.7× (`checks/fix_cost_by_tracer.py`); two `2d_shadertoys` links to the sky integrals pointed at `core_theory#colour-space-and-range` and now point at `#sky-and-environment`; a duplicated sentence in `related_screen_space_gi`'s PoE1 section removed.
