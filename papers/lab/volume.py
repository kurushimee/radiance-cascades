"""Voxel scenes, a GPU ray tracer, and dense-grid 3D radiance cascades with switchable merges.

A scene is a cube of n^3 unit voxels, voxel (i, j, k) spanning [i, i+1) x [j, j+1) x [k, k+1). Solid voxels are
opaque and emit a constant radiance in every direction; rays that leave the cube see the sky. Rays walk the grid
voxel by voxel (Amanatides and Woo's DDA) in CUDA, one thread per ray.

Cascade c has probes at (i + 0.5) * 2**c, M_c = n0 * 4**c directions on a nested equal-area cylindrical map (2m
azimuth by m height cells, m = sqrt(n0/2) * 2**c), and the interval [t0 * 4**(c-1), t0 * 4**c]; cascade 0 starts at 0
and the top cascade runs to infinity. Each texel stores the merged radiance of its bin and the merged depth, the
distance from its probe to the hit along the bin's centre ray, measured when the ray hits and estimated from the
parents when it misses.
"""
import math
from dataclasses import dataclass

import cupy as cp
import numpy as np

CHUNK = 1 << 22
MERGES = ("vanilla", "parallax", "fixed_depth", "depth", "depth_surface", "hit_distance", "visibility_rays",
          "inner_fix", "self_test", "depth_self_test", "trilinear_fix", "kuhn_fix", "sphere_fix")
BENT = MERGES.index("trilinear_fix")  # merges from here on trace their own rays instead of the straight one

