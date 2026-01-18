#!/usr/bin/env python3
"""
Generate a JWT token for testing API endpoints.

Usage:
    python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.auth import create_access_token


def main():
    parser = argparse.ArgumentParser(
        description="Generate JWT token for testing API endpoints"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="test-user",
        help="User ID to include in token (default: test-user)",
    )
    parser.add_argument(
        "--roles",
        type=str,
        default="user",
        help="Comma-separated roles (default: user)",
    )
    parser.add_argument(
        "--expiry-hours",
        type=int,
        default=24,
        help="Token expiration in hours (default: 24)",
    )

    args = parser.parse_args()

    # Parse roles
    roles = [role.strip() for role in args.roles.split(",")]

    # Create token
    try:
        token = create_access_token(
            data={"sub": args.user_id, "roles": roles},
            expires_delta=timedelta(hours=args.expiry_hours),
        )

        print("\n" + "=" * 80)
        print("JWT Token Generated Successfully")
        print("=" * 80)
        print(f"\nUser ID: {args.user_id}")
        print(f"Roles: {', '.join(roles)}")
        print(f"Expires in: {args.expiry_hours} hours")
        print("\n" + "-" * 80)
        print("Token:")
        print("-" * 80)
        print(token)
        print("\n" + "-" * 80)
        print("Usage:")
        print("-" * 80)
        print(f'\ncurl -H "Authorization: Bearer {token}" \\')
        print("     http://localhost:8000/api/projects")
        print("\nOR set as environment variable:")
        print("-" * 80)
        print(f'export TOKEN="{token}"')
        print('curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects')
        print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"\nError generating token: {e}", file=sys.stderr)
        print("\nMake sure JWT_SECRET_KEY is set in your .env file", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
