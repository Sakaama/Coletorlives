"""Tests for Authentication, RBAC, and Webhook Secret Validation."""
import os
import pytest
from flask import Flask

from miner.auth import (
    FORBIDDEN_PASSWORDS,
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_VIEWER,
    UserStore,
    has_role,
    verify_radar_secret,
)


def test_user_store_hashing_and_auth():
    store = UserStore()
    store.add_user("editor_jane", "SecurePass123!", ROLE_EDITOR)

    # Valid login
    user = store.authenticate("editor_jane", "SecurePass123!")
    assert user is not None
    assert user["username"] == "editor_jane"
    assert user["role"] == ROLE_EDITOR

    # Invalid password
    assert store.authenticate("editor_jane", "WrongPassword") is None

    # Unknown user
    assert store.authenticate("nonexistent", "Pass") is None


def test_forbidden_passwords_rejected():
    store = UserStore()
    for bad_pass in FORBIDDEN_PASSWORDS:
        with pytest.raises(ValueError, match="forbidden"):
            store.add_user("hacker", bad_pass, ROLE_ADMIN)


def test_role_hierarchy():
    assert has_role(ROLE_VIEWER, ROLE_ADMIN)
    assert has_role(ROLE_EDITOR, ROLE_ADMIN)
    assert has_role(ROLE_ADMIN, ROLE_ADMIN)

    assert has_role(ROLE_VIEWER, ROLE_EDITOR)
    assert has_role(ROLE_EDITOR, ROLE_EDITOR)
    assert not has_role(ROLE_ADMIN, ROLE_EDITOR)

    assert has_role(ROLE_VIEWER, ROLE_VIEWER)
    assert not has_role(ROLE_EDITOR, ROLE_VIEWER)
    assert not has_role(ROLE_ADMIN, ROLE_VIEWER)


def test_verify_radar_secret():
    app = Flask(__name__)
    os.environ["RADAR_WEBHOOK_SECRET"] = "super-secret-key-xyz"

    with app.test_request_context(headers={"X-Radar-Secret": "super-secret-key-xyz"}):
        assert verify_radar_secret() is True

    with app.test_request_context(headers={"Authorization": "Bearer super-secret-key-xyz"}):
        assert verify_radar_secret() is True

    with app.test_request_context("/?token=super-secret-key-xyz"):
        assert verify_radar_secret() is True

    with app.test_request_context(headers={"X-Radar-Secret": "wrong-secret"}):
        assert verify_radar_secret() is False

    with app.test_request_context():
        assert verify_radar_secret() is False

    del os.environ["RADAR_WEBHOOK_SECRET"]


def test_fail_closed_without_admin(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        UserStore()

