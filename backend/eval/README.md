# Evaluation (spec A.12)

**There are no results in this repo yet.** Numbers go into the main README only after you have
collected a consented dataset and run the script below. Every number must be reproducible from
`eval/report.json`.

## 1. Collect data (with written consent)

- 30–40 volunteers. For each person: 5 enrollment-style photos, 5 classroom-condition photos
  (different light, distance, angle), and 5 voice clips.
- Folder per person: `data/faces/person_01/*.jpg`, `data/voices/person_01/*.webm`.
- Store the data outside git (it is personal data). Delete it when the project ends.

## 2. Run

```bash
# copy the data into the media volume, or mount it, then:
docker compose run --rm -v "$PWD/data:/data/eval" api python -m eval.evaluate --data /data/eval/faces --modality face
docker compose run --rm -v "$PWD/data:/data/eval" api python -m eval.evaluate --data /data/eval/voices --modality voice --out eval/report-voice.json
```

The script splits **people** (not photos) into validation and test sets, chooses the threshold
on validation (lowest FRR with FAR ≤ 1%), and reports FAR/FRR on the untouched test set.

## 3. Use the result

1. Put the chosen thresholds into **Admin → Settings** (`face_accept` / `face_reject`).
   A common choice is `face_accept` = operating-point threshold, and `face_reject` slightly
   higher so borderline faces go to review as UNCERTAIN.
2. Copy the printed markdown table into the main README.

## Still to do by hand (protocols 2–5)

- **Identification in context:** real (consented) class photos with a roster of ~60. Measure
  PRESENT precision, present recall, UNCERTAIN rate.
- **Ablations:** face only vs fused; Hungarian vs greedy (`ml/matcher.py`).
- **Failure analysis:** label each error (back row / angle / occlusion / low light / noise) and count.
- **Latency:** `processing_ms` per session is shown on the admin dashboard (p50/p95).
