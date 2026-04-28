# Module: ai_roles
# BattleRolesMixin — always-on battlefield roles that run every tick regardless of tactic
# (HQ guards, artillery positioning, reinforcement, emergency fallback,
#  wounded pullback, square counter, artillery self-preservation)

import math

from src.game.ai_log import aiLog
from src.game.ai_helpers import (
    _dist, _centroid, _bestHighGround, _moveToSafe, _routeSafe,
    _scoreTarget, _bestTarget, _threatAt,
)


class BattleRolesMixin:

    def _doGuardHq(self, guards, players, enemyHq, terrain, W, H):
        if not enemyHq or not guards:
            return
        line_x = enemyHq.x - 155
        n      = len(guards)
        for i, u in enumerate(sorted(guards, key=lambda u: u.y)):
            ty  = H * (i + 1) / (n + 1)
            pos = _bestHighGround(terrain, line_x, ty, W, H, radius=90)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 200:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])

    def _doArtillery(self, artillery, bodyguards, front_units, players, terrain, W, H):
        if not artillery or not players:
            return
        enemyHq    = next((h for h in self.game.headquarters if h.team == 'enemy'), None)
        _prevRetr  = getattr(self, '_artRetreatSet', set())
        curRetr    = set()
        for u in artillery:
            nearest_p = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if _dist(u.x, u.y, nearest_p.x, nearest_p.y) < 140:
                if u.deployed:
                    u.deployed      = False
                    u.undeploying   = True
                    u.undeployTimer = 90
                u.attackTarget = None
                rx = (enemyHq.x - 80) if enemyHq else u.x + 120
                _moveToSafe(u, terrain, rx, u.y)
                curRetr.add(id(u))
                continue

            target = _bestTarget(u, players, maxRange=u.attackRange + 30)
            if not target:
                target = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            dtarget = _dist(u.x, u.y, target.x, target.y)
            if dtarget > u.attackRange - 20:
                dx, dy = target.x - u.x, target.y - u.y
                L      = math.hypot(dx, dy)
                stop   = u.attackRange - 50
                if L > 0:
                    ix = target.x - dx / L * stop
                    iy = target.y - dy / L * stop
                else:
                    ix, iy = u.x, u.y
                pos = _bestHighGround(terrain, ix, iy, W, H, radius=90)
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])  # bridges route via nearest bridge
            else:
                u.targetX, u.targetY = u.x, u.y
                u.attackTarget = target
        newRetr = curRetr - _prevRetr
        if newRetr:
            aiLog(f"ARTY RETREAT: {len(newRetr)} cannon(s) fleeing nearby enemy")
        self._artRetreatSet = curRetr
        if bodyguards and artillery:
            ax, ay = _centroid(artillery)
            n      = len(bodyguards)
            for i, u in enumerate(bodyguards):
                angle = math.pi * i / max(n - 1, 1) + math.pi / 2
                gx    = ax + math.cos(angle) * 50
                gy    = ay + math.sin(angle) * 50
                near  = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _dist(u.x, u.y, near.x, near.y) < 160:
                    u.attackTarget = near
                else:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, gx, gy)

    def _doChokepointHold(self, available_inf, available_art, players, terrain, W, H):
        """Actively occupy own-half and contested chokepoints.

        Sends 2 infantry per priority chokepoint (own-side first, then contested
        middle) and snaps 1 artillery to bombard through it. Returns the units
        that were committed so the caller can remove them from the mobile pool.

        Why: chokepoints are the highest-value real estate on the map — narrow
        passages where a small force projects disproportionate firepower. The
        AI used to only use them passively as anchor points for SIEGELINE; now
        it claims them whether or not the active tactic mentions them.
        """
        traits = getattr(self, '_terrainTraits', {})
        priority = list(traits.get('chokes_own', [])) + list(traits.get('chokes_mid', []))
        if not priority or not available_inf:
            return [], []

        committed_inf, committed_art = [], []
        used_inf_ids = set()

        for cx, cy in priority[:2]:   # cap at 2 chokepoints to avoid over-commitment
            # Skip if the player already holds it — sending 2 lone musketeers
            # into a held funnel is exactly the trap we want to avoid.
            player_held = sum(1 for u in self.game.units
                              if u.team == 'player' and _dist(u.x, u.y, cx, cy) < 100)
            if player_held >= 2:
                continue
            # Skip if we already hold it (≥2 friendly enemies within 90px)
            held = sum(1 for u in self.game.units
                       if u.team == 'enemy' and _dist(u.x, u.y, cx, cy) < 90)
            need = max(0, 2 - held)
            if need == 0:
                continue

            # Pull the closest free infantry to this chokepoint
            free = [u for u in available_inf if id(u) not in used_inf_ids]
            free.sort(key=lambda u: _dist(u.x, u.y, cx, cy))
            for u in free[:need]:
                used_inf_ids.add(id(u))
                committed_inf.append(u)
                u.attackTarget = None
                # Spread the two defenders slightly so they don't stack
                offset_y = 30 if len(committed_inf) % 2 else -30
                _moveToSafe(u, terrain, cx, max(60, min(H - 60, cy + offset_y)))

            # If we have artillery free and none nearby, send the closest one
            if available_art and not any(
                u.unitType == 'artillery' and _dist(u.x, u.y, cx, cy) < 220
                for u in self.game.units if u.team == 'enemy'
            ):
                a = min(available_art, key=lambda u: _dist(u.x, u.y, cx, cy))
                if a not in committed_art:
                    committed_art.append(a)
                    a.attackTarget = None
                    # Stand 180px back from the choke on the AI side so cannons
                    # can shell anything funnelled through it.
                    art_x = max(80, min(W - 80, cx + 180))
                    _moveToSafe(a, terrain, art_x, cy)

        return committed_inf, committed_art

    def _doBridgeClaim(self, available_inf, available_art, players, terrain, W, H):
        """On river maps, race to occupy bridges before the player does.

        Bridges are the only fast crossings — owning them lets us project across
        the river while the player has to wade. Mirrors _doChokepointHold:
        sends 2 infantry per bridge (own-half + contested), bails if the
        player already holds it.

        Returns committed (infantry, artillery) for caller pool removal.
        """
        bridges = getattr(terrain, 'bridges', None)
        if not bridges or not available_inf:
            return [], []

        # Only race for bridges on our half or contested middle.
        # AI spawns right (high x), so own = x > 0.5 W, contested = 0.35..0.65.
        priority = sorted(
            [b for b in bridges if b['x'] > W * 0.35],
            key=lambda b: -b['x']    # nearest to own HQ first
        )
        if not priority:
            return [], []

        committed_inf, committed_art = [], []
        used_inf_ids = set()

        for b in priority[:2]:
            bx, by = b['x'], b['y']
            player_held = sum(1 for u in players if _dist(u.x, u.y, bx, by) < 110)
            if player_held >= 2:
                continue
            held = sum(1 for u in self.game.units
                       if u.team == 'enemy' and _dist(u.x, u.y, bx, by) < 90)
            need = max(0, 2 - held)
            if need == 0:
                continue
            free = [u for u in available_inf if id(u) not in used_inf_ids]
            free.sort(key=lambda u: _dist(u.x, u.y, bx, by))
            for u in free[:need]:
                used_inf_ids.add(id(u))
                committed_inf.append(u)
                u.attackTarget = None
                # Stand on the AI side of the bridge (slightly east), spread y
                offset_y = 25 if len(committed_inf) % 2 else -25
                tx = max(80, min(W - 80, bx + 30))
                ty = max(60, min(H - 60, by + offset_y))
                _moveToSafe(u, terrain, tx, ty)

            # Optional artillery: drop one cannon back from the bridge to shell
            # the approach. Only if no friendly cannon is already in range.
            if available_art and not any(
                u.unitType == 'artillery' and _dist(u.x, u.y, bx, by) < 240
                for u in self.game.units if u.team == 'enemy'
            ):
                a = min(available_art, key=lambda u: _dist(u.x, u.y, bx, by))
                if a not in committed_art:
                    committed_art.append(a)
                    a.attackTarget = None
                    art_x = max(80, min(W - 80, bx + 200))
                    _moveToSafe(a, terrain, art_x, by)

        return committed_inf, committed_art

    def _doReinforce(self, units, op, players, terrain):
        for u in units:
            u.attackTarget = None
            _moveToSafe(u, terrain, op.x, op.y)
            if players:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                if _dist(u.x, u.y, near.x, near.y) < 170: u.attackTarget = near

    def _doFallback(self, units, players, enemyHq, terrain, W, H):
        if not enemyHq: return
        rally_x = enemyHq.x - 190
        for i, u in enumerate(sorted(units, key=lambda u: u.y)):
            pos = _bestHighGround(terrain, rally_x, H * (i + 1) / (len(units) + 1), W, H, radius=110)
            u.attackTarget = None
            _moveToSafe(u, terrain, pos[0], pos[1])
        if players:
            for u in units:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                if _dist(u.x, u.y, near.x, near.y) < 145: u.attackTarget = near

    # ── Wounded pullback ─────────────────────────────────────────────────────

    def _pullbackWounded(self):
        """Retreat wounded units behind healthy allies toward HQ."""
        enemies = [u for u in self.game.units if u.team == 'enemy' and not u.routing and u.hp > 0]
        if len(enemies) < 3:
            return
        enemyHq = next((h for h in self.game.headquarters if h.team == 'enemy'), None)
        if not enemyHq:
            return
        terrain  = self.game.terrain
        _prev    = getattr(self, '_pullbackSet', set())
        cur_set  = set()
        count    = 0
        for u in enemies:
            if u.hp / u.maxHp > 0.35 or u.unitType in ('artillery', 'heavy_infantry'):
                continue
            if not any(a.hp / a.maxHp > 0.5 for a in enemies if a is not u):
                continue
            cur_set.add(id(u))
            u.attackTarget = None
            dx = enemyHq.x - u.x
            dy = enemyHq.y - u.y
            d  = math.hypot(dx, dy)
            if d > 10:
                _moveToSafe(u, terrain, u.x + (dx / d) * 80, u.y + (dy / d) * 80)
                if id(u) not in _prev:
                    count += 1
        if count:
            aiLog(f"PULLBACK: {count} unit(s) below 35% HP retreating")
        self._pullbackSet = cur_set

    # ── Square counter ───────────────────────────────────────────────────────

    def _counterSquares(self, artillery, players):
        """Redirect artillery to focus player squares (1.5x damage bonus)."""
        squares = [p for p in players if p.inSquare and p.unitType in ('infantry', 'heavy_infantry')]
        if not squares or not artillery:
            return False
        redirected = False
        for u in artillery:
            if u.deployed or u.deployTimer > 60:
                best = min(squares, key=lambda s: _dist(u.x, u.y, s.x, s.y))
                if _dist(u.x, u.y, best.x, best.y) <= u.attackRange:
                    u.attackTarget = best
                    redirected = True
        if redirected:
            aiLog(f"COUNTER SQUARE: artillery redirected to {len(squares)} player square(s)")
        return True

    # ── Danger zone avoidance ────────────────────────────────────────────────

    def _avoidDangerZones(self):
        """Idle units dodge out of player artillery kill zones.
        After prolonged dodging (3s), fully disengage instead of wobbling."""
        players    = [u for u in self.game.units if u.team == 'player']
        player_art = [p for p in players
                      if p.unitType == 'artillery' and getattr(p, 'deployed', False)]
        if not player_art:
            return
        terrain    = self.game.terrain
        _prev      = getattr(self, '_dodgeSet', set())
        dodgeTicks = getattr(self, '_dodgeTicks', {})
        cur_set    = set()
        count      = 0
        enemyHq    = next((h for h in self.game.headquarters if h.team == 'enemy'), None)
        for u in self.game.units:
            if u.team != 'enemy' or u.routing or u.unitType in ('artillery', 'heavy_infantry'):
                continue
            if u.attackTarget and u.attackTarget.hp > 0:
                if _dist(u.x, u.y, u.attackTarget.x, u.attackTarget.y) < u.attackRange:
                    dodgeTicks.pop(id(u), None)
                    continue
            for art in player_art:
                d = _dist(u.x, u.y, art.x, art.y)
                if d < art.attackRange - 20 and d > 30:
                    uid = id(u)
                    cur_set.add(uid)
                    ticks = dodgeTicks.get(uid, 0) + 1
                    dodgeTicks[uid] = ticks
                    if ticks > 180 and enemyHq:
                        # Stuck dodging too long — fully disengage to safe distance
                        dx, dy = u.x - art.x, u.y - art.y
                        L = math.hypot(dx, dy)
                        if L > 0:
                            safe_d = art.attackRange + 40
                            _moveToSafe(u, terrain, art.x + dx/L*safe_d, art.y + dy/L*safe_d)
                        u.attackTarget = None
                    else:
                        dx, dy = u.x - art.x, u.y - art.y
                        L = math.hypot(dx, dy)
                        if L < 1: continue
                        perp_x, perp_y = -dy / L, dx / L
                        side = 1 if (u.targetY - u.y) * perp_y >= 0 else -1
                        nx = u.x + perp_x * side * 70 + (dx / L) * 30
                        ny = u.y + perp_y * side * 70 + (dy / L) * 30
                        _moveToSafe(u, terrain, nx, ny)
                    if uid not in _prev:
                        count += 1
                    break
        # Clear ticks for units no longer dodging
        for uid in list(dodgeTicks):
            if uid not in cur_set:
                del dodgeTicks[uid]
        self._dodgeSet   = cur_set
        self._dodgeTicks = dodgeTicks
        if count:
            aiLog(f"DODGE ARTY: {count} unit(s) evading artillery")

    # ── Wave coordination ────────────────────────────────────────────────────

    def _coordinateWaves(self):
        """Fast units wait for nearby allies before engaging — prevents trickling in."""
        for u in self.game.units:
            if u.team != 'enemy' or u.routing or u.unitType in ('artillery', 'heavy_infantry'):
                continue
            t = u.attackTarget
            if not t or t.hp <= 0: continue
            dt = _dist(u.x, u.y, t.x, t.y)
            if dt <= u.attackRange or dt > 400: continue
            allies_near = sum(1 for a in self.game.units
                              if a.team == 'enemy' and a is not u and not a.routing
                              and _dist(u.x, u.y, a.x, a.y) < 120)
            if allies_near < 2:
                # Alone — hold halfway until allies catch up
                u.targetX = (u.x + t.x) / 2
                u.targetY = (u.y + t.y) / 2

    # ── Heavy infantry role ──────────────────────────────────────────────────

    def _doHeavyInfantryRole(self, heavy_inf, players, enemyHq, terrain, tactic):
        """Lead bridge assaults, hold threatened OPs, or push defended positions."""
        if not heavy_inf or not players: return
        # Bridge assault: heavy infantry leads the crossing, absorbs bridge chokepoint fire
        if tactic in ('BRIDGE_CONTROL', 'COMBINED_ARMS'):
            bridges = getattr(self.game.terrain, 'bridges', [])
            if bridges:
                b = min(bridges, key=lambda b: sum(
                    1 for p in players if _dist(p.x, p.y, b['x'], b['y']) < 120))
                for u in heavy_inf:
                    _moveToSafe(u, terrain, b['x'], b['y'])
                    near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                    u.attackTarget = near if _dist(u.x, u.y, near.x, near.y) < 100 else None
                aiLog(f"HEAVY INF: bridge push at ({int(b['x'])},{int(b['y'])})")
                return
        # Rearguard on retreat: hold a line in front of HQ
        if tactic in ('DELAYING_ACTION', 'CONTACT_AND_FADE', 'MOBILE_SUPPLY_BUBBLE'):
            if not enemyHq: return
            for u in heavy_inf:
                _moveToSafe(u, terrain, enemyHq.x - 120, enemyHq.y)
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = near if _dist(u.x, u.y, near.x, near.y) < 110 else None
            return
        # Assault most densely defended player cluster
        assault = max(players, key=lambda p: sum(1 for q in players if _dist(p.x, p.y, q.x, q.y) < 110))
        for u in heavy_inf:
            u.attackTarget = assault; _moveToSafe(u, terrain, assault.x, assault.y)

    # ── Local fight assessment ───────────────────────────────────────────────

    def _assessLocalFights(self):
        """Units in a losing local fight disengage and retreat."""
        enemyHq  = next((h for h in self.game.headquarters if h.team == 'enemy'), None)
        if not enemyHq: return
        terrain, allUnits, retreated = self.game.terrain, self.game.units, 0
        for u in allUnits:
            if u.team != 'enemy' or u.routing or u.unitType in ('artillery', 'heavy_infantry'): continue
            if not u.attackTarget or u.attackTarget.hp <= 0: continue
            if _dist(u.x, u.y, u.attackTarget.x, u.attackTarget.y) > u.attackRange: continue
            local_allies  = sum(1 for a in allUnits if a.team == 'enemy' and not a.routing
                                and _dist(u.x, u.y, a.x, a.y) < 150)
            local_enemies = sum(1 for p in allUnits if p.team == 'player' and not p.routing
                                and _dist(u.x, u.y, p.x, p.y) < 150)
            if local_enemies > local_allies * 2:
                u.attackTarget = None
                dx, dy = enemyHq.x - u.x, enemyHq.y - u.y
                d = math.hypot(dx, dy)
                if d > 0: _moveToSafe(u, terrain, u.x + dx / d * 100, u.y + dy / d * 100)
                retreated += 1
        if retreated: aiLog(f"LOCAL RETREAT: {retreated} unit(s) disengaging from losing fight")
