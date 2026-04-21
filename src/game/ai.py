# Module: ai
# EnemyAI — personality system, tactic evaluation and main execution loop

import math
import random
from src.game.ai_log import aiLog

from src.game.ai_helpers import (
    _dist, _centroid, _avgHealth, _scoreTarget, _bestTarget, _flankPos,
    _approachThreat, _weightedChoice, _moveToSafe, _routeSafe,
    analyzeTerrain,
    TICK_INTERVAL, HQ_GUARD_COUNT, ART_GUARD_COUNT, SURVIVAL_TACTICS,
)
from src.game.ai_data            import (
    PERSONALITIES, PERSONALITY_TRAITS, COUNTER_MAP, TACTIC_AVOIDANCE,
    BIOME_MODIFIERS, TERRAIN_TRAIT_BONUSES, DIFFICULTY_SETTINGS,
)
from src.game.ai_detector        import PlayerDetector
from src.game.ai_roles           import BattleRolesMixin
from src.game.ai_tactics_offense import OffensiveTacticsMixin
from src.game.ai_tactics_defense import DefensiveTacticsMixin
from src.game.ai_tactics_special import SpecialTacticsMixin


class EnemyAI(BattleRolesMixin,
              OffensiveTacticsMixin,
              DefensiveTacticsMixin,
              SpecialTacticsMixin):

    def __init__(self, game, difficulty='NORMAAL'):
        self.game          = game
        self._rng          = random.Random()
        self._personality  = self._rng.choice(list(PERSONALITIES.keys()))
        self._traits       = PERSONALITY_TRAITS[self._personality]
        self._weights      = dict(PERSONALITIES[self._personality])

        # ── Difficulty ───────────────────────────────────────────────────────
        diff = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS['NORMAAL'])
        self._tickInterval  = diff['tick_interval']
        self._mistakeRate   = diff['mistake_rate']
        self._evalInterval  = diff['eval_interval']
        # Clamp fallback ratio with difficulty bonus
        base_fallback = self._traits['fallback_ratio']
        self._traits = dict(self._traits)
        self._traits['fallback_ratio'] = min(0.95, max(0.30,
            base_fallback + diff['fallback_bonus']))
        self._difficulty    = difficulty
        self._detector     = PlayerDetector()

        # ── Terrain awareness ────────────────────────────────────────────────
        self._terrainTraits = analyzeTerrain(game.terrain, game.mapWidth, game.mapHeight)
        self._applyTerrainWeights()
        self._detector.setChokepoints(self._terrainTraits.get('chokepoints', []))

        self._tactic       = self._pickTactic()
        self._timer        = self._rng.randint(0, self._tickInterval)
        self._evalTimer    = 0
        self._tacticTicks  = 0
        self._casualties   = 0
        self._lastCount    = sum(1 for u in game.units if u.team == 'enemy')
        self._commitSide   = self._rng.choice([-1, 1])
        self._feintDone    = False
        self._prevEnemyX   = None
        self._stuckTicks   = 0
        self._survivalMode = False
        self._fadePhase    = False

        # Dynamic danger map: each casualty leaves a short-lived "hot spot".
        # Entries are [x, y, ttl_frames]. TTL ~10s at 60 fps. Capped to keep
        # the per-frame _dangerAt scan cheap.
        self._dangerEvents = []
        self._DANGER_TTL   = 600
        self._DANGER_CAP   = 60

        traits = self._terrainTraits
        biome  = game.terrain.biome
        chokes = traits['n_chokepoints']
        aiLog(f"Personality: {self._personality}  |  Biome: {biome}  |  "
              f"Chokepoints: {chokes} (own:{len(traits.get('chokes_own',[]))} "
              f"mid:{len(traits.get('chokes_mid',[]))} foe:{len(traits.get('chokes_foe',[]))})  |  "
              f"Difficulty: {difficulty}")
        aiLog(f"Terrain: open={traits['openness']:.0%} forest={traits['forest_cover']:.0%} "
              f"hills={traits['hill_cover']:.0%} water={traits['water_cover']:.0%} "
              f"rocks={traits['rock_cover']:.0%}")
        aiLog(f"Opening tactic: {self._tactic}")

    # ── Dynamic danger map ───────────────────────────────────────────────────

    def recordCasualty(self, x, y):
        """Called from Game when one of OUR units dies. Marks the spot as
        dangerous for ~10 seconds; subsequent unit movement steers away."""
        self._dangerEvents.append([float(x), float(y), self._DANGER_TTL])
        if len(self._dangerEvents) > self._DANGER_CAP:
            # Drop the oldest (front of list) when over budget
            del self._dangerEvents[0:len(self._dangerEvents) - self._DANGER_CAP]

    def _decayDangerMap(self):
        if not self._dangerEvents:
            return
        for ev in self._dangerEvents:
            ev[2] -= 1
        self._dangerEvents = [e for e in self._dangerEvents if e[2] > 0]

    def dangerAt(self, x, y, radius=140):
        """Sum of danger contributions from recent casualties near (x,y).
        Falls off linearly with distance and remaining TTL.
        Public so helpers/tactics can consult it."""
        if not self._dangerEvents:
            return 0.0
        total = 0.0
        r2    = radius * radius
        for ex, ey, ttl in self._dangerEvents:
            dx, dy = x - ex, y - ey
            d2 = dx * dx + dy * dy
            if d2 < r2:
                total += (1.0 - d2 / r2) * (ttl / self._DANGER_TTL)
        return total

    def _avoidDangerHotspots(self):
        """Idle / out-of-combat units sidestep clusters of recent casualties.
        Distinct from _avoidDangerZones (which only reacts to deployed enemy
        artillery): this learns from where we actually got killed, even if the
        killer is invisible (musket line behind a forest, hidden artillery)."""
        if not self._dangerEvents:
            return
        for u in self.game.units:
            if u.team != 'enemy' or u.routing:
                continue
            if u.unitType == 'artillery':
                continue
            # Skip if actively engaging within range
            if u.attackTarget and u.attackTarget.hp > 0 \
                    and _dist(u.x, u.y, u.attackTarget.x, u.attackTarget.y) < u.attackRange:
                continue
            danger = self.dangerAt(u.x, u.y)
            if danger < 1.2:   # below threshold = ignore
                continue
            # Vector away from weighted danger centroid
            wx = wy = wt = 0.0
            for ex, ey, ttl in self._dangerEvents:
                d = math.hypot(u.x - ex, u.y - ey)
                if d < 140:
                    w = (1.0 - d / 140) * (ttl / self._DANGER_TTL)
                    wx += ex * w; wy += ey * w; wt += w
            if wt <= 0: continue
            cx, cy = wx / wt, wy / wt
            dx, dy = u.x - cx, u.y - cy
            L = math.hypot(dx, dy) or 1.0
            nx = u.x + (dx / L) * 90
            ny = u.y + (dy / L) * 90
            _moveToSafe(u, self.game.terrain, nx, ny)

    def _applyTerrainWeights(self):
        """Modify base tactic weights based on biome and terrain analysis."""
        biome = self.game.terrain.biome

        # 1) Biome-specific modifiers
        for tactic, mod in BIOME_MODIFIERS.get(biome, {}).items():
            if tactic in self._weights:
                self._weights[tactic] = max(1, self._weights[tactic] + mod)

        # 2) Dynamic trait-based bonuses
        for condition, bonuses in TERRAIN_TRAIT_BONUSES:
            if condition(self._terrainTraits):
                for tactic, mod in bonuses.items():
                    if tactic in self._weights:
                        self._weights[tactic] = max(1, self._weights[tactic] + mod)

    def _pickTactic(self, exclude=None):
        w = {k: v for k, v in self._weights.items() if k != exclude}
        for behaviour in self._detector.active():
            # Apply counter bonuses
            for tactic, bonus in COUNTER_MAP.get(behaviour, []):
                if tactic in w:
                    w[tactic] = w[tactic] + bonus
            # Suppress tactics that would walk into the detected trap
            for tactic in TACTIC_AVOIDANCE.get(behaviour, []):
                if tactic in w:
                    w[tactic] = 1
        return _weightedChoice(w, self._rng)

    def _pickCounterTactic(self, exclude=None):
        counter_w = {}
        for behaviour in self._detector.active():
            for tactic, bonus in COUNTER_MAP.get(behaviour, []):
                if tactic != exclude and tactic in self._weights:
                    counter_w[tactic] = counter_w.get(tactic, 0) + bonus
        # Respect avoidance even in counter selection
        for beh in self._detector.active():
            for t in TACTIC_AVOIDANCE.get(beh, []):
                if t in counter_w: counter_w[t] = 1
        if not counter_w:
            return self._pickTactic(exclude=exclude)
        return _weightedChoice(counter_w, self._rng)

    def _pickSurvivalTactic(self):
        style   = self._traits['survival_style']
        enemies = [u for u in self.game.units if u.team == 'enemy']
        if style == 'BURST':
            if any(u.unitType == 'cavalry'   for u in enemies): return 'BLITZKRIEG'
            if any(u.unitType == 'artillery' for u in enemies): return 'GRAND_BATTERY'
            return 'CONTACT_AND_FADE'
        if style == 'ANCHOR':
            return 'BRIDGE_CONTROL' if self.game.terrain.bridges else 'MOBILE_SUPPLY_BUBBLE'
        if style == 'FADE': return 'CONTACT_AND_FADE'
        return 'DELAYING_ACTION'

    def update(self):
        if self.game.gamemode == 'LAST_STAND':
            self._updateLastStand()
            return
        if self.game.gamemode == 'ASSAULT':
            self._updateAssault()
            return
        if self.game.gamemode == 'CONQUEST':
            self._updateConquest()
            return

        cur = sum(1 for u in self.game.units if u.team == 'enemy')
        self._casualties += max(0, self._lastCount - cur)
        self._lastCount   = cur
        self._timer     += 1
        self._evalTimer += 1
        if self._evalTimer >= self._evalInterval:
            self._evaluateTactic()
            self._evalTimer = 0
        self._decayDangerMap()
        self._pullbackWounded()
        self._avoidDangerZones()
        self._avoidDangerHotspots()
        if self._timer < self._tickInterval:
            self._refreshCombat()
            self._coordinateWaves()
            self._assessLocalFights()
            return
        self._timer       = 0
        self._tacticTicks += 1
        self._execute()

    def _updateLastStand(self):
        """Last Stand AI: every unit charges the player HQ. No tactics, no retreat."""
        self._timer += 1
        # Run combat refresh every frame regardless of tick interval
        self._refreshCombat()
        if self._timer < self._tickInterval:
            return
        self._timer = 0

        enemies  = [u for u in self.game.units if u.team == 'enemy']
        players  = [u for u in self.game.units if u.team == 'player']
        playerHq = next((h for h in self.game.headquarters if h.team == 'player'), None)
        terrain  = self.game.terrain
        if not enemies or not playerHq:
            return

        hx, hy = playerHq.x, playerHq.y

        for u in enemies:
            if u.routing:
                continue
            # Artillery: hang back and bombard
            if u.unitType == 'artillery':
                art_x = min(hx + 380, self.game.mapWidth - 80)
                art_y = hy + (hash(id(u)) % 300 - 150)
                art_y = max(60, min(self.game.mapHeight - 60, art_y))
                _moveToSafe(u, terrain, art_x, art_y)
                continue

            # Cavalry: flank charge
            if u.unitType == 'cavalry':
                side  = 1 if (hash(id(u)) % 2 == 0) else -1
                flank_y = hy + side * 200
                flank_y = max(60, min(self.game.mapHeight - 60, flank_y))
                _moveToSafe(u, terrain, hx + 20, flank_y)
                continue

            # Infantry / heavy infantry: direct rush with slight vertical spread
            spread = (hash(id(u)) % 280) - 140
            target_y = max(60, min(self.game.mapHeight - 60, hy + spread))
            _moveToSafe(u, terrain, hx + 30, target_y)

    def _updateAssault(self):
        """Assault AI: defenders sit on their assigned keypoint and only move
        when threatened. Lost keypoints are NOT auto-recaptured by the garrison
        (they're spent); the cavalry reserve responds to whichever keypoint is
        most pressured."""
        self._timer += 1
        self._refreshCombat()
        if self._timer < self._tickInterval:
            return
        self._timer = 0

        enemies = [u for u in self.game.units if u.team == 'enemy']
        players = [u for u in self.game.units if u.team == 'player']
        kps     = [op for op in self.game.outposts if op.strategic]
        terrain = self.game.terrain
        W, H    = self.game.mapWidth, self.game.mapHeight
        enemyHq = next((h for h in self.game.headquarters if h.team == 'enemy'), None)
        if not enemies:
            return

        # Index keypoints by id() so we can find a unit's assigned post.
        kp_by_id = {id(op): op for op in kps}

        cav = [u for u in enemies if u.unitType == 'cavalry'   and not u.routing]
        art_unassigned = [u for u in enemies if u.unitType == 'artillery'
                          and not u.routing and not getattr(u, 'assaultPost', None)]
        garrison_units = [u for u in enemies if not u.routing
                          and getattr(u, 'assaultPost', None) is not None]

        # ── Garrison units: defend their post; chase only nearby threats ────
        for u in garrison_units:
            op = kp_by_id.get(u.assaultPost)
            if op is None or op.team == 'player':
                # Post lost — fall back toward HQ rather than wandering forward
                if enemyHq:
                    _moveToSafe(u, terrain, enemyHq.x - 100, u.y)
                continue
            # Player units within 180px = active assault
            threats = [p for p in players if _dist(op.x, op.y, p.x, p.y) < 180]
            if threats:
                t = min(threats, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = t
                # Don't chase past 70px from the post — hold ground
                if _dist(op.x, op.y, t.x, t.y) < 90:
                    _moveToSafe(u, terrain, t.x, t.y)
                else:
                    # Keep the line: stand fast, just face the threat
                    u.targetX, u.targetY = u.x, u.y
            else:
                # Idle — return to a forward-facing position on the player
                # side of the keypoint (low-x side), preserving the unit's y.
                hold_x = max(80, min(W - 80, op.x - 45))
                hold_y = max(60, min(H - 60, u.y))
                if _dist(u.x, u.y, hold_x, hold_y) > 80:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, hold_x, hold_y)

        # ── Cavalry reserve: counter-attack the most threatened LIVE post ──
        live_kps = [op for op in kps if op.team != 'player']
        if cav and live_kps:
            def _pressure(op):
                return sum(1 for p in players if _dist(op.x, op.y, p.x, p.y) < 240)
            target_kp = max(live_kps, key=_pressure)
            tp = _pressure(target_kp)
            for u in cav:
                near = next((p for p in players
                             if _dist(u.x, u.y, p.x, p.y) < u.attackRange + 80), None)
                if near:
                    u.attackTarget = near
                elif tp >= 2:
                    # Only commit cavalry once a real threat exists
                    _moveToSafe(u, terrain, target_kp.x - 30, target_kp.y)
                elif enemyHq:
                    # Idle reserve: hold position behind HQ
                    _moveToSafe(u, terrain, enemyHq.x - 80, u.y)

        # ── Rear-bastion artillery: stay near HQ and bombard ────────────────
        if enemyHq:
            for i, u in enumerate(art_unassigned):
                ax = enemyHq.x - 120
                ay = enemyHq.y + (i * 2 - 1) * 80
                ay = max(80, min(H - 80, ay))
                _moveToSafe(u, terrain, ax, ay)

    def _updateConquest(self):
        """Conquest AI: capture and hold outposts to score points.

        Assignments are persisted on each unit (_cqTarget) and only changed
        when the current target is no longer valid, preventing the back-and-forth
        indecision caused by re-evaluating every tick.
        """
        self._timer += 1
        self._refreshCombat()
        if self._timer < self._tickInterval:
            return
        self._timer = 0

        g       = self.game
        enemies = [u for u in g.units if u.team == 'enemy' and not u.routing]
        players = [u for u in g.units if u.team == 'player']
        terrain = g.terrain
        W, H    = g.mapWidth, g.mapHeight
        enemyHq = next((h for h in g.headquarters if h.team == 'enemy'), None)

        if not enemies or not g.outposts:
            return

        ops        = g.outposts
        neutral    = [op for op in ops if op.team is None]
        player_ops = [op for op in ops if op.team == 'player']
        enemy_ops  = [op for op in ops if op.team == 'enemy']

        our_score = g._conquestScore.get('enemy',  0)
        foe_score = g._conquestScore.get('player', 0)
        behind    = our_score < foe_score - 100

        # ── Artillery: anchor near an owned outpost, independent of assignment ─
        art = [u for u in enemies if u.unitType == 'artillery']
        for i, u in enumerate(art):
            anchor = enemy_ops[i % len(enemy_ops)] if enemy_ops else enemyHq
            if anchor:
                ax = max(80, min(W - 80, anchor.x + 140))
                ay = max(80, min(H - 80, anchor.y + (i - len(art) // 2) * 80))
                if _dist(u.x, u.y, ax, ay) > 60:
                    _moveToSafe(u, terrain, ax, ay)

        # ── Build ordered target list (one outpost per entry, no duplicate slots)
        # Priority: defend threatened own > capture neutral > attack enemy > hold own
        targets = []
        for op in enemy_ops:
            pressure = sum(1 for p in players if _dist(op.x, op.y, p.x, p.y) < 220)
            if pressure > 0:
                targets.append((0, op))          # defend under-pressure post
        for op in neutral:
            targets.append((1, op))              # capture neutral
        if behind or not neutral:
            for op in player_ops:
                targets.append((2, op))          # attack enemy post
        for op in enemy_ops:
            pressure = sum(1 for p in players if _dist(op.x, op.y, p.x, p.y) < 220)
            if pressure == 0:
                targets.append((3, op))          # hold quiet own post

        targets.sort(key=lambda t: t[0])
        ordered = [op for _, op in targets]

        mobile = [u for u in enemies
                  if u.unitType in ('cavalry', 'infantry', 'heavy_infantry')]

        if not ordered:
            # Nothing to cap/defend — chase nearest enemy
            for u in mobile:
                if not players:
                    continue
                near = next((p for p in players
                             if _dist(u.x, u.y, p.x, p.y) < u.attackRange + 60), None)
                if near:
                    u.attackTarget = near
                else:
                    t = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                    _moveToSafe(u, terrain, t.x, t.y)
            return

        # ── Validate or (re-)assign persistent target ──────────────────────────
        # A unit keeps its target unless:
        #   a) it has no target yet
        #   b) its target is now owned by us (job done)
        #   c) an enemy post needs defending and this unit is the closest free unit
        cav = [u for u in mobile if u.unitType == 'cavalry']
        inf = [u for u in mobile if u.unitType != 'cavalry']

        def _needsNewTarget(u):
            t = getattr(u, '_cqTarget', None)
            if t is None:
                return True
            if t not in g.outposts:        # outpost removed (shouldn't happen)
                return True
            if t.team == 'enemy':          # already ours — find next job
                return True
            return False

        # Assign cavalry preferring capture/attack targets
        cap_ordered = [op for op in ordered if op.team != 'enemy'] or ordered
        for i, u in enumerate(cav):
            if _needsNewTarget(u):
                u._cqTarget = cap_ordered[i % len(cap_ordered)]

        # Spread infantry evenly across all targets using stable round-robin
        for i, u in enumerate(inf):
            if _needsNewTarget(u):
                u._cqTarget = ordered[i % len(ordered)]

        # ── Move each mobile unit toward its assigned target ───────────────────
        for u in mobile:
            near = next((p for p in players
                         if _dist(u.x, u.y, p.x, p.y) < u.attackRange + 60), None)
            if near:
                u.attackTarget = near
                continue
            op = getattr(u, '_cqTarget', None)
            if op is not None:
                # Already close enough — stand ground, don't pace back and forth
                if _dist(u.x, u.y, op.x, op.y) > 55:
                    _moveToSafe(u, terrain, op.x, op.y)
                else:
                    u.targetX, u.targetY = u.x, u.y

    def _evaluateTactic(self):
        enemies = [u for u in self.game.units if u.team == 'enemy']
        players = [u for u in self.game.units if u.team == 'player']
        if not enemies:
            return

        self._detector.update(
            players,
            self.game.outposts,
            self.game.headquarters,
            self.game.mapHeight,
            self.game.terrain,
        )

        casualty_rate = self._casualties / max(self._evalTimer, 1)
        ecx, _        = _centroid(enemies)

        if self._prevEnemyX is not None:
            moved = abs(ecx - self._prevEnemyX) if ecx else 0
            self._stuckTicks = self._stuckTicks + 1 if moved < 15 else 0
        self._prevEnemyX = ecx
        self._casualties = 0

        abandon_loss, abandon_stuck = self._traits['abandon_loss'], self._traits['abandon_stuck']
        avg_hp = _avgHealth(enemies)
        in_trouble    = (len(enemies) < len(players) * 0.50 or
                         (avg_hp < 0.35 and casualty_rate > abandon_loss * 0.5))

        if in_trouble and self._tactic not in SURVIVAL_TACTICS:
            old    = self._tactic
            picked = self._pickSurvivalTactic()
            if picked != old:
                self._tactic, self._survivalMode = picked, True
                self._tacticTicks, self._feintDone = 0, False
                aiLog(f"SURVIVAL: {old} -> {picked}  ({len(enemies)}v{len(players)} hp:{avg_hp:.0%})")
            return

        if self._survivalMode and len(enemies) >= len(players) * 0.75 and avg_hp > 0.50:
            self._survivalMode = False; old = self._tactic
            self._tactic      = self._pickTactic(exclude=old)
            self._tacticTicks = 0
            aiLog(f"RECOVERED: {old} -> {self._tactic}  (units stabilised)")
            return

        if self._tactic in SURVIVAL_TACTICS:
            return

        reason = 'high_losses' if casualty_rate > abandon_loss else None
        if reason is None and self._stuckTicks >= abandon_stuck:
            reason = 'stuck'; self._stuckTicks = 0

        if reason is None and self._tactic not in SURVIVAL_TACTICS:
            active = self._detector.active()
            if active:
                cscore = sum(b for beh in active
                             for t, b in COUNTER_MAP.get(beh, []) if t == self._tactic)
                if cscore == 0 and self._tacticTicks >= 2:
                    reason = 'counter_pressure'
        if reason:
            old = self._tactic
            self._weights[old] = max(1, self._weights[old] - 3)
            if reason == 'counter_pressure' or self._detector.active():
                self._tactic = self._pickCounterTactic(exclude=old)
            else:
                self._tactic = self._pickTactic(exclude=old)
            self._tacticTicks, self._feintDone, self._commitSide = 0, False, self._rng.choice([-1, 1])
            det = ','.join(self._detector.active()) or 'none'
            aiLog(f"SWITCH ({reason}): {old} -> {self._tactic}  detected:[{det}]")

    def _refreshCombat(self):
        players = [u for u in self.game.units if u.team == 'player']
        terrain = self.game.terrain
        if not players:
            return
        for u in self.game.units:
            if u.team != 'enemy' or u.routing:
                continue
            if u.unitType == 'cavalry' and terrain.isOnRiver(u.x, u.y):
                continue

            scanRange = u.attackRange + 55
            if self._mistakeRate > 0 and self._rng.random() < self._mistakeRate:
                # Difficulty: pick a random nearby target instead of optimal
                nearby = [p for p in players
                          if _dist(u.x, u.y, p.x, p.y) <= scanRange]
                best = self._rng.choice(nearby) if nearby else _bestTarget(u, players, maxRange=scanRange)
            else:
                best = _bestTarget(u, players, maxRange=scanRange)
            if not best: continue
            bestScore = _scoreTarget(u, best)
            if _dist(u.x, u.y, best.x, best.y) > u.attackRange:
                bestScore -= _approachThreat(u.x, u.y, best.x, best.y, players) * 0.3

            cur = u.attackTarget
            if cur and cur.hp > 0:
                curScore = _scoreTarget(u, cur)
                if _dist(u.x, u.y, cur.x, cur.y) > u.attackRange:
                    curScore -= _approachThreat(u.x, u.y, cur.x, cur.y, players) * 0.3
                if bestScore <= curScore + 10:
                    continue

            u.attackTarget = best

            if u.unitType == 'cavalry' and _dist(u.x, u.y, best.x, best.y) > 40:
                fx, fy = _flankPos(best)
                if _routeSafe(terrain, u.x, u.y, fx, fy):
                    u.targetX, u.targetY = fx, fy
                else:
                    _moveToSafe(u, terrain, best.x, best.y)

    # ── execute current tactic ───────────────────────────────────────────────

    def _execute(self):
        g       = self.game
        terrain = g.terrain
        enemies = [u for u in g.units if u.team == 'enemy' and not u.routing]
        players = [u for u in g.units if u.team == 'player']
        W, H    = g.mapWidth, g.mapHeight
        if not enemies or not players:
            return

        neutralOps = [op for op in g.outposts if op.team is None]
        enemyOps   = [op for op in g.outposts if op.team == 'enemy']
        playerHq   = next((h for h in g.headquarters if h.team == 'player'), None)
        enemyHq    = next((h for h in g.headquarters if h.team == 'enemy'),  None)
        infantry   = [u for u in enemies if u.unitType == 'infantry']
        heavy_inf  = [u for u in enemies if u.unitType == 'heavy_infantry']
        cavalry    = [u for u in enemies if u.unitType == 'cavalry']
        artillery  = [u for u in enemies if u.unitType == 'artillery']

        fallback_ratio = self._traits['fallback_ratio']
        hq_danger      = enemyHq and enemyHq.captureProgress > 20
        heavy_losses   = (self._casualties / max(self._tacticTicks, 1)) > 0.20
        outnumbered    = len(enemies) < len(players) * fallback_ratio

        if hq_danger or (heavy_losses and outnumbered):
            aiLog(f"FALLBACK: hq_danger={hq_danger} losses={heavy_losses} outnumbered={outnumbered}")
            self._doFallback(infantry + cavalry, players, enemyHq, terrain, W, H)
            self._doArtillery(artillery, [], infantry, players, terrain, W, H)
            self._doHeavyInfantryRole(heavy_inf, players, enemyHq, terrain, self._tactic)
            return

        threatened = [op for op in enemyOps
                      if any(_dist(p.x, p.y, op.x, op.y) < 160 for p in players)]
        if threatened:
            op    = min(threatened, key=lambda o: min(
                (_dist(u.x, u.y, o.x, o.y) for u in infantry), default=99999))
            inf_s = sorted(infantry, key=lambda u: _dist(u.x, u.y, op.x, op.y))
            self._doReinforce(inf_s[:2], op, players, terrain)          # 2 defenders on OP
            if enemyHq and len(inf_s) > 2:                              # 2 reserves held back
                d  = _dist(op.x, op.y, enemyHq.x, enemyHq.y) or 1
                rx = op.x + (enemyHq.x - op.x) / d * 90
                ry = op.y + (enemyHq.y - op.y) / d * 90
                for u in inf_s[2:4]:
                    u.attackTarget = None; _moveToSafe(u, terrain, rx, ry)
                    near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                    if near and _dist(u.x, u.y, near.x, near.y) < 120: u.attackTarget = near
            infantry = inf_s[4:]

        hq_guards  = infantry[:HQ_GUARD_COUNT]
        mobile_inf = infantry[HQ_GUARD_COUNT:]
        self._doGuardHq(hq_guards, players, enemyHq, terrain, W, H)

        # Claim valuable chokepoints before the tactic spends the mobile pool.
        # Skips entirely on offensive-only tactics that need every body for the push.
        if self._tactic not in ('BLITZKRIEG', 'CAVALRY_RAID', 'STEAMROLLER',
                                'CAVALRY_EXPLOIT', 'FEINT_STRIKE'):
            held_inf, held_art = self._doChokepointHold(
                mobile_inf, artillery, players, terrain, W, H)
            if held_inf:
                hi = set(id(u) for u in held_inf)
                mobile_inf = [u for u in mobile_inf if id(u) not in hi]
            if held_art:
                ha = set(id(u) for u in held_art)
                artillery = [u for u in artillery if id(u) not in ha]

        # On river maps, race for bridges (skip on aggressive cavalry tactics
        # that have their own crossing logic via BRIDGE_CONTROL).
        if terrain.bridges and self._tactic not in (
                'BLITZKRIEG', 'CAVALRY_RAID', 'STEAMROLLER',
                'BRIDGE_CONTROL'):
            br_inf, br_art = self._doBridgeClaim(
                mobile_inf, artillery, players, terrain, W, H)
            if br_inf:
                bi = set(id(u) for u in br_inf)
                mobile_inf = [u for u in mobile_inf if id(u) not in bi]
            if br_art:
                ba = set(id(u) for u in br_art)
                artillery = [u for u in artillery if id(u) not in ba]

        art_guards = []
        if artillery and mobile_inf:
            ax, ay = _centroid(artillery)
            mobile_inf.sort(key=lambda u: _dist(u.x, u.y, ax, ay))
            art_guards = mobile_inf[:ART_GUARD_COUNT]
            mobile_inf = mobile_inf[ART_GUARD_COUNT:]
        self._doArtillery(artillery, art_guards, mobile_inf, players, terrain, W, H)
        self._counterSquares(artillery, players)
        self._doHeavyInfantryRole(heavy_inf, players, enemyHq, terrain, self._tactic)

        fn = self._tacticMap().get(self._tactic)
        if fn:
            fn(mobile_inf, cavalry, players, playerHq, enemyHq,
               neutralOps, enemyOps, terrain, W, H)

    def _tacticMap(self):
        if not hasattr(self, '_cachedTacticMap'):
            m = {}
            for name, method in [
                ('BLITZKRIEG', self._tBlitzkrieg), ('SIEGELINE', self._tSiegeline),
                ('PINCER', self._tPincer), ('FEINT_STRIKE', self._tFeintStrike),
                ('ARTILLERY_DOM', self._tArtilleryDom), ('GUERRILLA', self._tGuerrilla),
                ('REFUSE_FLANK', self._tRefuseFlank), ('STEAMROLLER', self._tSteamroller),
                ('CAVALRY_RAID', self._tCavalryRaid), ('HILL_CONTROL', self._tHillControl),
                ('CENTER_PUSH', self._tCenterPush), ('COUNTERATTACK', self._tCounterattack),
                ('ENCIRCLEMENT', self._tEncirclement), ('BRIDGE_CONTROL', self._tBridgeControl),
                ('SKIRMISH_SCREEN', self._tSkirmishScreen), ('ECHELON', self._tEchelon),
                ('DOUBLE_ENVELOP', self._tDoubleEnvelop), ('ATTRITION', self._tAttrition),
                ('GRAND_BATTERY', self._tGrandBattery), ('SUPPLY_EDGE_PRESSURE', self._tSupplyEdgePressure),
                ('OP_ISOLATION', self._tOpIsolation), ('DOUBLE_OP_PRESSURE', self._tDoubleOpPressure),
                ('HAMMER_AND_ANVIL', self._tHammerAndAnvil), ('DELAYING_ACTION', self._tDelayingAction),
                ('CONTACT_AND_FADE', self._tContactAndFade), ('MOBILE_SUPPLY_BUBBLE', self._tMobileSupplyBubble),
                ('COUNTER_BATTERY', self._tCounterBattery), ('FEIGNED_RETREAT', self._tFeignedRetreat),
                ('DEFENSE_IN_DEPTH', self._tDefenseInDepth), ('CAVALRY_EXPLOIT', self._tCavalryExploit),
                ('FOREST_DELAY', self._tForestDelayZone), ('COMBINED_ARMS', self._tCombinedArms),
            ]:
                m[name] = method
            self._cachedTacticMap = m
        return self._cachedTacticMap
