# Module: unit
# Unit class — state, movement, combat logic for all unit types

import math
import random

from src.constants import UNIT_STATS
from src.entities.effect import Effect

# ── Spatial grid for O(n) separation instead of O(n²) ────────────────────────
_GRID_CELL    = 30   # slightly larger than max unit diameter (2 × 12)
_gridCache    = None
_gridFrameId  = 0
_lastFrameId  = -1

def _getSpatialGrid(allUnits):
    """Build or reuse a spatial hash grid for the current frame."""
    global _gridCache, _lastFrameId, _gridFrameId
    if _lastFrameId == _gridFrameId:
        return _gridCache
    grid = {}
    cell = _GRID_CELL
    for u in allUnits:
        key = (int(u.x) // cell, int(u.y) // cell)
        if key in grid:
            grid[key].append(u)
        else:
            grid[key] = [u]
    _gridCache   = grid
    _lastFrameId = _gridFrameId
    return grid

def _advanceGridFrame():
    """Call once per game frame to invalidate the spatial grid cache."""
    global _gridFrameId
    _gridFrameId += 1


class Unit:
    def __init__(self, x, y, team, unitType):
        self.x        = float(x)
        self.y        = float(y)
        self.team     = team
        self.unitType = unitType
        self.selected = False

        speed, attackRange, damage, hp, attackRate, radius = UNIT_STATS[unitType]
        self.speed       = speed
        self.attackRange = attackRange
        self.damage      = damage
        self.maxHp       = hp
        self.hp          = float(hp)
        self.attackRate  = attackRate
        self.radius      = radius

        self.targetX        = float(x)
        self.targetY        = float(y)
        self.attackCooldown = 0
        self.attackTarget   = None
        self.angle          = 0.0 if team == 'player' else 180.0
        self.turnRate       = 1.8

        self.morale  = 100.0
        self.routing = False

        self.inSquare    = False
        self.reformTimer = 0

        self.chargeFrames = 0
        self.shieldWall   = False   # heavy infantry: active when adjacent to friendly heavy unit

        self.deployed      = False
        self.deployTimer   = 0
        self.undeploying   = False
        self.undeployTimer = 0

        self.supplyStrength = 0.0   # 0.0 = no supply  ..  1.0 = full supply

        # Pathfinding waypoints
        self._waypoints    = []     # list of (x, y) to follow
        self._waypointTgtX = 0.0    # target that generated these waypoints
        self._waypointTgtY = 0.0
        self._pathCooldown = 0      # frames until next A* pathfind is allowed
        self._stuckFrames  = 0      # consecutive frames unable to move toward target

        # Patrol path (Ctrl+right-drag)
        self.patrolPath  = []   # list of (x, y) waypoints to patrol
        self._patrolIdx  = 0    # current target index in patrolPath
        self._patrolDir  = 1    # 1 = forward along path, -1 = backward

    # --- helpers ---
    def distanceTo(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def nearestEnemy(self, allUnits):
        enemies = [u for u in allUnits if u.team != self.team]
        return min(enemies, key=self.distanceTo) if enemies else None

    def _angleTo(self, tx, ty):
        return math.degrees(math.atan2(ty - self.y, tx - self.x))

    def _rotateTowards(self, desired):
        diff = (desired - self.angle + 180) % 360 - 180
        if abs(diff) <= self.turnRate:
            self.angle = desired
        else:
            self.angle += self.turnRate * (1 if diff > 0 else -1)

    def _facingCloseEnough(self, tx, ty, tolerance=25):
        desired = self._angleTo(tx, ty)
        diff    = abs((desired - self.angle + 180) % 360 - 180)
        return diff <= tolerance

    # --- combat ---
    def takeDamage(self, amount, sourceType=None, attacker=None):
        if self.inSquare:
            if sourceType == 'cavalry':
                amount *= 0.3
            elif sourceType == 'artillery':
                amount *= 1.5

        # Heavy infantry: steadfast 15% res; tanky vs infantry volleys, weak vs cavalry
        if self.unitType == 'heavy_infantry':
            type_mod = 0.65 if sourceType == 'infantry' else (1.35 if sourceType == 'cavalry' else 1.0)
            amount *= 0.85 * type_mod * (0.55 if self.shieldWall else 1.0)
        if attacker is not None:
            angleToAttacker = self._angleTo(attacker.x, attacker.y)
            diff = abs((angleToAttacker - self.angle + 180) % 360 - 180)
            if diff > 135:
                amount *= 1.8
                self.loseMorale(6)
            elif diff > 70:
                amount *= 1.35

        # Forest cover: defender in woods absorbs some damage
        if getattr(self, '_terrain', None) and self._terrain.isForest(self.x, self.y):
            amount *= 0.75

        self.hp -= amount
        self.loseMorale(amount * 0.3)

    def loseMorale(self, amount):
        self.morale = max(0, self.morale - amount * (0.5 if self.unitType == 'heavy_infantry' else 1.0))
        if self.morale <= 0 and not self.routing:
            self.routing  = True
            self.inSquare = False

    def _stopPosNear(self, target):
        dx   = self.x - target.x
        dy   = self.y - target.y
        dist = math.hypot(dx, dy)
        if dist == 0:
            return target.x, target.y
        stop = self.attackRange - 5
        return target.x + (dx / dist) * stop, target.y + (dy / dist) * stop

    def _fireVolley(self, focus, projectiles, effects, hBonus=1.0):
        from src.entities.projectile import Projectile
        from src import audio
        dmgPerBall = max(1, self.damage // 7) * hBonus
        for offset in [-18, -12, -6, 0, 6, 12, 18]:
            projectiles.append(Projectile(
                self.x, self.y, focus, dmgPerBall, 'musket',
                angleOffset=offset + random.uniform(-3, 3),
                sourceType='infantry', attacker=self
            ))
        rad = math.radians(self.angle)
        effects.append(Effect(self.x + math.cos(rad) * 18,
                              self.y + math.sin(rad) * 18, 'smoke'))
        audio.play_sfx('musket')

    # --- per-frame update ---
    def update(self, allUnits, projectiles, effects, terrain=None):
        self._terrain = terrain   # store for this frame's combat/movement use

        if self.attackTarget and self.attackTarget.hp <= 0:
            self.attackTarget = None

        moraleMax      = 60.0 + 40.0 * self.supplyStrength   # 60 at no supply, 100 at full
        moraleRecovery = 0.02 + 0.10 * self.supplyStrength   # slow far away, fast near OP
        self.morale    = min(moraleMax, self.morale + moraleRecovery)
        if self.routing and self.morale > 45:
            self.routing = False

        # Shield wall: active when a friendly heavy infantry is within 30px
        if self.unitType == 'heavy_infantry':
            self.shieldWall = any(u is not self and u.team == self.team
                                  and u.unitType == 'heavy_infantry'
                                  and math.hypot(self.x - u.x, self.y - u.y) < 30
                                  for u in allUnits)

        # Out-of-combat healing: slow HP regen when no enemy is nearby
        if self.hp < self.maxHp:
            enemy = self.nearestEnemy(allUnits)
            safe  = not enemy or self.distanceTo(enemy) > 280
            if safe and self.supplyStrength > 0:
                healRate = 0.004 + 0.016 * self.supplyStrength  # 0.24..1.2 HP/s at 60fps
                self.hp  = min(self.maxHp, self.hp + healRate)

        if self.routing:
            enemy = self.nearestEnemy(allUnits)
            if enemy:
                dx, dy = self.x - enemy.x, self.y - enemy.y
                result = self._steer(dx, dy, self.speed * 1.5)
                if result:
                    self.x, self.y = result
            self._separate(allUnits)
            self._clampToBounds()
            return

        if self.reformTimer > 0:
            self.reformTimer -= 1; return

        if self.inSquare:
            focus = self.attackTarget or self.nearestEnemy(allUnits)
            if focus and self.distanceTo(focus) <= self.attackRange:
                self._rotateTowards(self._angleTo(focus.x, focus.y))
                self.attackCooldown -= 1
                if self.attackCooldown <= 0 and self._facingCloseEnough(focus.x, focus.y):
                    self._fireVolley(focus, projectiles, effects)
                    self.attackCooldown = self.attackRate
            return

        if self.unitType == 'artillery':
            if self.undeploying:
                self.undeployTimer -= 1
                if self.undeployTimer <= 0:
                    self.undeploying = False
                    self.deployTimer = 0
            elif not self.deployed:
                moving = math.hypot(self.targetX - self.x, self.targetY - self.y) > self.speed + 1
                if moving:
                    self.deployTimer = 0
                else:
                    self.deployTimer = min(90, self.deployTimer + 1)
                    self.deployed    = self.deployTimer >= 90

        focus = self.attackTarget or self.nearestEnemy(allUnits)
        if focus:
            dist = self.distanceTo(focus)
            if dist <= self.attackRange:
                # AI cavalry: hold attack until charge bonus (2x damage) is ready
                if (self.unitType == 'cavalry' and self.team == 'enemy'
                        and self.chargeFrames < 45 and dist > self.radius * 3):
                    self.chargeFrames = min(120, self.chargeFrames + 1)
                else:
                    self._rotateTowards(self._angleTo(focus.x, focus.y))
                    self.attackCooldown -= 1
                    if self.attackCooldown <= 0:
                        self._executeAttack(focus, projectiles, effects)
            else:
                if self.attackTarget and self.team != 'enemy':
                    self.targetX, self.targetY = self._stopPosNear(focus)
                if self.unitType == 'cavalry':
                    self.chargeFrames = min(120, self.chargeFrames + 1)
        else:
            self.chargeFrames = max(0, self.chargeFrames - 1)

        # Rotate toward current movement goal (waypoint or final target)
        if self._waypoints:
            faceX, faceY = self._waypoints[0]
        else:
            faceX, faceY = self.targetX, self.targetY
        if math.hypot(faceX - self.x, faceY - self.y) > self.speed + 1:
            self._rotateTowards(self._angleTo(faceX, faceY))
        self._move()
        self._separate(allUnits)
        self._clampToBounds()

    def _executeAttack(self, focus, projectiles, effects):
        hBonus  = self._terrain.heightBonus(self, focus)    if self._terrain else 1.0
        dMult   = self._terrain.damageMultiplier(self.x, self.y) if self._terrain else 1.0
        hBonus *= dMult

        if self.unitType in ('cavalry', 'heavy_infantry'):
            from src import audio
            if self.unitType == 'cavalry':
                bonus = (2.0 if self.chargeFrames > 45 else 1.0); self.chargeFrames = 0
            else:
                bonus = 1.25 if self.shieldWall else 1.0
            focus.takeDamage(self.damage * bonus * hBonus, self.unitType, attacker=self)
            effects.append(Effect(focus.x, focus.y, 'slash'))
            self.attackCooldown = self.attackRate
            if self.unitType == 'cavalry':
                audio.play_sfx('cavalry')
        elif self.unitType == 'infantry':
            if self._facingCloseEnough(focus.x, focus.y):
                self._fireVolley(focus, projectiles, effects, hBonus)
                self.attackCooldown = self.attackRate
        elif self.unitType == 'artillery':
            if self.deployed and self._facingCloseEnough(focus.x, focus.y, tolerance=15):
                from src.entities.projectile import Projectile
                from src import audio
                projectiles.append(Projectile(
                    self.x, self.y, focus, self.damage * hBonus, 'cannonball',
                    sourceType='artillery', attacker=self
                ))
                self.attackCooldown = self.attackRate
                audio.play_sfx('cannon')

    def _steer(self, dx, dy, spd):
        """Try to move in direction (dx,dy). If blocked by lake/rock, steer
        around by testing alternative angles AND a longer probe distance.
        Each candidate is line-sampled (midpoint + endpoint) so we don't clip
        into an obstacle edge between grid samples.
        Rivers are intentionally NOT blocked here — they slow via speedMultiplier,
        and approach paths to bridges need to be allowed."""
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return None
        baseAng = math.atan2(dy, dx)
        t = self._terrain

        _BORDER = 20   # px inside map edge that units may not cross

        def clear(nx, ny):
            if not t:
                return True
            # Hard map-border check — prevents units from leaving the play area
            if (nx < _BORDER or ny < _BORDER or
                    nx > t.width - _BORDER or ny > t.height - _BORDER):
                return False
            # sample midpoint + endpoint — catches obstacle edges between cells
            mx, my = (self.x + nx) * 0.5, (self.y + ny) * 0.5
            if t.isLake(mx, my) or t.isRock(mx, my):
                return False
            if t.isLake(nx, ny) or t.isRock(nx, ny):
                return False
            return True

        # Angle offsets: straight ahead first, then ±20°, 40°, 65°, 90°, 125°, 150°
        offsets = (0, 0.35, -0.35, 0.7, -0.7, 1.15, -1.15,
                   1.57, -1.57, 2.2, -2.2, 2.6, -2.6)
        # Probe distances: normal step first; if everything fails at normal step,
        # try a longer reach (2× spd) which can squeeze past narrow rock tips.
        for probe in (spd, spd * 2.2):
            for offset in offsets:
                ang = baseAng + offset
                nx  = self.x + math.cos(ang) * probe
                ny  = self.y + math.sin(ang) * probe
                if clear(nx, ny):
                    # always move only by `spd` along the accepted direction —
                    # the longer probe is only used to find a clear heading
                    return (self.x + math.cos(ang) * spd,
                            self.y + math.sin(ang) * spd)
        return None

    def _needsNewPath(self):
        """Check if we need to recalculate the waypoint path."""
        # No waypoints yet
        if not self._waypoints:
            return True
        # Target changed significantly
        if (math.hypot(self.targetX - self._waypointTgtX,
                       self.targetY - self._waypointTgtY) > 60):
            return True
        return False

    def _pathBlocked(self):
        """True if a lake/rock lies on the direct path OR within one grid cell ahead.
        The 'one cell ahead' check catches units pressed sideways against an obstacle
        edge so A* fires even when the long-range path samples miss the obstacle."""
        if not self._terrain:
            return False
        t  = self._terrain
        dx = self.targetX - self.x
        dy = self.targetY - self.y
        # Check 4 points along the full path (20–80%)
        for i in range(1, 5):
            f = i / 5
            if t.isLake(self.x + dx*f, self.y + dy*f) or t.isRock(self.x + dx*f, self.y + dy*f):
                return True
        # Check one terrain cell (~22 px) immediately ahead in target direction
        dist = math.hypot(dx, dy)
        if dist > 1:
            nx = self.x + (dx / dist) * 22
            ny = self.y + (dy / dist) * 22
            if t.isLake(nx, ny) or t.isRock(nx, ny):
                return True
        return False

    def _advancePatrol(self):
        """Move to the next patrol waypoint, reversing direction at the ends."""
        if not self.patrolPath:
            return
        next_idx = self._patrolIdx + self._patrolDir
        if next_idx >= len(self.patrolPath):
            self._patrolDir = -1
            next_idx = self._patrolIdx - 1
        elif next_idx < 0:
            self._patrolDir = 1
            next_idx = 1
        if 0 <= next_idx < len(self.patrolPath):
            self._patrolIdx = next_idx
            self.targetX, self.targetY = self.patrolPath[next_idx]
            self._waypoints = []

    def _move(self):
        if self.deployed or self.undeploying: return
        dx, dy = self.targetX - self.x, self.targetY - self.y
        dist   = math.hypot(dx, dy)
        spd    = self.speed * (self._terrain.speedMultiplier(self.x, self.y) if self._terrain else 1.0)
        if dist <= spd:
            if self.patrolPath:
                self._advancePatrol()
            return

        # Drop stale waypoints when target moved significantly
        if self._waypoints and math.hypot(
                self.targetX - self._waypointTgtX,
                self.targetY - self._waypointTgtY) > 60:
            self._waypoints = []

        # Follow existing waypoints
        if self._waypoints:
            wx, wy = self._waypoints[0]
            wdx, wdy = wx - self.x, wy - self.y
            if math.hypot(wdx, wdy) < spd + 5:
                self._waypoints.pop(0)
                if not self._waypoints:
                    self._stuckFrames = 0
                    return
                wx, wy = self._waypoints[0]
                wdx, wdy = wx - self.x, wy - self.y
            result = self._steer(wdx, wdy, spd)
            if result:
                self.x, self.y = result
                self._stuckFrames = 0
            else:
                # Steer failed while following waypoint — discard waypoints and
                # force an immediate A* re-route so the unit doesn't freeze
                self._waypoints    = []
                self._pathCooldown = 0
                self._stuckFrames += 1
            return

        # Try direct steering first
        needsAstar = self._pathBlocked()
        if not needsAstar:
            result = self._steer(dx, dy, spd)
            if result:
                self.x, self.y = result
                self._stuckFrames = 0
                return
            needsAstar = True   # _steer failed against an undetected edge

        # Obstacle in the way — use A* (throttled, tightens fast when stuck)
        self._stuckFrames += 1
        cooldown_max = 8 if self._stuckFrames > 20 else 30
        self._pathCooldown = max(0, self._pathCooldown - 1)
        if self._pathCooldown <= 0 and self._terrain:
            path = self._terrain.findPath(self.x, self.y, self.targetX, self.targetY)
            if path and len(path) >= 2:
                self._waypoints    = path[1:] if len(path) > 1 else path
                self._waypointTgtX = self.targetX
                self._waypointTgtY = self.targetY
                self._stuckFrames  = 0
                self._pathCooldown = cooldown_max
            else:
                # No path found — retry soon (not 90 frames!) and meanwhile try
                # a sideways nudge so the unit doesn't freeze in place.
                self._pathCooldown = 15
                result = self._steer(dx, dy, spd)
                if result:
                    self.x, self.y = result
                elif self._stuckFrames > 60:
                    # Deep stuck: nudge perpendicular toward any open cell.
                    for perp in (math.pi / 2, -math.pi / 2, math.pi):
                        baseAng = math.atan2(dy, dx) + perp
                        nx = self.x + math.cos(baseAng) * spd
                        ny = self.y + math.sin(baseAng) * spd
                        if (not self._terrain.isLake(nx, ny)
                                and not self._terrain.isRock(nx, ny)):
                            self.x, self.y = nx, ny
                            break

    def _clampToBounds(self):
        """Hard safety net: ensure the unit can never leave the map area."""
        MARGIN = 20
        if self._terrain:
            w, h = self._terrain.width, self._terrain.height
        else:
            from src.constants import MAP_WIDTH, MAP_HEIGHT
            w, h = MAP_WIDTH, MAP_HEIGHT
        self.x = max(float(MARGIN), min(float(w - MARGIN), self.x))
        self.y = max(float(MARGIN), min(float(h - MARGIN), self.y))

    def _separate(self, allUnits):
        grid = _getSpatialGrid(allUnits)
        gx, gy = int(self.x) // _GRID_CELL, int(self.y) // _GRID_CELL
        for nx in range(gx - 1, gx + 2):
            for ny in range(gy - 1, gy + 2):
                for other in grid.get((nx, ny), ()):
                    if other is self: continue
                    minDist = self.radius + other.radius
                    dx, dy  = self.x - other.x, self.y - other.y
                    dist    = math.hypot(dx, dy)
                    if 0 < dist < minDist:
                        push = (minDist - dist) / 2
                        px   = self.x + (dx / dist) * push
                        py   = self.y + (dy / dist) * push
                        # Don't push into hard obstacles (lake/rock); rivers are OK
                        if self._terrain and (self._terrain.isLake(px, py)
                                              or self._terrain.isRock(px, py)):
                            continue
                        self.x = px
                        self.y = py
