# Module: formation
# FormationMixin — path smoothing, formation placement and infantry square commands

import math

from src.constants import MAP_WIDTH


class FormationMixin:
    def _smoothPath(self, path, iterations=4):
        for _ in range(iterations):
            smoothed = [path[0]]
            for i in range(1, len(path) - 1):
                smoothed.append((
                    (path[i - 1][0] + path[i][0] + path[i + 1][0]) / 3,
                    (path[i - 1][1] + path[i][1] + path[i + 1][1]) / 3
                ))
            smoothed.append(path[-1])
            path = smoothed
        return path

    def _pointOnPath(self, path, dists, t):
        for j in range(1, len(dists)):
            if dists[j] >= t or j == len(dists) - 1:
                segT = (t - dists[j - 1]) / max(dists[j] - dists[j - 1], 0.001)
                px   = path[j - 1][0] + segT * (path[j][0] - path[j - 1][0])
                py   = path[j - 1][1] + segT * (path[j][1] - path[j - 1][1])
                j0   = max(0, j - 4)
                j1   = min(len(path) - 1, j + 3)
                tang = math.degrees(math.atan2(
                    path[j1][1] - path[j0][1],
                    path[j1][0] - path[j0][0]
                ))
                return px, py, tang
        px, py = path[-1]
        tang   = math.degrees(math.atan2(
            path[-1][1] - path[-2][1],
            path[-1][0] - path[-2][0]
        ))
        return px, py, tang

    def _prepForRedeploy(self, units):
        """Break square formations and pack up deployed artillery so the
        selection is actually free to move when it receives a new order."""
        for u in units:
            if u.unitType == 'infantry' and u.inSquare:
                u.reformTimer = 105
            u.inSquare = False
            if u.unitType == 'artillery' and u.deployed:
                u.deployed      = False
                u.undeploying   = True
                u.undeployTimer = 90

    def _applyFormationPath(self, path):
        if not self.selectedUnits or len(path) < 2:
            return
        self._prepForRedeploy(self.selectedUnits)
        path  = self._smoothPath(path)
        dists = [0.0]
        for i in range(1, len(path)):
            dists.append(dists[-1] + math.hypot(
                path[i][0] - path[i - 1][0],
                path[i][1] - path[i - 1][1]
            ))
        totalLen = dists[-1]
        n        = len(self.selectedUnits)
        # Face the formation toward the foes of whichever team we're commanding
        # (important in multiplayer, where selectedUnits can be 'enemy'-team).
        ownTeam = self.selectedUnits[0].team if self.selectedUnits else 'player'
        foeTeam = 'enemy' if ownTeam == 'player' else 'player'
        foes    = [u for u in self.units if u.team == foeTeam]
        ecx     = sum(e.x for e in foes) / len(foes) if foes else MAP_WIDTH

        for i, u in enumerate(self.selectedUnits):
            t            = (i * totalLen / (n - 1)) if n > 1 else totalLen / 2
            px, py, tang = self._pointOnPath(path, dists, t)
            perpA        = tang + 90
            perpB        = tang - 90
            dot          = math.cos(math.radians(perpA)) * (ecx - px)
            u.targetX      = px
            u.targetY      = py
            u.attackTarget = None
            u.angle        = perpA if dot >= 0 else perpB

    def _applyPatrolPath(self, path):
        """Assign a back-and-forth patrol path to all selected units.
        Units are staggered evenly along the path so they spread out."""
        if not self.selectedUnits or len(path) < 2:
            return
        self._prepForRedeploy(self.selectedUnits)
        path  = self._smoothPath(path)
        dists = [0.0]
        for i in range(1, len(path)):
            dists.append(dists[-1] + math.hypot(
                path[i][0] - path[i - 1][0],
                path[i][1] - path[i - 1][1]
            ))
        totalLen = dists[-1]
        n = len(self.selectedUnits)
        for i, u in enumerate(self.selectedUnits):
            # Stagger start position evenly across the path
            t = (i * totalLen / n) if n > 1 else 0.0
            px, py, _ = self._pointOnPath(path, dists, t)
            # Find nearest index in the path list to the stagger position
            start_idx = min(range(len(path)),
                            key=lambda j: math.hypot(path[j][0] - px, path[j][1] - py))
            u.patrolPath   = list(path)
            u._patrolIdx   = start_idx
            u._patrolDir   = 1
            u.targetX      = path[start_idx][0]
            u.targetY      = path[start_idx][1]
            u.attackTarget = None
            u.inSquare     = False
            u._waypoints   = []

    def _toggleInfantrySquare(self):
        infantry = [u for u in self.selectedUnits if u.unitType == 'infantry']
        if not infantry:
            return

        alreadyIn = any(u.inSquare for u in infantry)
        if alreadyIn:
            for u in infantry:
                u.inSquare    = False
                u.reformTimer = 105
            return

        if len(infantry) == 1:
            infantry[0].inSquare     = True
            infantry[0].reformTimer  = 105
            infantry[0].attackTarget = None
            return

        cx      = sum(u.x for u in infantry) / len(infantry)
        cy      = sum(u.y for u in infantry) / len(infantry)
        nSide   = max(1, math.ceil(len(infantry) / 4))
        spacing = 34
        half    = nSide * spacing / 2

        sides = [
            [(-half + (i + 0.5) * spacing, -half,  270) for i in range(nSide)],
            [(half,  -half + (i + 0.5) * spacing,    0) for i in range(nSide)],
            [(half  - (i + 0.5) * spacing,  half,   90) for i in range(nSide)],
            [(-half,  half  - (i + 0.5) * spacing, 180) for i in range(nSide)],
        ]
        positions = [p for side in sides for p in side]

        for i, u in enumerate(infantry):
            ox, oy, face   = positions[i % len(positions)]
            u.targetX      = cx + ox
            u.targetY      = cy + oy
            u.angle        = face
            u.inSquare     = True
            u.reformTimer  = 105
            u.attackTarget = None
