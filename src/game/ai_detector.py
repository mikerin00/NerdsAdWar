# Module: ai_detector
# PlayerDetector — observes player behaviour and classifies it into tactical categories
#
# Detected behaviours (flags, multiple can be active at once):
#   CAVALRY_FORWARD     — player cavalry is ahead of their infantry line
#   WIDE_LINE           — player units span >65% of map height (broad front)
#   ARTILLERY_FORWARD   — player artillery is close to the front line
#   PLAYER_ADVANCING    — player centroid has moved toward enemy HQ this cycle
#   PLAYER_HOLDING      — player centroid has barely moved (defensive)
#   PLAYER_FLANKING     — >60% of player units are concentrated in one vertical half
#   PLAYER_IN_SQUARE    — player infantry are in square formation
#   SUPPLY_DEPENDENT    — player units clustered tightly around their own supply sources
#   OP_RAIDING          — player cavalry is approaching an enemy outpost
#   RIVER_DEFENSE       — player units are hugging the river bank as a defensive line
#   PLAYER_HOLDS_CHOKE  — player has ≥2 units sitting on/near a chokepoint we wanted to use

import math
from src.entities.terrain_helpers import distToSeg


def _dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def _centroidXY(units):
    if not units:
        return None, None
    return (sum(u.x for u in units) / len(units),
            sum(u.y for u in units) / len(units))


class PlayerDetector:
    # How many eval cycles a detected behaviour lingers before fading
    DECAY = 3

    def __init__(self):
        # Each behaviour maps to a remaining-cycles counter
        self._active: dict[str, int] = {}
        self._prevPlayerX = None
        self._chokepoints = []   # set by EnemyAI after terrain analysis

    def setChokepoints(self, chokepoints):
        self._chokepoints = list(chokepoints or [])

    def update(self, players, outposts, headquarters, H, terrain=None):
        """Call once per AI evaluation cycle to refresh behaviour flags."""
        if not players:
            self._active.clear()
            return

        # Decay all existing flags by 1
        self._active = {k: v - 1 for k, v in self._active.items() if v > 1}

        cav   = [u for u in players if u.unitType == 'cavalry']
        inf   = [u for u in players if u.unitType in ('infantry', 'heavy_infantry')]
        art   = [u for u in players if u.unitType == 'artillery']
        pcx, pcy = _centroidXY(players)
        enemyHq  = next((h for h in headquarters if h.team == 'enemy'), None)

        # ── CAVALRY_FORWARD ───────────────────────────────────────────────────
        # Cavalry centroid is more than 80 px ahead (closer to enemy HQ) than infantry
        if cav and inf:
            ccx, _ = _centroidXY(cav)
            icx, _ = _centroidXY(inf)
            if ccx is not None and icx is not None and ccx < icx - 80:
                self._flag('CAVALRY_FORWARD')

        # ── WIDE_LINE ─────────────────────────────────────────────────────────
        # Y spread of all player units > 65% of map height
        if len(players) >= 3:
            ys     = [u.y for u in players]
            spread = max(ys) - min(ys)
            if spread > H * 0.65:
                self._flag('WIDE_LINE')

        # ── ARTILLERY_FORWARD ────────────────────────────────────────────────
        # Player artillery is ahead of (or level with) their infantry centroid
        if art and inf:
            acx, _ = _centroidXY(art)
            icx, _ = _centroidXY(inf)
            if acx is not None and icx is not None and acx < icx + 30:
                self._flag('ARTILLERY_FORWARD')

        # ── PLAYER_ADVANCING / PLAYER_HOLDING ────────────────────────────────
        if self._prevPlayerX is not None and pcx is not None:
            dx = self._prevPlayerX - pcx   # positive = player moved toward enemy (right side)
            if dx > 18:
                self._flag('PLAYER_ADVANCING')
            elif abs(dx) < 8:
                self._flag('PLAYER_HOLDING')
        self._prevPlayerX = pcx

        # ── PLAYER_FLANKING ───────────────────────────────────────────────────
        # More than 60% of units in one vertical half of the map
        if len(players) >= 4:
            north = sum(1 for u in players if u.y < H / 2)
            south = len(players) - north
            if max(north, south) / len(players) > 0.60:
                self._flag('PLAYER_FLANKING')

        # ── PLAYER_IN_SQUARE ─────────────────────────────────────────────────
        if any(u.inSquare for u in inf):
            self._flag('PLAYER_IN_SQUARE')

        # ── SUPPLY_DEPENDENT ────────────────────────────────────────────────
        # Player units are tightly clustered within 250 px of their own HQ/OP
        playerHq = next((h for h in headquarters if h.team == 'player'), None)
        playerOps = [op for op in outposts if op.team == 'player']
        sources   = []
        if playerHq:  sources.append((playerHq.x, playerHq.y))
        sources  += [(op.x, op.y) for op in playerOps]
        if sources:
            near_supply = sum(
                1 for u in players
                if min(_dist(u.x, u.y, sx, sy) for sx, sy in sources) < 250
            )
            if near_supply / len(players) > 0.70:
                self._flag('SUPPLY_DEPENDENT')

        # ── OP_RAIDING ───────────────────────────────────────────────────────
        # Player cavalry heading toward an enemy outpost
        enemyOps = [op for op in outposts if op.team == 'enemy']
        if cav and enemyOps:
            for u in cav:
                nearest_op = min(enemyOps, key=lambda op: _dist(u.x, u.y, op.x, op.y))
                if _dist(u.x, u.y, nearest_op.x, nearest_op.y) < 300:
                    self._flag('OP_RAIDING')
                    break

        # ── RIVER_DEFENSE ────────────────────────────────────────────────────
        # Player units spread along the river bank, not advancing — using water as a wall.
        # Requires terrain to measure actual distance to river segments.
        if terrain and terrain.rivers and len(players) >= 3:
            BANK_DIST  = 200   # px either side of river counts as "hugging the bank"
            near_river = 0
            for u in players:
                for river in terrain.rivers:
                    close = False
                    for i in range(len(river) - 1):
                        if distToSeg(u.x, u.y,
                                     river[i][0], river[i][1],
                                     river[i+1][0], river[i+1][1]) < BANK_DIST:
                            close = True
                            break
                    if close:
                        near_river += 1
                        break
            # >40% near river AND not actively pushing forward
            if near_river / len(players) > 0.40 and not self.is_active('PLAYER_ADVANCING'):
                self._flag('RIVER_DEFENSE')

        # ── PLAYER_HOLDS_CHOKE ───────────────────────────────────────────
        # Any chokepoint with ≥2 player units within 90 px is "occupied" — a
        # narrow passage held by enemy musketry is a kill zone we must NOT
        # walk straight into. Triggers tactics that go around or soften it
        # with artillery from a distance.
        for cx, cy in self._chokepoints:
            held = sum(1 for u in players if _dist(u.x, u.y, cx, cy) < 90)
            if held >= 2:
                self._flag('PLAYER_HOLDS_CHOKE')
                break

        # ── FORTIFIED_RIVER ───────────────────────────────────────────────
        # Combined: river defense + artillery behind it = extremely strong position
        if self.is_active('RIVER_DEFENSE') and self.is_active('ARTILLERY_FORWARD'):
            self._flag('FORTIFIED_RIVER')
        elif self.is_active('RIVER_DEFENSE') and self.is_active('PLAYER_HOLDING'):
            self._flag('FORTIFIED_RIVER')

    def _flag(self, behaviour):
        self._active[behaviour] = self.DECAY

    def active(self):
        """Return set of currently active behaviour flags."""
        return set(self._active.keys())

    def is_active(self, behaviour):
        return behaviour in self._active