_SOURCE = r"""
#define INF __int_as_float(0x7f800000)
#define PI 3.14159265358979f

struct Hit { float t; int voxel; int face; int steps; };

__device__ float3 operator+(float3 a, float3 b) { return make_float3(a.x + b.x, a.y + b.y, a.z + b.z); }
__device__ float3 operator-(float3 a, float3 b) { return make_float3(a.x - b.x, a.y - b.y, a.z - b.z); }
__device__ float3 operator*(float s, float3 a) { return make_float3(s * a.x, s * a.y, s * a.z); }
__device__ float dot(float3 a, float3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
__device__ float component(float3 a, int k) { return k == 0 ? a.x : (k == 1 ? a.y : a.z); }

// First solid voxel along o + t*d, tmin <= t <= tmax, after clipping the ray to the cube [0, n]^3.
__device__ Hit march(const unsigned char* solid, int n, float3 o, float3 d, float tmin, float tmax) {
    Hit hit = {INF, -1, -1, 0};
    float t = tmin, t_end = tmax;
    int entered = -1;
    for (int k = 0; k < 3; ++k) {
        float ok = component(o, k), dk = component(d, k);
        if (dk == 0.0f) {
            if (ok < 0.0f || ok >= n) return hit;
            continue;
        }
        float a = -ok / dk, b = (n - ok) / dk;
        float near = fminf(a, b);
        if (near > t) { t = near; entered = k; }
        t_end = fminf(t_end, fmaxf(a, b));
    }
    if (t > t_end) return hit;

    int cell[3], step[3];
    float next[3], delta[3];
    for (int k = 0; k < 3; ++k) {
        float dk = component(d, k), pk = component(o, k) + t * dk;
        cell[k] = min(max((int)floorf(pk), 0), n - 1);
        step[k] = dk > 0.0f ? 1 : -1;
        delta[k] = dk != 0.0f ? fabsf(1.0f / dk) : INF;
        next[k] = dk != 0.0f ? t + ((float)(cell[k] + (dk > 0.0f)) - pk) / dk : INF;
    }
    while (t <= t_end) {
        if (cell[0] < 0 || cell[1] < 0 || cell[2] < 0 || cell[0] >= n || cell[1] >= n || cell[2] >= n) return hit;
        ++hit.steps;
        int index = (cell[0] * n + cell[1]) * n + cell[2];
        if (solid[index]) {
            hit.t = t;
            hit.voxel = index;
            hit.face = entered < 0 ? -1 : 2 * entered + (step[entered] < 0);
            return hit;
        }
        int k = next[0] < next[1] ? (next[0] < next[2] ? 0 : 2) : (next[1] < next[2] ? 1 : 2);
        t = next[k];
        cell[k] += step[k];
        next[k] += delta[k];
        entered = k;
    }
    return hit;
}

extern "C" __global__
void dda(const unsigned char* solid, const int n, const float* origin, const float* dir, const float* tmin,
         const float* tmax, const long long count, int* voxel, float* thit, signed char* face) {
    long long i = (long long)blockDim.x * blockIdx.x + threadIdx.x;
    if (i >= count) return;
    float3 o = make_float3(origin[3 * i], origin[3 * i + 1], origin[3 * i + 2]);
    float3 d = make_float3(dir[3 * i], dir[3 * i + 1], dir[3 * i + 2]);
    Hit hit = march(solid, n, o, d, tmin[i], tmax[i]);
    voxel[i] = hit.voxel;
    thit[i] = hit.t;
    face[i] = hit.face;
}

__device__ unsigned long long mix(unsigned long long z) {
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

// Fluence at each point from one jittered ray in each cell of a 2r x r equal-area map: one block per point.
extern "C" __global__
void sphere_mean(const unsigned char* solid, const float* emission, const int n, const float sky,
                 const float* points, const int r, const unsigned long long seed, double* fluence) {
    __shared__ double partial[256];
    int point = blockIdx.x;
    float3 o = make_float3(points[3 * point], points[3 * point + 1], points[3 * point + 2]);
    int cells = 2 * r * r;
    double sum = 0.0;
    for (int cell = threadIdx.x; cell < cells; cell += blockDim.x) {
        unsigned long long z = mix(seed ^ mix(((unsigned long long)point << 32) | (unsigned)cell));
        float u1 = (z >> 40) * (1.0f / 16777216.0f), u2 = ((z >> 16) & 0xffffff) * (1.0f / 16777216.0f);
        float phi = ((cell / r) + u1) * PI / r, h = -1.0f + ((cell % r) + u2) * 2.0f / r;
        float s = sqrtf(fmaxf(0.0f, 1.0f - h * h));
        Hit hit = march(solid, n, o, make_float3(s * cosf(phi), s * sinf(phi), h), 0.0f, INF);
        sum += hit.voxel >= 0 ? emission[hit.voxel] : sky;
    }
    partial[threadIdx.x] = sum;
    __syncthreads();
    for (int half = blockDim.x / 2; half > 0; half /= 2) {
        if (threadIdx.x < half) partial[threadIdx.x] += partial[threadIdx.x + half];
        __syncthreads();
    }
    if (threadIdx.x == 0) fluence[point] = 4.0 * PI * partial[0] / cells;
}

// The direction map is turned by the rotation R (row-major): R maps map coordinates to world coordinates.
__device__ float3 bin_direction(const float* R, int bin, int m) {
    float phi = (bin / m + 0.5f) * PI / m, h = -1.0f + (bin % m + 0.5f) * 2.0f / m;
    float s = sqrtf(fmaxf(0.0f, 1.0f - h * h));
    float3 d = make_float3(s * cosf(phi), s * sinf(phi), h);
    return make_float3(R[0] * d.x + R[1] * d.y + R[2] * d.z, R[3] * d.x + R[4] * d.y + R[5] * d.z,
                       R[6] * d.x + R[7] * d.y + R[8] * d.z);
}

__device__ float3 map_coordinates(const float* R, float3 u) {
    return make_float3(R[0] * u.x + R[3] * u.y + R[6] * u.z, R[1] * u.x + R[4] * u.y + R[7] * u.z,
                       R[2] * u.x + R[5] * u.y + R[8] * u.z);
}

__device__ int direction_bin(const float* R, float3 u, int m) {
    u = map_coordinates(R, u);
    float phi = atan2f(u.y, u.x);
    if (phi < 0.0f) phi += 2.0f * PI;
    int j = min((int)(phi * m / PI), 2 * m - 1), k = min(max((int)((u.z + 1.0f) * 0.5f * m), 0), m - 1);
    return j * m + k;
}

// The four bins of a 2m x m map around direction u, with bilinear weights over the bin centres.
__device__ void around(const float* R, float3 u, int m, int* bins, float* weights) {
    u = map_coordinates(R, u);
    float phi = atan2f(u.y, u.x);
    if (phi < 0.0f) phi += 2.0f * PI;
    float x = phi * m / PI - 0.5f, y = (u.z + 1.0f) * 0.5f * m - 0.5f;
    int j = (int)floorf(x), k = (int)floorf(y);
    float fx = x - j, fy = y - k;
    int j0 = (j + 2 * m) % (2 * m), j1 = (j + 1) % (2 * m), k0 = max(k, 0), k1 = min(k + 1, m - 1);
    bins[0] = j0 * m + k0; weights[0] = (1.0f - fx) * (1.0f - fy);
    bins[1] = j1 * m + k0; weights[1] = fx * (1.0f - fy);
    bins[2] = j0 * m + k1; weights[2] = (1.0f - fx) * fy;
    bins[3] = j1 * m + k1; weights[3] = fx * fy;
}

// A probe's radiance interpolated between bin centres toward direction u.
__device__ float sample(const float* R, const float* probe_row, float3 u, int m) {
    int bins[4];
    float weights[4];
    around(R, u, m, bins, weights);
    return weights[0] * probe_row[bins[0]] + weights[1] * probe_row[bins[1]] + weights[2] * probe_row[bins[2]]
         + weights[3] * probe_row[bins[3]];
}

__device__ int child_bin(int bin, int m, int child) {
    return (2 * (bin / m) + child / 2) * (2 * m) + 2 * (bin % m) + child % 2;
}

// Inverse of the depth along the lower line from p, for a parent at q seeing a hit at depth d along w; the
// estimate assumes the hit surface faces w, and is never nearer than the lower interval's end.
__device__ float inverse_depth(float d, float3 q, float3 p, float3 w, float t_end) {
    return isinf(d) ? 0.0f : 1.0f / fmaxf(d + dot(q - p, w), t_end);
}

// Where the ray p + t*w, t >= t_start, leaves the sphere of radius r around q, or INF if it never does.
__device__ float sphere_exit(float3 p, float3 w, float3 q, float r, float t_start) {
    float3 offset = p - q;
    float b = dot(offset, w), disc = b * b - dot(offset, offset) + r * r;
    float t = disc >= 0.0f ? -b + sqrtf(disc) : -INF;
    return t >= t_start ? t : INF;
}

enum { VANILLA, PARALLAX, FIXED_DEPTH, DEPTH, DEPTH_SURFACE, HIT_DISTANCE, VISIBILITY_RAYS, INNER_FIX, SELF_TEST,
       DEPTH_SELF_TEST, TRILINEAR_FIX, KUHN_FIX, SPHERE_FIX };

struct Parents { int index[8]; float3 position[8]; float weight[8]; int count; };

// Trilinear corners of the upper grid around p, or the corners of the enclosing Kuhn tetrahedron.
__device__ Parents parents(float3 p, const int* g, float h, bool kuhn) {
    Parents out;
    int base[3];
    float frac[3];
    for (int k = 0; k < 3; ++k) {
        float f = component(p, k) / h - 0.5f;
        base[k] = (int)floorf(f);
        frac[k] = f - base[k];
    }
    int corner[8][3], count = 0;
    float weight[8];
    if (kuhn) {
        int order[3] = {0, 1, 2};
        for (int a = 0; a < 3; ++a)
            for (int b = a + 1; b < 3; ++b)
                if (frac[order[b]] > frac[order[a]]) { int s = order[a]; order[a] = order[b]; order[b] = s; }
        int c[3] = {0, 0, 0};
        float previous = 1.0f;
        for (int v = 0; v <= 3; ++v) {
            float next = v < 3 ? frac[order[v]] : 0.0f;
            if (previous - next > 1e-6f) {
                corner[count][0] = c[0]; corner[count][1] = c[1]; corner[count][2] = c[2];
                weight[count++] = previous - next;
            }
            if (v < 3) c[order[v]] = 1;
            previous = next;
        }
    } else {
        for (int v = 0; v < 8; ++v) {
            int c[3] = {v >> 2, (v >> 1) & 1, v & 1};
            corner[count][0] = c[0]; corner[count][1] = c[1]; corner[count][2] = c[2];
            weight[count++] = (c[0] ? frac[0] : 1 - frac[0]) * (c[1] ? frac[1] : 1 - frac[1])
                            * (c[2] ? frac[2] : 1 - frac[2]);
        }
    }
    for (int v = 0; v < count; ++v) {
        int i[3] = {base[0] + corner[v][0], base[1] + corner[v][1], base[2] + corner[v][2]};
        out.index[v] = ((i[0] - g[0]) * g[4] + (i[1] - g[1])) * g[5] + (i[2] - g[2]);
        out.position[v] = make_float3((i[0] + 0.5f) * h, (i[1] + 0.5f) * h, (i[2] + 0.5f) * h);
        out.weight[v] = weight[v];
    }
    out.count = count;
    return out;
}

__device__ float3 probe_position(int probe, const int* g, float h) {
    int iz = probe % g[5], iy = (probe / g[5]) % g[4], ix = probe / (g[5] * g[4]);
    return make_float3((g[0] + ix + 0.5f) * h, (g[1] + iy + 0.5f) * h, (g[2] + iz + 0.5f) * h);
}

// Traced rays, DDA voxel visits, upper and own texel reads, visibility tests and the tests that dropped a parent.
__device__ void count(unsigned long long* counters, unsigned long long rays, unsigned long long steps,
                      unsigned long long reads, unsigned long long tests = 0, unsigned long long drops = 0) {
    atomicAdd(&counters[0], rays);
    atomicAdd(&counters[1], steps);
    atomicAdd(&counters[2], reads);
    atomicAdd(&counters[3], tests);
    atomicAdd(&counters[4], drops);
}

// Each texel's own ray over its interval: the radiance it hits (the sky past an infinite interval) and the distance.
extern "C" __global__
void trace_texels(const unsigned char* solid, const float* emission, const int n, const float sky, const int* g,
                  const float h, const int m, const float* R, const float t_start, const float t_end, float* radiance,
                  float* hit,
                  unsigned long long* counters) {
    int bins = 2 * m * m;
    long long tid = (long long)blockDim.x * blockIdx.x + threadIdx.x;
    if (tid >= (long long)g[3] * g[4] * g[5] * bins) return;
    float3 p = probe_position(tid / bins, g, h);
    Hit first = march(solid, n, p, bin_direction(R, tid % bins, m), t_start, t_end);
    radiance[tid] = first.voxel >= 0 ? emission[first.voxel] : (isinf(t_end) ? sky : 0.0f);
    hit[tid] = first.t;
    count(counters, 1, first.steps, 0);
}

// Merged radiance and depth of one texel of cascade c from the upper cascade, whose intervals start t_join
// from their probes.
extern "C" __global__
void merge(const unsigned char* solid, const float* emission, const int n, const int* g, const float h, const int m,
           const float* R, const float t_start, const float t_join, const float* own_radiance, const float* own_hit,
           const int* ug, const float* up_radiance, const float* up_depth, const float* up_hit,
           const float upper_end, const int mode, const float tau, float* radiance, float* depth,
           unsigned long long* counters) {
    int bins = 2 * m * m, up_bins = 4 * bins;
    long long tid = (long long)blockDim.x * blockIdx.x + threadIdx.x;
    if (tid >= (long long)g[3] * g[4] * g[5] * bins) return;
    int probe = tid / bins, bin = tid % bins;
    float3 p = probe_position(probe, g, h), w = bin_direction(R, bin, m);
    unsigned long long rays = 0, steps = 0, reads = 0, tests = 0, drops = 0;
    float out_radiance = 0.0f, out_inverse = 0.0f;

    if (mode < TRILINEAR_FIX) {
        if (mode != INNER_FIX && !isinf(own_hit[tid])) {
            radiance[tid] = own_radiance[tid];
            depth[tid] = own_hit[tid];
            return;
        }
        Parents up = parents(p, ug, 2.0f * h, false);
        bool visible[8];
        for (int v = 0; v < up.count; ++v) {
            visible[v] = true;
            float3 q = up.position[v];
            if (mode == HIT_DISTANCE) {
                float3 to_child = p - q;
                float distance = sqrtf(dot(to_child, to_child));
                int toward = direction_bin(R, (1.0f / distance) * to_child, 2 * m);
                visible[v] = up_hit[(long long)up.index[v] * up_bins + toward] >= distance - 0.5f;
                ++reads;
                ++tests;
                drops += !visible[v];
            }
            if (mode == VISIBILITY_RAYS) {
                float3 o = p + t_join * w, gap = q - p;
                float length = sqrtf(dot(gap, gap));
                Hit blocked = march(solid, n, o, (1.0f / length) * gap, 0.0f, length);
                ++rays;
                steps += blocked.steps;
                visible[v] = blocked.voxel < 0;
                ++tests;
                drops += !visible[v];
            }
        }
        bool by_depth = mode == DEPTH || mode == DEPTH_SURFACE || mode == DEPTH_SELF_TEST;
        bool self_test = mode == SELF_TEST || mode == DEPTH_SELF_TEST;
        for (int child = 0; child < 4; ++child) {
            int cbin = child_bin(bin, m, child);
            float3 wc = bin_direction(R, cbin, 2 * m);
            // DEPTH averages inverse depth over all parents, the sky counting as infinitely far; the others average
            // depth over the parents that see a surface, which is exact for a plane all of them see.
            float inverse = 0.0f, surface = 0.0f, surface_weight = 0.0f;
            for (int v = 0; v < up.count; ++v) {
                float d = up_depth[(long long)up.index[v] * up_bins + cbin];
                inverse += up.weight[v] * inverse_depth(d, up.position[v], p, wc, t_join);
                if (isinf(d)) continue;
                surface += up.weight[v] * (d + dot(up.position[v] - p, wc));
                surface_weight += up.weight[v];
            }
            if (mode == DEPTH_SURFACE || mode == DEPTH_SELF_TEST)
                inverse = surface_weight > 0.0f ? 1.0f / fmaxf(surface / surface_weight, t_join) : 0.0f;
            float reach = INF;
            if (mode == PARALLAX) reach = t_join;
            if (mode == FIXED_DEPTH && !isinf(upper_end)) reach = sqrtf(t_join * upper_end);
            if (by_depth) {
                reads += up.count;
                if (inverse > 0.0f) reach = 1.0f / inverse;
            }
            float kept = 0.0f, kept_weight = 0.0f, all = 0.0f, blocked = 0.0f;
            for (int v = 0; v < up.count; ++v) {
                float3 q = up.position[v], u = wc;
                if (!isinf(reach)) {
                    float3 to_hit = p + reach * wc - q;
                    u = (1.0f / sqrtf(dot(to_hit, to_hit))) * to_hit;
                }
                const float* row = up_radiance + (long long)up.index[v] * up_bins;
                float value = isinf(reach) ? row[cbin] : sample(R, row, u, 2 * m);
                reads += isinf(reach) ? 1 : 4;
                if (mode == INNER_FIX) {
                    // The lower probe's own interval, read toward the start of the parent's ray, in front of it.
                    float3 start = q + t_join * wc - p;
                    int near[4];
                    float weights[4], own = 0.0f, open = 0.0f;
                    around(R, (1.0f / sqrtf(dot(start, start))) * start, m, near, weights);
                    for (int i = 0; i < 4; ++i) {
                        long long texel = (long long)probe * bins + near[i];
                        own += weights[i] * own_radiance[texel];
                        open += weights[i] * isinf(own_hit[texel]);
                    }
                    value = own + open * value;
                    reads += 4;
                }
                all += up.weight[v] * value;
                bool keep = visible[v];
                if (self_test) {
                    // Whether the lower probe's own ray toward the start of the parent's ray reached it.
                    float3 start = q + t_join * u - p;
                    float distance = sqrtf(dot(start, start));
                    long long seen = (long long)probe * bins + direction_bin(R, (1.0f / distance) * start, m);
                    keep = own_hit[seen] >= distance - tau;
                    if (!keep) blocked += up.weight[v] * own_radiance[seen];
                    ++reads;
                    ++tests;
                    drops += !keep;
                }
                if (keep) {
                    kept += up.weight[v] * value;
                    kept_weight += up.weight[v];
                }
            }
            // With every parent dropped, the hit-distance test keeps them all, as its source's tiny weight does,
            // visibility rays return nothing, as in their source, and the self test returns what the lower probe
            // saw in front of the parents.
            float fallback = mode == HIT_DISTANCE ? all : (self_test ? blocked : 0.0f);
            out_radiance += 0.25f * (kept_weight > 0.0f ? kept / kept_weight : fallback);
            out_inverse += 0.25f * inverse;
        }
    } else {
        Parents up = parents(p, ug, 2.0f * h, mode == KUHN_FIX);
        float reach[8], longest = t_join;
        for (int v = 0; v < up.count; ++v) {
            float exit = mode == SPHERE_FIX ? sphere_exit(p, w, up.position[v], t_join, t_start) : INF;
            reach[v] = isinf(exit) ? t_join : exit;
            longest = fmaxf(longest, reach[v]);
        }
        Hit straight = {INF, -1, -1, 0};
        if (mode == SPHERE_FIX) {
            straight = march(solid, n, p, w, t_start, longest);
            rays = 1;
            steps = straight.steps;
        }
        for (int v = 0; v < up.count; ++v) {
            float3 q = up.position[v];
            Hit hit = straight;
            bool blocked = hit.voxel >= 0 && hit.t <= reach[v];
            if (mode != SPHERE_FIX) {
                float3 o = p + t_start * w, to_end = q + t_join * w - o;
                float length = sqrtf(dot(to_end, to_end));
                float3 d = (1.0f / length) * to_end;
                hit = march(solid, n, o, d, 0.0f, length);
                ++rays;
                steps += hit.steps;
                blocked = hit.voxel >= 0;
                if (blocked) {
                    float3 at = o + hit.t * d - p;
                    hit.t = sqrtf(dot(at, at));
                }
            }
            if (blocked) {
                out_radiance += up.weight[v] * emission[hit.voxel];
                out_inverse += up.weight[v] / hit.t;
                continue;
            }
            float value = 0.0f, inverse = 0.0f;
            const float* row = up_radiance + (long long)up.index[v] * up_bins;
            for (int child = 0; child < 4; ++child) {
                int cbin = child_bin(bin, m, child);
                float3 wc = bin_direction(R, cbin, 2 * m);
                float exit = mode == SPHERE_FIX ? sphere_exit(p, wc, q, t_join, t_start) : INF;
                value += 0.25f * (isinf(exit) ? row[cbin] : sample(R, row, (1.0f / t_join) * (p + exit * wc - q), 2 * m));
                inverse += 0.25f * inverse_depth(up_depth[(long long)up.index[v] * up_bins + cbin], q, p, wc, t_join);
                reads += isinf(exit) ? 1 : 4;
            }
            out_radiance += up.weight[v] * value;
            out_inverse += up.weight[v] * inverse;
        }
    }
    radiance[tid] = out_radiance;
    depth[tid] = out_inverse > 0.0f ? 1.0f / out_inverse : INF;
    count(counters, rays, steps, reads, tests, drops);
}
"""

