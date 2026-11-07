from datetime import timedelta
from httpx import ASGITransport, AsyncClient
from itsdangerous import URLSafeTimedSerializer
import pytest
from app.config import Settings, settings
from app.core import clock
from app.core.database import async_session_factory, init_db
from app.core.models import SessionRecord
from app.core.security import create_session
from app.main import app


def test_production_refuses_to_start_with_invalid_session_secret():
    # Production with valid APP_PASSWORD but empty SESSION_SECRET
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings(
            ENV="production",
            APP_PASSWORD="a_valid_long_production_password_123",
            SESSION_SECRET="",
        )

    # Production with short SESSION_SECRET (< 32 bytes)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings(
            ENV="production",
            APP_PASSWORD="a_valid_long_production_password_123",
            SESSION_SECRET="short_secret_under_32_bytes",
        )

    # Production with valid SESSION_SECRET (>= 32 bytes)
    valid_s = Settings(
        ENV="production",
        APP_PASSWORD="a_valid_long_production_password_123",
        SESSION_SECRET="a" * 32,
    )
    assert valid_s.SESSION_SECRET == "a" * 32


@pytest.mark.asyncio
async def test_forged_or_expired_or_raw_password_cookie_rejected():
    await init_db()
    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Raw password as cookie is rejected (returns redirect to /login)
        res_raw = await ac.get(
            "/",
            cookies={settings.ADMIN_SESSION_COOKIE: settings.APP_PASSWORD},
            follow_redirects=False,
        )
        assert res_raw.status_code == 303
        assert res_raw.headers["location"] == "/login"

        # 2. Forged / invalid signature cookie is rejected
        res_forged = await ac.get(
            "/",
            cookies={settings.ADMIN_SESSION_COOKIE: "forged_malicious_cookie_value"},
            follow_redirects=False,
        )
        assert res_forged.status_code == 303

        # 3. Expired cookie (> 7 days) is rejected
        s = URLSafeTimedSerializer(settings.SESSION_SECRET, salt="pja-session-auth")
        old_time = int((clock.utcnow() - timedelta(days=8)).timestamp())
        expired_cookie = s.dumps({"sid": "expired_sid", "iat": old_time})
        res_expired = await ac.get(
            "/",
            cookies={settings.ADMIN_SESSION_COOKIE: expired_cookie},
            follow_redirects=False,
        )
        assert res_expired.status_code == 303

        # 4. Valid signed cookie with active DB session succeeds (200)
        async with async_session_factory() as db:
            session_rec, valid_cookie = await create_session(db, client_ip="127.0.0.1")

        res_valid = await ac.get(
            "/",
            cookies={settings.ADMIN_SESSION_COOKIE: valid_cookie},
            follow_redirects=False,
        )
        assert res_valid.status_code == 200


@pytest.mark.asyncio
async def test_cookie_authenticated_post_without_csrf_returns_403():
    await init_db()
    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)

    # Create active session in DB
    async with async_session_factory() as db:
        session_rec, valid_cookie = await create_session(db, client_ip="127.0.0.1")
        csrf_token = session_rec.csrf_token

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set(settings.ADMIN_SESSION_COOKIE, valid_cookie)

        # 1. Cookie POST without X-CSRF-Token returns 403
        res_no_csrf = await ac.post("/api/settings", json={"min_match_score_notify": 75})
        assert res_no_csrf.status_code == 403
        assert "CSRF" in res_no_csrf.json().get("detail", "")

        # 2. Cookie POST with mismatched X-CSRF-Token returns 403
        res_bad_csrf = await ac.post(
            "/api/settings",
            json={"min_match_score_notify": 75},
            headers={"X-CSRF-Token": "wrong_token_value"},
        )
        assert res_bad_csrf.status_code == 403

        # 3. Cookie POST with valid X-CSRF-Token succeeds
        res_ok_csrf = await ac.post(
            "/api/settings",
            json={"min_match_score_notify": 75},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_ok_csrf.status_code == 200

        # 4. Bearer-authenticated POST is exempt from CSRF
        ac_bearer = AsyncClient(transport=transport, base_url="http://test")
        res_bearer = await ac_bearer.post(
            "/api/settings",
            json={"min_match_score_notify": 75},
            headers={"Authorization": f"Bearer {settings.APP_PASSWORD}"},
        )
        assert res_bearer.status_code == 200


@pytest.mark.asyncio
async def test_brute_force_sixth_failed_login_returns_429():
    import uuid
    from app.core.security import _login_failures

    _login_failures.clear()
    await init_db()
    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)
    test_ip = f"10.99.88.{uuid.uuid4().int % 200 + 1}"
    headers = {"X-Forwarded-For": test_ip}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First 5 failed attempts return 401
        for i in range(5):
            res = await ac.post(
                "/login",
                data={"password": "wrong_password"},
                headers=headers,
            )
            assert res.status_code == 401, f"Attempt {i+1} expected 401, got {res.status_code}"

        # 6th attempt must return 429 with Retry-After header
        res_6 = await ac.post(
            "/login",
            data={"password": "wrong_password"},
            headers=headers,
        )
        assert res_6.status_code == 429
        assert "Retry-After" in res_6.headers
        assert int(res_6.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_logout_invalidates_session():
    await init_db()
    settings.APP_PASSWORD = "supersecretpassword123"
    transport = ASGITransport(app=app)

    async with async_session_factory() as db:
        session_rec, valid_cookie = await create_session(db, client_ip="127.0.0.1")
        sid = session_rec.sid

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set(settings.ADMIN_SESSION_COOKIE, valid_cookie)

        # Access succeeds
        res_before = await ac.get("/", follow_redirects=False)
        assert res_before.status_code == 200

        # Logout
        res_logout = await ac.post("/logout", follow_redirects=False)
        assert res_logout.status_code == 303

        # Verify session is deleted from DB
        async with async_session_factory() as db:
            from sqlalchemy import select
            db_session = (await db.execute(select(SessionRecord).where(SessionRecord.sid == sid))).scalar_one_or_none()
            assert db_session is None
