import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey, Float, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


class GameState(enum.Enum):
    LOBBY = "LOBBY"
    ROLE_DISTRIBUTION = "ROLE_DISTRIBUTION"
    NIGHT = "NIGHT"
    NIGHT_RESOLUTION = "NIGHT_RESOLUTION"
    DAY_DISCUSSION = "DAY_DISCUSSION"
    VOTING = "VOTING"
    LYNCH_CONFIRMATION = "LYNCH_CONFIRMATION"
    END = "END"


class Role(enum.Enum):
    DON = "DON"
    MAFIA = "MAFIA"
    DOCTOR = "DOCTOR"
    DETECTIVE = "DETECTIVE"
    CIVILIAN = "CIVILIAN"
    MAYOR = "MAYOR"
    DEPUTY = "DEPUTY"
    EXECUTIONER = "EXECUTIONER"
    JESTER = "JESTER"
    SUICIDE = "SUICIDE"
    HOOKER = "HOOKER"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, index=True, nullable=False)
    state = Column(Enum(GameState), default=GameState.LOBBY, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    settings_id = Column(Integer, ForeignKey("game_settings.id"))
    current_round = Column(Integer, default=0)
    lobby_message_id = Column(Integer)
    voting_message_id = Column(Integer)
    lynch_confirm_message_id = Column(Integer)
    buckovel_mode_enabled = Column(Boolean, default=False)
    blind_next_night = Column(Boolean, default=False)

    settings = relationship("GameSettings", back_populates="games")
    players = relationship("Player", back_populates="game", cascade="all, delete-orphan")
    suspicions = relationship("Suspicion", back_populates="game", cascade="all, delete-orphan")
    buff_usages = relationship("BuffUsage", back_populates="game", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    is_bot = Column(Boolean, default=False)
    is_alive = Column(Boolean, default=True)
    role = Column(Enum(Role), default=Role.CIVILIAN, nullable=False)
    ai_profile_id = Column(Integer, ForeignKey("ai_profiles.id"))
    last_vote_target_id = Column(Integer, ForeignKey("players.id"))
    night_target_id = Column(Integer, ForeignKey("players.id"))
    used_suicide = Column(Boolean, default=False)
    night_action_done = Column(Boolean, default=False)
    vote_ready = Column(Boolean, default=False)
    mayor_revealed = Column(Boolean, default=False)
    buffs_state = Column(JSON, default=dict)
    last_words = Column(String)
    last_words_round = Column(Integer)
    awaiting_last_words = Column(Boolean, default=False)
    potato_decision = Column(Boolean)

    game = relationship("Game", back_populates="players", foreign_keys=[game_id])
    ai_profile = relationship("AIProfile")


class GameSettings(Base):
    __tablename__ = "game_settings"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    night_duration = Column(Integer, default=60)
    day_duration = Column(Integer, default=30)
    voting_duration = Column(Integer, default=30)
    show_role_on_death = Column(Boolean, default=True)
    buckovel_mode_enabled = Column(Boolean, default=False)

    games = relationship("Game", back_populates="settings")


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    coins = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    display_cosmetics = Column(JSON, default=dict)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Integer, default=0)
    extra = Column(JSON, default=dict)  # renamed from metadata to avoid SQLAlchemy reserved name


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_accounts.user_id"), nullable=False)
    item_id = Column(Integer, ForeignKey("shop_items.id"), nullable=False)
    quantity = Column(Integer, default=1)
    is_active = Column(Boolean, default=False)
    expires_at = Column(DateTime)

    item = relationship("ShopItem")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uniq_user_item"),
    )


class AIProfile(Base):
    __tablename__ = "ai_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    aggression = Column(Float, default=0.5)
    paranoia = Column(Float, default=0.5)
    loyalty_to_majority = Column(Float, default=0.5)
    randomness = Column(Float, default=0.1)


class Suspicion(Base):
    __tablename__ = "suspicions"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    bot_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    target_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    suspicion_score = Column(Float, default=0.0)

    game = relationship("Game", back_populates="suspicions")


class BuffUsage(Base):
    __tablename__ = "buff_usages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_accounts.user_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    buff_code = Column(String, nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extra = Column(JSON, default=dict)

    game = relationship("Game", back_populates="buff_usages")


