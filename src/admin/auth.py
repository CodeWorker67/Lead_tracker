import hashlib
import hmac
import time
from typing import Callable

import extra_streamlit_components as stx
import streamlit as st

from admin.audit_log import audit_info, audit_warning
from config import settings

# Cookie settings
COOKIE_NAME = "lead_tracker_auth"
COOKIE_EXPIRY_DAYS = 1  # 24 hours
_COOKIE_MANAGER_SESSION_KEY = "_lead_tracker_cookie_manager"


def verify_credentials(username: str, password: str) -> bool:
    """Проверка логина: полный admin или пользователь из ADMIN_SCOPED_USERS."""
    if (
        username == settings.admin_username
        and password == settings.admin_password
    ):
        return True
    scoped = settings.scoped_admin_users().get(username)
    return scoped is not None and scoped.password == password


def get_allowed_bot_id(username: str) -> int | None:
    """
    None — доступ ко всем ботам (admin).
    int — только данные указанного bot_id.
    """
    if username == settings.admin_username:
        return None
    scoped = settings.scoped_admin_users().get(username)
    if scoped is not None:
        return scoped.bot_id
    return None


def current_allowed_bot_id() -> int | None:
    """Ограничение бота для текущей сессии (None = все боты)."""
    username = st.session_state.get("username")
    if not username:
        return None
    return get_allowed_bot_id(username)


def _auth_scope_label(username: str) -> str:
    bot_id = get_allowed_bot_id(username)
    if bot_id is None:
        return "all_bots"
    return f"bot_id={bot_id}"


def _get_cookie_manager():
    """Один CookieManager на сессию (иначе StreamlitDuplicateElementKey при logout)."""
    if _COOKIE_MANAGER_SESSION_KEY not in st.session_state:
        st.session_state[_COOKIE_MANAGER_SESSION_KEY] = stx.CookieManager(
            key="lead_tracker_cookie_manager"
        )
    return st.session_state[_COOKIE_MANAGER_SESSION_KEY]


def _generate_token(username: str) -> str:
    """Generate an authentication token for the user."""
    timestamp = str(int(time.time()))
    data = f"{username}:{timestamp}"
    signature = hmac.new(
        settings.admin_cookie_secret.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{data}:{signature}"


def _validate_token(token: str) -> str | None:
    """Validate token and return username if valid, None otherwise."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None

        username, timestamp, signature = parts

        # Verify signature
        data = f"{username}:{timestamp}"
        expected_signature = hmac.new(
            settings.admin_cookie_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return None

        # Check expiration (24 hours)
        token_time = int(timestamp)
        if time.time() - token_time > COOKIE_EXPIRY_DAYS * 24 * 60 * 60:
            return None

        return username
    except (ValueError, TypeError):
        return None


def check_password() -> bool:
    """Returns `True` if the user is authenticated."""
    cookie_manager = _get_cookie_manager()

    # Check for existing auth cookie
    auth_cookie = cookie_manager.get(COOKIE_NAME)

    if auth_cookie:
        username = _validate_token(auth_cookie)
        if username:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            return True
        else:
            # Invalid or expired token - delete cookie
            cookie_manager.delete(COOKIE_NAME)
            if not st.session_state.get("_auth_cookie_invalid_logged"):
                audit_warning("Admin auth cookie invalid or expired, cleared")
                st.session_state["_auth_cookie_invalid_logged"] = True

    # Return True if already authenticated in session
    if st.session_state.get("authenticated", False):
        return True

    # Show login form
    st.markdown("## Вход в систему")
    st.markdown("")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input(
                "Имя пользователя",
                placeholder="Введите имя пользователя",
            )
            password = st.text_input(
                "Пароль",
                type="password",
                placeholder="Введите пароль",
            )
            submitted = st.form_submit_button(
                "Войти", type="primary", use_container_width=True
            )

        if submitted:
            if verify_credentials(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                audit_info(
                    "Admin login: user=%s scope=%s",
                    username,
                    _auth_scope_label(username),
                )
                st.session_state["_admin_audit_session_logged"] = True
                token = _generate_token(username)
                cookie_manager.set(
                    COOKIE_NAME,
                    token,
                    expires_at=None,
                    key="set_auth_cookie",
                )
                st.rerun()
            else:
                st.session_state["authenticated"] = False
                st.session_state["login_failed"] = True
                audit_warning("Admin login failed: user=%s", username)

        if st.session_state.get("login_failed", False):
            st.error("Неверное имя пользователя или пароль")
            st.session_state["login_failed"] = False

    return False


def logout():
    """Log out the user by clearing session state and deleting auth cookie."""
    username = st.session_state.get("username")
    cookie_manager = _get_cookie_manager()
    cookie_manager.delete(COOKIE_NAME)

    st.session_state["authenticated"] = False
    if "username" in st.session_state:
        del st.session_state["username"]

    if username:
        audit_info("Admin logout: user=%s", username)
    else:
        audit_info("Admin logout: user=<unknown>")

    st.session_state.pop("_admin_audit_session_logged", None)
    st.rerun()


def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication for a page."""
    def wrapper(*args, **kwargs):
        if not check_password():
            st.stop()
        return func(*args, **kwargs)
    return wrapper
