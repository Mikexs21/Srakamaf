import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("mafia")


def game_prefix(game_id: int | None = None, chat_id: int | None = None, round_no: int | None = None) -> str:
    parts = []
    if game_id is not None:
        parts.append(f"game={game_id}")
    if chat_id is not None:
        parts.append(f"chat={chat_id}")
    if round_no is not None:
        parts.append(f"round={round_no}")
    return "[" + " ".join(parts) + "]" if parts else ""