_MODULE = cp.RawModule(code=_SOURCE)
_DDA, _SPHERE_MEAN, _TRACE, _MERGE = (_MODULE.get_function(name)
                                      for name in ("dda", "sphere_mean", "trace_texels", "merge"))


@dataclass
class Volume:
    solid: np.ndarray       # (n, n, n) bool
    emission: np.ndarray    # (n, n, n) radiance leaving each solid voxel
    sky: float = 0.0

    @classmethod
    def empty(cls, n, sky=0.0):
        return cls(np.zeros((n, n, n), bool), np.zeros((n, n, n)), sky)

    @property
    def n(self):
        return self.solid.shape[0]

    def box(self, lo, hi, radiance=0.0):
        """Fills the voxels of [lo, hi) with solid of the given radiance."""
        region = tuple(slice(a, b) for a, b in zip(lo, hi))
        self.solid[region] = True
        self.emission[region] = radiance
        return self

    def inside_solid(self, points):
        cells = np.floor(points).astype(int)
        inside = np.all((cells >= 0) & (cells < self.n), axis=-1)
        result = np.zeros(len(points), bool)
        result[inside] = self.solid[tuple(cells[inside].T)]
        return result

    def device(self):
        return cp.asarray(self.solid, dtype=cp.uint8), cp.asarray(self.emission, dtype=cp.float32).ravel()


