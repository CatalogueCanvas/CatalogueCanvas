from __future__ import annotations

import pytest
from fastapi import HTTPException

from cataloguecanvas import auth, db
from cataloguecanvas.settings import settings


@pytest.fixture()
def global_conn():
    """A schema-applied connection on the *global* settings db_path.

    Session validation (``session_role``) opens its own connection via
    ``settings.db_path``, so session round-trip tests must write to that same
    database rather than an isolated fixture file.
    """
    conn = db.get_connection(settings.db_path)
    db.ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


class FakeRequest:
    """Minimal stand-in for starlette Request for CSRF / origin checks."""

    def __init__(self, method="POST", headers=None, cookies=None, netloc="testserver"):
        self.method = method
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.url = type("U", (), {"netloc": netloc})()


# --- password hashing ---

def test_hash_and_verify_admin_password(conn):
    db.set_admin_hash(conn, auth.hash_password("s3cret"))
    assert auth.verify_admin_password(conn, "s3cret") is True
    assert auth.verify_admin_password(conn, "wrong") is False


def test_verify_admin_password_no_hash(conn):
    assert auth.verify_admin_password(conn, "anything") is False


# --- ensure_admin ---

def test_ensure_admin_sets_hash_from_settings(conn, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "fromenv")
    auth.ensure_admin(conn)
    assert auth.verify_admin_password(conn, "fromenv") is True


# --- verify_login ---

def test_verify_login_single_user(conn):
    db.set_admin_hash(conn, auth.hash_password("pw"))
    assert auth.verify_login(conn, None, "pw") == "admin"
    assert auth.verify_login(conn, None, "nope") is None


def test_verify_login_multi_user(conn):
    db.set_settings(conn, {"multi_user_enabled": "true"})
    db.create_user(conn, "alice", auth.hash_password("pw"), "reader")
    assert auth.verify_login(conn, "alice", "pw") == "reader"
    assert auth.verify_login(conn, "alice", "bad") is None
    assert auth.verify_login(conn, "ghost", "pw") is None
    assert auth.verify_login(conn, None, "pw") is None


def test_multi_user_enabled_flag(conn):
    assert auth.multi_user_enabled(conn) is False
    db.set_settings(conn, {"multi_user_enabled": "true"})
    assert auth.multi_user_enabled(conn) is True


# --- session token round-trip (uses global db) ---

def test_session_token_roundtrip(global_conn):
    token = auth.create_session_token(global_conn, "admin", "admin")
    assert auth.session_role(token) == "admin"
    assert auth.session_username(token) == "admin"
    assert auth.is_valid_session(token) is True
    assert auth.session_sid(token)


def test_session_role_none_for_garbage():
    assert auth.session_role("garbage") is None
    assert auth.session_role(None) is None
    assert auth.is_valid_session(None) is False


def test_session_role_revoked_after_delete(global_conn):
    token = auth.create_session_token(global_conn, "reader", "bob")
    sid = auth.session_sid(token)
    db.delete_session(global_conn, sid)
    assert auth.session_role(token) is None


def test_session_username_none_for_garbage():
    assert auth.session_username("garbage") is None


# --- CSRF / cross-origin ---

def test_check_csrf_passes_with_matching_tokens():
    req = FakeRequest(cookies={"cc_csrf": "tok"}, headers={"x-csrf-token": "tok"})
    auth._check_csrf(req)  # no raise


def test_check_csrf_rejects_mismatch():
    req = FakeRequest(cookies={"cc_csrf": "a"}, headers={"x-csrf-token": "b"})
    with pytest.raises(HTTPException) as exc:
        auth._check_csrf(req)
    assert exc.value.status_code == 403


def test_check_csrf_skips_safe_methods():
    auth._check_csrf(FakeRequest(method="GET"))  # no raise


def test_check_cross_origin_rejects_foreign_origin():
    req = FakeRequest(headers={"origin": "http://evil.example"}, netloc="testserver")
    with pytest.raises(HTTPException) as exc:
        auth._check_cross_origin(req)
    assert exc.value.status_code == 403


def test_check_cross_origin_allows_same_origin():
    req = FakeRequest(headers={"origin": "http://testserver"}, netloc="testserver")
    auth._check_cross_origin(req)  # no raise


# --- require_session / require_admin ---

def _authed_request(token, **kw):
    cookies = {auth.SESSION_COOKIE: token}
    cookies.update(kw.pop("cookies", {}))
    return FakeRequest(method="GET", cookies=cookies, **kw)


def test_require_session_unauthenticated():
    with pytest.raises(HTTPException) as exc:
        auth.require_session(FakeRequest(method="GET"))
    assert exc.value.status_code == 401


def test_require_session_ok(global_conn):
    token = auth.create_session_token(global_conn, "reader", "bob")
    assert auth.require_session(_authed_request(token)) == "reader"


def test_require_admin_rejects_reader(global_conn):
    token = auth.create_session_token(global_conn, "reader", "bob")
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(_authed_request(token))
    assert exc.value.status_code == 403


def test_require_admin_ok(global_conn):
    token = auth.create_session_token(global_conn, "admin", "admin")
    auth.require_admin(_authed_request(token))  # no raise


def test_require_admin_unauthenticated():
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(FakeRequest(method="GET"))
    assert exc.value.status_code == 401
