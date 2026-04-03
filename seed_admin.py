#!/usr/bin/env python3
"""Create an admin user from command line arguments."""

import argparse
import sys
from database import init_db, get_db_context
from auth import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()

    init_db()

    with get_db_context() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (args.email,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE users SET is_admin = 1, password_hash = ? WHERE email = ?",
                (hash_password(args.password), args.email),
            )
            print(f"Updated existing user '{args.email}' to admin.")
        else:
            conn.execute(
                "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)",
                (args.email, hash_password(args.password)),
            )
            print(f"Created admin user '{args.email}'.")


if __name__ == "__main__":
    main()
