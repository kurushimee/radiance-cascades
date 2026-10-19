# Radiance Cascades Compared to Unity's Standard Global Illumination Methods

| | |
|---|---|
| Author | Mikhail Gerassimov (Kazakh-British Technical University, Almaty) |
| Date | 2026-04-18, DiGRA CA 2026 proceedings (https://doi.org/10.26503/dl.v2026i2.2775) |
| Kind | Conference paper |
| Link | https://dl.digra.org/index.php/dl/article/view/2775 ; data https://github.com/Zertass-2-0/Radiance-Cascades-Compared-to-Unity-s-Standard-Global-Illumination-Methods |

The paper compares three real-time global illumination (GI) methods in Unity's Universal Render Pipeline (URP): Screen Space Global Illumination (SSGI), built-in Realtime Lightmaps (RTLM), and Radiance Cascades (RC). It runs each method in three scenes with fixed camera paths and synchronized dynamic lights, then records FPS and frame time and annotates visual artifacts. RC and RTLM run at similar, higher frame rates than SSGI, and the paper rates RTLM as the most temporally stable and RC as the best at dynamic lights seen from a distance.

## Contents

- [Scope and limits (as stated)](#scope-and-limits-as-stated)
- [Test setup](#test-setup)
  - [Hardware and software](#hardware-and-software)
  - [Scenes](#scenes)
  - [Protocol](#protocol)
- [Methods compared](#methods-compared)
- [Results: performance](#results-performance)
  - [Reproduction from the source's linked measured data](#reproduction-from-the-sources-linked-measured-data)
- [Visual artifacts (paper text)](#visual-artifacts-paper-text)
  - [Isometric scene (dynamic emissive surfaces)](#isometric-scene-dynamic-emissive-surfaces)
  - [Realistic scene (daylight exterior)](#realistic-scene-daylight-exterior)
  - [Stylized scene (interior)](#stylized-scene-interior)
- [Discussion and recommendations](#discussion-and-recommendations)
- [Conclusions, limitations, future work](#conclusions-limitations-future-work)

## Scope and limits (as stated)

- Only free and openly available methods inside URP were tested.
- One hardware configuration was used.
- The visual evaluation is qualitative. No formal user studies were run.
- Each method and scene combination has one controlled measurement run.
- The stated goal was relative comparison on one setup, not reproducibility on other hardware.

## Test setup

### Hardware and software

| Item | Value |
|---|---|
| CPU | Intel Core i7-13620H |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| RAM | 16 GB |
| OS | Windows 11 |
| Engine | Unity 6000.2.12f1 |
| Pipeline | Universal Render Pipeline (URP) |
| Render resolution | unclear in source |
| Timing capture | Unity Recorder, plus a custom CSV logging script that records per-frame timing |

### Scenes

| Scene | Description | Base asset |
|---|---|---|
| Realistic FPS | FPS-like urban exterior, dynamic lighting, partial occlusion | Industrial Set V2.0 |
| Isometric | Fixed camera angle (see camera note) | Tanks Complete Project tutorial scene |
| Stylized | Low-poly interior, simplified geometry and materials, built for mobile-tier limits | Unity Learn FPS Microgame (URP) |

- Camera note: RC has no orthographic camera support. All methods therefore used a perspective camera with a very narrow field of view to approximate isometric projection.
- Each scene is a representative scene from its asset pack, with controlled lighting setups and test conditions added.

### Protocol

- The camera follows predefined spline paths, identical for every run.
- Dynamic light events are synchronized across methods: muzzle flashes, door opening sequences, and moving point lights.
- Each run lasts about one minute and covers the camera path twice.
- One representative run per method and scene is used for analysis.
- Performance metrics: frame time (ms per frame) and FPS.
- Performance analysis covers average trends, frame-time stability over time, and relative differences.
- Visual protocol: representative frames and screenshots per scene and method. Artifacts were annotated by hand and grouped.
- Visual focus areas: temporal instability and ghosting, handling of dynamic emissive surfaces, inconsistent indirect light, and artifacts specific to each method.

## Methods compared

| Method | What the paper states |
|---|---|
| SSGI | Screen-space method available in URP. Relies on previous frames (cites Abou 2025). Indirect light is computed mainly for geometry in view. Implementation not named. |
| RTLM | Built-in Realtime Lightmaps. Emissive light can only be baked for static geometry. Dynamic objects such as opening doors cannot be baked (cites Lambru 2021). |
| RC | "Recently proposed" technique. The paper gives no algorithm steps, formulas, parameters, probe layout, cascade count, or data layout. Implementation not named. |

- The paper does not describe the RC implementation at all. Unclear in source for every RC parameter.
- The data repository (read at 52c7393, MIT) adds nothing here: it holds no RC code, package name or settings, and no SSGI or RTLM settings are given anywhere. The paper says only that GI solutions "are currently not freely available for URP environments" and that free, openly available methods were tested. The DiGRA landing page lists no data link; the repository URL is printed in the PDF.

## Results: performance

### Reproduction from the source's linked measured data

The paper gives no tables of FPS values. Its data repository (in the Link row) holds one CSV per method and scene. The numbers below were recomputed from those CSVs.

Steady-state values use frames with time_sec >= 5 s. Each cell is one run; each run has 270 to 274 steady frames.

| Scene | Method | FPS median | FPS mean | FPS sd | ms median | ms sd |
|---|---|---|---|---|---|---|
| Isometric | NoGI | 343.0 | 338.7 | 30.1 | 2.92 | 0.42 |
| Isometric | RC | 225.7 | 224.2 | 10.6 | 4.43 | 0.32 |
| Isometric | RTLM | 216.5 | 213.3 | 14.1 | 4.62 | 0.44 |
| Isometric | SSGI | 104.0 | 104.0 | 1.0 | 9.62 | 0.09 |
| Realistic | NoGI | 387.3 | 393.2 | 52.8 | 2.58 | 0.43 |
| Realistic | RC | 229.9 | 225.7 | 20.3 | 4.35 | 0.40 |
| Realistic | RTLM | 208.5 | 206.1 | 12.7 | 4.80 | 0.34 |
| Realistic | SSGI | 140.1 | 142.1 | 12.2 | 7.14 | 0.57 |
| Stylized | NoGI | 391.0 | 415.5 | 78.4 | 2.56 | 0.45 |
| Stylized | RC | 266.9 | 266.1 | 17.9 | 3.75 | 0.26 |
| Stylized | RTLM | 272.2 | 283.3 | 39.1 | 3.67 | 0.46 |
| Stylized | SSGI | 144.1 | 144.1 | 13.2 | 6.94 | 0.61 |

- NoGI is a no-GI baseline. It appears only in the charts and the CSVs. The paper's text never mentions it.
- The CSVs (`gi_run_{NoGI,SSGI,RTLM,RC}_2026-02-19_*.csv` in each scene folder, with an xlsx summary and Unity analytics files) have the header `time_sec,ms_per_frame,fps,gi_mode` but write decimals with commas, so a row has more fields than the header and needs a locale-aware parse. Each RC run has about 288 rows.

## Visual artifacts (paper text)

### Isometric scene (dynamic emissive surfaces)

| Method | Observed | Cause as stated |
|---|---|---|
| RC | Convincing indirect light from emissive materials and dynamic lights | none stated |
| RTLM | No dynamic emissive contribution | Emissive light is baked only for static geometry |
| SSGI | Noticeable overall darkening | none stated |
| SSGI | Light trails behind moving emissive objects | Reliance on previous frames (Abou 2025). The paper calls it like long-exposure photography. |

### Realistic scene (daylight exterior)

| Method | Observed | Cause as stated |
|---|---|---|
| RC | Pronounced bloom-like effect on lit surfaces, even in neutral daylight. Excessive light bleeding. Loss of material definition. | The method "appears to over-amplify indirect radiance" in high-intensity light. Not well suited to physically plausible daylight. |
| RTLM | Most natural and stable indirect light. Dynamic doors need extra artificial light. | Doors cannot be baked into lightmaps (cites Lambru 2021). |
| SSGI | Little indirect light over large areas. Large areas look unnaturally dark. | Most contributing geometry is outside the camera frustum. |

### Stylized scene (interior)

| Method | Observed | Cause as stated |
|---|---|---|
| RTLM | Ignores dynamic emissive contributions, which limits interactive lighting | Same baking limit as above |
| RC | Excessive visual noise and blur, most visible at close distances | Cites Abou 2025 and Kung 2025. No cause stated. |
| SSGI | Most pleasing result: coherent indirect light and natural light interactions in a confined space. One notable artifact: multi-colored noise for the first few frames after initialization. | Not stated |

## Discussion and recommendations

Table 1 from the paper (qualitative):

| Criterion | RC | SSGI | RTLM |
|---|---|---|---|
| Performance | High | Low | High |
| Dynamic objects support | Full | Full | Limited |
| Temporal stability | Medium | Low | High |

Recommendations:
- RC: best for scenes with many dynamic light sources seen from a distance.
- SSGI: best for contained interiors where the main reflecting surfaces stay in screen space.
- RTLM: use as a supplement to traditional baking, for stable lighting of static geometry lit by dynamic sources.

## Conclusions, limitations, future work

- Conclusion: the paper presents a cross-genre comparison of currently available real-time GI solutions in Unity URP. It covers performance, temporal stability, and perceptual quality.
- Limitations, as stated: free methods only, one hardware configuration, qualitative perceptual evaluation without user studies, one measurement run per condition, so statistical robustness may be limited.
- Future work, as stated: HDRP, custom GI implementations, more hardware tiers, controlled user studies, and hybrid GI pipelines combining several techniques.

Related work the paper cites:
- Lambru et al. 2021 reviewed GI techniques in game engines. The paper says that study predates current URP pipelines. The study is Lambru, Morar, Moldoveanu, Asavei and Moldoveanu, "Comparative Analysis of Real-Time Global Illumination Techniques in Current Game Engines", IEEE Access 9 (2021) 125158-125183, DOI 10.1109/ACCESS.2021.3109663; its abstract says it describes several classes of real-time GI used in current engines together with the authors' own implementations. It is open access and described in [2021_lambru_realtime_gi_game_engines_comparison.md](2021_lambru_realtime_gi_game_engines_comparison.md).
- Kung 2025 compares RC with voxel cone tracing. The paper notes that voxel GI implementations are not freely available for URP.
- Abou and Jensen 2025 covers screen-space GI with radiance cascades in 3D games. The paper uses it for SSGI behavior.
