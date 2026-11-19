"""Streamlit screens for signing in, signing out and managing accounts. Logic lives in nassau.auth."""
from __future__ import annotations

import math
import os
import time

import pandas as pd
import streamlit as st

from . import auth, theme

SESSION_KEY = "auth"
SESSION_TIMEOUT = 30 * 60          # seconds of inactivity before the user must sign in again


def _secret(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:
        return st.secrets.get(name)
    except Exception:              # no secrets file configured
        return None


@st.cache_resource
def get_store() -> auth.UserStore:
    """One store per server process. On a brand-new install, optionally create the first admin from
    NASSAU_ADMIN_USER / NASSAU_ADMIN_PASSWORD (environment variables or Streamlit secrets)."""
    store = auth.UserStore()
    store.seed_error = ""
    user, pw = _secret("NASSAU_ADMIN_USER"), _secret("NASSAU_ADMIN_PASSWORD")
    if user and pw and not store.has_users():
        try:
            store.create_user(user, pw, "admin", actor="bootstrap")
        except ValueError as exc:
            store.seed_error = str(exc)
    return store


def fmt_ts(ts) -> str:
    return time.strftime("%d %b %Y, %H:%M UTC", time.gmtime(ts)) if ts else "never"


# ---------------------------------------------------------------------------- session
def _end_session(store: auth.UserStore, reason: str | None = None, notice: str | None = None) -> None:
    sess = st.session_state.get(SESSION_KEY) or {}
    if reason and sess.get("username"):
        store.audit(reason, sess["username"])
    st.session_state.clear()
    if notice:
        st.session_state["login_notice"] = notice


def current_user(store: auth.UserStore) -> dict | None:
    """Return the signed-in user, or None. Re-checks the account on every rerun, so disabling or deleting a
    person takes effect on their next click, and idle sessions expire."""
    sess = st.session_state.get(SESSION_KEY)
    if not sess:
        return None
    now = time.time()
    if now - sess["last_seen"] > SESSION_TIMEOUT:
        _end_session(store, "session_timeout", "You were signed out after 30 minutes of inactivity.")
        return None
    user = store.get_user(sess["username"])
    if not user or not user["active"]:
        _end_session(store, "session_revoked", "That account is no longer active.")
        return None
    sess["last_seen"] = now
    return user


def require(user: dict, permission: str) -> bool:
    return auth.can(user["role"], permission)


# ---------------------------------------------------------------------------- login screen
def render_login(store: auth.UserStore) -> None:
    st.markdown(theme.style_tag(theme.HIDE_SIDEBAR_CSS), unsafe_allow_html=True)
    left, right = st.columns([1.1, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown(theme.login_brand_html(), unsafe_allow_html=True)
    with right:
        if not store.has_users():
            _render_first_run(store)
        else:
            _render_login_form(store)
    st.stop()


def _render_first_run(store: auth.UserStore) -> None:
    st.markdown(theme.login_head_html("Create the first account",
                                      "No one can sign in yet. Add an admin from the command line on the machine "
                                      "running this app."), unsafe_allow_html=True)
    st.code("python manage_users.py add your-username --role admin --name \"Your Name\"", language="bash")
    st.markdown('<p class="nc-login-note">On a hosted deployment, set <code>NASSAU_ADMIN_USER</code> and '
                '<code>NASSAU_ADMIN_PASSWORD</code> as environment variables or Streamlit secrets instead, then reload. '
                'Change that password after your first sign-in.</p>', unsafe_allow_html=True)
    if getattr(store, "seed_error", ""):
        st.error(f"The admin from NASSAU_ADMIN_USER could not be created. {store.seed_error}")


def _render_login_form(store: auth.UserStore) -> None:
    st.markdown(theme.login_head_html("Sign in", "Use the account your administrator created."), unsafe_allow_html=True)
    notice = st.session_state.pop("login_notice", None)
    if notice:
        st.info(notice)
    with st.form("login", clear_on_submit=False):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
    st.markdown('<p class="nc-login-note">Sessions end after 30 minutes of inactivity.</p>', unsafe_allow_html=True)
    if not submitted:
        return
    if not username or not password:
        st.error("Enter both your username and password.")
        return
    res = store.authenticate(username, password)
    if res.ok:
        st.session_state[SESSION_KEY] = {"username": res.username, "last_seen": time.time()}
        st.rerun()
    elif res.reason == "locked":
        st.error(f"Too many failed attempts. Try again in {max(1, math.ceil(res.retry_after / 60))} minute(s), "
                 "or ask an admin to unlock the account.")
    else:
        extra = (f" {res.attempts_left} attempt(s) left before the account is locked for "
                 f"{auth.LOCK_SECONDS // 60} minutes." if res.attempts_left <= 2 else "")
        st.error("Incorrect username or password." + extra)


# ---------------------------------------------------------------------------- signed-in chrome
def render_sidebar_account(store: auth.UserStore, user: dict) -> None:
    sb = st.sidebar
    sb.markdown(theme.sidebar_brand_html(), unsafe_allow_html=True)
    if sb.button("Sign out", key="signout", width="stretch"):
        _end_session(store, "logout")
        st.session_state["login_notice"] = "You have been signed out."
        st.rerun()
    with sb.expander("Change password"):
        with st.form("change_password", clear_on_submit=True):
            current = st.text_input("Current password", type="password", autocomplete="current-password")
            new = st.text_input("New password", type="password", autocomplete="new-password")
            again = st.text_input("Repeat new password", type="password", autocomplete="new-password")
            go = st.form_submit_button("Update password", width="stretch")
        if go:
            if new != again:
                st.error("The new passwords don't match.")
            else:
                try:
                    store.change_own_password(user["username"], current, new)
                    st.success("Password updated.")
                except ValueError as exc:
                    st.error(str(exc))
    sb.divider()


def render_hero(user: dict) -> None:
    st.markdown(theme.hero_html(user["display_name"], auth.ROLE_LABELS[user["role"]]), unsafe_allow_html=True)


# ---------------------------------------------------------------------------- admin panel
def _flash(kind: str, message: str) -> None:
    st.session_state["_flash"] = (kind, message)


def _show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        {"success": st.success, "error": st.error}.get(item[0], st.info)(item[1])


def render_admin_panel(store: auth.UserStore, me: dict) -> None:
    if not require(me, "manage_users"):          # defence in depth: the tab is also hidden for other roles
        st.error("Only admins can manage access.")
        return
    _show_flash()
    st.subheader("Team and access")
    for role in auth.ROLES:
        st.markdown(f"**{auth.ROLE_LABELS[role]}**: {auth.ROLE_SUMMARY[role]}")

    users = store.list_users()
    table = pd.DataFrame([{
        "Username": u["username"], "Name": u["display_name"], "Role": auth.ROLE_LABELS[u["role"]],
        "Status": "Locked" if u["locked"] else ("Active" if u["active"] else "Disabled"),
        "Last sign-in": fmt_ts(u["last_login"]),
    } for u in users])
    st.dataframe(table, hide_index=True, width="stretch")

    add_col, manage_col = st.columns(2, gap="large")
    with add_col:
        st.markdown("#### Add a person")
        with st.form("add_user", clear_on_submit=True):
            username = st.text_input("Username", help="Lowercase letters, digits, dot, dash or underscore.")
            name = st.text_input("Display name")
            role = st.selectbox("Role", auth.ROLES, index=2, format_func=auth.ROLE_LABELS.get)
            password = st.text_input("Temporary password", type="password",
                                     help=f"At least {auth.MIN_PASSWORD_LEN} characters with a letter and a number.")
            add = st.form_submit_button("Add person", type="primary")
        if add:
            try:
                created = store.create_user(username, password, role, name, actor=me["username"])
                _flash("success", f"Added {created} as {auth.ROLE_LABELS[role]}. Share the password with them privately.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with manage_col:
        st.markdown("#### Change an account")
        actions = ["Change role", "Reset password", "Disable", "Enable", "Unlock", "Delete"]
        with st.form("manage_user", clear_on_submit=True):
            target = st.selectbox("Person", [u["username"] for u in users])
            action = st.selectbox("Action", actions)
            new_role = st.selectbox("New role (for Change role)", auth.ROLES, format_func=auth.ROLE_LABELS.get)
            new_pw = st.text_input("New password (for Reset password)", type="password")
            confirm = st.checkbox("Confirm (required for Delete)")
            apply = st.form_submit_button("Apply")
        if apply:
            _apply_action(store, me, target, action, new_role, new_pw, confirm)

    st.markdown("#### Recent activity")
    audit = store.read_audit(150)
    if audit:
        st.dataframe(pd.DataFrame([{
            "When": fmt_ts(e["ts"]), "Event": e["event"].replace("_", " "), "Person": e["user"],
            "By": e.get("actor", ""), "Detail": e.get("detail", ""),
        } for e in audit]), hide_index=True, width="stretch")
    else:
        st.caption("Nothing has been recorded yet.")


def _apply_action(store, me, target, action, new_role, new_pw, confirm) -> None:
    mine = target == me["username"]
    try:
        if mine and action in ("Disable", "Delete", "Change role"):
            raise ValueError("You can't change your own role, disable or delete your own account. "
                             "Ask another admin.")
        if action == "Change role":
            store.set_role(target, new_role, me["username"])
            msg = f"{target} is now {auth.ROLE_LABELS[new_role]}."
        elif action == "Reset password":
            store.set_password(target, new_pw, me["username"])
            msg = f"Password reset for {target}. Share it with them privately."
        elif action == "Disable":
            store.set_active(target, False, me["username"]); msg = f"{target} can no longer sign in."
        elif action == "Enable":
            store.set_active(target, True, me["username"]); msg = f"{target} can sign in again."
        elif action == "Unlock":
            store.unlock(target, me["username"]); msg = f"{target} is unlocked."
        else:
            if not confirm:
                raise ValueError("Tick the confirmation box to delete an account.")
            store.delete_user(target, me["username"]); msg = f"{target} was deleted."
    except ValueError as exc:
        st.error(str(exc))
        return
    _flash("success", msg)
    st.rerun()
