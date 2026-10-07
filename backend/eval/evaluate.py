"""Face/voice verification evaluation (spec A.12, protocol 1).

Folder layout (one folder per CONSENTING volunteer):
    data/
      person_01/  img1.jpg img2.jpg ...   (or .wav/.webm/... for --modality voice)
      person_02/  ...

What it does:
1. Splits PEOPLE (not photos) into validation and test sets, so no person is in both.
2. Embeds every file with the same models the worker uses.
3. Builds genuine pairs (same person) and impostor pairs (different people).
4. On VALIDATION: sweeps thresholds, computes FAR/FRR, finds the EER and the
   threshold where FAR <= --target-far (the operating point).
5. On TEST: reports FAR/FRR at that fixed threshold. The test set is never used for tuning.
6. Writes eval/report.json and prints a markdown table for the README.

Run inside the worker image:
    docker compose run --rm api python -m eval.evaluate --data /data/eval/faces --modality face
"""

import argparse
import itertools
import json
import random
import subprocess
import time
from pathlib import Path

import numpy as np

IMAGE_TYPES = {".jpg", ".jpeg", ".png"}
AUDIO_TYPES = {".wav", ".webm", ".ogg", ".mp3", ".m4a"}


def embed_folder(folder: Path, modality: str) -> tuple[list[np.ndarray], list[str], list[float]]:
    """Return (embeddings, skipped file messages, seconds per file)."""
    from snapclass.workers.models_cache import get_face_encoder, get_voice_embedder

    embeddings, skipped, timings = [], [], []
    allowed = IMAGE_TYPES if modality == "face" else AUDIO_TYPES
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in allowed):
        started = time.perf_counter()
        if modality == "face":
            from snapclass.ml.face import decode_image

            image = decode_image(path.read_bytes())
            faces = get_face_encoder().encode(image, min_face_px=40) if image is not None else []
            if len(faces) != 1:
                skipped.append(f"{path.name}: {len(faces)} faces found")
                continue
            embeddings.append(faces[0].embedding)
        else:
            from snapclass.ml.voice import decode_audio

            try:
                embeddings.append(get_voice_embedder().embed(decode_audio(path.read_bytes(), max_seconds=15)))
            except (ValueError, subprocess.SubprocessError) as exc:
                skipped.append(f"{path.name}: {exc}")
                continue
        timings.append(time.perf_counter() - started)
    return embeddings, skipped, timings


def pair_scores(people: dict[str, list[np.ndarray]], modality: str) -> tuple[np.ndarray, np.ndarray]:
    """Genuine and impostor scores. Face → L2 distance (lower = same). Voice → cosine (higher = same)."""

    def score(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b)) if modality == "face" else float(np.dot(a, b))

    genuine = [score(a, b) for vectors in people.values() for a, b in itertools.combinations(vectors, 2)]
    impostor = [score(a, b) for p1, p2 in itertools.combinations(people, 2) for a in people[p1] for b in people[p2]]
    return np.array(genuine), np.array(impostor)


def far_frr(genuine: np.ndarray, impostor: np.ndarray, threshold: float, modality: str) -> tuple[float, float]:
    """FAR = impostors wrongly accepted. FRR = genuine pairs wrongly rejected."""
    if modality == "face":  # accept when distance <= threshold
        return float(np.mean(impostor <= threshold)), float(np.mean(genuine > threshold))
    return float(np.mean(impostor >= threshold)), float(
        np.mean(genuine < threshold)
    )  # accept when similarity >= threshold


def sweep(genuine, impostor, modality):  # noqa: ANN001, ANN201
    grid = np.linspace(0.0, 2.0, 401) if modality == "face" else np.linspace(-1.0, 1.0, 401)
    return [(float(t), *far_frr(genuine, impostor, t, modality)) for t in grid]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--modality", choices=["face", "voice"], default="face")
    parser.add_argument("--val-people", type=int, default=15)
    parser.add_argument("--target-far", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("eval/report.json"))
    args = parser.parse_args()

    folders = sorted(p for p in args.data.iterdir() if p.is_dir())
    if len(folders) < 4:
        raise SystemExit("Need at least 4 people (folders) for a meaningful split.")
    random.Random(args.seed).shuffle(folders)  # noqa: S311 (reproducible split, not security)
    val_count = min(args.val_people, len(folders) // 2)
    splits = {"validation": folders[:val_count], "test": folders[val_count:]}

    embedded, skipped, timings = {}, [], []
    for split, people in splits.items():
        embedded[split] = {}
        for folder in people:
            vectors, problems, seconds = embed_folder(folder, args.modality)
            skipped += [f"{folder.name}/{p}" for p in problems]
            timings += seconds
            if len(vectors) >= 2:
                embedded[split][folder.name] = vectors

    val_genuine, val_impostor = pair_scores(embedded["validation"], args.modality)
    curve = sweep(val_genuine, val_impostor, args.modality)
    eer_point = min(curve, key=lambda row: abs(row[1] - row[2]))
    # Operating point: the threshold with the lowest FRR among those with FAR <= target.
    allowed = [row for row in curve if row[1] <= args.target_far]
    operating = min(allowed, key=lambda row: row[2]) if allowed else eer_point

    test_genuine, test_impostor = pair_scores(embedded["test"], args.modality)
    test_far, test_frr = far_frr(test_genuine, test_impostor, operating[0], args.modality)

    report = {
        "modality": args.modality,
        "seed": args.seed,
        "people": {k: len(v) for k, v in embedded.items()},
        "pairs": {
            "validation": {"genuine": len(val_genuine), "impostor": len(val_impostor)},
            "test": {"genuine": len(test_genuine), "impostor": len(test_impostor)},
        },
        "validation_eer": {"threshold": eer_point[0], "far": eer_point[1], "frr": eer_point[2]},
        "operating_point": {
            "threshold": operating[0],
            "target_far": args.target_far,
            "val_far": operating[1],
            "val_frr": operating[2],
        },
        "test_at_operating_point": {"far": test_far, "frr": test_frr},
        "seconds_per_file": {
            "p50": float(np.percentile(timings, 50)) if timings else None,
            "p95": float(np.percentile(timings, 95)) if timings else None,
        },
        "skipped_files": skipped,
        "det_curve_validation": curve,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))

    print("\n| Modality | People (val/test) | Val EER | Threshold | Test FAR | Test FRR |")
    print("|---|---|---|---|---|---|")
    print(
        f"| {args.modality} | {report['people']['validation']}/{report['people']['test']} "
        f"| {eer_point[1]:.3f} | {operating[0]:.3f} | {test_far:.3f} | {test_frr:.3f} |"
    )
    print(f"\nFull report: {args.out}  ({len(skipped)} files skipped)")


if __name__ == "__main__":
    main()
