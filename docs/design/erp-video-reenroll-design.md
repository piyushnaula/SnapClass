# SnapClass design (rejected): ERP identity, verified rosters, video attendance, face re-capture

Status: **REJECTED (2026-10-07)**: the author decided SnapClass stays separate from the ERP.
Kept as a decision record. The implemented design is [student-accounts-face-requests.md](student-accounts-face-requests.md).
Date: 2026-10-07

## 1. Problem

1. **Fake students.** Today anyone with a class QR link can self-register with any name and roll
   number, join the roster and be marked present (spec FR-A4 has this gap).
2. **No trusted identity data.** Name, roll number, section and photo are typed by the student.
3. **Photo limit.** Teachers can upload only 4 photos; large rooms need more, and walking
   bench-to-bench with a video is faster than taking many photos.
4. **No profile photos.** Teachers cannot compare the face in the class photo with the student's
   official photo.
5. **Stale face data.** When SnapClass keeps failing to recognise a student (new glasses, beard,
   bad setup photos) nobody is prompted to fix it.

## 2. Decisions (confirmed with the author, 2026-10-07)

| Topic | Decision |
|---|---|
| Identity | Students **and teachers** sign in with their **college ERP ID + password**. SnapClass never creates identities. Only the administrator keeps a local email/password account (break-glass). |
| ERP access | We do not have a real ERP API, so we build an **`ErpProvider` adapter** with a **mock ERP** (JSON data). A real ERP replaces the mock in one file. |
| Rosters | **ERP import + verified QR.** Teacher imports students by program/section/semester. QR join still works for electives, but only for ERP-logged-in students: a matching ERP section joins immediately; anyone else goes to a **teacher approval list**. |
| ERP photo | Shown to teachers (roster, review). Used to **cross-check** the student's selfies at setup. Selfies remain the face samples used for matching. |
| Video | Teacher can **record in the app** (compressed) **or upload a video file** (≤ 200 MB, ≤ 3 min used). |
| Photos | Up to **30 photos** per attendance (was 4). |

## 3. Requirements

### Functional

| ID | Requirement |
|---|---|
| FR-1 | Sign-in screen takes "College ID or email" + password. College IDs are verified by the ERP; email is only for the local admin. |
| FR-2 | First ERP sign-in creates the SnapClass account from ERP data (name, role, roll number, program, section, semester, email, photo). Later sign-ins refresh this data. ERP-inactive users cannot sign in. |
| FR-3 | Teacher can import a class roster from the ERP (program + section + semester of the class). Re-import adds new students and never removes anyone silently. |
| FR-4 | QR / invite link requires sign-in. ERP section + semester (+ program) match → joined. No match → join request the teacher approves or rejects. |
| FR-5 | Self-registration (typing name/roll number) is removed. |
| FR-6 | Profile photos (from ERP) shown: header avatar, roster, review screen (official photo next to the class crop). |
| FR-7 | **Face setup gate:** a student without face samples (or with an open re-capture request) sees a blocking screen after sign-in: *Set up now* or *No thanks — my teacher will mark me by hand*. Attendance is visible only after one of the two. Enforced by the API too, not only the UI. |
| FR-8 | **ERP cross-check:** at setup, selfies are compared with the ERP photo. Match → `VERIFIED`. No match → samples saved but marked `MISMATCH`: the student is **never auto-marked present** (always "Not sure") until a teacher confirms identity. No ERP photo → `NO_REFERENCE` (normal matching). |
| FR-9 | **Re-capture request:** on the review screen a teacher can choose *Ask to retake face photos* (with a reason). The student's next sign-in shows the blocking gate (FR-7) with the reason. The request closes automatically when new face photos are accepted. |
| FR-10 | **"Keeps missing" hint:** if a teacher marked a student present but SnapClass said "Not found/Not sure" in 2 of the last 3 attendances, the review screen suggests a re-capture request. |
| FR-11 | Teacher can add **up to 30 photos** per attendance (camera or device). |
| FR-12 | Teacher can **record a video** in the app (back camera, max 3 min) or **upload a video file** (MP4/MOV/WEBM, ≤ 200 MB). Upload shows a progress bar. |
| FR-13 | Worker extracts sharp frames from the video, matches faces exactly like photos, merges duplicates of unknown faces, and **deletes the video right after successful processing**. |
| FR-14 | Every new sensitive action is audited: ERP roster import, join approve/reject, re-capture request, identity confirmation, opt-out. |

### Non-functional (design targets — to be measured)

