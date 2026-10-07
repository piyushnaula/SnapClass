"""Create the first admin and the first consent text. Safe to run many times.

Run with:  python -m snapclass.scripts.seed
Reads ADMIN_EMAIL and ADMIN_PASSWORD from the environment.
"""

import logging

from pydantic import EmailStr, TypeAdapter
from sqlmodel import Session, select

from snapclass.core.config import settings
from snapclass.core.db import engine
from snapclass.core.logging import setup_logging
from snapclass.core.security import hash_password
from snapclass.models import ConsentText, User

logger = logging.getLogger(__name__)

# A starting template. Have it reviewed against the DPDP Act, 2023 and university policy.
CONSENT_V1 = """Consent for biometric attendance (version 1)

Purpose: SnapClass uses your face and voice ONLY to propose your attendance in classes you have joined. A teacher always reviews and confirms the result.

What we store: numeric "embeddings" calculated from your enrollment photos and voice clips. Your enrollment photos and recordings are deleted right after the embeddings are made. Class photos are deleted 7 days after the teacher finalizes attendance.

Who can see it: embeddings are never shown or sent to anyone. Teachers see a small face crop from the class photo while reviewing attendance.

Your rights: you may delete your biometric data at any time from the "My biometrics" page. It is erased immediately, and your attendance will then be marked manually by the teacher. Your attendance history is kept.

Saying no is fine: you can still be marked present manually."""


def seed() -> None:
    with Session(engine) as db:
        if db.exec(select(ConsentText)).first() is None:
            db.add(ConsentText(version=1, body=CONSENT_V1))
            logger.info("Created consent text v1")

        if settings.admin_email and settings.admin_password:
            # Use the same email check as the login endpoint, so we never create
            # an admin that cannot log in (e.g. reserved domains like ".local").
            email = TypeAdapter(EmailStr).validate_python(settings.admin_email).lower()
            if len(settings.admin_password) < 8:
                raise SystemExit("ADMIN_PASSWORD must be at least 8 characters")
            if db.exec(select(User).where(User.email == email)).first() is None:
                db.add(
                    User(
                        email=email,
                        password_hash=hash_password(settings.admin_password),
                        full_name="Administrator",
                        role="ADMIN",
                    )
                )
                logger.info("Created admin user", extra={"fields": {"email": email}})
        else:
            logger.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set, no admin created")
        db.commit()


if __name__ == "__main__":
    setup_logging()
    seed()
