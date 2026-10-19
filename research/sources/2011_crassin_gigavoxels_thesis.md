# GigaVoxels: a voxel-based rendering pipeline for large and detailed scenes

| | |
|---|---|
| Author | Cyril Crassin (supervisor Fabrice Neyret) |
| Date | PhD thesis, Université de Grenoble, defended 2011-07-12 |
| Kind | Thesis, 207 pages; chapters 4 to 7 and 9 read, in part for 4, 6 and 7; appendix A not read |
| Link | https://maverick.inria.fr/Publications/2011/Cra11/CCrassinThesis_EN_Web.pdf |

The thesis behind voxel cone tracing ([2011_crassin_voxel_cone_tracing.md](2011_crassin_voxel_cone_tracing.md)): a sparse voxel octree with bricks in a 3D texture, rendered by pre-integrated cone tracing and streamed on demand by the rays themselves. The RC discussions link it for its storage and streaming design ([sparse 3D RC](2026_sparse_and_3d_rc.md)). Page numbers are the printed ones, equal to the PDF's.

## Contents

- [Octree and bricks (ch. 5)](#octree-and-bricks-ch-5)
- [Rendering (ch. 4, 6)](#rendering-ch-4-6)
- [Streaming (ch. 7)](#streaming-ch-7)
- [Frame rates](#frame-rates)
- [Indirect light (ch. 9)](#indirect-light-ch-9)
- [For RC](#for-rc)

## Octree and bricks (ch. 5)

- One child pointer per node, with siblings stored together in blocks of `N³` nodes (`N = 2`), grouped as 2×2×2 node tiles in linear memory (pp. 100-101). A node is two 32-bit words: flags (terminal, and whether the second word is a constant or a brick pointer) with a 30-bit child pointer, and a constant colour or a 30-bit brick pointer (p. 102).
- Bricks live in a 3D texture, so trilinear filtering is hardware; data are split into structure-of-arrays layers. Brick addresses are three 10-bit coordinates. Addressing limits: `2^30` tiles × 64 B = 64 GB of nodes and `2^30` bricks of 8³ RGBA8 voxels = 2 TB (p. 103).
- Node-centered bricks need at least 8³ voxels without a border (p. 98); for Sponza and Coral the storage optimum was 4³ corner-centered bricks (p. 104).
- Sponza takes 68.48 MB of bricks and 1.93 MB of octree, 70.41 MB, 6.88 % of a dense mip pyramid; Coral 4.9 %. A dense 512³ pyramid is given as 1023 MB, which matches 8 bytes per voxel (derived from p. 142's 8 B per voxel).

## Rendering (ch. 4, 6)

- Rendering splits into top-down octree traversal and brick sampling, which communicate through video memory (p. 108). The level of detail follows the node's projected size (p. 109). A constant node is crossed in one step; a brick is ray-marched with trilinear samples.
- Each pixel footprint is an orthographic beam, and a cone is one ray sampled at the mip level matching its footprint, with linear interpolation between levels (pp. 79-86).
- Pre-integrated transport (eq. 4.9, p. 83): `I(D, P) ≈ Σ_i [∫_P Q(s_i, s_{i+1}, r) dr]·Π_{j>i} [∫_P exp(−τ(s_j, s_{j+1}, r)) dr]`, with the mean in-scattered energy `Q` and mean transparency precomputed per voxel and level. Per voxel, `T = exp(−κ·dx)` with `κ = κ'·ρ` and `dx` the voxel size, and colour is premultiplied by `α = 1 − T` (p. 91).
- Cone footprints have no closed form; measured footprints are plotted for 11.25° and 22.5° apertures (p. 86).

## Streaming (ch. 7)

- Each ray reports the nodes and bricks it needs at the resolution it needs; misses become requests, and rays may stop early (p. 74). Node tiles and bricks have separate caches with fine-grained LRU replacement on the GPU (pp. 121-122). Requests are batched during rendering and served in an update phase (p. 125) by producers that load from system memory, compute procedurally or read from disk; a 256 GB dataset streams on demand (pp. 122, 150).
- A real-time mode loads bricks first with one render-and-update pass per frame; a quality-first mode runs several passes to refine, as many as the frame budget allows (pp. 125-127).
- Example pools (p. 142): 262,144 node tiles (2,097,152 nodes × 8 B = 16 MB) and 110,592 bricks of 8³ (56,623,104 voxels × 8 B = 432 MB), with 13.84 MB of management buffers, 3.08 % overhead. Miss rates at 4× exploration speed: 2.6 % with a 512 MB brick cache, 5.9 % with 128 MB (p. 152).

## Frame rates

| Scene | Size | GPU | Frame rate |
|---|---|---|---|
| Lion | 2048³, 64 GB on disk, 512² output | GTX 480 | 60 to 80 FPS (pp. 95, 148) |
| CT scan | 2048³, 32 GB | GTX 280 | 20 FPS (p. 105) |
| Teaser scene | 8192³ | GTX 280 | 20 to 40 FPS (p. 148) |
| Procedural fractal | | GTX 480 | 70 to 90 FPS (p. 150) |
| Visible Male | 4096³, 256 GB | GTX 280 | 15 to 20 FPS (p. 150) |
| Power Plant, 13M triangles, GPU triangle cache | | GTX 280 | 15 to 30 FPS (p. 155) |
| Dragon | 1024³ | not stated | about 80 FPS (p. 95) |

## Indirect light (ch. 9)

- Two bounces, diffuse and glossy, at 25 to 70 FPS on a GTX 480 (p. 165). Light is injected by rasterizing from each light and splatting into the leaves, filtered up the octree with incoming directions stored as Gaussian lobes, and gathered with about five wide diffuse cones and one specular cone whose aperture follows the specular exponent (p. 167).
- Weighting each voxel by the inverse of its multiplicity gives a 3×3×3 Gaussian kernel (p. 170). Bricks are 3×3×3 and corner-centered, and nodes gain neighbour pointers (pp. 168-169). The octree is built on the GPU by rasterization without a full intermediate grid; semi-static geometry is voxelized once and dynamic objects every frame, separated by time stamps (p. 169).
- Table 9.1 (p. 175), Sponza (280K triangles, 9-level octree, 512³ virtual), 512² image, 3 diffuse cones and a 10° specular cone: rasterization 1.0, direct 2.0, indirect diffuse 7.8, direct plus diffuse 14.2, indirect specular 8.0, total 33.0 ms. The paper's version of the table prints 22.0 ms as the total, so the two disagree; neither total is a sum of the listed parts (derived).
- A 16K-triangle hand updates in about 5.5 ms; the static octree takes about 280 ms; Sponza runs at 30 FPS without and 20 FPS with the specular cone (GTX 480, Core 2 Duo E6850). Against Kaplanyan and Dachsbacher's LPV: 31 against 27 FPS (Fig. 9.10). AO runs at 70 to 150 FPS, and at 153 FPS against 0.1 FPS for an OptiX reference (Figs. 9.11-9.12). About 512 MB of GPU memory are allocated (p. 176), where the paper says about 1024 MB.

## For RC

- Ray-guided streaming, in which the rays that need data request it at the resolution they need, maps directly onto RC's interval structure: the upper cascades' long intervals need only coarse levels, so a sparse RC scene structure can be streamed per cascade by the same request scheme (inference).
- Pre-integrated transparency per voxel and level is the volumetric mip that RC's mip-marched opacity uses, with the same nonlinearity problem: averaging `T` over a footprint is not `exp` of the averaged density (inference, see [volumetric RC](2026_volumetric_rc.md)).
