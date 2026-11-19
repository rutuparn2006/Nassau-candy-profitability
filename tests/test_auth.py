"""Tests for nassau.auth (standard library only; run with `python -m unittest` or pytest)."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from nassau import auth


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class AuthTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        # low iteration count keeps the suite fast; production default is auth.ITERATIONS
        self.store = auth.UserStore(self._tmp.name, iterations=1000, clock=self.clock)
        self.store.create_user("alice", "Sup3rSecretPass", "admin", "Alice")

    def tearDown(self):
        self._tmp.cleanup()

    # ---- hashing
    def test_hash_roundtrip_and_salting(self):
        h1, h2 = auth.hash_password("correct horse 9", 1000), auth.hash_password("correct horse 9", 1000)
        self.assertNotEqual(h1, h2)
        self.assertTrue(auth.verify_password("correct horse 9", h1))
        self.assertFalse(auth.verify_password("correct horse 8", h1))
        self.assertNotIn("correct horse", h1)

    def test_malformed_hashes_fail_cleanly(self):
        for bad in (None, "", "garbage", "a$b$c", "pbkdf2_sha256$x$y$z", "pbkdf2_sha256$0$AAAA$AAAA",
                    "md5$1000$AAAA$AAAA", 12345):
            self.assertFalse(auth.verify_password("whatever", bad), bad)

    # ---- validation
    def test_password_rules(self):
        self.assertTrue(auth.password_problems("short1"))
        self.assertTrue(auth.password_problems("onlyletterspassword"))
        self.assertTrue(auth.password_problems("1234567890123"))
        self.assertTrue(auth.password_problems("bobsecret99xx", "bob") == ["not contain the username"])
        self.assertTrue(auth.password_problems("x" * 300 + "1"))
        self.assertFalse(auth.password_problems("Sup3rSecretPass", "alice"))

    def test_username_rules(self):
        self.assertEqual(auth.validate_username("  Bob.Smith "), "bob.smith")
        for bad in ("", "ab", "-bob", "bob smith", "bob/../x", "a" * 40):
            with self.assertRaises(ValueError):
                auth.validate_username(bad)

    # ---- sign-in
    def test_login_success_and_audit(self):
        res = self.store.authenticate("ALICE", "Sup3rSecretPass")
        self.assertTrue(res.ok)
        self.assertEqual(res.username, "alice")
        events = [e["event"] for e in self.store.read_audit()]
        self.assertIn("login_success", events)
        self.assertIsNotNone(self.store.list_users()[0]["last_login"])

    def test_wrong_password_and_unknown_user_look_identical(self):
        a = self.store.authenticate("alice", "nope-nope-nope1")
        b = self.store.authenticate("ghost", "nope-nope-nope1")
        self.assertEqual((a.ok, a.reason), (b.ok, b.reason))
        self.assertEqual((a.reason, a.attempts_left), ("invalid", 4))

    def test_lockout_then_expiry(self):
        for i in range(auth.MAX_FAILED - 1):
            self.assertEqual(self.store.authenticate("alice", "bad-password-1").reason, "invalid")
        locking = self.store.authenticate("alice", "bad-password-1")
        self.assertEqual(locking.reason, "locked")
        # correct password is refused while locked
        self.assertEqual(self.store.authenticate("alice", "Sup3rSecretPass").reason, "locked")
        self.clock.t += auth.LOCK_SECONDS + 5
        self.assertTrue(self.store.authenticate("alice", "Sup3rSecretPass").ok)

    def test_unknown_usernames_also_lock(self):
        for _ in range(auth.MAX_FAILED):
            res = self.store.authenticate("ghost", "bad-password-1")
        self.assertEqual(res.reason, "locked")

    def test_old_failures_expire(self):
        for _ in range(auth.MAX_FAILED - 1):
            self.store.authenticate("alice", "bad-password-1")
        self.clock.t += auth.LOCK_SECONDS + 5
        res = self.store.authenticate("alice", "bad-password-1")
        self.assertEqual(res.attempts_left, auth.MAX_FAILED - 1)

    def test_success_resets_counter(self):
        for _ in range(3):
            self.store.authenticate("alice", "bad-password-1")
        self.assertTrue(self.store.authenticate("alice", "Sup3rSecretPass").ok)
        self.assertEqual(self.store.authenticate("alice", "bad-password-1").attempts_left, 4)

    def test_disabled_user_cannot_sign_in(self):
        self.store.create_user("bob", "Another1Secret", "viewer")
        self.store.set_active("bob", False, "alice")
        res = self.store.authenticate("bob", "Another1Secret")
        self.assertFalse(res.ok)
        self.assertEqual(res.reason, "invalid")   # same message as a wrong password
        self.store.set_active("bob", True, "alice")
        self.assertTrue(self.store.authenticate("bob", "Another1Secret").ok)

    def test_overlong_password_rejected_without_crash(self):
        self.assertFalse(self.store.authenticate("alice", "a1" * 200).ok)
        self.assertFalse(self.store.authenticate("alice", None).ok)

    def test_old_hash_upgraded_on_login(self):
        weak = auth.UserStore(self._tmp.name, iterations=500, clock=self.clock)
        weak.create_user("carol", "Maple7Syrup2024", "viewer")
        self.assertTrue(self.store.authenticate("carol", "Maple7Syrup2024").ok)   # store wants 1000
        data = json.loads(Path(self._tmp.name, "users.json").read_text())
        self.assertEqual(auth.hash_iterations(data["users"]["carol"]["password_hash"]), 1000)

    # ---- management
    def test_duplicate_and_bad_role(self):
        with self.assertRaises(ValueError):
            self.store.create_user("Alice", "Sup3rSecretPass", "viewer")
        with self.assertRaises(ValueError):
            self.store.create_user("dave", "Sup3rSecretPass", "superuser")

    def test_last_admin_is_protected(self):
        with self.assertRaises(ValueError):
            self.store.set_role("alice", "viewer")
        with self.assertRaises(ValueError):
            self.store.set_active("alice", False)
        with self.assertRaises(ValueError):
            self.store.delete_user("alice")
        self.store.create_user("erin", "Tr1ckyPassphrase", "admin")
        self.store.set_role("alice", "viewer")            # allowed now: erin is an active admin
        with self.assertRaises(ValueError):
            self.store.delete_user("erin")

    def test_password_change_flow(self):
        with self.assertRaises(ValueError):
            self.store.change_own_password("alice", "wrong-current1", "Brand9NewPassword")
        self.store.change_own_password("alice", "Sup3rSecretPass", "Brand9NewPassword")
        self.assertFalse(self.store.authenticate("alice", "Sup3rSecretPass").ok)
        self.assertTrue(self.store.authenticate("alice", "Brand9NewPassword").ok)

    def test_admin_reset_clears_lock(self):
        for _ in range(auth.MAX_FAILED):
            self.store.authenticate("alice", "bad-password-1")
        self.store.set_password("alice", "Reset9Password", "root")
        self.assertTrue(self.store.authenticate("alice", "Reset9Password").ok)

    def test_permissions(self):
        self.assertTrue(auth.can("admin", "manage_users"))
        self.assertTrue(auth.can("analyst", "download"))
        self.assertFalse(auth.can("analyst", "manage_users"))
        self.assertTrue(auth.can("viewer", "view"))
        self.assertFalse(auth.can("viewer", "download"))
        self.assertFalse(auth.can("nobody", "view"))

    # ---- storage hygiene
    def test_no_plaintext_and_private_files(self):
        self.store.authenticate("alice", "Sup3rSecretPass")
        users = Path(self._tmp.name, "users.json")
        self.assertNotIn("Sup3rSecretPass", users.read_text())
        self.assertNotIn("Sup3rSecretPass", Path(self._tmp.name, "audit.log").read_text())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(users.stat().st_mode), 0o600)

    def test_audit_strips_control_characters(self):
        self.store.authenticate("evil\nname\x00", "bad-password-1")
        for line in Path(self._tmp.name, "audit.log").read_text().splitlines():
            json.loads(line)   # every record stays one valid JSON line


if __name__ == "__main__":
    unittest.main()
