"""Attendance reports (FR-A13) and the student's own attendance (FR-A14)."""

import csv
import io
import uuid
from datetime import date

from sqlalchemy import text
from sqlmodel import Session, col, select

from snapclass.models import AttendanceRecord, AttendanceSession, Classroom, Enrollment, User

# Plain SQL is the clearest way to write this report. Every enrolled student
# appears, even with zero sessions (LEFT JOIN). Parameters (:class_id, ...)
# are sent separately from the SQL, so there is no SQL injection risk.
REPORT_SQL = text(
    """
    SELECT u.id AS student_id, u.roll_no, u.full_name,
           COUNT(a.student_id) FILTER (WHERE a.status = 'PRESENT') AS present,
           COUNT(a.student_id) AS total
    FROM enrollments e
    JOIN users u ON u.id = e.student_id
    LEFT JOIN (
        attendance_records a
        JOIN sessions s ON s.id = a.session_id
                       AND s.class_id = :class_id
                       AND (CAST(:from_date AS DATE) IS NULL OR s.session_date >= :from_date)
                       AND (CAST(:to_date AS DATE) IS NULL OR s.session_date <= :to_date)
    ) ON a.student_id = u.id
    WHERE e.class_id = :class_id
    GROUP BY u.id, u.roll_no, u.full_name
    """
)


def percentage(present: int, total: int) -> float | None:
    return round(100.0 * present / total, 2) if total else None


def class_report(
    db: Session, classroom: Classroom, from_date: date | None, to_date: date | None, below_only: bool
) -> dict:
    rows = (
        db.execute(REPORT_SQL, {"class_id": classroom.id, "from_date": from_date, "to_date": to_date}).mappings().all()
    )

    report_rows = []
    for row in rows:
        pct = percentage(row["present"], row["total"])
        below = pct is not None and pct < classroom.min_attendance_pct
        if below_only and not below:
            continue
        report_rows.append({**row, "pct": pct, "below_threshold": below})

    # Lowest attendance first, students with no sessions at the end.
    report_rows.sort(key=lambda r: (r["pct"] is None, r["pct"] or 0, r["roll_no"] or ""))
    return {
        "class_id": classroom.id,
        "from_date": from_date,
        "to_date": to_date,
        "min_attendance_pct": classroom.min_attendance_pct,
        "rows": report_rows,
    }


def report_to_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["roll_no", "full_name", "present", "total", "percentage", "below_threshold"])
    for row in report["rows"]:
        writer.writerow(
            [
                _safe_cell(row["roll_no"] or ""),
                _safe_cell(row["full_name"]),
                row["present"],
                row["total"],
                "" if row["pct"] is None else row["pct"],
                "yes" if row["below_threshold"] else "no",
            ]
        )
    return buffer.getvalue()


def _safe_cell(value: str) -> str:
    """Stop 'CSV injection': Excel runs cells that start with = + - @ as formulas."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def my_attendance(db: Session, student: User) -> list[dict]:
    """Attendance per class for one student. Only their own rows are ever read."""
    classes = db.exec(
        select(Classroom)
        .join(Enrollment, col(Enrollment.class_id) == Classroom.id)
        .where(Enrollment.student_id == student.id)
    ).all()

    summary = []
    for classroom in classes:
        records = db.exec(
            select(AttendanceRecord, AttendanceSession)
            .join(AttendanceSession, col(AttendanceSession.id) == AttendanceRecord.session_id)
            .where(AttendanceRecord.student_id == student.id, AttendanceSession.class_id == classroom.id)
            .order_by(col(AttendanceSession.session_date).desc(), col(AttendanceSession.period).desc())
        ).all()
        present = sum(1 for record, _ in records if record.status == "PRESENT")
        summary.append(
            {
                "class_id": classroom.id,
                "subject": classroom.subject,
                "section": classroom.section,
                "semester": classroom.semester,
                "present": present,
                "total": len(records),
                "pct": percentage(present, len(records)),
                "min_attendance_pct": classroom.min_attendance_pct,
                # Every lecture, newest first, so students can check each one.
                "history": [
                    {"date": s.session_date.isoformat(), "period": s.period, "status": r.status} for r, s in records
                ],
            }
        )
    return summary


def below_threshold_by_teacher(db: Session, teacher_id: uuid.UUID) -> list[dict]:
    """Used by the weekly email (FR-A18): every class of a teacher with its low-attendance students."""
    classes = db.exec(select(Classroom).where(Classroom.teacher_id == teacher_id)).all()
    result = []
    for classroom in classes:
        report = class_report(db, classroom, None, None, below_only=True)
        if report["rows"]:
            result.append(
                {"class": f"{classroom.subject} {classroom.section} (Sem {classroom.semester})", "rows": report["rows"]}
            )
    return result
