# SnapClass — Build Design Notes

The full specification (requirements, capacity estimates, HLD, data model, API, flows) is
Project A in `5_project_for_resume.md`. This note records **only the decisions taken while
building**, especially where the build differs from the spec, and why.

## 1. Decisions confirmed with the author (2026-10-07)

| Topic | Spec | Built | Why |
|---|---|---|---|
| Infrastructure | Postgres + pgvector, Redis + RQ, MinIO/S3 presigned uploads | Postgres + pgvector, Redis + RQ, **uploads go through the API into a local media folder** (`core/storage.py`) | Presigned URLs need extra CORS + host-signature setup with MinIO in Docker. A small `LocalStorage` class keeps the same interface (`save/read/delete/exists`) so S3 can replace it later in one file. |
| Face model | dlib HOG + ResNet (128-d) | **OpenCV YuNet (detector) + SFace (128-d embedding)** | Installs with `pip` (no CMake / C++ build tools on Windows). YuNet is a CNN detector, so it finds smaller and angled faces than HOG. |
| Voice | Resemblyzer + webrtcvad | Same, plus `ffmpeg` to decode browser audio (webm/ogg/mp3) to 16 kHz mono | Browsers record webm/opus, which Python audio libraries cannot read directly. |
| Frontend | React or Streamlit | **React + Vite, plain JavaScript, plain CSS, no router library** | Author asked for a simple frontend. A ~20-line hash router replaces react-router. |

## 2. Other simplifications (and their trade-offs)

1. **No repository layer.** Services run SQLModel queries directly. Ownership scoping (IDOR
   protection) lives in a few helper functions such as `get_owned_class()`. Fewer files to read;
   the cost is that services are tested with a real database instead of fake repositories.
2. **Distance metric.** SFace embeddings are L2-normalised, so L2 distance and cosine similarity
   are linked: `cos = 1 - d² / 2`. Face matching uses L2 distance (pgvector `<->`, HNSW
   `vector_l2_ops`); fusion converts face distance to cosine similarity so both modalities are on
   the same scale. Fused thresholds default to the weighted mix of the single-modality thresholds.
3. **All thresholds are placeholders until measured.** Defaults come from the SFace authors'
   suggested cosine threshold (0.363 ≈ L2 1.128). Tune them with `eval/evaluate.py` on a
   person-split validation set. Admins can change them at runtime (`/admin/settings`); every
   session stores the thresholds it used in `config_snapshot`.
4. **Status updates by polling** (`GET /sessions/{id}` every 2 s). FR-A9 allows polling or SSE;
   browser `EventSource` cannot send an `Authorization` header, so SSE would need tokens in URLs.
5. **Signed media URLs.** Face crops for the review screen are served by
   `GET /api/v1/media/{key}?exp=&sig=` with an HMAC signature that expires in 5 minutes. This
   mimics S3 presigned GET URLs and works with `<img src>`.
6. **Extra table `biometric_jobs`.** Enrollment runs in the worker, so the student needs somewhere
   to read "photo 2 is blurry". The spec had no table for this.
7. **Extra columns.** `match_results.teacher_decision` (teacher's override during review),
   `match_results.has_biometrics` (student had no embeddings → manual), `sessions.processing_started_at`
   and `sessions.processing_ms` (stuck-job sweep and the job-duration metric).
8. **Extra table `app_settings`.** Holds thresholds and retention days so admins can change them
   (FR-A2 "settings") with an audit entry (FR-A15).
9. **Finalize requires every UNCERTAIN student to be resolved.** This is the strongest form of
   "uncertain matches always go to human review".
10. **Worker uses RQ `SimpleWorker`** (no fork per job). Models load once per process, and
    PyTorch does not run into fork-after-threads problems. A crash stops the worker
    process, and Docker restarts it.
11. **Scheduler is a simple loop** (every 60 s) that sweeps stuck sessions, applies retention
    hourly, and sends the weekly below-threshold email (SMTP if configured, otherwise logged).
12. **Tokens in `localStorage`.** Simple, but readable by any XSS. The mitigation is React's
    default escaping and no `dangerouslySetInnerHTML`. Moving the refresh token to an httpOnly
    cookie is the next hardening step.
13. **Emails** are stored lower-cased in a plain `TEXT UNIQUE` column instead of `CITEXT`.
14. **Duplicate enrollment check** writes an audit entry `DUPLICATE_FACE_SUSPECTED` that the admin
    dashboard lists; it does not block enrollment.

## 3. Changing photos before saving (added 2026-10-07)

The spec's state machine only allowed REVIEW → FINALIZED, so a teacher who noticed missing
students could not add a photo of the back rows. Now photos can be added or removed in every
state except PROCESSING (the worker is reading them) and FINALIZED (use audited corrections):

```
REVIEW / FAILED ──add or remove photos──▶ UPLOADED ──check again──▶ PROCESSING ──▶ REVIEW
UPLOADED ──last photo removed──▶ CREATED
```

- **Teacher choices are kept** when checking again: the match job copies existing
  `teacher_decision` values into the new results (human input is never silently discarded).
  `POST /sessions/{id}/process?clear_decisions=true` starts fresh when the teacher asks for it.
- `DELETE /sessions/{id}/media/{media_id}` removes one photo or the audio clip.
- Each check deletes the face crops of the previous check (`crops/<session_id>/`), so no
  orphaned images are left on disk.
- The teacher sees uploaded photos as thumbnails through 5-minute signed links (only `crops/`
  and `sessions/*.jpg|png` keys can be served; never audio or enrollment selfies).

## 4. Voice segmentation choice

The spec merges speech into 1.5–3 s windows. In a roll-call recording, merging across silences
would mix two students' voices into one window. We therefore keep each **continuous speech run**
(gaps under 300 ms joined) as one window, drop runs shorter than 1 s, and split runs longer than
3 s. Students should say "present" **plus their roll number** so each run is long enough to embed.
Voice alone never marks a student PRESENT.

## 5. Out of scope (unchanged from spec)

Liveness / anti-spoofing, students marking themselves, multi-institution tenancy.
