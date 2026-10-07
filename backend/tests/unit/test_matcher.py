import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from snapclass.ml.matcher import RosterMatcher, one_to_one_assign


def unit(vector):
    vector = np.asarray(vector, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def test_two_faces_closest_to_same_student_get_one_student():
    """Spec A.13 example: two probes near one student → only one is assigned to them."""
    alice = unit([1, 0, 0])
    bob = unit([0, 1, 0])
    matcher = RosterMatcher({"alice": alice[None, :], "bob": bob[None, :]})
    probes = np.stack([unit([1, 0.05, 0]), unit([1, 0.1, 0])])  # both look like alice

    pairs = matcher.assign(probes, reject_above=0.5)

    students = [student for _, student, _ in pairs]
    assert students.count("alice") == 1
    assert "bob" not in students  # bob is too far from both probes


def test_hungarian_beats_greedy():
    # Greedy would give probe 0 to "a" (0.1) and leave probe 1 with nobody.
    # The optimal assignment is probe0→b, probe1→a.
    distances = np.array([[0.1, 0.2], [0.15, 0.9]], dtype=np.float32)
    pairs = one_to_one_assign(distances, reject_above=0.5)
    assert sorted((r, c) for r, c, _ in pairs) == [(0, 1), (1, 0)]


def test_min_distance_over_gallery():
    student = np.stack([unit([1, 0]), unit([0, 1])])  # two enrolled photos
    matcher = RosterMatcher({"s": student})
    d = matcher.distance_matrix(unit([0, 1])[None, :])
    assert d[0, 0] < 1e-6


def test_empty_inputs():
    assert RosterMatcher({}).assign(np.zeros((2, 3), dtype=np.float32), 1.0) == []
    assert one_to_one_assign(np.zeros((0, 3)), 1.0) == []


@settings(max_examples=60, deadline=None)
@given(
    n_probes=st.integers(1, 8),
    n_students=st.integers(1, 8),
    seed=st.integers(0, 10_000),
    reject=st.floats(0.2, 2.0),
)
def test_matcher_invariants(n_probes, n_students, seed, reject):
    """Property: no student assigned twice, no probe used twice, all distances ≤ reject."""
    rng = np.random.default_rng(seed)
    roster = {f"s{i}": rng.normal(size=(3, 16)).astype(np.float32) for i in range(n_students)}
    roster = {k: v / np.linalg.norm(v, axis=1, keepdims=True) for k, v in roster.items()}
    probes = rng.normal(size=(n_probes, 16)).astype(np.float32)
    probes /= np.linalg.norm(probes, axis=1, keepdims=True)

    pairs = RosterMatcher(roster).assign(probes, reject_above=reject)

    students = [s for _, s, _ in pairs]
    probe_ids = [p for p, _, _ in pairs]
    assert len(students) == len(set(students))
    assert len(probe_ids) == len(set(probe_ids))
    assert all(d <= reject for _, _, d in pairs)
