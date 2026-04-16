# Module: ai_tactics_defense
# DefensiveTacticsMixin — defensive and reactive tactics for EnemyAI

from src.game.ai_helpers import (
    _dist, _centroid, _terrainScore, _bestHighGround, _bestCorridorY,
    _moveToSafe, _formationLine, _pairAttack, _nearestBridge,
    _nearestChokepoint, ARTILLERY_RANGE,
)


class DefensiveTacticsMixin:

    def _tSiegeline(self, inf, cav, players, playerHq, enemyHq,
                    neutralOps, enemyOps, terrain, W, H):
        """Hold a long line on the best terrain; prefer chokepoints."""
        if not enemyHq: return
        chokes = getattr(self, '_terrainTraits', {}).get('chokepoints', [])
        # If chokepoints exist between us and the enemy, anchor the line there
        ecx    = enemyHq.x
        usable = [c for c in chokes if ecx - 450 < c[0] < ecx - 100]
        if usable:
            # Anchor line at the chokepoint X
            line_x = sum(c[0] for c in usable) / len(usable)
        else:
            line_x = ecx - 280
        units  = sorted(inf + cav, key=lambda u: u.y)
        for i, u in enumerate(units):
            pos  = _bestHighGround(terrain, line_x, H * (i + 1) / (len(units) + 1), W, H, radius=140)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 200:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])

    def _tRefuseFlank(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """One flank holds defensively; other flank masses for attack."""
        if not enemyHq: return
        hold_side  = self._commitSide
        mid        = len(inf) // 2
        inf_s      = sorted(inf, key=lambda u: u.y)
        hold_grp   = inf_s[:mid] if hold_side < 0 else inf_s[mid:]
        attack_grp = inf_s[mid:] if hold_side < 0 else inf_s[:mid]
        line_x     = enemyHq.x - 260
        for i, u in enumerate(sorted(hold_grp, key=lambda u: u.y)):
            ty  = H * (0.05 if hold_side < 0 else 0.55) + i * 50
            pos = _bestHighGround(terrain, line_x, ty, W, H, radius=100)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 190:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        pcx, _ = _centroid(players)
        atk_y  = H * 0.75 if hold_side < 0 else H * 0.25
        target = min(players, key=lambda p: _dist(p.x, p.y, pcx, atk_y)) if players else None
        for u in attack_grp:
            if target:
                u.attackTarget = target
                _moveToSafe(u, terrain, target.x, atk_y)
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 30, atk_y)

    def _tSteamroller(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """Slow methodical full-line advance; everyone moves together."""
        _pairAttack(inf, players, terrain)
        pcx, pcy = _centroid(players)
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 170 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None; _moveToSafe(u, terrain, pcx + 50, pcy)

    def _tHillControl(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """Occupy key hills before attacking; fire down once on high ground."""
        pcx, pcy = _centroid(players)
        cx = ((enemyHq.x if enemyHq else W) + pcx) / 2 if players else W * 0.6
        hill_positions = [
            _bestHighGround(terrain, cx, H * (i + 1) / (len(inf) + 1), W, H, radius=160)
            for i in range(len(inf))
        ]
        for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
            pos     = hill_positions[i]
            near    = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            on_hill = terrain.isHighGround(u.x, u.y)
            if on_hill and near and _dist(u.x, u.y, near.x, near.y) < 200:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 150 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, cx + 40, pcy)

    def _tCounterattack(self, inf, cav, players, playerHq, enemyHq,
                        neutralOps, enemyOps, terrain, W, H):
        """Hold defensive line; when player crosses it, counter-charge hard.
        If chokepoints exist, set the trigger line there for maximum advantage."""
        if not enemyHq:
            return
        chokes = getattr(self, '_terrainTraits', {}).get('chokepoints', [])
        ecx    = enemyHq.x
        usable = [c for c in chokes if ecx - 500 < c[0] < ecx - 100]
        if usable:
            trigger_x = sum(c[0] for c in usable) / len(usable)
        else:
            trigger_x = ecx - 350
        player_crossed = any(p.x < trigger_x for p in players) if players else False
        if player_crossed:
            _pairAttack(inf, players, terrain)
            for u in cav:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _terrainScore(terrain, u.x, u.y) >= 0:
                    u.attackTarget = near
                    _moveToSafe(u, terrain, near.x, near.y)
        else:
            line_x = enemyHq.x - 300
            units  = sorted(inf + cav, key=lambda u: u.y)
            n      = len(units)
            for i, u in enumerate(units):
                ty  = H * (i + 1) / (n + 1)
                pos = _bestHighGround(terrain, line_x, ty, W, H, radius=120)
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])

    def _tBridgeControl(self, inf, cav, players, playerHq, enemyHq,
                        neutralOps, enemyOps, terrain, W, H):
        """Artillery clears bridge defenders; infantry advances once softened."""
        bridges = terrain.bridges
        if not bridges:
            # No river — fall back to SIEGELINE (which uses chokepoints if available)
            self._tSiegeline(inf, cav, players, playerHq, enemyHq,
                             neutralOps, enemyOps, terrain, W, H)
            return
        bridge_hot = any(
            any(_dist(p.x, p.y, b['x'], b['y']) < 220 for p in players)
            for b in bridges)
        bx = min(b['x'] for b in bridges)
        heavy_crossed = any(u.unitType == 'heavy_infantry' and u.x < bx
                            for u in self.game.units if u.team == 'enemy' and not u.routing)
        if heavy_crossed and getattr(self, '_heavyCrossedAt', None) is None:
            self._heavyCrossedAt = self._tacticTicks
        if not heavy_crossed: self._heavyCrossedAt = None
        # Infantry follows 2 tactic cycles (~3 s) after heavies establish a foothold
        foothold = heavy_crossed and self._tacticTicks - getattr(self, '_heavyCrossedAt', 0) >= 2
        if bridge_hot and not foothold:
            ecx = enemyHq.x if enemyHq else W * 0.75
            for u in inf:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                if _dist(u.x, u.y, near.x, near.y) < 150:
                    u.attackTarget = near
                else:
                    u.attackTarget = None; _moveToSafe(u, terrain, max(bx, ecx - 200), u.y)
        elif bridge_hot and foothold:
            _pairAttack(inf, players, terrain)  # foothold secured — full push
        else:
            per_bridge = max(1, len(inf) // len(bridges))
            for b_idx, b in enumerate(bridges):
                squad = inf[b_idx * per_bridge:(b_idx + 1) * per_bridge]
                for u in squad:
                    near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                    if _dist(u.x, u.y, near.x, near.y) < 180:
                        u.attackTarget = near
                    else:
                        u.attackTarget = None
                        _moveToSafe(u, terrain, b['x'], b['y'])
            remaining = inf[len(bridges) * per_bridge:]
            for i, u in enumerate(remaining):
                pos = _bestHighGround(terrain, bridges[0]['x'] + 60,
                                      H * (i + 1) / (len(remaining) + 1), W, H, radius=100)
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        for i, u in enumerate(cav):
            b    = bridges[i % len(bridges)]
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if not bridge_hot and near and _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, b['x'] + 80, b['y'])

    def _tSkirmishScreen(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Cavalry screen in front probes; infantry waits on high ground."""
        pcx, pcy = _centroid(players)
        for i, u in enumerate(cav):
            lo, hi = (0, H // 2) if i < len(cav) // 2 else (H // 2, H)
            cy_  = _bestCorridorY(terrain, int(u.x), int(pcx), lo, hi)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 170 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 100, cy_)
        for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
            ty  = H * (i + 1) / (len(inf) + 1)
            pos = _bestHighGround(terrain, pcx + 220, ty, W, H, radius=120)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 150:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])

    def _tAttrition(self, inf, cav, players, playerHq, enemyHq,
                    neutralOps, enemyOps, terrain, W, H):
        """Stay at artillery range; let cannons grind them down.
        Tighter formation on open terrain to avoid being flanked."""
        pcx, pcy = _centroid(players)
        openness = getattr(self, '_terrainTraits', {}).get('openness', 0.5)
        # Tighter line on open terrain (less cover = need mutual support)
        spacing  = 40 if openness > 0.45 else 52
        hold_x   = pcx + ARTILLERY_RANGE + 30
        _formationLine(inf, hold_x, pcy, terrain, spacing=spacing)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 110:
                u.attackTarget = near
            else:
                u.attackTarget = None
        for u in cav:
            art_targets = [p for p in players if p.unitType == 'artillery'] if players else []
            if art_targets:
                target = min(art_targets, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                if _dist(u.x, u.y, target.x, target.y) < 200 and _terrainScore(terrain, u.x, u.y) >= 0:
                    u.attackTarget = target
                    continue
            u.attackTarget = None
            _moveToSafe(u, terrain, hold_x - 50, pcy + self._commitSide * 120)

    def _tArtilleryDom(self, inf, cav, players, playerHq, enemyHq,
                       neutralOps, enemyOps, terrain, W, H):
        """Push artillery to dominant high ground; infantry screens at range."""
        if not inf:
            return
        pcx, pcy = _centroid(players)
        screen_x = pcx + 280
        _formationLine(inf, screen_x, pcy, terrain, spacing=52)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 180:
                u.attackTarget = near
            else:
                u.attackTarget = None
        for i, u in enumerate(cav):
            lo, hi = (0, H // 2) if i < len(cav) // 2 else (H // 2, H)
            cy_  = _bestCorridorY(terrain, int(u.x), int(pcx), lo, hi)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 150 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 60, cy_)

    def _tDefenseInDepth(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Two staggered lines: front skirmishes, reserve counter-charges on breach.
        Anchors front line at chokepoints when available."""
        if not enemyHq: return
        pcx, pcy = _centroid(players)
        mid      = max(1, len(inf) // 2)
        inf_s    = sorted(inf, key=lambda u: u.y)
        chokes   = getattr(self, '_terrainTraits', {}).get('chokepoints', [])
        ecx      = enemyHq.x
        usable   = [c for c in chokes if ecx - 500 < c[0] < ecx - 80]
        if usable:
            front_x = sum(c[0] for c in usable) / len(usable)
        else:
            front_x = (pcx + ecx) / 2
        for i, u in enumerate(inf_s[:mid]):
            ty  = H * (i + 1) / (mid + 1)
            pos = _bestHighGround(terrain, front_x, ty, W, H, radius=100)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if _dist(u.x, u.y, near.x, near.y) < 180: u.attackTarget = near
            else: u.attackTarget = None; _moveToSafe(u, terrain, pos[0], pos[1])
        reserve_x    = front_x + 150
        front_broken = any(p.x > front_x - 40 for p in players)
        for i, u in enumerate(inf_s[mid:]):
            ty = H * (i + 1) / (len(inf_s) - mid + 1)
            if front_broken:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = near; _moveToSafe(u, terrain, near.x, near.y)
            else: u.attackTarget = None; _moveToSafe(u, terrain, reserve_x, ty)
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if front_broken and _dist(u.x, u.y, near.x, near.y) < 200: u.attackTarget = near
            else: u.attackTarget = None; _moveToSafe(u, terrain, reserve_x + 40, pcy)

    def _tGuerrilla(self, inf, cav, players, playerHq, enemyHq,
                    neutralOps, enemyOps, terrain, W, H):
        """Small groups harass from forest/hills; retreat when taking fire."""
        pcx, pcy = _centroid(players)
        groups   = [inf[i::3] for i in range(3)]
        offsets  = [H * 0.25, H * 0.5, H * 0.75]
        for g_idx, squad in enumerate(groups):
            dest_y   = offsets[g_idx]
            forest_x = pcx + 100 + self._rng.randint(-60, 60)
            best     = _bestHighGround(terrain, forest_x, dest_y, W, H, radius=120)
            for u in squad:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _dist(u.x, u.y, near.x, near.y) < 130 and u.hp / u.maxHp > 0.45:
                    u.attackTarget = near
                elif near and u.hp / u.maxHp < 0.45:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, best[0] + 100, best[1])
                else:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, best[0], best[1])
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 150 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 80, self._rng.uniform(H * 0.1, H * 0.9))