| Category | Target |
|---|---|
| Video processing | 2-minute in-app video processed in < 60 s on a 2-vCPU worker (p95) |
| Photo processing | 30 photos processed in < 45 s (p95) |
| Security | ERP passwords are never stored, logged or sent anywhere except the ERP adapter; login rate limits unchanged |
| Privacy | Opting out is always possible; videos deleted after processing; ERP photo embedding computed on the fly, never stored |

## 4. Capacity estimate (why videos are deleted immediately)

- In-app recording at 1280×720, 2.5 Mbit/s → **≈ 19 MB per minute**; a 2-min walk-through ≈ 38 MB.
- Phone-camera file at 1080p/30 fps ≈ 17 Mbit/s → ≈ 125 MB per minute (hence the 200 MB cap ≈ 1.5 min).
- 1,000 sessions/day × 38 MB = 38 GB/day. With the current 7-day retention that is **≈ 266 GB**,
  versus ≈ 21 GB for photos. **Decision:** delete the video as soon as processing succeeds (keep
  only face crops for review). If processing fails, the video stays until retry or retention.
- Frames: 2 frames/s sampled, sharpest frame per second kept → ≤ 180 frames for 3 min. At
  ~0.15 s per frame (detection + embeddings, to be measured) ≈ 27 s.

## 5. High-level design (what changes)

```
Browser ── login(ID, pwd) ─▶ API ── ErpProvider.authenticate ─▶ Mock ERP (JSON)  ← swap for real ERP / SSO
                              │
                              ├─ roster import ─────────────▶ ErpProvider.list_students
                              ├─ media upload (photos/video, streamed to disk)
                              └─ enqueue match job ─▶ Worker: video → ffmpeg frames → sharp-frame
                                                       selection → same face matcher → dedupe unknowns
```

### ERP adapter (`snapclass/erp/`)

```python
@dataclass
class ErpPerson:
    erp_id: str; full_name: str; role: str          # "STUDENT" | "TEACHER"
    email: str | None; roll_no: str | None
    program: str | None; section: str | None; semester: int | None
    is_active: bool

class ErpProvider(Protocol):
    def authenticate(self, erp_id: str, password: str) -> ErpPerson | None: ...
    def get_person(self, erp_id: str) -> ErpPerson | None: ...
    def list_students(self, program: str, section: str, semester: int) -> list[ErpPerson]: ...
    def get_photo(self, erp_id: str) -> bytes | None: ...
```

- `MockErpProvider`: reads `backend/erp_mock/people.json` (bcrypt-hashed demo passwords) and
  optional photos in `backend/erp_mock/photos/<erp_id>.jpg`. Ships with fictional people and
  **no real faces**; you can add consented photos locally for demos (git-ignored).
- **Trade-off to explain in interviews:** relaying passwords to an ERP means SnapClass handles
  every student's college password. A real deployment should use the ERP's **SSO** (OIDC, SAML or
  CAS), where the student types the password on the ERP's own page and SnapClass receives only a
  signed identity token. The adapter boundary keeps that switch local to the auth service.

## 6. Data model changes (one Alembic migration)

| Table | Change |
|---|---|
| `users` | + `erp_id` (unique, nullable), + `auth_source` (`LOCAL`/`ERP`), + `program`, `section`, `semester`, + `photo_key` (cached ERP photo), + `face_verification` (`VERIFIED`/`MISMATCH`/`NO_REFERENCE`, nullable), + `biometric_opt_out` (bool); `password_hash` and `email` become nullable (ERP users have no local password) |
| `classes` | + `program` (nullable; needed for roster import) |
| `enrollments` | + `source` (`ERP_IMPORT` / `QR_VERIFIED` / `TEACHER_APPROVED` / `LEGACY`) |
| **new** `join_requests` | id, class_id, student_id, status (`PENDING`/`APPROVED`/`REJECTED`), created_at, decided_by, decided_at; unique (class_id, student_id) |
| **new** `reenroll_requests` | id, student_id, requested_by, session_id (nullable), reason, created_at, resolved_at |
| `session_media` | kind may be `VIDEO`; + `duration_s` |

Existing dev accounts become `auth_source = LOCAL`. Pending join requests live in their own table
so they can never leak into rosters, matching or reports (all of which read `enrollments`).

## 7. API changes (`/api/v1`)

