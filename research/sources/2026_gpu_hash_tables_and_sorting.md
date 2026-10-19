# GPU hash tables, spatial hashing, sorting and Morton codes

| Source | Author | Date | Link |
|---|---|---|---|
| Spatial hashing for raytraced ambient occlusion | Kostas Anagnostou (Interplay of Light) | 2025-11-23, updated 2026-02-10 | https://interplayoflight.wordpress.com/2025/11/23/spatial-hashing-for-raytraced-ambient-occlusion/ |
| Maximizing Performance with Massively Parallel Hash Maps on GPUs | Jünger, Iskos, Wang, Hemstad, Hundt, Lan, Nyland (NVIDIA) | 2023-03-06 | https://developer.nvidia.com/blog/maximizing-performance-with-massively-parallel-hash-maps-on-gpus/ ; library https://github.com/NVIDIA/cuCollections |
| A Simple GPU Hash Table | nosferalatu | 2020-03-08 | http://nosferalatu.com/SimpleGPUHashTable.html ; code https://github.com/nosferalatu/SimpleGPUHashTable (read at `d3f5b74`) |
| GPUSorting | b0nes164 (Thomas Smith) | repository read at `09a6081` | https://github.com/b0nes164/GPUSorting |
| Decoding Morton Codes | Fabian Giesen | 2009-12-13 | https://fgiesen.wordpress.com/2009/12/13/decoding-morton-codes/ |

These are the building blocks that sparse and surfel RC designs link for storing probes only where surfaces are: a hash table keyed by cell coordinates, a sort to group work, and Morton codes to order cells ([sparse 3D RC](2026_sparse_and_3d_rc.md), [surfel RC](2025_coppen_surfel_radiance_cascades.md)). All five use only integer atomics, which Godot's `RenderingDevice` compute shaders also have.

## Spatial hashing for ray-traced AO (Interplay of Light)

The post caches AO hit ratios in a world-space hash table whose cells grow with distance, then reuses cached cells instead of tracing new rays.

- Key, as printed: `H(p, s) = h(s + h(floor(p_x/s) + h(floor(p_y/s) + h(floor(p_z/s)))))`, nesting one hash per coordinate. A normal-aware key hashes `floor(n·s_n)` the same way on top; the code uses `floor(normal·3.0)`. The slot is `H % N`.
- The hash is a PCG variant: `state = v·747796405u + 2891336453u; word = ((state >> ((state >> 28) + 4)) ^ state)·277803737u; return (word >> 22) ^ word`.
- A checksum built the same way with xxhash32 (`PRIME32_2 = 2246822519`, `PRIME32_3 = 3266489917`, `PRIME32_4 = 668265263`, `PRIME32_5 = 374761393`) tells cells apart within a slot; it is forced to at least 1 because 0 marks an empty slot. The code multiplies the cell size by 10000 before hashing to spread small sizes.
- Insertion: `InterlockedCompareExchange(hash[idx], 0, checksum, cmp)` succeeds if `cmp` is 0 or the checksum. Linear probing tries 10 slots (`SEARCH_COUNT`); failure returns `0xFFFFFFFF` and the pixel shows a black cell. The post notes rehashing distributes better but linear probing keeps cache locality.
- Each cell packs hits in the top 16 bits and samples in the low 16 bits of one uint, updated with `InterlockedAdd`, so it overflows past 65,535 samples.
- Eviction: a `hashTime` buffer stores each slot's last-use frame, and a slot unused for more than 20 frames is reset and taken over while probing. The stress test used a table of 1M entries.
- Cell size first was a constant 0.1 m (2 m AO radius, one ray per pixel), blocky up close. The distance-based size follows Gautron et al. (SIGGRAPH 2020): `h = d·tan(fov/2)`, `s_w = s_p·2h/R_y`, `s = 2^floor(log2(s_w/s_min))·s_min`, so sizes come in power-of-two steps of `s_min`. Examples use `s_p = 10 px, s_min = 0.4`, and `s_p = 3, s_min = 0.07` with a 10M-cell table for the main image.
- A cell with at least 500 samples skips new rays and returns its cached ratio. With `s_p = 5` this costs 0.4 ms against 1.72 ms for uncached RTAO, which is also noisier and needs a denoiser (RTX 3080 Mobile, 1080p).
- Memory: 1M entries × 4 B × 3 buffers (hash, hashTime, spatialData), "about 11.4 MB".
- Jitter: `worldPos += JitterScale·cellSize·(random tangent and bitangent offset)` before the lookup, removed before tracing, acts as a free spatial filter.
- Limits: static scenes only, and only cells the screen touches are updated.
- Reader comments, unanswered in the text: the table has no guard band, so the last slots get fewer than 10 probes and show black squares; how eviction affects disocclusion noise; how to size the table.

