"""The frozen solve as an operator in flatland: the leak deficit of each merge, its dependence on the cascade 0
interval and on overlap, the shift it gives the dominant eigenvalue, and the converged bias predicted from the
first bounce and that shift (Table 1)."""
import numpy as np

from common import CLOSED, MERGES, OFFSETS, SCENES, Flat, bias, cached, params, perron, rd

ALBEDO = 0.9
T0_FACTORS = (0.2, 0.5, 1.0, 2.0)


def eigen(flat, merge, offset):
    estimate, rays = flat.estimate(params(), merge, offset)
    K, K_hat = flat.bounce_matrix(flat.exact, ALBEDO), flat.bounce_matrix(estimate, ALBEDO)
    mu, left, right = perron(K)
    mu_hat = perron(K_hat)[0]
    E, sky, where = flat.patches.emission, flat.sky, flat.receivers
    source = np.append(E, sky)
    first, first_hat = K @ source, K_hat @ source
    out = {"rays": rays, "mu": mu, "mu_hat": mu_hat,
           "bias": bias(rd.converged(K_hat, E, sky), rd.converged(K, E, sky), where),
           "bias_predicted": float((left @ first_hat) / (left @ first) * (1 - mu) / (1 - mu_hat) - 1)}
    if flat.name in CLOSED:
        deficit = flat.deficit(estimate)
        weight = (left * right)[flat.receivers]
        out.update(deficit=float(deficit.mean()), deficit_max=float(deficit.max()),
                   mu_predicted=mu * (1 - float((weight * deficit).sum() / weight.sum())))
    return out


def sweep(flat, merge, t0_factor, overlap):
    return [float(flat.deficit(flat.estimate(params(t0_factor=t0_factor, overlap=overlap), merge, offset)[0]).mean())
            for offset in OFFSETS]


def compute():
    out = {}
    for name in SCENES:
        flat = Flat(name)
        for merge in MERGES:
            rows = [eigen(flat, merge, offset) for offset in OFFSETS]
            out[f"{name}/{merge}"] = {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}
            if name in CLOSED:
                settings = [(f, 0.0) for f in T0_FACTORS] + [(1.0, 0.5)]
                out[f"{name}/{merge}"]["sweep"] = [float(np.mean(sweep(flat, merge, f, o))) for f, o in settings]
    return out


def main():
    results = cached("deficit", compute)
    print("| Scene | Merge | Rays | Deficit, mean / max | mu | mu hat | predicted | Bias | predicted |")
    print("|---|---|---|---|---|---|---|---|---|")
    for key, row in results.items():
        name, merge = key.split("/")
        deficit = f"{row['deficit']:.4f} / {row['deficit_max']:.3f}" if "deficit" in row else "-"
        predicted = f"{row['mu_predicted']:.4f}" if "mu_predicted" in row else "-"
        print(f"| {name} | {merge} | {row['rays'] / 1e6:.2f}M | {deficit} | {row['mu']:.4f} | {row['mu_hat']:.4f} | "
              f"{predicted} | {row['bias']:+.4f} | {row['bias_predicted']:+.4f} |")
    print("\nMean deficit at t0 = " + ", ".join(f"{f} t_eq" for f in T0_FACTORS) + ", and with overlap 0.5:")
    for key, row in results.items():
        if "sweep" in row:
            print(f"  {key}: " + "  ".join(f"{d:.4f}" for d in row["sweep"]))


if __name__ == "__main__":
    main()
