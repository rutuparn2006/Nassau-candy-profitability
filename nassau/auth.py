"""Authentication and authorisation for the dashboard.

Standard library only, so it can be tested and used from the command line without Streamlit.

Security model
--------------
* Passwords are never stored. Each user has a salted PBKDF2-HMAC-SHA256 hash
  (``pbkdf2_sha256$<iterations>$<salt>$<hash>``), compared in constant time.
* Unknown usernames cost the same time as known ones (a dummy hash is checked) and produce the same
  error, so the login form does not reveal which accounts exist.
* After ``MAX_FAILED`` wrong attempts a username is locked for ``LOCK_SECONDS``. The counter is kept
  for unknown usernames too, so locking looks the same either way.
* Roles map to permissions (see ``PERMISSIONS``); the app checks permissions, not role names.
* The last active admin cannot be deleted, disabled or demoted.
* Every sign-in, failure, lock-out and account change is appended to a JSON-lines audit log.
* Files are written atomically (temp file + ``os.replace``) with owner-only permissions.

Limits worth knowing: lock-out is per username (Streamlit does not expose a reliable client IP), and
the store is a JSON file, which suits a small team on one server rather than many app instances.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

AUTH_DIR = Path(os.environ.get("NASSAU_AUTH_DIR") or Path(__file__).resolve().parent.parent / "auth_data")

ROLES = ("admin", "analyst", "viewer")
PERMISSIONS = {
    "admin": frozenset({"view", "download", "view_method", "manage_users"}),
    "analyst": frozenset({"view", "download", "view_method"}),
    "viewer": frozenset({"view"}),
}
ROLE_LABELS = {
    "admin": "Admin",
    "analyst": "Analyst",
    "viewer": "Viewer",
}
ROLE_SUMMARY = {
    "admin": "Everything, including managing people and reading the audit log",
    "analyst": "All dashboards, data & method, and CSV export",
    "viewer": "Dashboards only; no export or data details",
}

ITERATIONS = 600_000        # OWASP guidance for PBKDF2-HMAC-SHA256
MAX_FAILED = 5
LOCK_SECONDS = 15 * 60
MAX_PASSWORD_LEN = 256
MIN_PASSWORD_LEN = 10
THROTTLE_CAP = 2000

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_COMMON = {
    "password123", "password1234", "1234567890", "qwertyuiop", "letmein123", "welcome123",
    "admin12345", "iloveyou123", "changeme123", "passw0rd123",
}


# ---------------------------------------------------------------------------- password hashing
def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored) -> bool:
    """Return True only for a correct password. Malformed or missing hashes return False, never raise."""
    try:
        scheme, iters, salt_b64, digest_b64 = stored.split("$")
        iterations = int(iters)
        if scheme != "pbkdf2_sha256" or not 1 <= iterations <= 10_000_000:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    except (AttributeError, ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def hash_iterations(stored) -> int:
    try:
        return int(stored.split("$")[1])
    except (AttributeError, ValueError, IndexError):
        return 0


# ---------------------------------------------------------------------------- validation
def normalize_username(username) -> str:
    return str(username or "").strip().lower()[:64]


def validate_username(username: str) -> str:
    name = normalize_username(username)
    if not _USERNAME_RE.match(name):
        raise ValueError("Username must be 3-32 characters: lowercase letters, digits, dot, dash or underscore, "
                         "starting with a letter or digit.")
    return name


def password_problems(password: str, username: str = "") -> list[str]:
    problems = []
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        problems.append(f"be at least {MIN_PASSWORD_LEN} characters long")
        password = password if isinstance(password, str) else ""
    if len(password) > MAX_PASSWORD_LEN:
        problems.append(f"be at most {MAX_PASSWORD_LEN} characters long")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("include at least one letter and one number")
    if username and normalize_username(username) in password.lower():
        problems.append("not contain the username")
    if password.lower() in _COMMON:
        problems.append("not be a commonly used password")
    return problems


def check_password(password: str, username: str = "") -> None:
    problems = password_problems(password, username)
    if problems:
        raise ValueError("Password must " + ", ".join(problems) + ".")


# ---------------------------------------------------------------------------- results
@dataclass(frozen=True)
class AuthResult:
    ok: bool
    username: str = ""
    reason: str = ""          # "ok" | "invalid" | "locked"
    retry_after: int = 0      # seconds, when locked
    attempts_left: int = 0


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


# ---------------------------------------------------------------------------- store
class UserStore:
    """JSON-file user store with lock-out and audit logging."""

    def __init__(self, directory: Path | str | None = None, iterations: int = ITERATIONS,
                 clock: Callable[[], float] = time.time):
        self.dir = Path(directory) if directory else AUTH_DIR
        self.users_path = self.dir / "users.json"
        self.audit_path = self.dir / "audit.log"
        self.iterations = iterations
        self.clock = clock
        self._lock = threading.RLock()
        self._dummy_hash = hash_password(secrets.token_hex(8), iterations)

    # -- persistence
    def _load(self) -> dict:
        try:
            data = json.loads(self.users_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        data.setdefault("users", {})
        data.setdefault("throttle", {})
        return data

    def _save(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".users-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.users_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def audit(self, event: str, username: str = "", actor: str = "", detail: str = "") -> None:
        clean = lambda s: re.sub(r"[\x00-\x1f\x7f]", " ", str(s))[:200]
        record = {"ts": self.clock(), "event": event, "user": clean(username), "actor": clean(actor),
                  "detail": clean(detail)}
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            new = not self.audit_path.exists()
            with open(self.audit_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
            if new:
                os.chmod(self.audit_path, 0o600)

    def read_audit(self, limit: int = 200) -> list[dict]:
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        out = []
        for line in reversed(lines[-limit:]):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # -- queries
    def has_users(self) -> bool:
        with self._lock:
            return bool(self._load()["users"])

    def get_user(self, username: str) -> dict | None:
        with self._lock:
            u = self._load()["users"].get(normalize_username(username))
        if not u:
            return None
        return {"username": normalize_username(username), "display_name": u.get("display_name") or username,
                "role": u["role"], "active": u.get("active", True)}

    def list_users(self) -> list[dict]:
        with self._lock:
            data = self._load()
        now = self.clock()
        rows = []
        for name, u in sorted(data["users"].items()):
            t = data["throttle"].get(name, {})
            rows.append({"username": name, "display_name": u.get("display_name") or name, "role": u["role"],
                         "active": u.get("active", True), "created_at": u.get("created_at"),
                         "last_login": u.get("last_login"), "locked": t.get("locked_until", 0) > now})
        return rows

    def _active_admins(self, data: dict, excluding: str = "") -> int:
        return sum(1 for n, u in data["users"].items()
                   if n != excluding and u["role"] == "admin" and u.get("active", True))

    # -- account management
    def create_user(self, username: str, password: str, role: str = "viewer", display_name: str = "",
                    actor: str = "system") -> str:
        name = validate_username(username)
        if role not in ROLES:
            raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")
        check_password(password, name)
        with self._lock:
            data = self._load()
            if name in data["users"]:
                raise ValueError("That username is already taken.")
            data["users"][name] = {
                "display_name": (display_name or "").strip()[:60] or name,
                "role": role, "active": True, "password_hash": hash_password(password, self.iterations),
                "created_at": self.clock(), "last_login": None,
            }
            self._save(data)
            self.audit("user_created", name, actor, f"role={role}")
        return name

    def set_password(self, username: str, new_password: str, actor: str = "system") -> None:
        name = normalize_username(username)
        check_password(new_password, name)
        with self._lock:
            data = self._load()
            if name not in data["users"]:
                raise ValueError("No such user.")
            data["users"][name]["password_hash"] = hash_password(new_password, self.iterations)
            data["throttle"].pop(name, None)
            self._save(data)
            self.audit("password_changed", name, actor)

    def change_own_password(self, username: str, current: str, new_password: str) -> None:
        res = self.authenticate(username, current, _event_prefix="reauth")
        if not res.ok:
            raise ValueError("Current password is incorrect." if res.reason != "locked"
                             else "Too many attempts. Try again later.")
        if current == new_password:
            raise ValueError("New password must differ from the current one.")
        self.set_password(username, new_password, actor=username)

    def set_role(self, username: str, role: str, actor: str = "system") -> None:
        name = normalize_username(username)
        if role not in ROLES:
            raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")
        with self._lock:
            data = self._load()
            if name not in data["users"]:
                raise ValueError("No such user.")
            if data["users"][name]["role"] == "admin" and role != "admin" and self._active_admins(data, name) == 0:
                raise ValueError("At least one active admin must remain.")
            data["users"][name]["role"] = role
            self._save(data)
            self.audit("role_changed", name, actor, f"role={role}")

    def set_active(self, username: str, active: bool, actor: str = "system") -> None:
        name = normalize_username(username)
        with self._lock:
            data = self._load()
            if name not in data["users"]:
                raise ValueError("No such user.")
            if not active and data["users"][name]["role"] == "admin" and self._active_admins(data, name) == 0:
                raise ValueError("At least one active admin must remain.")
            data["users"][name]["active"] = bool(active)
            if active:
                data["throttle"].pop(name, None)
            self._save(data)
            self.audit("user_enabled" if active else "user_disabled", name, actor)

    def unlock(self, username: str, actor: str = "system") -> None:
        name = normalize_username(username)
        with self._lock:
            data = self._load()
            data["throttle"].pop(name, None)
            self._save(data)
            self.audit("user_unlocked", name, actor)

    def delete_user(self, username: str, actor: str = "system") -> None:
        name = normalize_username(username)
        with self._lock:
            data = self._load()
            if name not in data["users"]:
                raise ValueError("No such user.")
            if data["users"][name]["role"] == "admin" and self._active_admins(data, name) == 0:
                raise ValueError("At least one active admin must remain.")
            del data["users"][name]
            data["throttle"].pop(name, None)
            self._save(data)
            self.audit("user_deleted", name, actor)

    # -- sign-in
    def authenticate(self, username: str, password: str, _event_prefix: str = "login") -> AuthResult:
        key = normalize_username(username)
        password = password if isinstance(password, str) else ""
        with self._lock:
            data = self._load()
            now = self.clock()
            t = data["throttle"].get(key, {"failed": 0, "locked_until": 0, "last": 0})
            if t.get("locked_until", 0) > now:
                self.audit(f"{_event_prefix}_blocked", key, detail="account locked")
                return AuthResult(False, key, "locked", retry_after=int(t["locked_until"] - now) + 1)
            if t.get("failed", 0) and now - t.get("last", 0) > LOCK_SECONDS:
                t = {"failed": 0, "locked_until": 0, "last": 0}   # old failures expire

            user = data["users"].get(key)
            too_long = len(password) > MAX_PASSWORD_LEN
            stored = user["password_hash"] if user else self._dummy_hash
            matches = verify_password("" if too_long else password, stored) and not too_long
            good = bool(user) and user.get("active", True) and matches

            if good:
                data["throttle"].pop(key, None)
                user["last_login"] = now
                if hash_iterations(user["password_hash"]) < self.iterations:
                    user["password_hash"] = hash_password(password, self.iterations)
                self._save(data)
                self.audit(f"{_event_prefix}_success", key)
                return AuthResult(True, key, "ok")

            t["failed"] = t.get("failed", 0) + 1
            t["last"] = now
            reason = "unknown user" if not user else ("disabled account" if not user.get("active", True)
                                                      else "wrong password")
            locked_now = t["failed"] >= MAX_FAILED
            if locked_now:
                t["locked_until"] = now + LOCK_SECONDS
                t["failed"] = 0
            data["throttle"][key] = t
            self._prune_throttle(data, now)
            self._save(data)
            self.audit(f"{_event_prefix}_failed", key, detail=reason)
            if locked_now:
                self.audit("account_locked", key, detail=f"{LOCK_SECONDS // 60} minutes")
                return AuthResult(False, key, "locked", retry_after=LOCK_SECONDS)
            return AuthResult(False, key, "invalid", attempts_left=MAX_FAILED - t["failed"])

    @staticmethod
    def _prune_throttle(data: dict, now: float) -> None:
        th = data["throttle"]
        for k in [k for k, v in th.items() if v.get("locked_until", 0) <= now and v.get("failed", 0) == 0]:
            del th[k]
        if len(th) > THROTTLE_CAP:
            for k, _ in sorted(th.items(), key=lambda kv: kv[1].get("last", 0))[: len(th) - THROTTLE_CAP]:
                del th[k]
