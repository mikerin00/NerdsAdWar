# Module: headquarters
# Headquarters class — capturable objective; losing yours ends the game

import math


class Headquarters:
    CAPTURE_RADIUS = 70    # pixels; units must be inside to capture
    CAPTURE_TIME   = 300   # frames to fully capture (~5 seconds at 60 fps)

    def __init__(self, x, y, team):
        self.x               = float(x)
        self.y               = float(y)
        self.team            = team
        self.captureProgress = 0.0
        self.captured        = False

    def update(self, allUnits):
        if self.captured:
            return

        friendlies = [
            u for u in allUnits
            if u.team == self.team
            and math.hypot(u.x - self.x, u.y - self.y) <= self.CAPTURE_RADIUS
        ]
        enemies = [
            u for u in allUnits
            if u.team != self.team
            and math.hypot(u.x - self.x, u.y - self.y) <= self.CAPTURE_RADIUS
        ]

        if enemies and not friendlies:
            # Uncontested enemy presence — progress increases
            self.captureProgress = min(self.CAPTURE_TIME, self.captureProgress + 1)
        elif friendlies:
            # Defenders push back — progress decreases
            self.captureProgress = max(0, self.captureProgress - 1)
        # Mixed: contested — progress stays

        if self.captureProgress >= self.CAPTURE_TIME:
            self.captured = True
