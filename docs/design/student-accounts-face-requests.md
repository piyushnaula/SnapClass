# SnapClass: student accounts, face photo requests, 10 class photos

Status: **implemented (2026-10-07)**. Replaces the rejected ERP design
([erp-video-reenroll-design.md](erp-video-reenroll-design.md)): SnapClass stays separate from the ERP.

## 1. What changed and why

| Change | Why |
|---|---|
| Students create their own account with **student ID + full name + password** and sign in with the student ID | Students know their ID; no email needed. Teachers and the admin still sign in with email |
| Joining a class needs a **signed-in student** (invite link / QR) | One account per student across all subjects; no typing details again per class |
| Teacher can **ask a student for a new face photo** | Old or poor selfies stop matching; the teacher needs a one-tap way to fix it |
| While a request is open the student is **not marked present automatically** in any lecture | Their old photos are no longer trusted. The teacher can still mark them by hand (human always decides) |
| Students see the request as a **pop-up on sign-in and a banner** until they upload new photos | Nobody misses it |
| Request **closes automatically** when new face photos are accepted | No extra step for the teacher |
| **10 class photos** per lecture (was 4) | Large rooms need more angles |
| Students see the **full history** per subject | "Everything in their account" |

## 2. Flows

**Student**
1. *Create account* → student ID (stored upper-case, unique), full name, password → signed in.
2. Opens the teacher's invite link → *Join this class* (or creates an account / signs in on the same page, then joins automatically).
3. Face setup: permission → 3–5 selfies.
4. *My attendance*: per subject: attended / total, %, advice ("attend the next 3 classes"), full lecture history.

**Teacher asks for a new photo**
1. Review screen: a student is "Not found" or "Not sure" → *Ask for new face photo* → choose a reason → *Send request*.
   (Also available in the class's *Students* tab.)
2. From the next lecture on, the match job leaves this student out of face and voice matching.
   Their row shows *Waiting for a new face photo: not marked automatically* and defaults to Absent.
   The teacher can still press Present.
3. The student signs in → pop-up + banner with teacher, subject and reason → uploads new selfies.
4. Worker accepts the photos → every open request for this student is closed → automatic marking resumes.
5. The teacher can *Cancel request* at any time. Request and cancellation are written to the audit log.

## 3. Backend changes

| Area | Change |
|---|---|
| `users.email` | now nullable (students may have none); still unique when present |
| new table `face_update_requests` | id, student_id, requested_by, class_id, session_id, reason, created_at, resolved_at |
| `match_results.face_update_pending` | true when the student was left out of matching because of an open request |
| `POST /auth/login` | body `{login_id, password}`: `login_id` with "@" = email, otherwise student ID |
| `POST /auth/register` | `{student_id, full_name, password}` → 201 + tokens; 409 `STUDENT_ID_TAKEN`; 5 sign-ups/hour per IP |
| `POST /join/{code}` | requires a signed-in **student**; no request body; joining twice is harmless |
| `POST/DELETE /classes/{id}/students/{sid}/face-update-request` | teacher of that class only (others get 404); idempotent |
| `GET /me/biometrics` | adds `face_update_request {reason, requested_by, subject, created_at}` |
| `GET /me/attendance` | `recent` (last 10) → `history` (all lectures) |
| match job | skips students with an open request; records `face_update_pending` |
| face enrollment job | on success closes the student's open requests |
| `MAX_PHOTOS` | 4 → 10 |

Migration: `74b2ec1edf3a_student_id_login_and_face_update_.py` (the new boolean column gets
`server_default false` so existing rows migrate).

## 4. Tests added

- Register + sign in with student ID (case-insensitive), duplicate ID → 409, invalid ID → 422.
- Join needs a signed-in student; teachers cannot join; joining twice is harmless.
- Request / idempotency / cancel / student sees the reason / audit entries.
- Only the class's teacher can request (other teacher → 404, student → 403).
- 10 photos accepted, the 11th refused.
- Match job: a perfect face match is **not** marked present while a request is open.
- Enrollment job: accepted photos close the request.

## 5. Known risk: student ID squatting (no ERP)

Without the ERP, SnapClass cannot prove that the person registering `23CSE041` really is that
student. Someone could register another student's ID first, and the real student would then
see "already registered". Mitigations available today:

- The teacher sees every name on the roster and can remove anyone who does not belong.
- The admin can turn off a suspicious account (audited).
- Face setup + teacher review means an impostor's face never matches the real student's face.

Possible next steps (not built): teacher uploads the official roster (list of student IDs) so
only those IDs can join; or teacher approval of each join; or the admin resets a disputed ID.
