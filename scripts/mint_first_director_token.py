"""Mint the very first director token for a center.

One-shot bootstrap: before any director token exists, the
`POST /api/admin/tokens/issue` endpoint can't be called (it requires a
director token to call). This script bypasses that chicken-and-egg by
calling generate_token() directly.

Usage (run from the repo root):

    DATABASE_URL='postgresql://...' \
    AUTH_TOKEN_SECRET='...' \
    APP_BASE_URL='https://your-app.up.railway.app' \
    PYTHONPATH=. \
    python scripts/mint_first_director_token.py \
        --admin-id <uuid> --center-id <uuid>

Hand the printed URL to the director. They open it once on their phone,
Add to Home Screen, and use that session to issue every subsequent token
through the API.
"""

import argparse
import sys
from uuid import UUID

from backend.config import get_settings
from backend.utils.auth_tokens import generate_token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-id", required=True, help="UUID from the admins table")
    parser.add_argument("--center-id", required=True, help="UUID from the centers table")
    parser.add_argument("--days", type=int, default=90, help="Token validity in days")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.auth_token_secret:
        sys.stderr.write("AUTH_TOKEN_SECRET is not set — aborting\n")
        return 1

    admin_id = UUID(args.admin_id)
    center_id = UUID(args.center_id)

    token, payload = generate_token(
        role="director",
        sub=admin_id,
        center_id=center_id,
        expires_in_days=args.days,
    )

    base = settings.app_base_url.rstrip("/")
    url = f"{base}/app?token={token}"

    print()
    print("Bootstrap URL (hand this to the director):")
    print()
    print(f"  {url}")
    print()
    print(f"Expires: {payload.expires_at.isoformat()}")
    print(f"Nonce  : {payload.nonce}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
