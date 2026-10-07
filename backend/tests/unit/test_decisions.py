import math

import pytest

from snapclass.domain.decisions import Decision, Thresholds, decide, face_distance_to_similarity

T = Thresholds()


def test_nothing_detected():
    assert decide(None, None, T) == (Decision.NOT_DETECTED, None)


def test_face_only_bands():
    assert decide(T.face_accept - 0.01, None, T)[0] == Decision.PRESENT
    assert decide(T.face_accept, None, T)[0] == Decision.PRESENT  # boundary is inclusive
    assert decide((T.face_accept + T.face_reject) / 2, None, T)[0] == Decision.UNCERTAIN
    assert decide(T.face_reject + 0.01, None, T)[0] == Decision.NOT_DETECTED


def test_voice_alone_is_never_present():
    decision, score = decide(None, 0.99, T)
    assert decision == Decision.UNCERTAIN
    assert score == 0.99
    assert decide(None, T.voice_reject - 0.01, T)[0] == Decision.NOT_DETECTED


def test_fused_uses_weighted_similarity():
    face_d, voice_s = 0.9, 0.9
    decision, score = decide(face_d, voice_s, T)
    expected = T.w_face * face_distance_to_similarity(face_d) + (1 - T.w_face) * voice_s
    assert math.isclose(score, expected)
    assert decision == Decision.PRESENT


def test_fused_weak_both_is_not_present():
    decision, _ = decide(T.face_reject, T.voice_reject, T)
    assert decision != Decision.PRESENT


@pytest.mark.parametrize("distance,similarity", [(0.0, 1.0), (math.sqrt(2), 0.0), (2.0, -1.0)])
def test_distance_to_similarity(distance, similarity):
    assert math.isclose(face_distance_to_similarity(distance), similarity, abs_tol=1e-9)


def test_default_thresholds_are_valid():
    assert Thresholds().problems() == []


def test_invalid_thresholds_are_reported():
    bad = Thresholds(face_accept=1.3, face_reject=1.1)
    assert bad.problems()


def test_from_dict_ignores_unknown_keys():
    t = Thresholds.from_dict({"face_accept": "1.0", "nonsense": 5})
    assert t.face_accept == 1.0