def trace(volume, origins, dirs, tmin, tmax):
    """First solid voxel along each ray `origin + t*dir`, `tmin <= t <= tmax`, on the GPU.

    Returns device arrays (radiance, hit, t, voxel, face). A ray that hits nothing returns radiance 0, or the sky if
    `tmax` is infinite. `voxel` is the flat index of the hit voxel or -1; `face` is 2*axis + (normal points to +axis),
    or -1 when the interval starts inside the solid.
    """
    solid, emission = volume.device()
    origins, dirs = cp.asarray(origins, cp.float32), cp.asarray(dirs, cp.float32)
    count = len(origins)
    tmin = cp.broadcast_to(cp.asarray(tmin, cp.float32), (count,))
    tmax = cp.broadcast_to(cp.asarray(tmax, cp.float32), (count,))
    voxel, t, face = cp.empty(count, cp.int32), cp.empty(count, cp.float32), cp.empty(count, cp.int8)
    for lo in range(0, count, CHUNK):
        chunk = slice(lo, min(lo + CHUNK, count))
        size = chunk.stop - chunk.start
        _DDA(((size + 255) // 256,), (256,),
             (solid, np.int32(volume.n), cp.ascontiguousarray(origins[chunk]), cp.ascontiguousarray(dirs[chunk]),
              cp.ascontiguousarray(tmin[chunk]), cp.ascontiguousarray(tmax[chunk]), np.int64(size),
              voxel[chunk], t[chunk], face[chunk]))
    hit = voxel >= 0
    radiance = cp.where(hit, emission[cp.maximum(voxel, 0)], cp.where(cp.isinf(tmax), volume.sky, 0.0))
    return radiance, hit, t, voxel, face


def reference_fluence(volume, points, r=64, seed=0):
    """Fluence at each point from 2r^2 stratified jittered rays, on the GPU; returns a host array."""
    solid, emission = volume.device()
    points = cp.asarray(points, cp.float32)
    out = cp.empty(len(points), cp.float64)
    _SPHERE_MEAN((len(points),), (256,), (solid, emission, np.int32(volume.n), np.float32(volume.sky), points,
                                          np.int32(r), np.uint64(seed), out))
    return out.get()


def box_solid_angle(points, lo, hi):
    """Exact solid angle of the box [lo, hi] seen from each point outside it: the sum over its faces that face the
    point of the rectangle formula."""
    points, lo, hi = (np.asarray(a, float) for a in (points, lo, hi))
    total = np.zeros(len(points))
    for axis in range(3):
        u, v = (a for a in range(3) if a != axis)
        for plane, facing in ((lo[axis], points[:, axis] < lo[axis]), (hi[axis], points[:, axis] > hi[axis])):
            z = np.abs(points[:, axis] - plane)
            for su, a in ((1, hi[u]), (-1, lo[u])):
                for sv, b in ((1, hi[v]), (-1, lo[v])):
                    x, y = a - points[:, u], b - points[:, v]
                    with np.errstate(divide="ignore", invalid="ignore"):
                        term = np.arctan(x * y / (z * np.sqrt(x * x + y * y + z * z)))
                    total += np.where(facing, su * sv * term, 0.0)
    return total


@dataclass(frozen=True)
class Params:
    """Cascade c has probe spacing 2**c, n0 * 4**c directions, and the interval [t0 * 4**(c-1), t0 * 4**c] whose end
    `overlap` extends by that many upper probe spacings."""

    n0: int = 32
    t0: float = math.sqrt(32 / (4 * math.pi))
    levels: int = 4
    overlap: float = 0.0
    rotation: tuple = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)  # row-major, from map to world coordinates

    @property
    def m0(self):
        m = math.isqrt(self.n0 // 2)
        assert 2 * m * m == self.n0, "n0 must be 2 m^2"
        return m

    def directions(self, c):
        return self.n0 * 4 ** c

    def boundary(self, c):
        return self.t0 * 4.0 ** c

    def interval(self, c):
        start = 0.0 if c == 0 else self.boundary(c - 1)
        end = math.inf if c == self.levels - 1 else self.boundary(c) + self.overlap * 2.0 ** (c + 1)
        return start, end


def generic_rotation(seed=3):
    """A fixed rotation of the direction map, so that no bin direction lines up with the voxel axes."""
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return tuple(float(x) for x in q.ravel())


def levels_for(n, t0):
    """Cascade count that puts the top cascade's start at the last hand-over inside the cube."""
    return max(2, math.ceil(math.log(n * math.sqrt(3) / t0) / math.log(4)) + 1)


def grids(params, n):
    """Per cascade, (first probe index, probe counts) per axis: cascade 0 covers the voxels, each upper grid the
    trilinear lookups of the one below."""
    out = [(np.zeros(3, int), np.full(3, n))]
    for c in range(1, params.levels):
        start, count = out[-1]
        h = 2.0 ** c
        lo = np.floor(((start + 0.5) * 2.0 ** (c - 1)) / h - 0.5).astype(int)
        hi = np.floor(((start + count - 0.5) * 2.0 ** (c - 1)) / h - 0.5).astype(int) + 2
        out.append((lo, hi - lo))
    return out


def cascades(volume, params, merge="vanilla", tau=0.5, merges=None):
    """Radiance cascades over the volume. `merges` may name a merge per cascade below the top, overriding `merge`;
    `tau` is the self test's tolerance in lower probe spacings.

    Returns, from cascade 0 up, each cascade's merged radiance, merged depth and own hit distance as device arrays of
    shape (probes, directions), and the cost summed over cascades: traced rays, DDA voxel visits, texel reads,
    visibility tests and the tests that dropped a parent.
    """
    merges = merges or [merge] * (params.levels - 1)
    solid, emission = volume.device()
    rotation = cp.asarray(params.rotation, cp.float32)
    counters = cp.zeros(5, cp.uint64)
    levels = []
    for c, (start, count) in reversed(list(enumerate(grids(params, volume.n)))):
        g = cp.asarray(np.concatenate([start, count]), cp.int32)
        h, m = 2.0 ** c, params.m0 * 2 ** c
        texels = int(np.prod(count)) * params.directions(c)
        blocks = ((texels + 255) // 256,)
        t_start, t_end = params.interval(c)
        own_radiance, own_hit = cp.empty(texels, cp.float32), cp.empty(texels, cp.float32)
        traced = cp.zeros(5, cp.uint64)
        _TRACE(blocks, (256,), (solid, emission, np.int32(volume.n), np.float32(volume.sky), g, np.float32(h),
                                np.int32(m), rotation, np.float32(t_start), np.float32(t_end), own_radiance, own_hit,
                                traced))
        radiance, depth = own_radiance, own_hit
        if levels:
            mode = MERGES.index(merges[c])
            if mode < BENT:
                counters += traced
            radiance, depth = cp.empty(texels, cp.float32), cp.empty(texels, cp.float32)
            upper = levels[-1]
            _MERGE(blocks, (256,), (solid, emission, np.int32(volume.n), g, np.float32(h), np.int32(m), rotation,
                                    np.float32(t_start), np.float32(params.boundary(c)), own_radiance, own_hit,
                                    upper["grid"], upper["radiance"], upper["depth"], upper["hit"],
                                    np.float32(upper["end"]), np.int32(mode), np.float32(tau * h), radiance, depth,
                                    counters))
        else:
            counters += traced
        shape = (-1, params.directions(c))
        levels.append({"grid": g, "end": t_end, "radiance": radiance.reshape(shape), "depth": depth.reshape(shape),
                       "hit": own_hit.reshape(shape)})
    cost = dict(zip(("rays", "steps", "reads", "tests", "drops"), (int(v) for v in counters.get())))
    return levels[::-1], cost


def solve(volume, params, merge="vanilla", tau=0.5, merges=None):
    """Fluence at every voxel centre from cascade 0 (host array, (n, n, n)), and the cost, as for `cascades`."""
    levels, cost = cascades(volume, params, merge, tau, merges)
    fluence = levels[0]["radiance"].sum(1) * (4 * math.pi / params.directions(0))
    return fluence.reshape((volume.n,) * 3).get(), cost


def bin_directions(params, c):
    """Centre directions of cascade c's bins, in bin order."""
    m = params.m0 * 2 ** c
    phi = (np.arange(2 * m)[:, None] + 0.5) * math.pi / m
    z = -1 + (np.arange(m)[None] + 0.5) * 2 / m
    s = np.sqrt(1 - z * z)
    local = np.stack(np.broadcast_arrays(s * np.cos(phi), s * np.sin(phi), z), -1).reshape(-1, 3)
    return local @ np.reshape(params.rotation, (3, 3)).T


def probe_positions(params, n, c):
    start, count = grids(params, n)[c]
    axes = [(start[k] + np.arange(count[k]) + 0.5) * 2.0 ** c for k in range(3)]
    return np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
