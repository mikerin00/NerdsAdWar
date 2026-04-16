# Module: ai_tactics_special
# SpecialTacticsMixin — supply, outpost and survival tactics for EnemyAI

import math

from src.constants import TERR_CLAIM_RADIUS
from src.game.ai_helpers import (
    _dist, _centroid, _terrainScore, _bestHighGround,
    _moveToSafe, _formationLine, _pairAttack, ARTILLERY_RANGE,
)


class SpecialTacticsMixin:

    def _tGrandBattery(self, inf, cav, players, playerHq, enemyHq,
                       neutralOps, enemyOps, terrain, W, H):
        """Mass artillery focus on the weakest enemy cluster; infantry screens."""
        if not players:
            return
        pcx, pcy = _centroid(players)
        weakest  = min(players, key=lambda p: p.hp / p.maxHp + p.morale / 100)
        hold_x   = weakest.x + ARTILLERY_RANGE + 40
        _formationLine(inf, hold_x, weakest.y, terrain, spacing=54)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 140:
                u.attackTarget = near
            else:
                u.attackTarget = None
        art_targets = [p for p in players if p.unitType == 'artillery']
        for u in cav:
            target = (min(art_targets, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                      if art_targets
                      else min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                      if players else None)
            if target and _dist(u.x, u.y, target.x, target.y) < 230 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = target
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, hold_x - 60, pcy + self._commitSide * 100)

    def _tSupplyEdgePressure(self, inf, cav, players, playerHq, enemyHq,
                             neutralOps, enemyOps, terrain, W, H):
        """Advance to the edge of player supply radius — fight where morale drains."""
        if not players or not playerHq:
            return
        pcx, pcy = _centroid(players)
        edge_x   = playerHq.x + TERR_CLAIM_RADIUS + 60
        _formationLine(inf, edge_x, pcy, terrain, spacing=48)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
        for u in cav:
            probe_y = H * 0.2 if self._commitSide > 0 else H * 0.8
            near    = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, edge_x - 40, probe_y)

    def _tOpIsolation(self, inf, cav, players, playerHq, enemyHq,
                      neutralOps, enemyOps, terrain, W, H):
        """Position between the player army and their nearest outpost."""
        playerOps = [op for op in self.game.outposts if op.team == 'player']
        if not players or not playerOps:
            self._tSteamroller(inf, cav, players, playerHq, enemyHq,
                               neutralOps, enemyOps, terrain, W, H)
            return
        pcx, pcy    = _centroid(players)
        nearest_op  = min(playerOps, key=lambda op: _dist(pcx, pcy, op.x, op.y))
        mid_x       = (pcx + nearest_op.x) / 2
        mid_y       = (pcy + nearest_op.y) / 2
        block_pos   = _bestHighGround(terrain, mid_x, mid_y, W, H, radius=100)
        _formationLine(inf, block_pos[0], block_pos[1], terrain, spacing=46)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 170:
                u.attackTarget = near
            else:
                u.attackTarget = None
        for u in cav:
            if _dist(u.x, u.y, nearest_op.x, nearest_op.y) < 200 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = None
                _moveToSafe(u, terrain, nearest_op.x, nearest_op.y)
            else:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _dist(u.x, u.y, near.x, near.y) < 160:
                    u.attackTarget = near
                else:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, nearest_op.x, nearest_op.y)

    def _tCounterBattery(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """Own artillery hunts enemy cannons; cavalry flanks to destroy them."""
        pcx, pcy   = _centroid(players)
        player_art = [p for p in players if p.unitType == 'artillery']
        # Override own artillery targets: force counter-battery fire
        own_art = [u for u in self.game.units
                   if u.team == 'enemy' and u.unitType == 'artillery' and not u.routing]
        for u in own_art:
            if player_art and u.deployed:
                u.attackTarget = min(player_art, key=lambda p: _dist(u.x, u.y, p.x, p.y))
        # Infantry screens at safe distance
        hold_x = pcx + ARTILLERY_RANGE + 50
        _formationLine(inf, hold_x, pcy, terrain, spacing=50)
        for u in inf:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if _dist(u.x, u.y, near.x, near.y) < 130:
                u.attackTarget = near
            else:
                u.attackTarget = None
        # Cavalry specifically hunts enemy artillery
        for u in cav:
            if player_art:
                t = min(player_art, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = t
                _moveToSafe(u, terrain, t.x, t.y)
            else:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                u.attackTarget = near

    def _tForestDelayZone(self, inf, cav, players, playerHq, enemyHq,
                          neutralOps, enemyOps, terrain, W, H):
        """Position in forests for 25% damage reduction; fight only from cover."""
        pcx, pcy = _centroid(players)
        ecx      = enemyHq.x if enemyHq else W * 0.75
        mid_x    = (pcx + ecx) / 2
        for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
            ty  = H * (i + 1) / (len(inf) + 1)
            pos = _bestHighGround(terrain, mid_x, ty, W, H, radius=160)
            # Prefer forest positions (override hill preference)
            if terrain.isForest(pos[0], pos[1]) or terrain.isForest(u.x, u.y):
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
                if terrain.isForest(u.x, u.y) and _dist(u.x, u.y, near.x, near.y) < 160:
                    u.attackTarget = near
                else:
                    u.attackTarget = None
                    _moveToSafe(u, terrain, pos[0], pos[1])
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y))
            if _dist(u.x, u.y, near.x, near.y) < 160 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, ecx - 100, pcy + self._commitSide * 80)

    def _tCombinedArms(self, inf, cav, players, playerHq, enemyHq,
                       neutralOps, enemyOps, terrain, W, H):
        """Phased assault: tick 0-1 artillery prep, 2-3 infantry advance, 4+ cavalry charge."""
        pcx, pcy = _centroid(players)
        phase    = self._tacticTicks
        if phase <= 1:
            # Phase 1: hold everyone back, let artillery work
            hold_x = pcx + ARTILLERY_RANGE + 60
            _formationLine(inf, hold_x, pcy, terrain, spacing=48)
            for u in inf:
                u.attackTarget = None
            for u in cav:
                u.attackTarget = None
                _moveToSafe(u, terrain, hold_x + 40, pcy + self._commitSide * 100)
        elif phase <= 3:
            # Phase 2: infantry advances to engage
            _pairAttack(inf, players, terrain)
            for u in cav:
                u.attackTarget = None
                _moveToSafe(u, terrain, pcx + 120, H * 0.15 if self._commitSide < 0 else H * 0.85)
        else:
            # Phase 3: full combined assault, cavalry charges flanks
            _pairAttack(inf, players, terrain)
            weakest = min(players, key=lambda p: p.hp / p.maxHp + p.morale / 100)
            for u in cav:
                u.attackTarget = weakest
                _moveToSafe(u, terrain, weakest.x, weakest.y)

    # ── survival tactics ──────────────────────────────────────────────────────

    def _tDelayingAction(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """[SURVIVAL] Controlled stepwise retreat — fight only when cornered."""
        if not enemyHq:
            return
        rally_x = enemyHq.x - 160
        for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
            ty  = H * (i + 1) / (len(inf) + 1)
            pos = _bestHighGround(terrain, rally_x, ty, W, H, radius=130)
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 120:
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
                if enemyHq:
                    _moveToSafe(u, terrain, enemyHq.x - 140,
                                H * 0.3 if self._commitSide < 0 else H * 0.7)

    def _tContactAndFade(self, inf, cav, players, playerHq, enemyHq,
                         neutralOps, enemyOps, terrain, W, H):
        """[SURVIVAL] Quick strike then pull back, repeat — drain without commitment."""
        if not enemyHq:
            return
        pcx, pcy       = _centroid(players)
        self._fadePhase = not self._fadePhase
        if self._fadePhase:
            for u in inf:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near:
                    u.attackTarget = near
                    _moveToSafe(u, terrain, near.x + 30, near.y)
            for u in cav:
                near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
                if near and _terrainScore(terrain, u.x, u.y) >= 0:
                    u.attackTarget = near
                    _moveToSafe(u, terrain, near.x, near.y)
        else:
            rally_x = max(enemyHq.x - 220, pcx + 120)
            for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
                ty  = H * (i + 1) / (len(inf) + 1)
                pos = _bestHighGround(terrain, rally_x, ty, W, H, radius=100)
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
            for u in cav:
                u.attackTarget = None
                _moveToSafe(u, terrain, rally_x - 50,
                            H * 0.25 if self._commitSide < 0 else H * 0.75)

    def _tMobileSupplyBubble(self, inf, cav, players, playerHq, enemyHq,
                             neutralOps, enemyOps, terrain, W, H):
        """[SURVIVAL] Stay compact near own supply — recover morale, defend tightly."""
        if not enemyHq:
            return
        friendly_ops = [op for op in self.game.outposts if op.team == 'enemy']
        if friendly_ops and (inf + cav):
            cx, cy = _centroid(inf + cav)
            anchor = min(friendly_ops, key=lambda op: _dist(cx, cy, op.x, op.y))
            ax, ay = anchor.x, anchor.y
        else:
            ax, ay = enemyHq.x - 130, enemyHq.y
        for i, u in enumerate(sorted(inf, key=lambda u: u.y)):
            angle = math.pi * (i + 1) / (len(inf) + 1)
            rx    = ax - math.cos(angle) * 120
            ry    = ay + math.sin(angle) * 120
            pos   = _bestHighGround(terrain, rx, ry, W, H, radius=70)
            near  = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 160:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, pos[0], pos[1])
        for u in cav:
            near = min(players, key=lambda p: _dist(u.x, u.y, p.x, p.y)) if players else None
            if near and _dist(u.x, u.y, near.x, near.y) < 170 and _terrainScore(terrain, u.x, u.y) >= 0:
                u.attackTarget = near
            else:
                u.attackTarget = None
                _moveToSafe(u, terrain, ax - 180, ay + self._commitSide * 80)
