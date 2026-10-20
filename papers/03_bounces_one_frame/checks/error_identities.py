"""The error of a converged frozen solve, its part along the dominant mode, the eigenvalue shift a leak deficit
gives, and the ambient term's exact mean, on random nonnegative matrices."""
import numpy as np

rng = np.random.default_rng(3)
P = 40


def perron(A):
    values, right = np.linalg.eig(A)
    values_t, left = np.linalg.eig(A.T)
    i, j = np.argmax(values.real), np.argmax(values_t.real)
    return values[i].real, np.abs(left[:, j].real), np.abs(right[:, i].real)


# Bounce matrices K (exact) and K_hat (estimate): L = E + K[:, :-1] L + K[:, -1] sky.
K = rng.uniform(0, 1, (P, P + 1))
K *= 0.85 / K.sum(1, keepdims=True)
K_hat = np.clip(K * rng.uniform(0.8, 1.15, K.shape), 0, None)
E, sky = rng.uniform(0, 1, P) * (rng.random(P) < 0.2), 0.4
I = np.eye(P)
L = np.linalg.solve(I - K[:, :-1], E + K[:, -1] * sky)
L_hat = np.linalg.solve(I - K_hat[:, :-1], E + K_hat[:, -1] * sky)

# The converged error is one pass's error on the exact solution, carried through every further bounce.
assert np.allclose(L_hat - L, np.linalg.solve(I - K_hat[:, :-1], (K_hat - K) @ np.append(L, sky)))

# Along the left Perron vector u of K, the error is one pass's error on the estimate, divided by 1 - mu.
mu, u, v = perron(K[:, :-1])
assert np.isclose(u @ (L_hat - L), u @ ((K_hat - K) @ np.append(L_hat, sky)) / (1 - mu))

# The light reflected at least once, L - E, is the first bounce carried through every further bounce, so along u it is
# the first bounce's part divided by 1 - mu.
first = K @ np.append(E, sky)
assert np.isclose(u @ (L - E), u @ first / (1 - mu))

# A deficit that scales row i by 1 - d_i lowers mu by mu times the Perron-weighted mean deficit, to first order.
d = rng.uniform(0, 1, P)
weighted = (u * v * d).sum() / (u * v).sum()
for scale in (1e-2, 1e-3):
    mu_hat = perron((1 - scale * d)[:, None] * K[:, :-1])[0]
    assert abs(mu_hat - mu * (1 - scale * weighted)) < 2 * scale ** 2

# With reciprocal form factors (G symmetric, F = G / row sums, so area_i F_ij = area_j F_ji) and one albedo, the
# area-weighted mean of the bounces still to come is the last bounce's times rho / (1 - rho): the ambient term of
# progressive radiosity restores the exact mean after any number of bounces.
G = rng.uniform(0, 1, (P, P))
G = G + G.T
area = G.sum(1)
F = G / area[:, None]
rho = 0.8
exact = np.linalg.solve(I - rho * F, E)
last, now = E, E + rho * F @ E
for _ in range(6):
    tail = rho * (area @ (now - last)) / area.sum() / (1 - rho)
    assert np.isclose(area @ now / area.sum() + tail, area @ exact / area.sum())
    last, now = now, E + rho * F @ now
print("ok")
