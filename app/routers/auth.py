from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.auth import AuthLogin, AuthSignup
from app.supabase_client import get_supabase

auth_router = APIRouter(prefix="/auth", tags=["auth"])
protected_router = APIRouter(prefix="/protected", tags=["protected"])


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: AuthSignup):
    supabase = await get_supabase()
    try:
        res = await supabase.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
        return res.user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
    except Exception as e:
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
