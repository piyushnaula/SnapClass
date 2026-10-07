# SnapClass — High-Level Design (HLD)

> Scope: the **big boxes** — which components exist, what each one owns, how they talk, and how
> the main user journeys flow through them. For tables, APIs and algorithms see [LLD.md](LLD.md).
> For requirements, estimates and trade-offs see [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

---

## 1. Architecture at a glance

```mermaid
flowchart TB
    subgraph Browser["Browser (phone / laptop)"]
        SPA["React SPA<br/>teacher · student · admin pages<br/>camera + microphone capture"]
    end

    subgraph Edge["frontend container"]
        NGINX["nginx<br/>serves static files<br/>proxies /api → api:8000"]
    end

    subgraph App["Application tier"]
        API["FastAPI (api)<br/>auth · RBAC · validation<br/>business rules · signed media URLs"]
        WORKER["RQ workers ×2 (worker)<br/>face: YuNet + SFace<br/>voice: webrtcvad + Resemblyzer<br/>matching: NumPy + Hungarian"]
        SCHED["Scheduler (scheduler)<br/>stuck-job sweep · retention<br/>weekly report email"]
    end

    subgraph Data["Data tier"]
        PG[("PostgreSQL 16 + pgvector<br/>system of record")]
        REDIS[("Redis 7<br/>job queues · rate-limit counters")]
        MEDIA[("Media volume<br/>photos · audio · face crops")]
    end

    SPA -->|HTTPS JSON| NGINX --> API
    API --> PG
    API --> REDIS
    API --> MEDIA
    REDIS -->|jobs| WORKER
    WORKER --> PG
    WORKER --> MEDIA
    SCHED --> PG
    SCHED --> MEDIA
    SCHED -->|re-queue| REDIS
```

**One sentence:** the browser talks only to the API; the API stores data, saves files and puts slow
work on a Redis queue; workers do the ML and write results back; a scheduler does housekeeping.

---

## 2. Components and responsibilities

| Component | Owns | Does **not** do | Scales by |
|---|---|---|---|
| **React SPA** | Screens for 3 roles, camera/mic capture, image compression (≤ 2048 px), polling, accessibility settings | Business rules (server is the source of truth) | Static files (CDN-able) |
| **nginx** | Static hosting, `/api` reverse proxy, 50 MB body limit, security headers | Logic | Replicas |
| **FastAPI API** | Authentication, RBAC, input validation, ownership checks (IDOR), state machine, file storage, queueing, reports, signed URLs | Any ML (keeps it fast and light) | Stateless → horizontal replicas |
| **RQ workers** | Match jobs (class photos/audio → proposals), enrollment jobs (selfies/voice → embeddings + quality checks) | HTTP | Number of worker processes (queue depth) |
| **Scheduler** | Re-queue stuck lectures (> 10 min), retention cleanup (hourly), weekly below-minimum email (Monday 08:00 IST) | Request handling | Exactly one instance |
| **PostgreSQL + pgvector** | Users, classes, lectures, proposals, attendance (truth), embeddings, consents, audit log, settings | Files | Vertical; read replica later |
| **Redis** | Job queues `match` (high priority) and `enroll`, retry scheduling, login rate-limit counters | Durable data | Single node at this scale |
| **Media volume** | Class photos, roll-call audio, face crops, temporary enrollment selfies | Metadata | Swap for S3 (same interface) |

---

## 3. Deployment view (Docker Compose)

```mermaid
flowchart LR
    subgraph host["One host — docker compose up"]
        FE["frontend<br/>nginx :80 → host :3000"]
        API["api<br/>uvicorn :8000"]
        W1["worker-1"]
        W2["worker-2"]
        SC["scheduler"]
        MG["migrate<br/>(runs once: alembic upgrade + seed)"]
        DB[("db<br/>pgvector/pgvector:pg16")]
        RD[("redis<br/>redis:7-alpine")]
        VOL[["volumes: pgdata, media"]]
    end
    FE --> API
    API --> DB & RD
    W1 & W2 --> DB & RD
    SC --> DB & RD
    MG --> DB
    API & W1 & W2 & SC -.-> VOL
```

- One backend **image** is used for `api`, `worker`, `scheduler` and `migrate` (different start commands).
- Start order is enforced: `db` healthy → `migrate` completes → `api`/`worker`/`scheduler` start.
- Health checks: Postgres `pg_isready`, Redis `PING`, API `/healthz`.
- Secrets (`JWT_SECRET`, admin password) come from `.env` (git-ignored); `.env.example` documents them.
- Cloud path (not deployed): EC2 + RDS (pgvector supported) + S3, HTTPS via load balancer/ACM or Caddy.

---

## 4. Main flows

### 4.1 Sign in and token refresh

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as API
    participant R as Redis
    participant D as Postgres
    B->>A: POST /auth/login {login_id, password}
    A->>R: INCR rate-limit counters (IP, account)
    A->>D: find user by student ID or email
    A->>A: bcrypt verify (dummy check if user unknown)
    A->>D: INSERT refresh_token (SHA-256 hash only)
    A-->>B: access JWT (15 min) + refresh token (7 days)
    Note over B,A: later, a request returns 401 (access token expired)
    B->>A: POST /auth/refresh {refresh_token}
    A->>D: find token by hash · revoke it · insert new one (rotation)
    A-->>B: new access + new refresh token
    Note over A,D: reuse of an already-revoked token → revoke ALL of the user's tokens
```

### 4.2 Student onboarding (register → join → consent → face enrollment)

```mermaid
sequenceDiagram
    participant S as Student browser
    participant A as API
    participant Q as Redis queue
    participant W as Worker
    participant D as Postgres
    participant F as Media volume
    S->>A: POST /auth/register {student_id, full_name, password}
    A-->>S: tokens (signed in)
    S->>A: POST /join/{code}
    A->>D: INSERT enrollment
    S->>A: POST /consent {version}
    S->>A: POST /me/biometrics/face (3–5 selfies)
    A->>A: size + magic-byte checks
    A->>F: save selfies
    A->>D: INSERT biometric_job (QUEUED)
    A->>Q: enqueue enroll job
    A-->>S: 202 Accepted (page polls status)
    Q->>W: job
    W->>F: read selfies
    W->>W: detect → exactly one face? ≥ 80 px? sharp? → embed
    W->>D: replace face_embeddings · duplicate check (HNSW) · close open face-photo requests · job DONE
    W->>F: delete selfies (raw media not kept)
```

### 4.3 Taking attendance (the core flow)

```mermaid
sequenceDiagram
    participant T as Teacher browser
    participant A as API
    participant F as Media volume
    participant Q as Redis (RQ)
    participant W as Worker
    participant D as Postgres
    T->>A: POST /classes/{id}/sessions {date, period}
    A->>D: INSERT session (CREATED)
    T->>A: POST /sessions/{id}/media (1–10 photos, optional audio)
    A->>F: save files · store SHA-256
    A->>D: status → UPLOADED
    T->>A: POST /sessions/{id}/process
    A->>A: verify every file exists and SHA-256 matches
    A->>D: status → PROCESSING (+ config snapshot of thresholds)
    A->>Q: enqueue job id "match-{session_id}" (retries 3×)
    A-->>T: 202 Accepted
    loop every 2 s
        T->>A: GET /sessions/{id}
    end
    Q->>W: job
    W->>D: TX 1: lock session, check PROCESSING, load class roster embeddings
    W->>F: read photos/audio (no DB transaction open)
    W->>W: detect → embed → one-to-one assignment per photo → best distance per student → decide
    W->>F: save face crops
    W->>D: TX 2: lock, re-check PROCESSING, replace match_results (keep teacher choices), status → REVIEW
    T->>A: GET /sessions/{id} → results + signed crop URLs
    T->>A: PATCH /sessions/{id}/results/{student} (Present/Absent)
    T->>A: POST /sessions/{id}/finalize
    A->>D: ONE TX: attendance_records + audit_log + status FINALIZED
```

**Add photos during review:** `POST /sessions/{id}/media` (or `DELETE .../media/{mid}`) moves the lecture
from REVIEW back to UPLOADED; "Check again" runs the same job, which **keeps the teacher's own
Present/Absent choices** (unless the teacher ticks "start fresh").

### 4.4 Face photo request (re-capture)

```mermaid
sequenceDiagram
    participant T as Teacher
    participant A as API
    participant D as Postgres
    participant W as Worker
    participant S as Student
    T->>A: POST /classes/{c}/students/{s}/face-update-request {reason}
    A->>D: INSERT face_update_request (open) + audit
    Note over W,D: every following match job skips this student →<br/>never auto-PRESENT (teacher can still mark by hand)
    S->>A: sign in → GET /me/biometrics
    A-->>S: request {teacher, subject, reason} → pop-up + banner
    S->>A: POST /me/biometrics/face (new selfies)
    W->>D: embeddings replaced → open requests resolved
```

---

## 5. Lecture (session) state machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> UPLOADED: photos/audio added
    UPLOADED --> CREATED: last photo removed
    UPLOADED --> PROCESSING: Check attendance
    PROCESSING --> REVIEW: job succeeded
    PROCESSING --> FAILED: job failed after 3 retries
    FAILED --> PROCESSING: Check again
    FAILED --> UPLOADED: photos changed
    REVIEW --> UPLOADED: photos added / removed
    REVIEW --> FINALIZED: Save attendance
    FINALIZED --> FINALIZED: correction (reason + audit)
```

- All transitions are checked in **one place** (`domain/session.py`); an illegal move → HTTP 409.
- Photos are **locked** only while PROCESSING (the worker is reading them) and after FINALIZED.

---

## 6. Asynchronous processing design

| Concern | Design |
|---|---|
| Queues | `match` (teacher is waiting → processed first) and `enroll` |
| Job identity | `match-{session_id}` — one job per lecture; duplicates impossible |
| Retries | `Retry(max=3, interval=[10, 30, 60])`; needs the RQ scheduler (`with_scheduler=True`) |
| Failure | `on_failure` callback runs after **every** failed attempt (verified in RQ source), so it marks FAILED only when `retries_left` is 0 |
| Idempotency | Worker re-checks `status == PROCESSING` under a row lock before writing; late/duplicate jobs do nothing |
| Locks | Two short transactions; no lock is held during file I/O or inference |
| Stuck jobs | Scheduler re-queues lectures in PROCESSING > 10 min if no live job exists |
| Model loading | Models load **once per worker** at start-up (RQ `SimpleWorker`, no fork per job) and the voice model is **warmed up** (first call compiles librosa code: 18 s cold → 0.4 s warm, measured once) |
| Back-pressure | Queue depth visible on the admin dashboard; add workers when it grows |

---

## 7. Technology choices

| Layer | Choice | Why | Alternatives considered |
|---|---|---|---|
| API | Python 3.11, FastAPI, Pydantic v2 | Typed, fast to build, automatic OpenAPI docs, same language as the ML | Django REST (heavier), Node/Express (ML in another language) |
| ORM / migrations | SQLModel (SQLAlchemy 2) + Alembic | Typed models; explicit transactions; versioned schema | Raw SQL only |
| Database | PostgreSQL 16 + pgvector | One store for relational data **and** vectors, with transactions | Separate vector DB (unnecessary at ~30 MB of vectors) |
| Queue | Redis 7 + RQ | Simple, Redis-only | Celery (more config), Kafka (overkill) |
| Face | OpenCV YuNet (detector) + SFace (128-d) | pip install, CPU-friendly, finds small faces | dlib (needs C++ build; HOG misses back rows), InsightFace/ArcFace (stronger, heavier) |
| Voice | webrtcvad + Resemblyzer (256-d) + ffmpeg | Lightweight speaker embeddings; ffmpeg decodes browser audio | SpeechBrain ECAPA (stronger, heavier) |
| Assignment | SciPy `linear_sum_assignment` | Optimal one-to-one matching | Greedy (simpler, can be wrong) |
| Frontend | React 19 + Vite, plain JavaScript and CSS | Simple to read; author's requirement: no extra frontend stack | Next.js (SSR not needed), Tailwind/TypeScript (more tooling) |
| Auth | PyJWT + bcrypt | Standard, explicit | Managed auth service |
| Ops | Docker Compose, GitHub Actions CI, JSON logs, Prometheus metrics | Reproducible local stack, automated checks | Kubernetes (overkill) |

---

## 8. Cross-cutting concerns

- **Security:** see [SYSTEM_DESIGN.md §12](SYSTEM_DESIGN.md#12-security-and-privacy).
- **Errors:** every error has the same JSON shape with a `request_id`; no stack traces leave the server.
- **Configuration:** `pydantic-settings` reads environment variables; runtime-changeable settings
  (thresholds, retention) live in the `app_settings` table and every change is audited.
- **Reproducibility of decisions:** each lecture stores the thresholds and model versions it used
  (`config_snapshot`), so any decision can be explained later.
- **Usability:** the UI follows Nielsen's heuristics and accessibility rules (text size, high contrast,
  44 px targets, keyboard, screen reader labels) — see [design/ux-hci.md](design/ux-hci.md).