## Parallel hash maps (NVIDIA cuCollections)

- The simplified design has fixed capacity, a sentinel empty key, key plus value of at most 8 bytes and no deletion. Buckets are a flat array of `cuda::std::atomic<pair<K, V>>` with linear probing wrapping at capacity; insertion is a CAS on the bucket, and a duplicate key returns false.
- Cooperative probing: a group of 4 threads loads a window of consecutive buckets in one coalesced read, detects duplicates with `group.any`, finds empty slots with `group.ballot`, elects the lowest with `__ffs` and broadcasts with `shfl`, then advances by the group size.
- On an A100 80GB, groups of 4 give up to 13 % more insert and 40 % more lookup throughput at high load factors; at low load the plain version is close to optimal.
- Random 64-bit read bandwidth (GUPS), peak / measured GB/s: Xeon Platinum 8360Y 204 / 15, A100-80GB 2039 / 141, H100-80GB 3352 / 256.
- 2^27 unique pairs of 4-byte keys and values (1 GB) at 50 % load on an H100-80GB-SXM: `cuco::static_map` inserts at 87.5 GB/s and finds at 134.6 GB/s, 3.8× and 2.6× faster than Kokkos `UnorderedMap`; the fastest CPU maps are more than 10× slower.
- cuDF joins use `cuco::static_multimap` with the row hash as key and the row index as payload, resolving collisions by comparing rows.

## A simple lock-free GPU hash table (nosferalatu)

- 32-bit keys and values, power-of-two capacity, `0xffffffff` reserved as empty for both. The code uses 128M slots at 50 % load, 8 bytes per slot, 1 GiB in all.
- The hash is the 32-bit Murmur3 finalizer: `k ^= k >> 16; k *= 0x85ebca6b; k ^= k >> 13; k *= 0xc2b2ae35; k ^= k >> 16; return k & (cap − 1)`. Only keys and values are stored.
- Insertion: `prev = atomicCAS(&slot.key, kEmpty, key)`; if `prev` is empty or equal to the key, a plain store writes the value; otherwise the next slot is tried, with no bound on the loop. Lookup has no bound either.
- Deletion stores `kEmpty` in the value and leaves the key, so the slot is never reused for another key; re-inserting the same key reuses it.
- The lock-free argument: keys never move, and each slot is in one of four states (empty, key only, both, value seen before key), all valid to observe, so memory ordering does not matter. With duplicate keys in one batch the surviving value is undefined; separate dispatches make it defined.
- No resizing; the suggested method is reinserting into a larger table without deleted entries. Iteration keeps slots whose key and value are both set, through an `atomicAdd` counter into a buffer sized for 64M entries.
- On a GTX 1060 laptop: 64M random inserts in about 210 ms (about 300M/s), 32M deletes in about 64 ms (about 500M/s); 984 ms with copies, allocation and iteration, 271 ms in kernels, against 70,691 ms for `std::unordered_map`.
- Insert time per 4M-key batch against load factor: 0.00 11.61 ms; 0.25 12.88 ms; 0.50 14.69 ms; 0.72 20.28 ms; 0.75 22.55 ms; 0.90 105.70 ms; 0.94 240.20 ms. Probe length averages 0.48 (max 60) at 0.50 load and 10.2 (max 6474) at about 0.97.
- At a 0.25 target load, 768 MB of a 128M-slot table sits unused.

## GPUSorting (b0nes164)

