# Module: outpost
# Outpost class — capturable neutral structure that extends the supply chain

import math


class Outpost:
    CAPTURE_RADIUS = 60    # units must be inside this zone to capture
    CAPTURE_RATE   = 1 / 120   # per frame; 2 seconds from neutral to captured

    def __init__(self, x, y, strategic=False):
        self.x          = float(x)
        self.y          = float(y)
        self.strategic  = strategic   # True → star marker, counts toward Conquest win
        # control ranges from -1.0 (enemy) to 1.0 (player); 0 = neutral
        self.control    = 0.0

    @property
    def team(self):
        if self.control >= 1.0:
            return 'player'
        if self.control <= -1.0:
            return 'enemy'
        return None

    def update(self, allUnits):
        players = [
            u for u in allUnits
            if u.team == 'player'
            and math.hypot(u.x - self.x, u.y - self.y) <= self.CAPTURE_RADIUS
        ]
        enemies = [
            u for u in allUnits
            if u.team == 'enemy'
            and math.hypot(u.x - self.x, u.y - self.y) <= self.CAPTURE_RADIUS
        ]

        if players and not enemies:
            self.control = min(1.0, self.control + self.CAPTURE_RATE)
        elif enemies and not players:
            self.control = max(-1.0, self.control - self.CAPTURE_RATE)
        # mixed or empty: control stays unchanged
