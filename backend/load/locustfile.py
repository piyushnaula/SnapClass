"""Load test for non-ML endpoints (NFR: p95 < 200 ms at 50 users).

    locust -f load/locustfile.py --host http://localhost:8000
Set LOAD_TEACHER_EMAIL / LOAD_TEACHER_PASSWORD to an existing teacher (with
some classes) and open http://localhost:8089 to start 50 users.

Note: login is rate-limited (5/min per IP), so each simulated user logs in
once and then reuses its token. Run from one machine with the limit raised
(LOGIN_LIMIT_PER_IP_PER_MINUTE) only in a test environment.
"""

import os

from locust import HttpUser, between, task


class TeacherUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": os.environ["LOAD_TEACHER_EMAIL"], "password": os.environ["LOAD_TEACHER_PASSWORD"]},
        )
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        classes = self.client.get("/api/v1/classes", headers=self.headers).json()
        self.class_ids = [c["id"] for c in classes]

    @task(3)
    def list_classes(self) -> None:
        self.client.get("/api/v1/classes", headers=self.headers)

    @task(2)
    def report(self) -> None:
        for class_id in self.class_ids[:1]:
            self.client.get(f"/api/v1/classes/{class_id}/report", headers=self.headers, name="/classes/{id}/report")

    @task(1)
    def sessions(self) -> None:
        for class_id in self.class_ids[:1]:
            self.client.get(f"/api/v1/classes/{class_id}/sessions", headers=self.headers, name="/classes/{id}/sessions")
