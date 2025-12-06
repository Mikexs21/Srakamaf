import secrets


def generate_internal_id(prefix: str = "id") -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


