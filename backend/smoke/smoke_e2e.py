"""End-to-end smoke test against the RUNNING stack (nginx → API → Redis → worker → Postgres),
using the real face and voice models.

It uses synthetic images (no real faces) and a synthetic tone, so it proves that every part is
wired together correctly. It does NOT measure recognition accuracy (see eval/).

Run (stack must be up):
    docker compose run --rm api python smoke/smoke_e2e.py

It creates a few test accounts and a test class with a random suffix in the database you point it
at, so use it on a development stack only.
"""

import os
import subprocess
import sys
import time
import uuid

import cv2
import httpx
import numpy as np

BASE = os.environ.get("SMOKE_BASE_URL", "http://frontend/api/v1")
RUN = uuid.uuid4().hex[:6]
client = httpx.Client(timeout=60)
passed = 0


def check(condition: bool, message: str) -> None:
    global passed
    if not condition:
        print(f"FAIL {message}")
        sys.exit(1)
    passed += 1
    print(f"PASS {message}")


def jpeg(width: int = 1280, height: int = 960, seed: int = 0) -> bytes:
    pixels = np.random.default_rng(seed).integers(90, 160, size=(height, width, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", pixels)[1].tobytes()


def tone_webm(seconds: int = 6) -> bytes:
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=220:duration={seconds}",
        "-c:a",
        "libopus",
        "-f",
        "webm",
        "pipe:1",
    ]
    return subprocess.run(command, capture_output=True, check=True).stdout


def bearer(token_response: dict) -> dict:
    return {"Authorization": f"Bearer {token_response['access_token']}"}


def wait_for(fetch, done, seconds: int = 120):  # noqa: ANN001, ANN201
    end = time.time() + seconds
    value = fetch()
    while time.time() < end and not done(value):
        time.sleep(1.5)
        value = fetch()
    return value


# ---------- Accounts ----------
admin_login = client.post(
    f"{BASE}/auth/login", json={"login_id": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}
)
check(admin_login.status_code == 200, "admin signs in with email (through nginx)")
ADMIN = bearer(admin_login.json())

teacher_email = f"teacher-{RUN}@snapclass.dev"
created = client.post(
    f"{BASE}/admin/teachers",
    json={"email": teacher_email, "full_name": "Smoke Teacher", "password": "smoke-pass-123"},
    headers=ADMIN,
)
check(created.status_code == 201, "admin creates a teacher")
TEACHER = bearer(
    client.post(f"{BASE}/auth/login", json={"login_id": teacher_email, "password": "smoke-pass-123"}).json()
)

student_id = f"SMK{RUN.upper()}"
registered = client.post(
    f"{BASE}/auth/register",
    json={"student_id": student_id.lower(), "full_name": "Smoke Student", "password": "student-pass-1"},
)
check(registered.status_code == 201, "student registers with a student ID")
login_student = client.post(f"{BASE}/auth/login", json={"login_id": student_id, "password": "student-pass-1"})
check(login_student.status_code == 200, "student signs in with the student ID")
STUDENT = bearer(login_student.json())

# ---------- Class and joining ----------
klass = client.post(
    f"{BASE}/classes", json={"subject": f"Smoke {RUN}", "section": "A", "semester": 5}, headers=TEACHER
).json()
invite = client.post(f"{BASE}/classes/{klass['id']}/join-codes", json={}, headers=TEACHER).json()
check(invite["qr_png_base64"].startswith("iVBOR"), "invite code comes with a PNG QR code")
joined = client.post(f"{BASE}/join/{invite['code']}", headers=STUDENT)
check(joined.status_code == 200 and joined.json()["already_joined"] is False, "signed-in student joins the class")

# ---------- Enrollment with the real models ----------
consent = client.get(f"{BASE}/consent/current", headers=STUDENT).json()
client.post(f"{BASE}/consent", json={"version": consent["version"]}, headers=STUDENT)
faces = [("photos", (f"p{i}.jpg", jpeg(640, 480, i), "image/jpeg")) for i in range(3)]
check(
    client.post(f"{BASE}/me/biometrics/face", files=faces, headers=STUDENT).status_code == 202,
    "face enrollment is queued",
)
bio = wait_for(
    lambda: client.get(f"{BASE}/me/biometrics", headers=STUDENT).json(), lambda b: b["jobs"][0]["status"] != "QUEUED"
)
check(
    bio["jobs"][0]["status"] == "FAILED" and "No face found" in bio["jobs"][0]["message"],
    "worker's face model rejects photos without a face",
)
clips = [("clips", (f"c{i}.webm", tone_webm(), "audio/webm")) for i in range(3)]
check(
    client.post(f"{BASE}/me/biometrics/voice", files=clips, headers=STUDENT).status_code == 202,
    "voice enrollment is queued",
)
bio = wait_for(
    lambda: client.get(f"{BASE}/me/biometrics", headers=STUDENT).json(), lambda b: b["jobs"][0]["status"] != "QUEUED"
)
print(f"INFO voice job on a pure tone: {bio['jobs'][0]['status']} (webrtcvad can accept a pure tone as speech)")

# ---------- Taking attendance ----------
lecture = client.post(
    f"{BASE}/classes/{klass['id']}/sessions", json={"session_date": "2026-10-07", "period": 3}, headers=TEACHER
).json()
media = [("photos", ("class.jpg", jpeg(), "image/jpeg")), ("audio", ("roll.webm", tone_webm(10), "audio/webm"))]
uploaded = client.post(f"{BASE}/sessions/{lecture['id']}/media", files=media, headers=TEACHER)
check(uploaded.status_code == 200 and uploaded.json()["status"] == "UPLOADED", "class photo + audio uploaded")
first, second = (client.post(f"{BASE}/sessions/{lecture['id']}/process", headers=TEACHER) for _ in range(2))
check((first.status_code, second.status_code) == (202, 200), "check attendance is idempotent (202 then 200)")


def lecture_detail() -> dict:
    return client.get(f"{BASE}/sessions/{lecture['id']}", headers=TEACHER).json()


detail = wait_for(lecture_detail, lambda d: d["status"] in ("REVIEW", "FAILED"))
check(detail["status"] == "REVIEW", f"worker finishes the check → REVIEW ({detail['processing_ms']} ms)")
photo_link = detail["media"][0]["url"]
check(
    client.get(f"{BASE.removesuffix('/api/v1')}{photo_link}").status_code == 200,
    "teacher's class photo loads through a signed link",
)

# ---------- Face photo request ----------
request = client.post(
    f"{BASE}/classes/{klass['id']}/students/{registered.json()['user']['id']}/face-update-request",
    json={"reason": "Not recognised in the class photo"},
    headers=TEACHER,
)
check(request.status_code == 201, "teacher asks the student for a new face photo")
seen = client.get(f"{BASE}/me/biometrics", headers=STUDENT).json()["face_update_request"]
check(
    seen is not None and seen["reason"] == "Not recognised in the class photo",
    "student sees the request and the reason",
)

# ---------- Add a photo during review, then check again ----------
more = client.post(
    f"{BASE}/sessions/{lecture['id']}/media",
    files=[("photos", ("back.jpg", jpeg(seed=7), "image/jpeg"))],
    headers=TEACHER,
)
check(
    more.status_code == 200 and more.json()["status"] == "UPLOADED" and more.json()["photo_count"] == 2,
    "photo added during review → waits for a new check",
)
check(
    client.post(f"{BASE}/sessions/{lecture['id']}/process", headers=TEACHER).status_code == 202, "check again is queued"
)
detail = wait_for(lecture_detail, lambda d: d["status"] in ("REVIEW", "FAILED"))
row = detail["results"][0]
check(
    detail["status"] == "REVIEW" and row["face_update_pending"] is True,
    "re-check done; student with an open request is not auto-marked",
)

# ---------- Save, report, access control ----------
client.patch(
    f"{BASE}/sessions/{lecture['id']}/results/{row['student_id']}",
    json={"teacher_decision": "PRESENT"},
    headers=TEACHER,
)
saved = client.post(f"{BASE}/sessions/{lecture['id']}/finalize", headers=TEACHER)
check(saved.status_code == 200 and saved.json()["status"] == "FINALIZED", "teacher saves the attendance")
locked = client.post(
    f"{BASE}/sessions/{lecture['id']}/media", files=[("photos", ("x.jpg", jpeg(seed=9), "image/jpeg"))], headers=TEACHER
)
check(locked.status_code == 409, "photos are locked after saving")
csv = client.get(f"{BASE}/classes/{klass['id']}/report?format=csv", headers=TEACHER)
check(csv.status_code == 200 and student_id in csv.text, "CSV report downloads")
mine = client.get(f"{BASE}/me/attendance", headers=STUDENT).json()
check(mine[0]["present"] == 1 and mine[0]["total"] == 1, "student sees their own attendance")
check(
    client.get(f"{BASE}/media/crops/x.jpg?exp=9999999999&sig=deadbeef").status_code == 403,
    "tampered signed link is rejected",
)
check(
    client.get(f"{BASE}/classes/{klass['id']}", headers=STUDENT).status_code == 403,
    "student cannot use teacher endpoints",
)
metrics = client.get(f"{BASE}/admin/metrics", headers=ADMIN).json()
check(
    metrics["queue_depth"] is not None,
    f"admin metrics: queue {metrics['queue_depth']}, match p50 {metrics['match_job_ms']['p50']} ms",
)

print(f"\nALL {passed} SMOKE CHECKS PASSED")
