# Bevy Solari: ReSTIR GI with a hashed world cache

| | |
|---|---|
| Author | JMS55 |
| Date | 2025-09-20 |
| Kind | Blog post for Bevy 0.17 |
| Link | https://jms55.github.io/posts/2025-09-20-solari-bevy-0-17/ |

Solari is Bevy's hardware ray-traced lighting. It started in 2023 with Lumen-style screen probes, moved to radiance cascades, and was then shelved and rebuilt on ReSTIR with DLSS Ray Reconstruction. The post says screen probes were hard to make look good because one probe is reused and reprojected across many pixels, and that RC "brought their own artifacts and performance costs", with no details. Its world cache is a hashed irradiance cache much like the one Split RC uses.

## World cache

- Cells are found by spatial hashing of the quantized world position (`floor(p/cell + 0.0001)`), the quantized geometric normal (`floor(n + 0.0001)`) and a LOD that grows cells with distance. A PCG hash chain gives the slot and a second hash a checksum; on a mismatch the lookup rehashes to another slot, a bounded number of times. The post picked hashing over clipmaps, cards or bricks because it needs no build step, adapts to geometry and leaks little.
- A query of a live cell returns its irradiance and resets its lifetime. A query of an empty slot claims it and returns zero; the cell starts updating next frame. Each frame every cell's life drops by 1 and it is freed at 0.
- A prefix sum compacts live cells into a list with indirect dispatch arguments.
- Each live cell traces two rays per frame: one light sample chosen by RIS, and one cosine-hemisphere ray that reads the cache at its hit point times the hit's albedo. Light spreads one bounce per frame, so multi-bounce builds up over frames.
- Blend: sample count `min(n + 1, max)` kept in alpha, value `mix(old, new, 1/n)`. The blend runs in its own dispatch so cells that read each other do not race.
- Adding the cache "significantly improved quality" and halved the cost of initial GI samples.

## Known cache problems

- A cell's position and normal are fixed when it is created, so a bad first sample stays. The post names this as the cause of artifacts the author has not solved.
- The voxelized cache loses energy: tracing one more ray toward a random light instead of ending paths at the cache was brighter, despite more noise and no multi-bounce. The post gives no cause beyond "the voxelized nature of the world cache" and suggests reprojecting the last frame for multi-bounce on rays that hit on screen ("Future Work", "GI Quality").
- Bright outlier cells flicker, and the recursive cache with no validation rays leaves trails behind moving lights.

## ReSTIR settings worth reusing

- Neighbor rejection: tangent-plane distance over view depth above 0.003, or normal dot below 0.906 (25°).
- DI: 32 light candidates by RIS, one visibility ray, temporal reuse without re-tracing visibility, one spatial sample in a 30 px disk. One spatial sample beat more, and subgroup or workgroup resampling caused tiling or broke the denoiser.
- GI: one uniform hemisphere ray per pixel, reading the world cache at the hit. Temporal reuse jitters the reprojected position a few pixels to break correlation. The Jacobian for reusing neighbors' samples is the hardest part; neighbors with a Jacobian above 2 are rejected, and it still overflows if left for minutes.

## Timings

RTX 3080, 1600×900 rendered and upscaled to 3200×1800 with DLSS-RR. Totals: PICA PICA 8.2 ms, Bistro 14.5 ms, Cornell box 8.3 ms. DLSS-RR alone takes 5.8 to 6.3 ms. The world cache costs under 0.2 ms except its lighting pass in Bistro (2.1 ms). The main passes are memory bound or limited by ray tracing throughput.
