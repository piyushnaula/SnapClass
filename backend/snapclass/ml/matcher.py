"""Roster matching with one-to-one assignment (spec A.9.3).

Naive nearest-neighbour can give the same student to two faces. Instead we
solve an assignment problem with the Hungarian algorithm
(scipy.optimize.linear_sum_assignment): it pairs faces and students so the
total distance is as small as possible and each student is used at most once.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment

# Cost used for pairs that are too far apart, so the algorithm avoids them.
FORBIDDEN = 1e6


def one_to_one_assign(distances: np.ndarray, reject_above: float) -> list[tuple[int, int, float]]:
    """distances: (n_probes, n_students). Returns (probe_index, student_index, distance).

    Pairs farther than `reject_above` are never returned.
    """
    if distances.size == 0:
        return []
    cost = np.where(distances > reject_above, FORBIDDEN, distances)
    rows, cols = linear_sum_assignment(cost)
    return [
        (int(r), int(c), float(distances[r, c]))
        for r, c in zip(rows, cols, strict=True)
        if distances[r, c] <= reject_above
    ]


class RosterMatcher:
    """Matches probe embeddings (faces from a class photo) against one class roster."""

    def __init__(self, roster: dict[str, np.ndarray]):
        # roster: student_id -> (k, dim) matrix, one row per enrolled embedding
        self.ids = list(roster)
        self.galleries = [np.asarray(roster[sid], dtype=np.float32) for sid in self.ids]

    def distance_matrix(self, probes: np.ndarray) -> np.ndarray:
        """(n_probes, dim) -> (n_probes, n_students). Each cell is the smallest
        L2 distance from that probe to any of the student's enrolled embeddings."""
        result = np.empty((len(probes), len(self.ids)), dtype=np.float32)
        for j, gallery in enumerate(self.galleries):
            # probes[:, None, :] - gallery[None, :, :] has shape (n_probes, k, dim)
            pairwise = np.linalg.norm(probes[:, None, :] - gallery[None, :, :], axis=2)
            result[:, j] = pairwise.min(axis=1)
        return result

    def assign(self, probes: np.ndarray, reject_above: float) -> list[tuple[int, str, float]]:
        """Returns (probe_index, student_id, distance) for every accepted pair."""
        if len(probes) == 0 or not self.ids:
            return []
        distances = self.distance_matrix(probes)
        return [(r, self.ids[c], d) for r, c, d in one_to_one_assign(distances, reject_above)]


def best_unassigned_distance(matcher: RosterMatcher, probe: np.ndarray) -> float | None:
    """Smallest distance from an unmatched face to anyone on the roster (for the review UI)."""
    if not matcher.ids:
        return None
    return float(matcher.distance_matrix(probe[None, :]).min())
