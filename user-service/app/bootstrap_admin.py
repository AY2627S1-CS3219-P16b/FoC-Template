"""Idempotent operator command to bootstrap an existing account as first admin."""

import argparse
import os

from dotenv import load_dotenv

from .database import BootstrapUnavailableError, Database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of an existing active registered user")
    parser.add_argument(
        "--env-file", help="Optional environment file containing DATABASE_URL"
    )
    args = parser.parse_args()

    if args.env_file:
        load_dotenv(args.env_file, override=False)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL is required")

    database = Database(database_url)
    try:
        database.initialize()
        try:
            result = database.bootstrap_first_admin(args.email.strip().lower())
        except BootstrapUnavailableError:
            parser.error(
                "bootstrap is unavailable: another account was bootstrapped, "
                "an admin already exists, or the candidate is missing or inactive"
            )
        user = result.user
        if result.created:
            print(f"Initial admin created: {user['email']} ({user['id']})")
        else:
            print(
                f"Bootstrap already completed for {user['email']} ({user['id']}); "
                f"current role is {user['auth_role']} and status is {user['account_status']}."
            )
    finally:
        database.close()


if __name__ == "__main__":
    main()
