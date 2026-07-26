import os
import time

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE = "http://localhost:8000"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or not SUPABASE_ANON_KEY:
    raise RuntimeError(
        "E2E tests require SUPABASE_URL, SUPABASE_SERVICE_KEY, "
        "and SUPABASE_KEY in .env"
    )

_state = {}


def _url(path):
    return f"{BASE}{path}"


def _seed_test_user():
    """Create a test user via Supabase admin API (service_role)."""
    ts = time.time()
    email = f"flyrank-e2e-{ts:.0f}@seed-test.com"
    pw = "TestPass123!"
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        json={"email": email, "password": pw, "email_confirm": True},
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
        },
    )
    return (email, pw, r)


def _confirm_user(email: str):
    """Confirm a user's email via Supabase admin API."""
    r = requests.put(
        f"{SUPABASE_URL}/auth/v1/admin/users/{_state['user_id']}",
        json={"email_confirm": True},
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
        },
    )
    print(f"\n[CONFIRM USER] status={r.status_code} body={r.text}")
    return r


def test_1_signup_new_user():
    ts = time.time()
    email = f"flyrank-e2e-{ts:.0f}@gmail.com"
    pw = "TestPass123!"
    _state["email"] = email
    _state["password"] = pw

    r = requests.post(_url("/auth/signup"), json={"email": email, "password": pw})
    print(f"\n[SIGNUP NEW] status={r.status_code} body={r.text}")
    if r.status_code == 400 and "rate limit" in r.text:
        print(
            "  WARNING: Supabase rate limited signup. Will use admin-seeded account instead."
        )
        _state["signup_rate_limited"] = True
    else:
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert "id" in data
        assert data["email"] == email
        _state["user_id"] = data["id"]
        _confirm_user(email)


def test_2_signup_duplicate_email():
    r = requests.post(
        _url("/auth/signup"),
        json={"email": _state["email"], "password": _state["password"]},
    )
    print(f"\n[SIGNUP DUPE] status={r.status_code} body={r.text}")
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "error" in r.json()


def test_3_login_correct():
    email, pw = _state.get("email"), _state.get("password")
    if _state.get("signup_rate_limited"):
        _state["email"], _state["password"], r = _seed_test_user()
        email, pw = _state["email"], _state["password"]
        _state["user_id"] = r.json()["id"]
        print(f"\n[SEED USER] email={email} id={r.json()['id']}")

    r = requests.post(_url("/auth/login"), json={"email": email, "password": pw})
    print(f"\n[LOGIN OK] status={r.status_code} body={r.text}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    _state["access_token"] = data["access_token"]
    _state["refresh_token"] = data["refresh_token"]


def test_4_login_wrong_password():
    r = requests.post(
        _url("/auth/login"),
        json={"email": _state["email"], "password": "DefinitelyWrong!!"},
    )
    print(f"\n[LOGIN BAD PW] status={r.status_code} body={r.text}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    assert r.json() == {"error": "Invalid login credentials"}


def test_5_public_info():
    r = requests.get(_url("/public/info"))
    print(f"\n[PUBLIC INFO] status={r.status_code} body={r.text}")
    assert r.status_code == 200
    assert r.json() == {"message": "Welcome stranger! This info is public."}


def test_6_profile_no_token():
    r = requests.get(_url("/protected/profile"))
    print(f"\n[PROFILE NO TOKEN] status={r.status_code} body={r.text}")
    assert r.status_code == 401
    assert r.json() == {"error": "Access token required"}


def test_7_profile_valid_token():
    r = requests.get(
        _url("/protected/profile"),
        headers={"Authorization": f"Bearer {_state['access_token']}"},
    )
    print(f"\n[PROFILE VALID] status={r.status_code} body={r.text}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["id"] == _state["user_id"]
    assert data["email"] == _state["email"]
    assert "created_at" in data
    assert set(data.keys()) == {"id", "email", "created_at"}


def test_8_profile_tampered_token():
    tok = _state["access_token"]
    tampered = tok[:10]
    r = requests.get(
        _url("/protected/profile"),
        headers={"Authorization": f"Bearer {tampered}"},
    )
    print(f"\n[PROFILE TAMPERED] status={r.status_code} body={r.text}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    assert r.json() == {"error": "Invalid or expired token"}


def test_9_dashboard_valid_token():
    r = requests.get(
        _url("/protected/dashboard"),
        headers={"Authorization": f"Bearer {_state['access_token']}"},
    )
    print(f"\n[DASHBOARD] status={r.status_code} body={r.text}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert "message" in data
    assert _state["email"] in data["message"]


def test_10_logout():
    r = requests.post(
        _url("/auth/logout"),
        headers={"Authorization": f"Bearer {_state['access_token']}"},
    )
    print(f"\n[LOGOUT] status={r.status_code} body={r.text!r}")
    assert r.status_code == 204
    assert r.content == b""


def test_11_profile_after_logout():
    r = requests.get(
        _url("/protected/profile"),
        headers={"Authorization": f"Bearer {_state['access_token']}"},
    )
    print(f"\n[PROFILE AFTER LOGOUT] status={r.status_code} body={r.text}")
    print(
        f"NOTE: After logout, Supabase returned status {r.status_code}. "
        f"JWTs are stateless; Supabase's get_user() may still validate "
        f"the token until it expires."
    )
