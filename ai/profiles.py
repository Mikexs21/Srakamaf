from dataclasses import dataclass


@dataclass
class AIProfileData:
    name: str
    aggression: float
    paranoia: float
    loyalty_to_majority: float
    randomness: float


AGGRESSIVE = AIProfileData("aggressive", 0.8, 0.4, 0.4, 0.1)
CAUTIOUS = AIProfileData("cautious", 0.3, 0.7, 0.8, 0.05)
SEMI_RANDOM = AIProfileData("semi_random", 0.5, 0.5, 0.5, 0.2)

PROFILE_MAP = {p.name: p for p in [AGGRESSIVE, CAUTIOUS, SEMI_RANDOM]}


