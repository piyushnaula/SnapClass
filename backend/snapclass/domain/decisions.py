"""Decision policy: turn match scores into PRESENT / UNCERTAIN / NOT_DETECTED (spec A.9.4).

Scales used here:
* face distance  = L2 distance between unit-length SFace embeddings (0 = identical, 2 = opposite)
* voice score    = cosine similarity between Resemblyzer embeddings (1 = identical)
* For unit vectors: cosine = 1 - distance² / 2, so we can turn a face distance
  into a cosine similarity and fuse both modalities on the same scale.

Policy rules:
1. Voice alone never marks a student PRESENT (noisy classrooms, easy to replay).
2. Scores between the accept and reject thresholds are UNCERTAIN, so a teacher decides.
3. All thresholds are defaults until tuned on validation data (see eval/).
"""

from dataclasses import asdict, dataclass
from enum import StrEnum


class Decision(StrEnum):
    PRESENT = "PRESENT"
    UNCERTAIN = "UNCERTAIN"
    NOT_DETECTED = "NOT_DETECTED"


@dataclass(frozen=True)
class Thresholds:
    face_accept: float = 1.05  # L2 distance, lower is better (≈ cosine 0.45)
    face_reject: float = 1.15  # (≈ cosine 0.34; SFace authors suggest 0.363)
    voice_accept: float = 0.80  # cosine similarity, higher is better
    voice_reject: float = 0.65
    fused_accept: float = 0.55  # = 0.7 × 0.45 + 0.3 × 0.80
    fused_reject: float = 0.43  # = 0.7 × 0.34 + 0.3 × 0.65
    w_face: float = 0.7  # weight of the face score in the fused score

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Thresholds":
        known = {key: float(value) for key, value in data.items() if key in cls.__dataclass_fields__}
        return cls(**known)

    def problems(self) -> list[str]:
        """Rules that keep the UNCERTAIN band valid. Empty list = thresholds are OK."""
        found = []
        if not 0 < self.face_accept <= self.face_reject <= 2:
            found.append("need 0 < face_accept <= face_reject <= 2")
        if not 0 <= self.voice_reject <= self.voice_accept <= 1:
            found.append("need 0 <= voice_reject <= voice_accept <= 1")
        if not self.fused_reject <= self.fused_accept <= 1:
            found.append("need fused_reject <= fused_accept <= 1")
        if not 0 <= self.w_face <= 1:
            found.append("need 0 <= w_face <= 1")
        return found


def face_distance_to_similarity(distance: float) -> float:
    """Convert L2 distance between unit vectors into cosine similarity."""
    return 1.0 - (distance * distance) / 2.0


def decide(face_distance: float | None, voice_score: float | None, t: Thresholds) -> tuple[Decision, float | None]:
    """Return (decision, score) for one student.

    The score is what the teacher sees: face cosine similarity, voice cosine
    similarity, or the fused score when both exist.
    """
    # Nothing matched this student.
    if face_distance is None and voice_score is None:
        return Decision.NOT_DETECTED, None

    # Face only.
    if voice_score is None:
        assert face_distance is not None
        score = face_distance_to_similarity(face_distance)
        if face_distance <= t.face_accept:
            return Decision.PRESENT, score
        if face_distance <= t.face_reject:
            return Decision.UNCERTAIN, score
        return Decision.NOT_DETECTED, score

    # Voice only: at best UNCERTAIN (rule 1).
    if face_distance is None:
        if voice_score >= t.voice_reject:
            return Decision.UNCERTAIN, voice_score
        return Decision.NOT_DETECTED, voice_score

    # Both: weighted average of the two similarities.
    face_similarity = face_distance_to_similarity(face_distance)
    fused = t.w_face * face_similarity + (1 - t.w_face) * voice_score
    if fused >= t.fused_accept:
        return Decision.PRESENT, fused
    if fused >= t.fused_reject:
        return Decision.UNCERTAIN, fused
    return Decision.NOT_DETECTED, fused
