"""Later bounces from a coarser solve in flatland: the first bounce from the full solve, every later one from a solve
one or two levels coarser, against re-merging the full solve (Table 3)."""
import numpy as np

from common import MERGES, OFFSETS, SCENES, Flat, cached, params, rd, relative_rmse

ALBEDOS = (0.5, 0.9)
SPACINGS = (1.0, 2.0, 4.0)


def compare(flat, fine, coarse, albedo):
    """Errors of the second bounce and of the converged solution when bounces after the first use `coarse`."""
    E, sky, where = flat.patches.emission, flat.sky, flat.receivers
    K = flat.bounce_matrix(flat.exact, albedo)
    first, first_hat = K @ np.append(E, sky), flat.bounce_matrix(fine, albedo) @ np.append(E, sky)
    later = flat.bounce_matrix(coarse, albedo)[:, :-1]
    second, second_hat = K[:, :-1] @ first, later @ first_hat
    indirect = np.linalg.solve(np.eye(len(E)) - later, first_hat)
    return {"second": relative_rmse(second_hat, second, where),
            "second_share": float(second_hat[where].sum() / second[where].sum()),
            "converged": relative_rmse(E + indirect, rd.converged(K, E, sky), where)}


def compute():
    out = {}
    for name in SCENES:
        flat = Flat(name)
        for merge in MERGES:
            for ds0 in SPACINGS:
                rows = []
                for offset in OFFSETS:
                    fine, _ = flat.estimate(params(), merge, offset)
                    coarse, rays = flat.estimate(params(ds0=ds0), merge, offset) if ds0 > 1 else (fine, _)
                    rows += [dict(compare(flat, fine, coarse, a), albedo=a, rays=rays) for a in ALBEDOS]
                for a in ALBEDOS:
                    chosen = [r for r in rows if r["albedo"] == a]
                    out[f"{name}/{merge}/{ds0}/{a}"] = {key: float(np.mean([r[key] for r in chosen]))
                                                        for key in chosen[0]}
    return out


def main():
    results = cached("coarse", compute)
    print("| Scene | Merge | Later bounces from | Rays | Albedo | Second bounce | Its light | Converged |")
    print("|---|---|---|---|---|---|---|---|")
    for key, r in results.items():
        name, merge, ds0, albedo = key.split("/")
        source = "re-merge" if float(ds0) == 1 else f"spacing {float(ds0):.0f}"
        print(f"| {name} | {merge} | {source} | {r['rays'] / 1e6:.2f}M | {albedo} | {r['second']:.4f} | "
              f"{r['second_share']:.3f} | {r['converged']:.4f} |")


if __name__ == "__main__":
    main()
