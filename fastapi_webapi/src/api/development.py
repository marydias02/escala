from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent.absolute().__str__()


def generate_api_key():
    """
    run this with `uv run generate_api_key` to generate a new API key and its hash
    """
    import json
    import secrets

    from argon2 import PasswordHasher

    ph = PasswordHasher()

    api_key = secrets.token_urlsafe(64)
    hash = ph.hash(api_key)
    print(json.dumps({"HASHED_API_KEY": hash, "X-API-KEY": api_key}))
