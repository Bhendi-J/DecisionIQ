"""Provision an administrator through trusted local access; never through public signup."""

import argparse
import getpass
import sqlite3

from decisioniq.dashboard import store
from decisioniq.dashboard.auth import normalized_email, password_hash


def main():
    parser = argparse.ArgumentParser(
        description="Create or promote a ForeSight administrator locally"
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="ForeSight administrator")
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote an existing account without changing its password",
    )
    args = parser.parse_args()
    email = normalized_email(args.email)
    store.initialize()
    if args.promote:
        with store.connect() as connection:
            result = connection.execute("UPDATE users SET is_admin=1 WHERE email=?", (email,))
            if not result.rowcount:
                raise SystemExit(
                    "Account not found. Register it first or create a new administrator without --promote."
                )
        print("Administrator access granted. Existing account password is unchanged.")
        return
    password = getpass.getpass("New administrator password (12–128 characters): ")
    if not 12 <= len(password) <= 128 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords must match and contain 12–128 characters.")
    encoded = password_hash(password)
    try:
        with store.connect() as connection:
            connection.execute(
                "INSERT INTO users VALUES (?,?,?,?,1,?)",
                (
                    store.uid(),
                    email,
                    args.name.strip() or "ForeSight administrator",
                    encoded,
                    store.stamp(),
                ),
            )
    except sqlite3.IntegrityError:
        raise SystemExit(
            "Account exists. Use --promote to grant admin access without replacing its password."
        ) from None
    print("Administrator created. Sign in through the ForeSight login page.")


if __name__ == "__main__":
    main()
