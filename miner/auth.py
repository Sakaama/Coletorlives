"""Authentication, Roles, and Security Services for Tutuco Clip Miner.

Provides:
- Role-based Access Control (Admin, Editor, Viewer).
- Secure password hashing via werkzeug.security (PBKDF2/scrypt).
- Session and API token validation.
- Radar webhook secret validation.
- Zero hardcoded passwords (prohibits legacy Coletorlives credentials).
- Offline / Local developer bypass mode when AUTH_REQUIRED=false.
"""
from __future__ import annotations

import functools
import logging
import os
import secrets
from typing import Any, Callable, Dict, Optional, Set

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger("miner.auth")

# Defined roles with hierarchical capabilities
ROLE_ADMIN = "Admin"
ROLE_EDITOR = "Editor"
ROLE_VIEWER = "Viewer"

ROLE_HIERARCHY: Dict[str, int] = {
    ROLE_ADMIN: 30,
    ROLE_EDITOR: 20,
    ROLE_VIEWER: 10,
}

# Block common trivial passwords from user registration
FORBIDDEN_PASSWORDS: Set[str] = {
    "password",
    "admin",
    "123456",
    "root",
    "qwerty",
}


def is_auth_required() -> bool:
    """Check if authentication is strictly enforced.
    
    Defaults to False for local developer / desktop convenience,
    can be enabled with AUTH_REQUIRED=true in production/cloud.
    """
    val = os.environ.get("AUTH_REQUIRED", "false").lower().strip()
    return val in {"1", "true", "yes", "on"}


class UserStore:
    """In-memory user store initialized from environment or defaults."""

    def __init__(self):
        self._users: Dict[str, Dict[str, Any]] = {}
        self._init_default_users()

    def has_admin(self) -> bool:
        """Check if at least one Admin account is registered."""
        return any(u.get("role") == ROLE_ADMIN for u in self._users.values())

    def reload_from_env(self):
        """Initialize or refresh users from environment variables."""
        admin_pass = os.environ.get("ADMIN_PASSWORD", "").strip()
        editor_pass = os.environ.get("EDITOR_PASSWORD", "").strip()
        viewer_pass = os.environ.get("VIEWER_PASSWORD", "").strip()

        if admin_pass:
            if admin_pass in FORBIDDEN_PASSWORDS:
                raise ValueError("ADMIN_PASSWORD é uma senha trivial/proibida! Defina uma senha forte.")
            self.add_user("admin", admin_pass, ROLE_ADMIN)
        elif "admin" in self._users:
            del self._users["admin"]

        if editor_pass:
            if editor_pass not in FORBIDDEN_PASSWORDS:
                self.add_user("editor", editor_pass, ROLE_EDITOR)
        elif "editor" in self._users:
            del self._users["editor"]

        if viewer_pass:
            if viewer_pass not in FORBIDDEN_PASSWORDS:
                self.add_user("viewer", viewer_pass, ROLE_VIEWER)
        elif "viewer" in self._users:
            del self._users["viewer"]

        # Fail closed when auth is required but no administrator is configured
        if is_auth_required() and not self.has_admin():
            raise RuntimeError(
                "Configuração inválida: AUTH_REQUIRED=true exige a definição de ADMIN_PASSWORD no ambiente. "
                "Defina ADMIN_PASSWORD no arquivo .env ou no container para iniciar em modo autenticado."
            )

    _init_default_users = reload_from_env

    def add_user(self, username: str, password: str, role: str = ROLE_VIEWER) -> bool:
        """Register or update a user with a hashed password."""
        if password in FORBIDDEN_PASSWORDS:
            raise ValueError(f"Password for {username} is in the forbidden insecure passwords list.")
        if role not in ROLE_HIERARCHY:
            raise ValueError(f"Invalid role: {role}")

        self._users[username.lower()] = {
            "username": username.lower(),
            "password_hash": generate_password_hash(password),
            "role": role,
        }
        return True

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify username and password; return user record or None."""
        user = self._users.get(username.lower().strip())
        if not user:
            return None
        if check_password_hash(user["password_hash"], password):
            return {
                "username": user["username"],
                "role": user["role"],
            }
        return None

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user details (excluding hash)."""
        user = self._users.get(username.lower().strip())
        if not user:
            return None
        return {
            "username": user["username"],
            "role": user["role"],
        }


# Global store instance
_user_store = UserStore()


def get_current_user() -> Dict[str, Any]:
    """Return currently authenticated user from session, or default Admin if auth is disabled."""
    logged_user = session.get("user")
    if logged_user:
        return {
            "username": logged_user.get("username", "unknown"),
            "role": logged_user.get("role", ROLE_VIEWER),
            "authenticated": True,
            "auth_required": is_auth_required(),
        }

    if not is_auth_required():
        return {
            "username": "local_admin",
            "role": ROLE_ADMIN,
            "authenticated": True,
            "auth_required": False,
        }

    return {
        "username": "anonymous",
        "role": ROLE_VIEWER,
        "authenticated": False,
        "auth_required": True,
    }


def has_role(required_role: str, user_role: Optional[str] = None) -> bool:
    """Check if user_role satisfies required_role in the hierarchy."""
    if user_role is None:
        user_role = get_current_user().get("role", ROLE_VIEWER)

    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= required_level


def require_auth(view_func: Callable) -> Callable:
    """Decorator requiring active session authentication when AUTH_REQUIRED is enabled."""
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        if not is_auth_required():
            return view_func(*args, **kwargs)

        current = get_current_user()
        if not current.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "code": 401}), 401
            return redirect(url_for("login_page", next=request.path))

        return view_func(*args, **kwargs)
    return wrapper


def require_role(required_role: str) -> Callable:
    """Decorator requiring a minimum role level (Admin > Editor > Viewer)."""
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if not is_auth_required():
                return view_func(*args, **kwargs)

            current = get_current_user()
            if not current.get("authenticated"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required", "code": 401}), 401
                return redirect(url_for("login_page", next=request.path))

            if not has_role(required_role, current.get("role")):
                return jsonify({
                    "error": f"Forbidden: Requires '{required_role}' privileges (current: '{current.get('role')}').",
                    "code": 403,
                }), 403

            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def verify_radar_secret() -> bool:
    """Validate incoming radar webhook secret or API key.
    
    Checks in order:
    1. Header `X-Radar-Secret`
    2. Header `Authorization: Bearer <secret>`
    3. Query parameter `?token=<secret>`
    """
    configured_secret = (
        os.environ.get("RADAR_WEBHOOK_SECRET")
        or os.environ.get("WEBHOOK_SECRET")
        or ""
    ).strip()

    if not configured_secret:
        # If no secret configured and auth is disabled, allow local development
        if not is_auth_required():
            return True
        logger.error("RADAR_WEBHOOK_SECRET is not configured while auth is required!")
        return False

    incoming_secret = request.headers.get("X-Radar-Secret", "").strip()
    if not incoming_secret:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.startswith("Bearer "):
            incoming_secret = auth_header[7:].strip()
    if not incoming_secret:
        incoming_secret = request.args.get("token", "").strip()

    if not incoming_secret:
        return False

    # Constant time comparison to prevent timing attacks
    return secrets.compare_digest(incoming_secret, configured_secret)


def get_user_store(reload: bool = False) -> UserStore:
    """Obtain global UserStore instance, optionally reloading from environment."""
    if reload or (not _user_store.has_admin() and bool(os.environ.get("ADMIN_PASSWORD"))):
        _user_store.reload_from_env()
    return _user_store