- DeviceRadixSort: 8-bit LSD radix sort, four passes for 32-bit keys (`RADIX_PASSES 4`, `SortCommon.hlsl:55`), with a reduce-then-scan prefix across blocks in separate kernels. The README calls it the portable choice.
- OneSweep: the same binning with a chained scan and decoupled lookback (Merrill and Garland 2016; Adinets and Merrill, arXiv 2206.01784). Predecessor flags are NOT_READY 0, REDUCTION 1, INCLUSIVE 2 (`SweepCommon.hlsl:25-28`), and `Lookback` spins on them (`SweepCommon.hlsl:268-296`). It relies on forward thread-progress guarantees; the author's rule of thumb is that anything except mobile, software rasterizers and Apple has them.
- ForwardSweep (D3D12 and Unity only): OneSweep without the forward-progress requirement. Each wave polls a predecessor flag at most once (`MAX_SPIN_COUNT = 1`); if any wave sees NOT_READY it sets a group-shared flag, and the block recomputes that predecessor's digit histogram from the raw keys and publishes it with `InterlockedCompareExchange` (`LookbackWithFallback`, `SweepCommon.hlsl:317-395`). The fallback needs no cross-block cooperation, but the predecessor keys must stay unmodified during the pass.
- EmulatedDeadlocking (D3D12 and CUDA) emulates GPUs without forward progress, so the fallback path can be tested on any hardware. SplitSort (CUDA) is a proof-of-concept segmented sort.
- Defaults (`SortCommon.hlsl:14-46`): 512 threads per group, 15 keys per thread, 7680 keys per partition, radix 256, 7936 uints of shared memory, at most 65535 groups per dispatch. Wave size is handled at runtime (16 or more lanes versus fewer, with bit-packed histograms below 16); tested on 4, 16, 32 and 64 lanes.
- D3D12 buffers are `globallycoherent` and flags use interlocked stores; a Vulkan port needs the same coherence on the flag buffer (inferred, the repository does not discuss Vulkan).
- Throughput read from the README charts (2^28 uniform random uint32, RTX 2080 Super, elements/s): OneSweep keys 1.09e10 (CUB), 1.10e10 (CUDA), 9.67e9 (D3D12); DeviceRadixSort keys 7.69e9, 7.69e9, 7.38e9; OneSweep pairs 5.15e9, 5.74e9, 5.46e9; DeviceRadixSort pairs 3.40e9, 4.80e9, 4.77e9. On an RX 7900 XT under D3D12: OneSweep keys 1.57e10, DeviceRadixSort keys 1.13e10, pairs 8.17e9 and 6.52e9. FidelityFX ParallelSort reaches about 1.7e9 to 2.1e9 keys/s on the same sweep, where OneSweep reaches 7.6e9 to 9.7e9. ForwardSweep has no published numbers.

## Morton codes (Giesen)

- Encoding: 2D `(Part1By1(y) << 1) + Part1By1(x)` for 16-bit inputs; 3D `(Part1By2(z) << 2) + (Part1By2(y) << 1) + Part1By2(x)` for 10-bit inputs. Decoding applies `Compact1By1` or `Compact1By2` to the code shifted by the axis index.
- `Part1By1`: `x &= 0x0000ffff; x = (x ^ (x << 8)) & 0x00ff00ff; x = (x ^ (x << 4)) & 0x0f0f0f0f; x = (x ^ (x << 2)) & 0x33333333; x = (x ^ (x << 1)) & 0x55555555`.
- `Compact1By1`: `x &= 0x55555555; x = (x ^ (x >> 1)) & 0x33333333; x = (x ^ (x >> 2)) & 0x0f0f0f0f; x = (x ^ (x >> 4)) & 0x00ff00ff; x = (x ^ (x >> 8)) & 0x0000ffff`.
- `Part1By2`: `x &= 0x000003ff; x = (x ^ (x << 16)) & 0xff0000ff; x = (x ^ (x << 8)) & 0x0300f00f; x = (x ^ (x << 4)) & 0x030c30c3; x = (x ^ (x << 2)) & 0x09249249`.
- `Compact1By2`: `x &= 0x09249249; x = (x ^ (x >> 2)) & 0x030c30c3; x = (x ^ (x >> 4)) & 0x0300f00f; x = (x ^ (x >> 8)) & 0xff0000ff; x = (x ^ (x >> 16)) & 0x000003ff`.
- A reimplementation of these masks passed all single-axis cases and 200,000 random 2D and 3D round trips against a bit-by-bit reference.
- Method: for a 1:2 spread, bit N moves 2N places, built from power-of-two moves in turn; a move is safe with XOR only when the target bits are empty. For non-square 2D, Giesen suggests rounding each axis to a power of two and packing the major axis linearly once the minor axis runs out of bits. For 64 bits Giesen recommends generating the masks with a small program.
