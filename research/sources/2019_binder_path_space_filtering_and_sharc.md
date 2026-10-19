# Hashed radiance caches: path space filtering and SHaRC

| Source | Authors | Date | Link |
|---|---|---|---|
| Massively Parallel Path Space Filtering | Nikolaus Binder, Sascha Fricke, Alexander Keller (NVIDIA) | 2019 | https://arxiv.org/abs/1902.05942 |
| SHaRC: Spatially Hashed Radiance Cache | NVIDIA | 2023 to 2026 (v1.8.3) | https://github.com/NVIDIA-RTX/SHARC (license forbids use without an NVIDIA agreement) |

Split RC stores probes in per-cascade hash maps, as do Solari's [world cache](2025_jms55_bevy_solari.md) and the [GI-1.0](2023_boisse_gi10_two_level_radiance_cache.md) world cache. These two sources describe the hashing scheme they all descend from, with tested parameters for slot layout, LOD, fixed-point atomics and eviction.

## Contents

- [Path space filtering](#path-space-filtering)
- [SHaRC](#sharc)
  - [Passes](#passes)
  - [Hash grid](#hash-grid)
  - [Fixed-point accumulation](#fixed-point-accumulation)
  - [Resolve](#resolve)
  - [Query rules](#query-rules)

## Path space filtering

- Each path vertex gets a key from a quantized descriptor, and vertices with the same key share one average. One hash lookup replaces a neighbor search, and no motion vectors are needed.
- Voxel size grows with distance from the camera; the paper found it easiest to set it as a multiple of the projected pixel size.
- Including the normal in the key stops smearing across edges. Glossy surfaces add the incident angle; mirrors should not be filtered.
- Positions are jittered in the tangent plane before quantizing, which trades block artifacts for noise that is easier to filter.
- Key build: `l = lod(|cam − x|)`, `x' = x + jitter(n)·s·2^l`, `l' = lod(|cam − x'|)`, cell `floor(x'/(s·2^l'))`; index `hash(cell)`, fingerprint `hash2(cell, n)` (32 bits). Collisions use capped linear probing; on overflow the vertex keeps its own unfiltered value.
- Accumulation: each vertex atomically adds its value and increments a counter. A moving average does not converge in cells with few samples; `α = N_old/(N_old + N_new)` does, but only while the scene is static, so the paper blends between the two with a finite-difference change test.
- Eviction can use one `atomicMin` when the fingerprint's high bits hold a priority (count and age).
- Leaks are the price: averaging across a voxel always risks light and shadow leaking.

## SHaRC

### Passes

1. **Update:** trace a sparse subset of paths (for example one random pixel per 5×5 block, about 4%) and add each vertex's radiance into its cell and the earlier vertices of the path.
2. **Resolve:** one thread per entry blends this frame's sums into the stored value and evicts stale entries.
3. **Query:** at a hit, look up the cell and use its radiance instead of tracing further.

Each pass needs a UAV barrier before the next one touches the cache.

### Hash grid

- Default 64-bit key: 17 bits per axis of the quantized position, 9 bits of level, 3 normal sign bits, one spare bit. A compact 32-bit key uses 8 bits per axis.
- Level from distance: `level = clamp(0.5·log_b(dist²) + bias, 1, 511)` with base 2, and voxel size `b^(level − bias)/sceneScale`. Position `floor((p + 1e−4)/voxelSize)`.
- Slot `Jenkins32(lo) ^ Jenkins32(hi)` modulo `capacity − 15`, then a 16-slot bucket probed linearly without wrapping. Key 0 marks an empty slot. Insert uses a 64-bit atomic compare-exchange (or a lock buffer when 64-bit atomics are missing).
- Memory: 8 bytes of key, 16 bytes of accumulation (`uint` RGB sums and count) and 16 bytes of resolved data (half RGB, count, age), 40 bytes per entry. The baseline is 2²² entries (160 MiB); a static camera uses about 10 to 20% of them.

### Fixed-point accumulation

Radiance is added as `uint(radiance·weight·scale)` with `InterlockedAdd`, with `scale` starting at 1000 and lowered for bright scenes to avoid overflow. This is the same portable integer-atomic approach Split RC uses.

### Resolve

- An entry with no samples for `staleFrameNumMax` frames (at least 8) is evicted.
- Blend: `rad = (prev·Nprev + cur·Ncur)/(Nprev + Ncur)`, with `Nprev` rescaled so the history covers at most `accumulationFrameNum` frames.
- When an entry is new and the camera moved, history is borrowed from the same cell one level coarser or finer, so LOD changes do not reset lighting.
- An optional directional mode stores luma as L1 SH (YCoCg) to keep glossy light from leaking into other directions.

### Query rules

- Skip the cache at the primary hit.
- Use it only when the path segment is longer than the voxel, or the glossy lobe's spread `2·len·sqrt(0.5a²/(1 − a²))` exceeds it; otherwise keep tracing.