| Method | Path | Role | Change |
|---|---|---|---|
| POST | `/auth/login` | public | body `{login_id, password}`; `login_id` = ERP ID, or email for the local admin |
| GET | `/me/status` | any | `{face_setup_required, reenroll_request, biometric_opt_out, photo_url}` — drives the gate |
| POST | `/me/biometrics/opt-out` | student | "My teacher will mark me by hand" (withdraws consent, deletes samples) |
| GET | `/me/attendance` | student | **403 `FACE_SETUP_REQUIRED`** while the gate is open |
| POST | `/join/{code}` | **student (signed in)** | returns `{status: "JOINED" \| "PENDING"}`; no more self-registration body |
| POST | `/classes/{id}/import-roster` | teacher | ERP import → `{added, already_enrolled, total_in_erp}` |
| GET | `/classes/{id}/join-requests` | teacher | pending list (with ERP photo, section) |
| POST | `/classes/{id}/join-requests/{rid}/approve` · `/reject` | teacher | audited |
| POST | `/classes/{id}/students/{sid}/reenroll-request` | teacher | `{reason, session_id?}`; student must be in this teacher's class (IDOR check) |
| POST | `/classes/{id}/students/{sid}/confirm-identity` | teacher | clears `MISMATCH` after the teacher compares photos; audited |
| POST | `/sessions/{id}/media` | teacher | accepts up to 30 `photos` and one `video`; streamed to disk |
| GET | `/sessions/{id}` | teacher | results gain `photo_url` (ERP), `face_verification`, `keeps_missing` |

Admin: the "Add teacher" form is removed (teachers come from the ERP); turning accounts off stays.

## 8. Key flows

**Student first sign-in**
1. Enters ERP ID + password → ERP verifies → account created/updated → photo cached.
2. `/me/status` says `face_setup_required` → **gate**: *Set up my face* or *Not now — teacher marks me by hand*.
3. Setup: consent → 3–5 selfies → worker embeds, cross-checks with the ERP photo → `VERIFIED` / `MISMATCH` / `NO_REFERENCE` → gate opens.

**Teacher asks for a re-capture**
1. Review screen → student row → *Ask to retake face photos* → reason (e.g. "Not recognised in photos").
2. Student's next sign-in → gate shows the teacher's reason → new selfies accepted → request resolved automatically.

**Video attendance**
1. Teacher → *Record video* (back camera) → walks bench by bench, pausing ~2 s → stop → upload with progress bar → *Check attendance*.
2. Worker: `ffmpeg` samples 2 frames/s → keep the sharpest frame in each second and drop blurry ones → detect + embed → one-to-one assignment **per frame** → best distance per student across all frames → unknown faces clustered (one crop per unknown person) → results → video deleted.

## 9. Matching policy changes

- `MISMATCH` students: decision is capped at **UNCERTAIN** (teacher must decide), whatever the score.
- Video faces below a sharpness threshold are ignored (motion blur while walking).
- Everything else (thresholds, one-to-one assignment, human finalize) is unchanged.

## 10. Risks and limits

| Risk | Mitigation |
|---|---|
| ERP photo is years old | Cross-check uses a looser threshold than matching; mismatch only forces review, never blocks the student |
| Large uploads on weak college Wi-Fi | In-app recording is compressed; progress bar; upload can be retried; photo option still exists |
| Same student counted twice from many frames | One-to-one assignment per frame + best-of across frames (a student is present or not, never counted twice) |
| Proxy: a friend enrolls their face on another account | ERP cross-check → `MISMATCH` → never auto-present |
| Gate feels coercive | "Not now — teacher marks me by hand" is always available (DPDP: consent must be free) |
| Mock ≠ real ERP | Adapter contract tests; real integration needs university IT approval and preferably SSO |

## 11. Implementation plan (vertical slices; each ends with tests + review)

1. **ERP identity:** adapter + mock ERP data + ERP login + account sync + profile photos; remove self-registration; local admin login kept. Migration.
2. **Verified rosters:** ERP roster import, verified QR join, join-request approval UI.
3. **Face gate + cross-check:** `/me/status`, blocking screen with opt-out, API enforcement, ERP photo cross-check, `MISMATCH` cap, teacher "confirm identity".
4. **Re-capture requests:** teacher action + reasons, "keeps missing" hint, automatic resolution.
5. **More photos + video:** 30-photo limit, streamed uploads with progress, in-app video recorder, worker frame extraction + unknown-face clustering, delete video after success.
6. **Hardening:** tests for every slice (incl. IDOR on new endpoints, gate enforcement, video job with a synthetic clip), docs, HCI review, end-to-end smoke test.

Out of scope: liveness/anti-spoofing (unchanged), real ERP connection, SSO.
