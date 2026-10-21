# DLSS Ray Reconstruction 4.5

| | |
|---|---|
| Announcements | NVIDIA, [DLSS 4.5 at CES](https://www.nvidia.com/en-us/geforce/news/dlss-4-5-dynamic-multi-frame-gen-6x-2nd-gen-transformer-super-res/) (2026-01-06); [Ray Reconstruction 4.5 at Gamescom](https://www.nvidia.com/en-us/geforce/news/gamescom-2026-nvidia-geforce-rtx-dlss-4-5-announcements) (2026-08-25) |
| SDKs | [DLSS SDK releases](https://github.com/NVIDIA/DLSS/releases), [Streamline releases](https://github.com/NVIDIA-RTX/Streamline/releases), [`sl_dlss_d.h`](https://raw.githubusercontent.com/NVIDIA-RTX/Streamline/main/include/sl_dlss_d.h), [Ray Reconstruction programming guide](https://raw.githubusercontent.com/NVIDIA-RTX/Streamline/main/docs/ProgrammingGuideDLSS_RR.md) |
| Press | [Guru3D](https://guru3d.com/story/nvidia-driver-brings-dlss-45-ray-reconstruction-to-all-rtx-gpus/) (2026-08-25), [PC Games Hardware](https://www.pcgameshardware.de/Nvidia-Geforce-Grafikkarte-255598/News/DLSS-Ray-Reconstruction-auf-RTX-2000-und-RTX-3000-1552109/) (2026-08-26, German), [TechSpot on DLSS 3.5](https://www.techspot.com/article/2740-dlss-35-ray-reconstruction) |

"DLSS 4.5" names two releases. The CES one brought a second-generation Super Resolution transformer and 6× and dynamic multi frame generation, and does not mention Ray Reconstruction. The Gamescom one brought a second-generation Ray Reconstruction transformer, exposed as Preset F. NVIDIA publishes no algorithm for either, and nothing on how Ray Reconstruction's output relates to a converged image.

## Contents

- [Versions](#versions)
- [Hardware and cost](#hardware-and-cost)
- [Inputs and behaviour](#inputs-and-behaviour)

## Versions

- NVIDIA's Gamescom post calls the model a "new 2nd generation transformer model" with "35% more compute capability" and "20% more parameters" at "similar performance to the previous model". It shipped first as early access through the NVIDIA app, with an official release announced for September 2026.
- DLSS SDK 310.9.1 (2026-09-08) "Added DLSS Ray Reconstruction Transformer Mode (Preset F)". 310.9.16 (2026-10-16) fixes bugs only. 310.1.0 (2025-01-30) added the first transformer model for Ray Reconstruction; 310.5.0 and 310.6.0 (2026) changed Super Resolution and frame generation, not Ray Reconstruction.
- Streamline 2.14.1 (2026-09-08) and 2.14.16 (2026-10-16) came out on the same days as those DLSS SDKs. No Streamline note names a DLSS version or Ray Reconstruction, so the pairing rests on the dates.
- In Streamline's current `sl_dlss_d.h`, `ePresetF = 6` is the "Latest and default transformer model". Presets D and E are earlier transformer models, and A to C are removed. Streamline 2.10.0's header carries the same value with the comment "Reverts to default", so a build against it selects Preset F by its number once a newer runtime library is loaded (inference).

## Hardware and cost

- Guru3D: every RTX generation runs Ray Reconstruction 4.5, from the RTX 20 series on. NVIDIA's own post says "all GeForce RTX GPUs".
- PC Games Hardware measured up to 29% fewer frames per second on an RTX 2080 Ti and up to 25% on an RTX 3090 Ti, and attributes the cost to FP8 throughput, which RTX 40 and 50 have and Turing and Ampere lack. The article does not state its baseline.
- NVIDIA's CES post gives the same caveat for Super Resolution: RTX 20 and 30 lack native FP8, so the newer models cost more there.

## Inputs and behaviour

- The programming guide asks for linear diffuse and specular albedo, normalized shading normals in view or world space, linear roughness at the input resolution, dense motion vectors including camera motion, specular motion vectors or the specular hit distance, and the depth the motion vectors came from.
- Streamline's matrices are row-major and must not contain the jitter offset.
- Changing the input resolution while rendering reinitializes the denoiser.
- The guide's DLAA example uses Preset D.
- The guide mentions no static camera, convergence, accumulation, history reset or bias, and the header's options hold no accumulation or history field, only pre-exposure and exposure scale.
- NVIDIA describes Ray Reconstruction as generating "pixels in the parts of a ray traced frame where rays were not sampled", so its output is an estimate learned from its inputs, not an average of them (inference).
- With DLSS 3.5, TechSpot saw reflections take a few seconds to settle after the camera stopped.
