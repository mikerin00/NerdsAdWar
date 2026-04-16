# Module: ai_helpers
# Standalone utility functions and shared constants for the EnemyAI system

import math

# ── Shared constants ──────────────────────────────────────────────────────────

TICK_INTERVAL   = 100
HQ_GUARD_COUNT  = 2
ART_GUARD_COUNT = 1
ARTILLERY_RANGE = 240

# Tactics that are purely survival / retreat — never penalised by _evaluateTactic
SURVIVAL_TACTICS = {'DELAYING_ACTION', 'CONTACT_AND_FADE', 'MOBILE_SUPPLY_BUBBLE'}


# ── Helper functions ──────────────────────────────────────────────────────────

def _dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def _centroid(units):
    if not units:
        return None, None
    return (sum(u.x for u in units) / len(units),
            sum(u.y for u in units) / len(units))


def _avgHealth(units):
    if not units:
        return 1.0
    return sum(u.hp / u.maxHp for u in units) / len(units)


def _terrainScore(terrain, x, y):
    if not terrain.isPassable(x, y):
        return -20
    if terrain.isOnRiver(x, y):
        return -10
    s = 0
    if terrain.isHighGround(x, y): s += 3
    if terrain.isForest(x, y):     s -= 1
    return s


def _routeSafe(terrain, x1, y1, x2, y2, samples=8):
    for i in range(samples + 1):
        t = i / samples
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t
        if not terrain.isPassable(px, py):
            return False
    return True


def _nearestBridge(terrain, x, y):
    if not terrain.bridges:
        return None
    return min(terrain.bridges, key=lambda b: _dist(x, y, b['x'], b['y']))


def _nearestChokepoint(chokepoints, x, y):
    """Return (cx, cy) of nearest chokepoint, or None."""
    if not chokepoints:
        return None
    return min(chokepoints, key=lambda c: _dist(x, y, c[0], c[1]))


def _bestHighGround(terrain, cx, cy, W, H, radius=180, step=40):
    best, pos = -999, (cx, cy)
    for dx in range(-radius, radius + 1, step):
        for dy in range(-radius, radius + 1, step):
            if math.hypot(dx, dy) > radius:
                continue
            x, y = max(0, min(W - 1, cx + dx)), max(0, min(H - 1, cy + dy))
            s = _terrainScore(terrain, x, y)
            if s > best:
                best, pos = s, (x, y)
    return pos


def _bestCorridorY(terrain, x1, x2, lo, hi, steps=8):
    best, best_y = -999, (lo + hi) // 2
    xs = [x1 + (x2 - x1) * t for t in (0.3, 0.5, 0.7)]
    for i in range(steps):
        y = int(lo + (hi - lo) * (i + 0.5) / steps)
        s = sum(_terrainScore(terrain, x, y) for x in xs)
        if s > best:
            best, best_y = s, y
    return best_y


def _moveToSafe(u, terrain, tx, ty):
    if _routeSafe(terrain, u.x, u.y, tx, ty):
        u.targetX, u.targetY = tx, ty
        return
    # Only use bridge routing when the path actually crosses a river
    riverBlocks = any(terrain.isOnRiver(u.x + (tx - u.x) * i / 8,
                                        u.y + (ty - u.y) * i / 8) for i in range(9))
    b = _nearestBridge(terrain, u.x, u.y) if riverBlocks else None
    if b:
        u.targetX, u.targetY = b['x'], b['y']
    else:
        # Lake/rock obstacle (or no bridge) — set target directly; unit A* handles routing
        u.targetX, u.targetY = tx, ty


def _formationLine(units, cx, cy, terrain, spacing=46):
    """Spread units in a N-S line centred on (cx, cy)."""
    n = len(units)
    for i, u in enumerate(sorted(units, key=lambda u: u.y)):
        offset = (i - (n - 1) / 2) * spacing
        _moveToSafe(u, terrain, cx, cy + offset)


def _pairAttack(inf, players, terrain):
    """Each infantry targets its Y-paired player unit."""
    if not players or not inf:
        return
    inf_s = sorted(inf,     key=lambda u: u.y)
    pl_s  = sorted(players, key=lambda p: p.y)
    for i, u in enumerate(inf_s):
        t = pl_s[min(int(i / len(inf_s) * len(pl_s)), len(pl_s) - 1)]
        u.attackTarget = t
        _moveToSafe(u, terrain, t.x, t.y)


def _findGap(players, H):
    if len(players) < 3:
        return None
    ys   = sorted(u.y for u in players)
    gaps = [(ys[i + 1] - ys[i], (ys[i] + ys[i + 1]) / 2) for i in range(len(ys) - 1)]
    best = max(gaps, key=lambda g: g[0])
    return best[1] if best[0] > 130 else None


def _weightedChoice(weights_dict, rng):
    items = list(weights_dict.items())
    total = sum(w for _, w in items)
    r     = rng.uniform(0, total)
    for k, w in items:
        r -= w
        if r <= 0:
            return k
    return items[-1][0]


# ── Target scoring & focus fire ──────────────────────────────────────────────

