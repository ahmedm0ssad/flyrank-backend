import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AuthApiError, create_async_client

from app.dependencies.auth import bearer_scheme, get_current_user
from app.models.auth import AuthLogin, AuthSignup
from app.core.supabase import get_client_credentials, get_supabase

auth_router = APIRouter(prefix="/auth", tags=["auth"])
protected_router = APIRouter(
    prefix="/protected",
    tags=["protected"],
    dependencies=[Depends(bearer_scheme)],
)


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: AuthSignup):
    supabase = await get_supabase()
    try:
        if await _email_exists(body.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        res = await supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
        return res.user
    except HTTPException:
        raise
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def _email_exists(email: str) -> bool:
    url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not service_key:
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{url}/auth/v1/admin/users",
                params={"filter": f"email:eq:{email}"},
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
            )
            if r.is_error:
                return False
            data = r.json()
            return len(data.get("users", [])) > 0
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@auth_router.post("/login")
async def login(body: AuthLogin):
    supabase = await get_supabase()
    try:
        res = await supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }
    except HTTPException:
        raise
    except AuthApiError as e:
        msg = str(e)
        if "Invalid login credentials" in msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login credentials",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@protected_router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "created_at": current_user["created_at"],
    }


@protected_router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    return {
        "message": f"Welcome to your dashboard, {current_user['email']}",
        "user_id": current_user["id"],
    }


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: dict = Depends(get_current_user)):
    url, key = get_client_credentials()
    scoped_client = await create_async_client(url, key)
    await scoped_client.auth.set_session(current_user["access_token"], "")
    await scoped_client.auth.sign_out()
