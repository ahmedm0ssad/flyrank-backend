from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AuthError

from app.core.supabase import get_supabase

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required",
        )

    token = credentials.credentials
    supabase = await get_supabase()
    try:
        res = await supabase.auth.get_user(token)
        user = res.user
        return {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "access_token": token,
        }
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
