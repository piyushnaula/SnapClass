from fastapi import APIRouter, Request

from snapclass.api.deps import CurrentUser, DbSession
from snapclass.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from snapclass.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbSession) -> dict:
    """Students sign in with their student ID; teachers and the admin with their email."""
    user, access, refresh = auth_service.login(db, body.login_id, body.password, _client_ip(request))
    return {"access_token": access, "refresh_token": refresh, "user": user}


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, request: Request, db: DbSession) -> dict:
    """A student creates an account with their college student ID and is signed in."""
    user, access, refresh = auth_service.register_student(
        db, body.student_id, body.full_name, body.password, _client_ip(request)
    )
    return {"access_token": access, "refresh_token": refresh, "user": user}


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: DbSession) -> dict:
    user, access, new_refresh = auth_service.rotate_refresh_token(db, body.refresh_token)
    return {"access_token": access, "refresh_token": new_refresh, "user": user}


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: DbSession) -> None:
    auth_service.logout(db, body.refresh_token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> object:
    return user