def _scoreTarget(attacker, target):
    """Score a player unit as a target — higher = more attractive to attack."""
    score = 0.0
    d = _dist(attacker.x, attacker.y, target.x, target.y)

    # In range: big bonus
    if d <= attacker.attackRange:
        score += 30
    else:
        score -= d * 0.05

    # Low HP: finish kills fast to trigger morale cascades
    hp_ratio = target.hp / target.maxHp
    score += (1.0 - hp_ratio) * 40

    # Low morale: one more hit triggers a rout
    score += (1.0 - target.morale / 100) * 25

    # Unit type priority: artillery > heavy_infantry > infantry > cavalry
    if target.unitType == 'artillery':        score += 20
    elif target.unitType == 'heavy_infantry': score += 10
    elif target.unitType == 'infantry':       score += 5

    # Cavalry should avoid heavy infantry shield walls — they're built for this
    if target.unitType == 'heavy_infantry' and attacker.unitType == 'cavalry':
        score -= 30

    # Square formation: avoid with cavalry, prefer with artillery
    if target.inSquare:
        if attacker.unitType == 'cavalry':    score -= 40
        elif attacker.unitType == 'artillery': score += 25

    # Out of supply: easy target with poor morale recovery
    score += (1.0 - target.supplyStrength) * 15

    # Already routing: low priority (already neutralised)
    if target.routing:
        score -= 30

    return score


def _bestTarget(attacker, players, maxRange=None):
    """Pick the highest-scored target, optionally filtered by range."""
    if not players:
        return None
    if maxRange:
        candidates = [p for p in players
                      if _dist(attacker.x, attacker.y, p.x, p.y) <= maxRange]
        if not candidates:
            candidates = players
    else:
        candidates = players
    return max(candidates, key=lambda p: _scoreTarget(attacker, p))


def _flankPos(target, offset=60):
    """Position behind a target for the 1.8x flank damage bonus (>135 deg)."""
    behind_rad = math.radians(target.angle + 180)
    return (target.x + math.cos(behind_rad) * offset,
            target.y + math.sin(behind_rad) * offset)


# ── Threat assessment ────────────────────────────────────────────────────────

def _threatAt(x, y, hostiles):
    """Danger score at (x,y) from hostile fire. Higher = more dangerous.
    Deployed artillery counts 3x because of high damage + splash."""
    threat = 0.0
    for h in hostiles:
        rng = h.attackRange + 20
        d   = _dist(x, y, h.x, h.y)
        if d >= rng:
            continue
        base = h.damage
        if h.unitType == 'artillery' and getattr(h, 'deployed', False):
            base *= 3.0
        elif h.unitType in ('infantry', 'heavy_infantry'):
            base *= 0.7
        threat += base * (1.0 - d / rng)
    return threat


def _approachThreat(ax, ay, tx, ty, hostiles, samples=3):
    """Average threat along the straight-line path from (ax,ay) to (tx,ty)."""
    total = 0.0
    for i in range(1, samples + 1):
        t = i / (samples + 1)
        total += _threatAt(ax + (tx - ax) * t, ay + (ty - ay) * t, hostiles)
    return total / samples


# ── Terrain analysis (run once at game start) ────────────────────────────────

def analyzeTerrain(terrain, W, H):
    """Scan the map and return a dict of terrain traits for AI decision-making.

    Traits:
      openness       0.0–1.0  fraction of passable non-forest non-highland cells
      forest_cover   0.0–1.0  fraction of forested cells
      hill_cover     0.0–1.0  fraction of highland cells
      water_cover    0.0–1.0  fraction of lake cells
      rock_cover     0.0–1.0  fraction of rock cells
      has_river      bool     river present
      chokepoints    list of (x, y) — narrow passages between obstacles
      n_chokepoints  int      number of detected chokepoints
    """
    from src.entities.terrain_helpers import CELL
    gw = W // CELL + 2
    gh = H // CELL + 2
    total = gw * gh

    nForest  = sum(1 for k, v in terrain._forest.items() if v)
    nHill    = sum(1 for k, v in terrain._height.items() if v >= terrain.HIGHLAND_THRESH)
    nLake    = len(terrain._lake)
    nRock    = len(terrain._rock)
    nBlocked = nLake + nRock
    nOpen    = total - nBlocked - nForest - nHill

    # ── Chokepoint detection ─────────────────────────────────────────────
    # Scan vertical slices across the map; a slice with few passable
    # cells relative to the map height is a chokepoint.
    chokepoints = []
    sliceThresh = gh * 0.45   # fewer than 45% of cells passable = choke
    step        = max(1, gw // 40)
    for gx in range(gw // 5, gw * 4 // 5, step):
        passable = 0
        passY    = []
        for gy in range(gh):
            cell = (gx, gy)
            if cell not in terrain._lake and cell not in terrain._rock:
                px, py = gx * CELL, gy * CELL
                if not terrain._isNearRiver(px, py, 16):
                    passable += 1
                    passY.append(gy)
        if passable < sliceThresh and passY:
            midY = passY[len(passY) // 2]
            cx, cy = gx * CELL, midY * CELL
            # Don't cluster chokepoints too close together
            if not any(math.hypot(cx - ex, cy - ey) < 200 for ex, ey in chokepoints):
                chokepoints.append((cx, cy))

    # Classify chokepoints by side relative to the AI (enemy spawns right).
    # own  : on AI's half  (defensive value — must hold)
    # mid  : contested centre band (offensive value — race to seize)
    # foe  : on player's half (deny value — disrupts player projection)
    own_side, mid, foe_side = [], [], []
    for cx, cy in chokepoints:
        if cx > W * 0.60:   own_side.append((cx, cy))
        elif cx < W * 0.40: foe_side.append((cx, cy))
        else:               mid.append((cx, cy))

    return {
        'openness':         max(0.0, nOpen / total),
        'forest_cover':     nForest / total,
        'hill_cover':       nHill / total,
        'water_cover':      nLake / total,
        'rock_cover':       nRock / total,
        'has_river':        bool(terrain.rivers),
        'chokepoints':      chokepoints,
        'n_chokepoints':    len(chokepoints),
        'chokes_own':       own_side,
        'chokes_mid':       mid,
        'chokes_foe':       foe_side,
    }
