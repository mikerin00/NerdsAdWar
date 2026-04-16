# Module: ai_tactics_offense
# OffensiveTacticsMixin — aggressive manoeuvre tactics for EnemyAI

from src.game.ai_helpers import (
    _dist, _centroid, _terrainScore, _bestHighGround, _bestCorridorY,
    _moveToSafe, _formationLine, _pairAttack, _findGap, _nearestBridge,
    _routeSafe,
)


class OffensiveTacticsMixin:

    def _tBlitzkrieg(self, inf, cav, players, playerHq, enemyHq,
                     neutralOps, enemyOps, terrain, W, H):
        """Cavalry charges immediately; infantry follows at full speed."""
        target = min(players, key=lambda p: p.hp / p.maxHp + p.morale / 100)
        for u in cav:
            u.attackTarget = target
            _moveToSafe(u, terrain, target.x, target.y)
        _pairAttack(inf, players, terrain)

    def _tPincer(self, inf, cav, players, playerHq, enemyHq,
                 neutralOps, enemyOps, terrain, W, H):
        """Two wings converge simultaneously from north and south."""
        pcx, pcy = _centroid(players)
        mid   = len(inf) // 2
        north = sorted(inf, key=lambda u: u.y)[:mid]
        south = sorted(inf, key=lambda u: u.y)[mid:]
        for u in north:
            target = min(players, key=lambda p: _dist(p.x, p.y, pcx, H * 0.15))
            u.attackTarget = target
            _moveToSafe(u, terrain, pcx, H * 0.15)
        for u in south:
            target = min(players, key=lambda p: _dist(p.x, p.y, pcx, H * 0.85))
            u.attackTarget = target
            _moveToSafe(u, terrain, pcx, H * 0.85)
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 170 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 40, pcy)

    def _tFeintStrike(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """Feint one side for 2 ticks, then hard commit the other side."""
        gap_y    = _findGap(players, H)
        pcx, pcy = _centroid(players)
        if not self._feintDone and self._tacticTicks <= 2:
            feint_y = gap_y if gap_y else pcy
            mid     = len(inf) // 2
            for u in inf[:mid]:
                near = min(players, key=lambda p: _dist(p.x, p.y, pcx, feint_y)) if players else None
                if near:
                    u.attackTarget = near
                    _moveToSafe(u, terrain, pcx, feint_y)
            for u in inf[mid:]:
                pos = _bestHighGround(terrain, u.x - 30, u.y, W, H, radius=80)
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
            lo  = 0    if self._commitSide < 0 else H // 2
            hi  = H // 2 if self._commitSide < 0 else H
            if cav:
                cy_ = _bestCorridorY(terrain,
                                     int(min(u.x for u in cav)), int(pcx), lo, hi)
                for u in cav:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, (u.x + pcx) / 2, cy_)
        else:
            self._feintDone  = True
            self._commitSide *= -1
            lo  = 0    if self._commitSide < 0 else H // 2
            hi  = H // 2 if self._commitSide < 0 else H
            _pairAttack(inf, players, terrain)
            if not cav:
                return
            cy_ = _bestCorridorY(terrain,
                                 int(min(u.x for u in cav)), int(pcx), lo, hi)
            target = min(players, key=lambda p: p.hp / p.maxHp + p.morale / 100)
            for u in cav:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _dist(u.x, u.y, near.x, near.y) < 180 and _terrainScore(terrain, u.x, u.y) >= 0:
                    u.attackTarget = near
                else:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, target.x, cy_)

    def _tCavalryRaid(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """All cavalry races to hit player OPs and HQ; infantry advances steadily."""
        playerOps    = [op for op in self.game.outposts if op.team == 'player']
        raid_targets = playerOps + ([playerHq] if playerHq else [])
        if raid_targets:
            for i, u in enumerate(cav):
                rt = raid_targets[i % len(raid_targets)]
                u.attackTarget = None
                if not _routeSafe(terrain, u.x, u.y, rt.x, rt.y):
                    b = _nearestBridge(terrain, u.x, u.y)
                    if b:
                        _moveToSafe(u, terrain, b['x'], b['y'])
                else:
                    _moveToSafe(u, terrain, rt.x, rt.y)
        _pairAttack(inf, players, terrain)

    def _tEncirclement(self, inf, cav, players, playerHq, enemyHq,
                       neutralOps, enemyOps, terrain, W, H):
        """Three prongs try to surround the player formation."""
        pcx, pcy = _centroid(players)
        thirds   = [inf[i::3] for i in range(3)]
        dest_y   = [H * 0.15, pcy, H * 0.85]
        for g_idx, grp in enumerate(thirds):
            ty = dest_y[g_idx]
            for u in grp:
                near = min(players, key=lambda p: _dist(p.x, p.y, pcx, ty)) if players else None
                if near:
                    u.attackTarget = near
                    _moveToSafe(u, terrain, pcx, ty)
        for u in cav:
            cy_ = _bestCorridorY(terrain, int(u.x), int(pcx), 0, H)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx - 60, cy_)

    def _tDoubleEnvelop(self, inf, cav, players, playerHq, enemyHq,
                        neutralOps, enemyOps, terrain, W, H):
        """Both flanks attack simultaneously; centre holds."""
        pcx, pcy = _centroid(players)
        thirds   = [inf[i::3] for i in range(3)]
        for u in thirds[1]:
            pos  = _bestHighGround(terrain, pcx + 160, pcy, W, H, radius=100)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 180:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        for u in thirds[0]:
            target = min(players, key=lambda p: _dist(p.x, p.y, pcx, H * 0.1)) if players else None
            if target:
                u.attackTarget = target
                _moveToSafe(u, terrain, target.x, H * 0.1)
        for u in thirds[2]:
            target = min(players, key=lambda p: _dist(p.x, p.y, pcx, H * 0.9)) if players else None
            if target:
                u.attackTarget = target
                _moveToSafe(u, terrain, target.x, H * 0.9)
        for i, u in enumerate(cav):
            cy_ = H * 0.1 if i < len(cav) // 2 else H * 0.9
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 20, cy_)

    def _tEchelon(self, inf, cav, players, playerHq, enemyHq,
                  neutralOps, enemyOps, terrain, W, H):
        """Staggered diagonal advance: each unit offset in both X and Y."""
        if not players or not inf:
            return
        pcx, pcy = _centroid(players)
        inf_s    = sorted(inf, key=lambda u: u.y)
        n        = len(inf_s)
        for i, u in enumerate(inf_s):
            y_frac = i / (n - 1) if n > 1 else 0.5
            dest_y = H * 0.1 + y_frac * H * 0.8
            dest_x = pcx + 60 + (0.5 - y_frac) * 200 * self._commitSide
            near   = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, dest_x, dest_y)
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 40,
                            H * 0.9 if self._commitSide > 0 else H * 0.1)

    def _tCenterPush(self, inf, cav, players, playerHq, enemyHq,
                     neutralOps, enemyOps, terrain, W, H):
        """Hard push through the centre; flanks ignored."""
        pcx, pcy = _centroid(players)
        target   = min(players, key=lambda p: abs(p.y - H / 2)) if players else None
        _formationLine(inf, pcx, H / 2, terrain, spacing=44)
        for u in inf:
            if target:
                u.attackTarget = target
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx - 30, H / 2 + self._commitSide * 80)

    def _tHammerAndAnvil(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Infantry pins frontally (anvil); cavalry sweeps the flank hard (hammer)."""
        pcx, pcy = _centroid(players)
        _pairAttack(inf, players, terrain)
        sweep_y       = H * 0.15 if self._commitSide < 0 else H * 0.85
        weakest_flank = min(players, key=lambda p: _dist(p.x, p.y, pcx, sweep_y)) if players else None
        for u in cav:
            if weakest_flank and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = weakest_flank
                _moveToSafe(u, terrain, weakest_flank.x, sweep_y)
            else:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near:
                    u.attackTarget = near
                _moveToSafe(u, terrain, pcx + 30, pcy)

    def _tDoubleOpPressure(self, inf, cav, players, playerHq, enemyHq,
                           neutralOps, enemyOps, terrain, W, H):
        """Threaten two player OPs simultaneously to split their defence."""
        playerOps = sorted(
            [op for op in self.game.outposts if op.team == 'player'],
            key=lambda op: _dist(op.x, op.y,
                                 playerHq.x if playerHq else W / 2,
                                 playerHq.y if playerHq else H / 2)
        )
        if len(playerOps) < 2:
            self._tCavalryRaid(inf, cav, players, playerHq, enemyHq,
                               neutralOps, enemyOps, terrain, W, H)
            return
        op1, op2 = playerOps[0], playerOps[1]
        half     = len(inf) // 2
        for u in inf[:half]:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, op1.x, op1.y)
        for u in inf[half:]:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, op2.x, op2.y)
        for i, u in enumerate(cav):
            target_op = op1 if i < len(cav) // 2 else op2
            u.attackTarget = None
            _moveToSafe(u, terrain, target_op.x, target_op.y)

    def _tFeignedRetreat(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Fake retreat to lure player out of position, then counter-charge."""
        if not enemyHq:
            return
        pcx, pcy = _centroid(players)
        if self._tacticTicks <= 2:
            # Phase 1: retreat, look weak
            rally_x = enemyHq.x - 180
            for i, u in enumerate(sorted(inf + cav, key=lambda u: u.y)):
                ty = H * (i + 1) / (len(inf) + len(cav) + 1)
                u.attackTarget = None
                _moveToSafe(u, terrain, rally_x, ty)
        else:
            # Phase 2: player followed → hard counter-charge
            _pairAttack(inf, players, terrain)
            weakest = min(players, key=lambda p: p.hp / p.maxHp + p.morale / 100)
            for u in cav:
                u.attackTarget = weakest
                _moveToSafe(u, terrain, weakest.x, weakest.y)

    def _tCavalryExploit(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Infantry pins front; cavalry exploits gaps to hit artillery/HQ."""
        pcx, pcy = _centroid(players)
        _pairAttack(inf, players, terrain)
        gap_y = _findGap(players, H)
        player_art = [p for p in players if p.unitType == 'artillery']
        for u in cav:
            if player_art:
                target = min(player_art, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = target
                # Route through gap if one exists
                if gap_y and _dist(u.x, u.y, target.x, target.y) > 120:
                    _moveToSafe(u, terrain, pcx - 40, gap_y)
                else:
                    _moveToSafe(u, terrain, target.x, target.y)
            elif playerHq:
                u.attackTarget = None
                _moveToSafe(u, terrain, playerHq.x, playerHq.y)
