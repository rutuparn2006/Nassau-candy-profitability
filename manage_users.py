"""Manage dashboard accounts from the command line.

    python manage_users.py add alice --role admin --name "Alice Rao"
    python manage_users.py list
    python manage_users.py passwd alice
    python manage_users.py role alice analyst
    python manage_users.py disable bob        (or: enable / unlock / delete)
    python manage_users.py audit --limit 50

Passwords are always prompted for (hidden), never passed as arguments, so they stay out of shell history.
"""
from __future__ import annotations

import argparse
import getpass
import sys
import time

from nassau import auth


def _ts(v):
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(v)) if v else "-"


def _ask_password(confirm: bool = True) -> str:
    pw = getpass.getpass("Password: ")
    if confirm and pw != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords do not match.")
    return pw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("username"); a.add_argument("--role", choices=auth.ROLES, default="viewer")
    a.add_argument("--name", default="")
    sub.add_parser("list")
    for c in ("passwd", "enable", "disable", "unlock", "delete"):
        sub.add_parser(c).add_argument("username")
    r = sub.add_parser("role"); r.add_argument("username"); r.add_argument("role", choices=auth.ROLES)
    au = sub.add_parser("audit"); au.add_argument("--limit", type=int, default=30)
    args = ap.parse_args(argv)

    store = auth.UserStore()
    actor = "cli"
    try:
        if args.cmd == "add":
            name = store.create_user(args.username, _ask_password(), args.role, args.name, actor)
            print(f"Created {name} ({args.role}).")
        elif args.cmd == "list":
            for u in store.list_users():
                state = "locked" if u["locked"] else ("active" if u["active"] else "disabled")
                print(f"{u['username']:<20} {u['role']:<8} {state:<9} last login {_ts(u['last_login'])}")
        elif args.cmd == "passwd":
            store.set_password(args.username, _ask_password(), actor); print("Password updated.")
        elif args.cmd == "role":
            store.set_role(args.username, args.role, actor); print("Role updated.")
        elif args.cmd == "enable":
            store.set_active(args.username, True, actor); print("Enabled.")
        elif args.cmd == "disable":
            store.set_active(args.username, False, actor); print("Disabled.")
        elif args.cmd == "unlock":
            store.unlock(args.username, actor); print("Unlocked.")
        elif args.cmd == "delete":
            if input(f"Delete {args.username}? Type the username to confirm: ").strip() != args.username:
                print("Cancelled."); return 1
            store.delete_user(args.username, actor); print("Deleted.")
        elif args.cmd == "audit":
            for e in store.read_audit(args.limit):
                print(f"{_ts(e['ts'])}  {e['event']:<18} {e['user']:<16} {e['actor']:<8} {e['detail']}")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
