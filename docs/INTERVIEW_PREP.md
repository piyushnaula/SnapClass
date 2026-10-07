# SnapClass — Learning and Interview Guide

> This guide is for **you, the author**. Goal: understand every part of SnapClass well enough to
> explain it on a whiteboard, defend every decision, and answer follow-up questions honestly.
>
> Golden rule for interviews: **say only what you have built or measured.** If something is a
> target or an idea, say so ("I designed for…", "I would measure…"). Interviewers respect that.

## Contents
1. [Study plan (5 days)](#1-study-plan-5-days)
2. [Read the code in this order](#2-read-the-code-in-this-order)
3. [Concepts you must be able to explain](#3-concepts-you-must-be-able-to-explain)
4. [How to pitch the project](#4-how-to-pitch-the-project)
5. [Resume bullets (honest)](#5-resume-bullets-honest)
6. [Question bank with answers](#6-question-bank-with-answers)
7. [STAR stories from this project](#7-star-stories-from-this-project)
8. [Weaknesses and what I would improve](#8-weaknesses-and-what-i-would-improve)
9. [Numbers cheat sheet](#9-numbers-cheat-sheet)
10. [Glossary](#10-glossary)

---

## 1. Study plan (5 days)

| Day | Focus | Read | Practise |
|---|---|---|---|
| 1 | The problem and the big picture | [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) §1–6, [HLD.md](HLD.md) §1–4 | Draw the architecture from memory in 3 minutes |
| 2 | Data and APIs | [LLD.md](LLD.md) §4–5, `models.py`, `schemas.py` | Explain "proposal vs truth"; write the report SQL from memory |
| 3 | The ML pipeline | LLD §6, `ml/face.py`, `ml/matcher.py`, `domain/decisions.py` | Explain L2 vs cosine, Hungarian vs greedy, the uncertainty band |
| 4 | Reliability and security | LLD §7–8, `workers/match_job.py`, `services/auth_service.py` | Explain the two-transaction job and refresh-token rotation |
| 5 | Practice | §4–7 of this guide | Answer 15 questions from §6 aloud; tell 2 STAR stories |

Run the project and click through every role at least once (README → "Try the whole flow").

---

## 2. Read the code in this order

Each step says **what to look for** and **one thing to try**.

1. **`backend/snapclass/domain/session.py`** — the lecture state machine.
   *Look for:* `ALLOWED_TRANSITIONS`. *Try:* name a transition that is forbidden and why
   (REVIEW → PROCESSING: changed photos must go through UPLOADED).
2. **`domain/decisions.py`** — how scores become PRESENT / UNCERTAIN / NOT_DETECTED.
   *Look for:* why voice alone never returns PRESENT. *Try:* compute `decide(0.9, None)` by hand.
3. **`ml/matcher.py`** — one-to-one assignment. *Try:* run `tests/unit/test_matcher.py::test_hungarian_beats_greedy` and explain the example.
4. **`ml/face.py`** — detect → align → embed → normalise. *Look for:* why boxes are rescaled.
5. **`workers/match_job.py`** — the core job. *Look for:* TX 1, slow part, TX 2, the status re-check, keeping teacher choices.
6. **`services/session_service.py`** — upload, check, review, finalize, corrections. *Look for:* `get_owned_session` (IDOR) and `finalize` (one transaction).
7. **`services/auth_service.py` + `core/security.py`** — login, rotation, reuse detection, signed URLs.
8. **`workers/queue.py` + `workers/callbacks.py`** — retries, job ids, "fail only after the last retry".
9. **`services/face_update_service.py`** — the re-capture feature end to end.
10. **`frontend/src/api.js`** — automatic token refresh; **`pages/teacher/SessionPage.jsx`** — the teacher flow.
11. **`tests/`** — read one test per folder; tests are the best documentation of behaviour.

---

## 3. Concepts you must be able to explain

Explain each one in **two or three plain sentences**, then connect it to SnapClass.

| Concept | Plain explanation | In SnapClass |
|---|---|---|
| **Face embedding** | A model turns a face into a list of numbers so that photos of the same person are close together and different people are far apart | SFace gives 128 numbers per face |
| **Detection vs recognition** | Detection finds *where* faces are; recognition decides *who* it is | YuNet detects, SFace recognises |
| **L2 distance vs cosine similarity** | L2 = straight-line distance; cosine = angle. For unit-length vectors they carry the same information: `d² = 2 − 2·cos` | Faces compared with L2 (pgvector `<->`); fusion converts to cosine |
| **Threshold and uncertainty band** | One threshold forces every case into yes/no. Two thresholds create a "not sure" zone for humans | `face_accept` 1.05, `face_reject` 1.15 |
| **FAR / FRR / EER** | FAR = strangers wrongly accepted; FRR = genuine people wrongly rejected; EER = where they are equal. Lowering one raises the other | `eval/evaluate.py` picks the threshold with FAR ≤ 1 % |
| **Validation vs test split by person** | Tune on some people, report on *different* people; splitting photos of the same person leaks information | Evaluation design |
| **Hungarian algorithm** | Finds the pairing of faces to students with the smallest total cost where each is used at most once | `scipy.optimize.linear_sum_assignment` |
| **Why restrict to the roster** | Each extra comparison is another chance for a false match; FAR grows with the size of the gallery | Compare with ≤ 120 students, not 5,000 |
| **HNSW index** | A graph-based index that finds approximate nearest vectors fast | pgvector index for the duplicate-account check only |
| **VAD** | Voice activity detection: which parts of audio contain speech | webrtcvad, 30 ms frames |
| **Job queue** | Slow work is put in a list; separate workers take jobs from it; the web request returns immediately | Redis + RQ, queues `match` and `enroll` |
| **Idempotency** | Doing the same operation twice has the same effect as once | Fixed job id `match-{id}`; `/process` returns 200 the second time |
| **Row lock (`SELECT … FOR UPDATE`)** | Locks one row until the transaction ends so two writers cannot clash | Session row in the worker and in finalize |
| **Why two transactions** | Don't hold locks during slow work; re-check after the slow work | Match job |
| **State machine** | Allowed statuses and allowed moves written in one place | `domain/session.py`, illegal move → 409 |
| **Human-in-the-loop** | The model proposes, a person decides | `match_results` vs `attendance_records` |
| **JWT access token** | Signed, short-lived proof of identity; server does not store it | 15 minutes, HS256 |
| **Refresh token rotation + reuse detection** | Each refresh gives a new token and kills the old one; if an old one is used again, someone copied it → revoke all | `rotate_refresh_token` |
| **bcrypt** | Slow, salted password hash; slowness makes guessing expensive | cost 12 |
| **RBAC vs IDOR** | RBAC: what a *role* may do. IDOR: accessing *someone else's* object by changing an id. Need both checks | `require_role` + `get_owned_class` → 404 |
| **Signed URL (HMAC)** | A link that contains an expiry and a signature only the server can create | Face crops in `<img src>`, 5 minutes |
| **Magic bytes** | The first bytes of a file reveal its real type, whatever the file name says | JPEG `FF D8 FF`, PNG `89 50 4E 47` |
| **CSV injection** | A cell starting with `=` can run as a formula in Excel | Prefix `'` in exports |
| **Consent (DPDP Act, 2023)** | Biometric data needs free, informed, specific consent and must be erasable | Versioned consent, erase button |
| **Nielsen's heuristics** | 10 rules of thumb for usable interfaces | [design/ux-hci.md](design/ux-hci.md) |

---

## 4. How to pitch the project

### 30 seconds
> "SnapClass is an attendance system for college classrooms. The teacher takes a few photos of
> the class; a background worker detects faces, compares them only with that class's students,
> and proposes who is present. The teacher reviews 'not sure' cases and saves. I built it as a
> real service: FastAPI, Postgres with pgvector, a Redis job queue with retries, OpenCV face
> models, a React frontend, 72 automated tests and Docker. The key design idea is that the AI only
> proposes: attendance is written only when a teacher confirms."

### 2 minutes (structure)
1. **Problem** — roll call wastes minutes and allows proxies.
2. **Solution** — photo → async matching → teacher review → save.
3. **Architecture** — SPA → API → Postgres; slow work → Redis queue → workers.
4. **Two interesting decisions** — roster-restricted one-to-one matching; proposal vs truth tables.
5. **Reliability** — idempotent two-transaction jobs, retries, stuck-job sweeper.
6. **Privacy** — consent, embeddings only, erasure, signed URLs, retention.
7. **Honesty** — "Accuracy isn't measured yet; I built the evaluation script and need a consented dataset."

### Whiteboard deep dive (draw in this order)
Requirements → estimates (embeddings are tiny; media is the cost) → boxes (SPA, API, Redis, worker,
Postgres, storage) → the take-attendance sequence → state machine → data model (proposal vs truth)
→ failure handling → security → how to scale ×10.

---

## 5. Resume bullets (honest)

Use these **now** (every fact is in the repo):

- Built **SnapClass**, a face- and voice-based classroom attendance platform (**FastAPI, PostgreSQL + pgvector, Redis/RQ, OpenCV, React**) in which ML proposals become attendance records only after teacher confirmation; 44 REST endpoints, 18-table schema, 7-service Docker Compose stack.
- Designed an **asynchronous matching pipeline**: roster-restricted face matching with **Hungarian one-to-one assignment**, an uncertainty band routed to human review, and **idempotent two-transaction worker jobs** with retries and stuck-job recovery.
- Implemented **security and privacy controls**: rotating refresh tokens with reuse detection, ownership-scoped queries (IDOR → 404), login rate limiting, magic-byte upload validation, HMAC-signed media URLs, versioned consent, biometric erasure and media retention.
- Wrote **72 automated tests** (unit, property-based, API, worker) against real Postgres/Redis plus a **25-check end-to-end smoke test**; traced an **18 s worker cold start** to librosa JIT compilation and removed it with a start-up warm-up (job then ran in 0.4 s on my machine).
- Designed the UI for **non-technical users** using HCI principles (Nielsen's heuristics, Fitts's and Hick's laws, WCAG touch targets), with adjustable text size and contrast.

Add these **only after you measure them** (fill in real numbers from `eval/report.json` and a load test):

- "Reached ___ % FAR at ___ % FRR on a consented ___-person held-out test set (threshold chosen on a separate validation set)."
- "p95 API latency ___ ms at 50 concurrent users (Locust); median teacher review time ___ s in a pilot with ___ teachers."

---

## 6. Question bank with answers

### System design
1. **Why a job queue instead of doing matching in the request?**
   Matching takes seconds and uses CPU. Inside a request it would block API workers, time out on
   slow networks, and fail in different ways. A queue gives retries, back-pressure (queue depth),
   and lets me scale workers separately from the API.
2. **Why RQ and not Celery or Kafka?**
   RQ only needs Redis and is simple. My scale (~1,000 jobs/day) does not need Celery's routing or
   Kafka's streaming. If I needed multiple brokers or complex workflows I would revisit.
3. **How does the client know when the job is done?**
   It polls `GET /sessions/{id}` every 2 seconds while the status is PROCESSING. I chose polling
   over SSE because the browser's EventSource cannot send an Authorization header.
4. **How would you scale to 10 colleges?**
   API is stateless → replicas behind a load balancer. Workers autoscale on queue depth. Media moves
   to S3 with lifecycle rules. Managed Postgres with a read replica for reports. Per-class matching
   stays small, so the hot path doesn't change. Add a tenant id for isolation.
5. **What is the bottleneck?**
   Worker CPU for face detection on large photos, and media storage. Not the database: embeddings are ~30 MB.
6. **Why no separate vector database?**
   Total vectors are tiny (~30 MB). pgvector keeps vectors next to relational data with transactions,
   and per-class matching runs in NumPy anyway. I use HNSW only for the cross-student duplicate check.
7. **What happens if a worker dies mid-job?**
   RQ retries up to 3 times. If the job vanished, the scheduler re-queues lectures stuck in PROCESSING
   for over 10 minutes. The worker's status re-check makes duplicates harmless.

### Backend and database
8. **Explain the two-transaction worker.**
   TX 1 locks the lecture, checks it is PROCESSING, loads the roster, and ends. Then files are read
   and models run with no transaction open. TX 2 locks again, re-checks PROCESSING, and writes all
   results plus the status change atomically. No lock is held for seconds, and a late duplicate job
   finds the status already changed and does nothing.
9. **Why separate `match_results` and `attendance_records`?**
   Proposal vs truth. Only the teacher's Save writes the truth table, so the human-in-the-loop rule
   is enforced by the schema, not just the UI.
10. **How is `/process` idempotent?**
    If the lecture is already PROCESSING, REVIEW or FINALIZED it returns the current state with 200
    and queues nothing. The RQ job id `match-{session_id}` also prevents duplicate jobs.
11. **How do you stop a teacher from reading another teacher's class?**
    Every query uses `get_owned_class` / `get_owned_session`, which filter by `teacher_id`. Foreign
    ids return 404 so ids can't even be probed. There are tests for this.
12. **What happens to the teacher's choices when they add photos and check again?**
    The job copies existing `teacher_decision` values into the new results, so human input is never
    silently lost. A "start fresh" option clears them on purpose.
13. **How did you handle schema changes?**
    Alembic migrations; CI runs `alembic upgrade head` and `alembic check` to catch drift. When I added
    a NOT NULL column to a table with data, I gave it a server default so existing rows migrate.

### Machine learning
14. **Why OpenCV YuNet + SFace instead of dlib?**
    dlib needs C++ build tools on Windows and its HOG detector misses small, angled, back-row faces.
    YuNet is a small CNN detector and SFace gives 128-d embeddings; both install with pip and run on CPU.
15. **Why one-to-one assignment?**
    With nearest-neighbour, two faces can both pick the same student. The Hungarian algorithm
    minimises total distance with each face and student used at most once. Greedy can lock in an early
    wrong pair; there is a unit test showing a case where greedy fails.
16. **How do you choose thresholds?**
    Not by guessing: collect a consented dataset, split by person into validation and test, sweep
    thresholds on validation, pick the lowest FRR with FAR ≤ 1 %, report FAR/FRR on test. The current
    values are placeholders from the SFace authors' suggestion — I say this openly.
17. **Why is voice never enough for PRESENT?**
    Classroom audio is noisy, overlapping and easy to replay. Voice only adds evidence when a face is also found.
18. **How do you handle a student whose selfie is old?**
    The teacher presses "Ask for new face photo". The match job then excludes that student (no automatic
    PRESENT), the student sees a pop-up, and the request closes when new photos pass the quality checks.
19. **What about spoofing with a printed photo?**
    Out of scope; I state it. Mitigation: the teacher's device takes the photo in class and a human reviews
    every result. Next step would be liveness detection or multi-frame capture.
20. **How would you know if accuracy drops?**
    Track the teacher override rate and the "not sure" rate per week — a rising override rate means the
    model or thresholds no longer fit.

### Security and privacy
21. **Walk me through refresh-token rotation.** — §8 of LLD: hash lookup, revoke old, issue new; reuse of a revoked token revokes all tokens.
22. **Why store refresh tokens as hashes?** — If the database leaks, the attacker cannot use the tokens.
23. **Why SHA-256 for tokens but bcrypt for passwords?** — Tokens are long and random (no guessing); passwords are short and human, so they need a slow hash.
24. **How do face crops appear in `<img>` without exposing them?** — 5-minute HMAC-signed URLs; only crops and class photos can be served.
25. **What biometric data do you store?** — Only embeddings (numbers). Selfies are deleted after embedding; class media is deleted N days after saving; students can erase everything.
26. **Known security weaknesses?** — Tokens in localStorage (XSS risk), student-ID squatting without an official roster, no password reset. I list them in the docs with next steps.

### Frontend and HCI
27. **Why no router library or Tailwind?** — Requirement to keep the stack minimal; a 40-line hash router and plain CSS are enough and easy to read.
28. **How does the client refresh tokens?** — On a 401, `api.js` calls `/auth/refresh` once (parallel requests share the same promise) and retries; if it fails, the user is signed out.
29. **How did you make it usable for non-technical teachers?** — Plain words ("Not sure", "Save attendance"), "What to do now" boxes, one main button per step, filters and search for big classes, confirmations, text size/contrast settings, 44 px targets. I planned a think-aloud test and SUS survey to verify.

### Testing and DevOps
30. **Why test against real Postgres instead of SQLite?** — pgvector, JSONB, CHECK constraints and row locks behave differently in SQLite; tests would pass but production would fail.
31. **What does your property-based test check?** — For random embeddings and thresholds, no student and no face is used twice and every returned distance is within the threshold.
32. **What runs in CI?** — ruff, mypy, migrations + drift check, pytest with Postgres and Redis services, and a frontend build.

---

## 7. STAR stories from this project

Use real stories; these all happened while building SnapClass.

**1. The 18-second job (performance debugging)**
- *Situation:* the end-to-end test showed a match job taking 18.5 s for one photo.
- *Task:* find why; the target is < 20 s for a whole class.
- *Action:* profiled each stage inside the worker container. Detection 0.06–0.36 s, audio decode 0.1 s,
  VAD 1 ms — but the **first** voice embedding took 18.4 s. Timed `librosa.feature.melspectrogram`:
  18 s first call, 0.002 s second → numba JIT compilation. Added a warm-up call when the worker starts.
- *Result:* the same job then took 0.41 s (one measurement, my machine). Lesson: measure per stage before optimising.

**2. The 502 after a deploy (infrastructure)**
- *Situation:* after rebuilding the API container, every request through nginx returned 502.
- *Action:* found nginx had resolved `api` to an IP once at start-up; the new container had a new IP.
  Configured Docker's DNS resolver with a 10 s validity and a variable in `proxy_pass`.
- *Result:* API restarts no longer break the site.

**3. The admin who could never log in (validation)**
- *Situation:* the seeded admin `admin@snapclass.local` got 422 at login.
- *Action:* the email validator rejects reserved domains like `.local`. Changed the default and made
  the seed script validate the email with the **same** rules as the login endpoint, failing at start-up.
- *Result:* misconfiguration now fails loudly and early instead of silently.

**4. Retry semantics (reading library source)**
- *Situation:* I needed "mark the lecture FAILED only after the last retry".
- *Action:* read RQ's worker source: the failure callback runs on **every** failed attempt, before retry
  bookkeeping. So the callback returns early while `retries_left` is not zero. Added a test for it.
- *Result:* no false "failed" states while a retry is pending.

**5. User feedback changed the state machine (product)**
- *Situation:* a teacher in review wanted to add a photo of the back rows, but photos were locked after checking.
- *Action:* added transitions REVIEW/FAILED → UPLOADED, a delete-photo endpoint, "Check again", and made the
  job keep the teacher's own choices (with an opt-out). 11 new tests.
- *Result:* teachers can fix missing students before saving without losing work.

**6. Pushing back on a requirement (ethics/privacy)**
- *Situation:* the idea was to block students from seeing attendance until they set up their face.
- *Action:* pointed out that consent for biometrics must be free (DPDP Act); blocking a basic service
  for refusing would be coercive. Proposed: block automatic marking instead, always allow "mark me by hand".
- *Result:* the feature kept its purpose without forcing consent.

**7. Scope decision (ERP integration)**
- *Situation:* integrating with the college ERP for identity was considered.
- *Action:* wrote a design (adapter + mock ERP + SSO recommendation), then the decision was to stay
  standalone. Kept the document as a rejected decision record and listed the remaining risk (ID squatting).
- *Result:* clear scope; risks documented instead of hidden.

---

## 8. Weaknesses and what I would improve

| Weakness | Why it matters | Next step |
|---|---|---|
| Accuracy not measured | Can't claim it works well | Consented dataset → `eval/evaluate.py` → tune thresholds |
| No liveness detection | Printed-photo spoofing possible | Blink/motion check or anti-spoof model |
| Student-ID squatting | Fake account can take a real ID | Teacher uploads official roster (allow-list) |
| Tokens in localStorage | XSS could steal them | httpOnly refresh cookie + CSRF protection |
| No password reset | Users get locked out | Admin reset + email/OTP flow |
| Local media volume | Doesn't scale across machines | S3 with presigned uploads |
| Polling | Extra requests | SSE/WebSocket with cookie auth |
| Voice VAD accepts tones | Quality check is weak | Speech classifier, not only VAD |

---

## 9. Numbers cheat sheet

| Number | Type | Source |
|---|---|---|
| 72 automated tests passing | measured | `docker compose run --rm api pytest` |
| 25/25 end-to-end smoke checks | measured | `backend/smoke/smoke_e2e.py` |
| 44 API routes, 18 tables, ~9,400 lines of app code | counted | code |
| 18 s → 0.41 s match job after warm-up | measured once, synthetic data | profiling story |
| Embeddings ≈ 30 MB for 5,000 students | estimate | §5 System Design |
| ~21 GB media at 3 photos/lecture, 7-day retention | estimate | §5 System Design |
| Face accept/reject 1.05 / 1.15 (L2) | placeholder defaults | `domain/decisions.py` |
| FAR/FRR, latency p95, SUS score | **not measured** | — |

---

## 10. Glossary

| Term | Meaning |
|---|---|
| Lecture / session | One class meeting: class + date + period (`sessions` table) |
| Roster | Students enrolled in a class |
| Proposal | The AI's suggestion (`match_results`) |
| Finalize / Save | Teacher confirms; attendance records are written |
| Face photo request | Teacher asks a student for new selfies; blocks automatic PRESENT until done |
| Crop | Small image of one face cut from a class photo, shown during review |
| Embedding | Numbers that represent a face or voice |
| HITL | Human-in-the-loop |
| IDOR | Insecure direct object reference |
| RBAC | Role-based access control |
| FAR / FRR / EER | False accept rate / false reject rate / equal error rate |
| VAD | Voice activity detection |
| HNSW | Hierarchical navigable small world (vector index) |
| SUS | System Usability Scale (10-question questionnaire) |
