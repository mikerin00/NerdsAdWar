# Module: renderer
# RendererMixin — all screen drawing orchestration for the Game class

import math

import pygame

from src.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, MAP_WIDTH, MAP_HEIGHT,
    BG_COLOR, WHITE, BLACK, YELLOW, SELECTION_FILL,
    UNIT_COLORS, TERR_CLAIM_RADIUS, PLAYER_COLORS, EMOTE_TEXTS,
)
from src.game.renderer_draw import (
    chaikin, simplify, drawUnit, drawOutpost, drawHeadquarters,
)
from src.game.ai_log import aiLogRecent


_fontBig     = None
_fontBanner  = None

# Fog tint — sprite RGB matches so BLEND_RGBA_MIN only changes alpha,
# never darkens the RGB channels outside the vision disc.
_FOG_RGB = (235, 238, 243)

# Vision sprite cache: radius → SRCALPHA surface where alpha is 0 at the
# centre and ramps up to 255 at the edge. Blitted with BLEND_RGBA_MIN so
# each one "punches" a soft hole in the fog overlay.
_visionSprites = {}

def _getVisionSprite(radius):
    s = _visionSprites.get(radius)
    if s is not None:
        return s
    size = radius * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # Background stays opaque fog so rectangular corners don't punch holes;
    # the inner disc clears the alpha only.
    surf.fill((*_FOG_RGB, 255))
    cx, cy = size // 2, size // 2
    inner = max(1, int(radius * 0.70))   # fully clear inside this distance
    for r in range(radius, 0, -1):
        if r <= inner:
            a = 0
        else:
            t = (r - inner) / (radius - inner)
            a = int(255 * (t ** 1.4))   # ease-in: soft falloff
        pygame.draw.circle(surf, (*_FOG_RGB, a), (cx, cy), r)
    _visionSprites[radius] = surf
    return surf

# Per-source vision range in map pixels (MAP is 1920×1080).
_VISION_RANGE = {
    'infantry':       140,
    'heavy_infantry': 110,
    'cavalry':        200,
    'artillery':      160,
    'commander':      220,
    '_outpost':       240,
    '_hq':            280,
}

def _getBigFont():
    global _fontBig
    if _fontBig is None:
        _fontBig = pygame.font.SysFont(None, 42)
    return _fontBig

def _getBannerFont():
    global _fontBanner
    if _fontBanner is None:
        _fontBanner = pygame.font.SysFont(None, 80)
    return _fontBanner


class RendererMixin:
    def _getMapSurface(self):
        """Lazy-create a map-sized offscreen surface for world-space drawing."""
        if not hasattr(self, '_mapSurf') or self._mapSurf is None:
            self._mapSurf = pygame.Surface((self.mapWidth, self.mapHeight))
        return self._mapSurf

    def _draw(self):
        ms    = self._getMapSurface()
        scale = self._mapScale

        ms.fill(BG_COLOR)
        if self.terrain.surface:
            ms.blit(self.terrain.surface, (0, 0))
        self._drawSquares(ms)
        self._drawOrders(ms)
        self._drawTerritoryBorder(ms)
        for op in self.outposts:
            drawOutpost(ms, op)
        for hq in self.headquarters:
            drawHeadquarters(ms, hq)
        for u in self.units:
            u._drawColor = self.colorForUnit(u)
            drawUnit(ms, u)
        for p in self.projectiles:
            p.draw(ms)
        for e in self.effects:
            e.draw(ms)
        # Fog overlay: hides enemy units/projectiles in unseen areas. Drawn
        # AFTER everything in-world so it covers them, BEFORE the tactical
        # overlays (battleplans/pings) so player commands stay visible.
        if self.gamemode == 'FOG':
            self._drawFog(ms)
        if self.selRect and self.selRect.width > 2:
            surf = pygame.Surface((self.selRect.width, self.selRect.height), pygame.SRCALPHA)
            surf.fill(SELECTION_FILL)
            ms.blit(surf, (self.selRect.x, self.selRect.y))
            pygame.draw.rect(ms, YELLOW, self.selRect, 2)

        self._drawBattleplans(ms)
        self._drawPings(ms)

        # Scale map surface to screen (scale is faster than smoothscale for real-time)
        scaledW = int(self.mapWidth  * scale)
        scaledH = int(self.mapHeight * scale)
        self.screen.fill((0, 0, 0))
        if scaledW == self.mapWidth and scaledH == self.mapHeight:
            scaled = ms   # native resolution — no scaling needed
        else:
            scaled = pygame.transform.scale(ms, (scaledW, scaledH))
        # Centre on screen
        ox = (SCREEN_WIDTH  - scaledW) // 2
        oy = (SCREEN_HEIGHT - scaledH) // 2
        self.screen.blit(scaled, (ox, oy))

        # UI drawn directly on screen (not scaled)
        self._drawUi()
        if getattr(self, 'showAiLog', False):
            self._drawAiLog()
        if self.freezeTimer > 0:
            self._drawPlanningOverlay()
        pygame.display.flip()

    def _computeTerritoryBoundary(self):
        CELL = 14
        gw   = self.mapWidth  // CELL + 2
        gh   = self.mapHeight // CELL + 2

        pSrc  = [(h.x, h.y) for h in self.headquarters if h.team == 'player']
        pSrc += [(o.x, o.y) for o in self.outposts    if o.team == 'player']
        eSrc  = [(h.x, h.y) for h in self.headquarters if h.team == 'enemy']
        eSrc += [(o.x, o.y) for o in self.outposts    if o.team == 'enemy']

        grid = {}
        for gy in range(gh):
            for gx in range(gw):
                cx, cy = gx * CELL, gy * CELL
                if pSrc and min(math.hypot(cx - sx, cy - sy) for sx, sy in pSrc) <= TERR_CLAIM_RADIUS:
                    grid[(gx, gy)] = 'P'
                elif eSrc and min(math.hypot(cx - sx, cy - sy) for sx, sy in eSrc) <= TERR_CLAIM_RADIUS:
                    grid[(gx, gy)] = 'E'
                else:
                    grid[(gx, gy)] = 'N'

        open_n = set()
        border_seeds = (
            [(0, gy) for gy in range(gh)] + [(gw - 1, gy) for gy in range(gh)] +
            [(gx, 0) for gx in range(gw)] + [(gx, gh - 1) for gx in range(gw)]
        )
        queue = [c for c in border_seeds if grid.get(c) == 'N']
        for c in queue:
            open_n.add(c)
        head = 0
        while head < len(queue):
            gx, gy = queue[head]; head += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (gx + dx, gy + dy)
                if nb not in open_n and grid.get(nb) == 'N':
                    open_n.add(nb)
                    queue.append(nb)

        for key, val in grid.items():
            if val == 'N' and key not in open_n:
                gx, gy = key
                cx, cy = gx * CELL, gy * CELL
                dp = min(math.hypot(cx - sx, cy - sy) for sx, sy in pSrc) if pSrc else float('inf')
                de = min(math.hypot(cx - sx, cy - sy) for sx, sy in eSrc) if eSrc else float('inf')
                grid[key] = 'P' if dp <= de else 'E'

        self._terrGrid     = grid
        self._terrGridCELL = CELL

        def _frontierLine(team):
            pts = []
            for gy in range(gh):
                if team == 'P':
                    for gx in range(gw - 1, -1, -1):
                        if grid.get((gx, gy)) == 'P':
                            pts.append(((gx + 1) * CELL, int((gy + 0.5) * CELL)))
                            break
                else:
                    for gx in range(gw):
                        if grid.get((gx, gy)) == 'E':
                            pts.append((gx * CELL, int((gy + 0.5) * CELL)))
                            break
            if len(pts) < 2:
                return []
            dx = pts[1][0] - pts[0][0]
            dy = pts[1][1] - pts[0][1]
            if abs(dy) > 0.01:
                t = -pts[0][1] / dy
                pts.insert(0, (pts[0][0] + dx * t, 0))
            dx = pts[-1][0] - pts[-2][0]
            dy = pts[-1][1] - pts[-2][1]
            if abs(dy) > 0.01:
                t = (self.mapHeight - pts[-1][1]) / dy
                pts.append((pts[-1][0] + dx * t, self.mapHeight))
            pts = simplify(pts)
            for _ in range(6):
                pts = chaikin(pts)
            return pts

        self._terrBoundary = {
            'player':  [_frontierLine('P')] if pSrc else [],
            'enemy':   [_frontierLine('E')] if eSrc else [],
            'contact': [],
        }

    def _drawTerritoryBorder(self, surf):
        self._terrTimer += 1
        if self._terrTimer % 15 == 0:
            self._computeTerritoryBoundary()
        for chain in self._terrBoundary.get('player', []):
            if len(chain) >= 2:
                pygame.draw.lines(surf, (70, 130, 180), False, chain, 3)
        for chain in self._terrBoundary.get('enemy', []):
            if len(chain) >= 2:
                pygame.draw.lines(surf, (220, 80, 80), False, chain, 3)
        for chain in self._terrBoundary.get('contact', []):
            if len(chain) >= 2:
                pygame.draw.lines(surf, (150, 110, 75), False, chain, 3)

    def _drawSquares(self, surf):
        for team in ('player', 'enemy'):
            sq = [u for u in self.units if u.team == team and u.inSquare and u.unitType == 'infantry']
            if len(sq) < 3:
                continue
            cx = sum(u.x for u in sq) / len(sq)
            cy = sum(u.y for u in sq) / len(sq)
            sq.sort(key=lambda u: math.atan2(u.y - cy, u.x - cx))
            pts   = [(int(u.x), int(u.y)) for u in sq]
            color = (255, 165, 0) if team == 'player' else (255, 80, 80)
            # Use a bounding-box crop instead of a full-map alpha surface
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            bx, by = max(0, min(xs) - 4), max(0, min(ys) - 4)
            bw = min(self.mapWidth  - bx, max(xs) - min(xs) + 8)
            bh = min(self.mapHeight - by, max(ys) - min(ys) + 8)
            fill = pygame.Surface((bw, bh), pygame.SRCALPHA)
            shifted = [(p[0] - bx, p[1] - by) for p in pts]
            pygame.draw.polygon(fill, (*color, 25), shifted)
            surf.blit(fill, (bx, by))
            pygame.draw.polygon(surf, color, pts, 3)

    def _drawOrders(self, surf):
        if len(self.formPath) >= 2:
            pygame.draw.lines(surf, (255, 220, 50), False, self.formPath, 2)
            for pt in self.formPath[::max(len(self.formPath) // 10, 1)]:
                pygame.draw.circle(surf, (255, 220, 50), pt, 3)

        if len(self.patrolPath) >= 2:
            pts = [(int(x), int(y)) for x, y in self.patrolPath]
            pygame.draw.lines(surf, (80, 220, 255), False, pts, 2)
            # Arrow-head at the end to show direction
            ex, ey = pts[-1]
            pygame.draw.circle(surf, (80, 220, 255), (ex, ey), 5)
            for pt in pts[::max(len(pts) // 10, 1)]:
                pygame.draw.circle(surf, (80, 220, 255), pt, 3)

        # Draw assigned patrol paths for selected units (dashed cyan)
        for u in self.selectedUnits:
            if len(u.patrolPath) >= 2:
                pts = [(int(x), int(y)) for x, y in u.patrolPath]
                pygame.draw.lines(surf, (60, 180, 220), False, pts, 1)
                # Mark current target on path
                cx, cy = int(u.patrolPath[u._patrolIdx][0]), int(u.patrolPath[u._patrolIdx][1])
                pygame.draw.circle(surf, (60, 220, 180), (cx, cy), 5, 2)

        # Teammate unit destinations — visible in any team mode (2v2/COOP/3v3/4v4)
        if self.matchMode in ('2v2', 'COOP', '3v3', '4v4'):
            ALLY_COLOR = (120, 220, 140)   # soft green, distinct from own yellow
            for u in self.units:
                if u.team != self.mySide:
                    continue
                if u.controller == self.mySlot:
                    continue
                dist = math.hypot(u.targetX - u.x, u.targetY - u.y)
                if dist > 10 and not (u.attackTarget and u.attackTarget.hp > 0):
                    tx, ty = int(u.targetX), int(u.targetY)
                    size = 5
                    pygame.draw.line(surf, ALLY_COLOR, (tx - size, ty - size), (tx + size, ty + size), 2)
                    pygame.draw.line(surf, ALLY_COLOR, (tx + size, ty - size), (tx - size, ty + size), 2)

        attackTargets = {}
        for u in self.selectedUnits:
            if u.attackTarget and u.attackTarget.hp > 0:
                attackTargets.setdefault(u.attackTarget, []).append(u)
            elif not u.patrolPath:
                tx, ty = int(u.targetX), int(u.targetY)
                dist   = math.hypot(u.targetX - u.x, u.targetY - u.y)
                if dist > 10:
                    pygame.draw.line(surf, (200, 200, 100), (int(u.x), int(u.y)), (tx, ty), 1)
                    size = 6
                    pygame.draw.line(surf, YELLOW, (tx - size, ty - size), (tx + size, ty + size), 2)
                    pygame.draw.line(surf, YELLOW, (tx + size, ty - size), (tx - size, ty + size), 2)

        for target, attackers in attackTargets.items():
            tx, ty = int(target.x), int(target.y)
            pygame.draw.circle(surf, (255, 80,  0), (tx, ty), target.radius + 8,  2)
            pygame.draw.circle(surf, (255, 150, 0), (tx, ty), target.radius + 13, 1)
            for u in attackers:
                pygame.draw.line(surf, (255, 100, 0), (int(u.x), int(u.y)), (tx, ty), 1)

    def _drawUi(self):
        self._drawScoreboard()
        if getattr(self, '_emoteBarOpen', False):
            self._drawEmoteBar()
        if self.selectedUnits:
            txt = self.font.render(f"Selected: {len(self.selectedUnits)}", True, WHITE)
            self.screen.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, 10))
        hint = self.font.render(
            "LMB: select | RMB: move/attack | Shift+RMB: formation | F: square | "
            "1-4: cat. | V: ping | B+drag: plan | T+1-6: emote | L: AI log",
            True, (200, 200, 200))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 28))
        # Legend shows the LOCAL player's own color per unit type — matches
        # whatever you picked in the lobby.
        mySlot = getattr(self, 'mySlot', 0)
        class _StubUnit:
            def __init__(self, ut):
                self.unitType   = ut
                self.team       = 'player'     # used only as fallback in SP
                self.controller = mySlot
        legend = [
            ("Infantry",  self.colorForUnit(_StubUnit('infantry'))),
            ("Cavalry",   self.colorForUnit(_StubUnit('cavalry'))),
            ("Artillery", self.colorForUnit(_StubUnit('artillery'))),
        ]
        for i, (label, color) in enumerate(legend):
            self.screen.blit(self.font.render(label, True, color), (10 + i * 130, SCREEN_HEIGHT - 55))
        # Gamemode-specific HUD
        if self.gamemode == 'LAST_STAND':
            self._drawLastStandHud()
        elif self.gamemode == 'ASSAULT':
            self._drawAssaultHud()
        elif self.gamemode == 'COMMANDER':
            self._drawCommanderHud()
        elif self.gamemode == 'CONQUEST':
            self._drawConquestHud()

        if self.winner is not None:
            if self.gamemode == 'LAST_STAND' and self.winner == 'enemy':
                self._drawBanner(f"WAVE {self._waveNumber} — FALLEN", (255, 120, 80))
            elif self.winner == self.mySide:
                self._drawBanner("YOU WIN!",  (100, 255, 100))
            else:
                self._drawBanner("YOU LOSE!", (255, 100, 100))

        if getattr(self, '_battleBannerFrames', 0) > 0:
            self._drawBattleStartBanner()

    def _drawPlanningOverlay(self):
        secs = math.ceil(self.freezeTimer / 60)
        cx   = SCREEN_WIDTH // 2

        # Top banner strip
        bar = pygame.Surface((SCREEN_WIDTH, 58), pygame.SRCALPHA)
        bar.fill((12, 20, 8, 185))
        self.screen.blit(bar, (0, 0))

        # Gold separator lines
        pygame.draw.line(self.screen, (168, 110, 50), (0, 57), (SCREEN_WIDTH, 57), 1)
        pygame.draw.line(self.screen, (205, 145, 75), (0, 58), (SCREEN_WIDTH, 58), 1)

        # Main label
        font_big = _getBigFont()
        label    = "PLANNING PHASE"
        lw       = font_big.size(label)[0]
        # Shadow
        sh = font_big.render(label, True, (0, 0, 0))
        self.screen.blit(sh, (cx - lw // 2 + 2, 9))
        tx = font_big.render(label, True, (255, 225, 80))
        self.screen.blit(tx, (cx - lw // 2, 7))

        # Countdown badge
        badge_w = 54
        bx      = cx + lw // 2 + 14
        pygame.draw.rect(self.screen, (168, 110, 50),
                         (bx, 6, badge_w, 32), border_radius=5)
        pygame.draw.rect(self.screen, (255, 220, 80),
                         (bx, 6, badge_w, 32), 1, border_radius=5)
        cd = _getBigFont().render(f"{secs}s", True, (15, 25, 10))
        self.screen.blit(cd, (bx + badge_w // 2 - cd.get_width() // 2, 9))

        # Sub-hint
        hint_f = pygame.font.SysFont(None, 22)
        ready  = hint_f.render("Give your troops a target   ·   [SPACE] Ready!", True,
                               (160, 210, 140))
        self.screen.blit(ready, (cx - ready.get_width() // 2, 38))

    def _drawAiLog(self):
        entries = aiLogRecent(18)
        if not entries:
            return
        ai  = getattr(self, 'ai', None)
        lh  = 18
        pad = 8
        panelH = (len(entries) + 2) * lh + pad * 2
        panelW = 520
        px, py = SCREEN_WIDTH - panelW - 10, 40
        bg = pygame.Surface((panelW, panelH), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        self.screen.blit(bg, (px, py))
        logFont = pygame.font.SysFont('consolas', 14)
        # Header: biome + personality + tactic
        hdr = ""
        if ai:
            mode  = "SURVIVAL" if ai._survivalMode else "NORMAL"
            biome = getattr(self.terrain, 'biome', '?')
            hdr   = f"[{biome}]  [{ai._personality}]  {ai._tactic}  ({mode})"
        hdrSurf = logFont.render(hdr, True, (255, 220, 100))
        self.screen.blit(hdrSurf, (px + pad, py + pad))
        pygame.draw.line(self.screen, (255, 220, 100, 120),
                         (px + pad, py + pad + lh), (px + panelW - pad, py + pad + lh))
        # Log entries
        for i, (frame, msg) in enumerate(entries):
            secs = frame / 60
            txt  = f"{secs:6.1f}s  {msg}"
            if len(txt) > 68:
                txt = txt[:65] + "..."
            color = (200, 200, 200)
            if 'SURVIVAL' in msg or 'FALLBACK' in msg: color = (255, 100, 100)
            elif 'SWITCH' in msg:                       color = (100, 200, 255)
            elif 'DODGE' in msg or 'RETREAT' in msg:    color = (255, 200, 80)
            elif 'PULLBACK' in msg:                     color = (180, 255, 180)
            elif 'COUNTER' in msg:                      color = (255, 160, 255)
            surf = logFont.render(txt, True, color)
            self.screen.blit(surf, (px + pad, py + pad + (i + 2) * lh))

    def _drawLastStandHud(self):
        cx   = SCREEN_WIDTH // 2
        font = _getBigFont()

        # Wave badge (top centre, below unit counts)
        wave_label = f"WAVE  {self._waveNumber}" if self._waveNumber > 0 else "WAVE  —"
        wave_txt   = font.render(wave_label, True, (255, 200, 80))
        self.screen.blit(wave_txt, (cx - wave_txt.get_width() // 2, 32))

        if self.winner is not None or self.freezeTimer > 0:
            return

        enemies = [u for u in self.units if u.team == 'enemy']
        if self._waveNumber == 0:
            remaining = max(0, self._FIRST_WAVE - self._waveTimer)
            secs      = math.ceil(remaining / 60)
            cd_txt    = self.font.render(f"First wave in: {secs}s", True, (220, 180, 100))
            self.screen.blit(cd_txt, (cx - cd_txt.get_width() // 2, 72))
        elif enemies:
            # Wave in progress — show enemy count
            cd_txt = self.font.render(f"Enemies remaining: {len(enemies)}", True, (255, 140, 80))
            self.screen.blit(cd_txt, (cx - cd_txt.get_width() // 2, 72))
        else:
            # Wave cleared — countdown to next
            remaining = max(0, self._INTER_WAVE - self._waveTimer)
            secs      = math.ceil(remaining / 60)
            cd_txt    = self.font.render(f"Wave cleared!  Next in: {secs}s", True, (120, 220, 120))
            self.screen.blit(cd_txt, (cx - cd_txt.get_width() // 2, 72))

    def _drawAssaultHud(self):
        """Show how many keypoints + the HQ are still in enemy hands."""
        cx     = SCREEN_WIDTH // 2
        font   = self.font
        kps    = [op for op in self.outposts if op.strategic]
        taken  = sum(1 for op in kps if op.team == 'player')
        total  = len(kps)
        enemyHq = next((h for h in self.headquarters if h.team == 'enemy'), None)
        hq_taken = bool(enemyHq and enemyHq.captured)

        title = "★ Capture Objectives"
        self.screen.blit(font.render(title, True, (220, 190, 60)),
                         (cx - font.size(title)[0] // 2, 14))

        # One pip per keypoint + one for the HQ
        pip_r = 9
        gap   = 28
        n     = total + 1
        start_x = cx - (n - 1) * gap // 2
        py      = 38
        for i, op in enumerate(kps):
            color = (90, 170, 235) if op.team == 'player' else (220, 80, 80)
            pygame.draw.circle(self.screen, color, (start_x + i * gap, py), pip_r)
            pygame.draw.circle(self.screen, (30, 30, 30), (start_x + i * gap, py), pip_r, 2)
        # HQ pip (square so it stands out)
        hq_color = (90, 170, 235) if hq_taken else (180, 50, 50)
        hx = start_x + total * gap
        pygame.draw.rect(self.screen, hq_color, (hx - pip_r, py - pip_r, pip_r * 2, pip_r * 2))
        pygame.draw.rect(self.screen, (30, 30, 30),
                         (hx - pip_r, py - pip_r, pip_r * 2, pip_r * 2), 2)

        score = f"Outposts: {taken}/{total}   HQ: {'✓' if hq_taken else '✗'}"
        score_surf = font.render(score, True, (220, 210, 170))
        self.screen.blit(score_surf, (cx - score_surf.get_width() // 2, py + pip_r + 6))

    def _drawCommanderHud(self):
        """Show HP bars for both commanders so players track their objective."""
        GOLD = (218, 165, 32)
        cx   = SCREEN_WIDTH // 2
        font = self.font

        title = "♛  Hunt the Commander"
        self.screen.blit(font.render(title, True, GOLD),
                         (cx - font.size(title)[0] // 2, 10))

        player_cmd = next((u for u in self.units
                           if u.team == 'player' and u.unitType == 'commander'), None)
        enemy_cmd  = next((u for u in self.units
                           if u.team == 'enemy'  and u.unitType == 'commander'), None)

        bar_w, bar_h = 160, 14
        for cmd, label, bx, color in [
            (player_cmd, "Your CMD",  cx - bar_w - 20, (80, 140, 220)),
            (enemy_cmd,  "Enemy CMD", cx + 20,         (220, 70,  70)),
        ]:
            by = 30
            self.screen.blit(font.render(label, True, color), (bx, by - 16))
            pygame.draw.rect(self.screen, (50, 50, 50),  (bx, by, bar_w, bar_h))
            if cmd:
                frac = max(0.0, cmd.hp / cmd.maxHp)
                pygame.draw.rect(self.screen, color, (bx, by, int(bar_w * frac), bar_h))
                hp_txt = font.render(f"{int(cmd.hp)}/{cmd.maxHp}", True, (230, 230, 230))
                self.screen.blit(hp_txt, (bx + bar_w // 2 - hp_txt.get_width() // 2,
                                          by + 1))
            else:
                dead = font.render("FALLEN", True, (255, 80, 80))
                self.screen.blit(dead, (bx + bar_w // 2 - dead.get_width() // 2, by + 1))
            pygame.draw.rect(self.screen, GOLD, (bx, by, bar_w, bar_h), 1)

    def _drawConquestHud(self):
        """Score bars + outpost ownership for Conquest mode."""
        cx   = SCREEN_WIDTH // 2
        font = self.font
        WIN  = self._CONQUEST_WIN
        p_sc = min(WIN, self._conquestScore.get('player', 0))
        e_sc = min(WIN, self._conquestScore.get('enemy',  0))

        title = "⚑  Conquest"
        self.screen.blit(font.render(title, True, (200, 180, 60)),
                         (cx - font.size(title)[0] // 2, 8))

        bar_w, bar_h = 180, 12
        bar_y  = 30
        gap    = 16

        # Player bar (left of centre)
        bx = cx - bar_w - gap
        pygame.draw.rect(self.screen, (30, 30, 30),   (bx, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, (60, 110, 200),
                         (bx, bar_y, int(bar_w * p_sc / WIN), bar_h))
        pygame.draw.rect(self.screen, (100, 150, 255), (bx, bar_y, bar_w, bar_h), 1)
        ps = font.render(str(int(p_sc)), True, (180, 210, 255))
        self.screen.blit(ps, (bx - ps.get_width() - 5, bar_y - 1))

        # Win threshold
        mid = font.render(f"/ {WIN}", True, (160, 150, 120))
        self.screen.blit(mid, (cx - mid.get_width() // 2, bar_y - 1))

        # Enemy bar (right of centre)
        ex = cx + gap
        pygame.draw.rect(self.screen, (30, 30, 30),   (ex, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, (200, 60, 60),
                         (ex, bar_y, int(bar_w * e_sc / WIN), bar_h))
        pygame.draw.rect(self.screen, (255, 100, 100), (ex, bar_y, bar_w, bar_h), 1)
        es = font.render(str(int(e_sc)), True, (255, 170, 170))
        self.screen.blit(es, (ex + bar_w + 5, bar_y - 1))

        # Outpost ownership summary
        p_ops  = sum(1 for op in self.outposts if op.team == 'player')
        e_ops  = sum(1 for op in self.outposts if op.team == 'enemy')
        n_ops  = len(self.outposts) - p_ops - e_ops
        ops    = font.render(
            f"Outposts — You: {p_ops}  ·  Enemy: {e_ops}  ·  Neutral: {n_ops}",
            True, (210, 200, 170))
        self.screen.blit(ops, (cx - ops.get_width() // 2, bar_y + bar_h + 4))

    def _drawBanner(self, text, color):
        font = _getBannerFont()
        cx   = SCREEN_WIDTH  // 2
        cy   = SCREEN_HEIGHT // 2
        tw   = font.size(text)[0]
        th   = font.size(text)[1]
        pad  = 28

        # Dark backing panel with colored border
        bg = pygame.Surface((tw + pad * 2, th + pad), pygame.SRCALPHA)
        bg.fill((8, 12, 6, 210))
        self.screen.blit(bg, (cx - tw // 2 - pad, cy - th // 2 - pad // 2))
        pygame.draw.rect(self.screen, color,
                         (cx - tw // 2 - pad, cy - th // 2 - pad // 2,
                          tw + pad * 2, th + pad), 2)

        # Shadow + text
        sh = font.render(text, True, (0, 0, 0))
        self.screen.blit(sh, (cx - tw // 2 + 3, cy - th // 2 + 3))
        tx = font.render(text, True, color)
        self.screen.blit(tx, (cx - tw // 2, cy - th // 2))

    def _drawBattleplans(self, ms):
        """Translucent arrows teammates can draw to plan attacks (B + drag).
        Drawn on a per-arrow SRCALPHA layer so they don't smear over units."""
        if not getattr(self, 'battleplans', None) and \
           not getattr(self, '_planDragStart', None):
            return
        # Draw committed arrows
        for bp in self.battleplans:
            if not self._battleplanVisibleToMe(bp):
                continue
            color = self._pingColorForSlot(bp['fromSlot'])
            self._drawArrow(ms, bp['x1'], bp['y1'], bp['x2'], bp['y2'],
                            color, alpha=120)
        # Live drag preview (the player drawing right now)
        drag = getattr(self, '_planDragStart', None)
        if drag is not None:
            mx, my = self._screenToMap(*pygame.mouse.get_pos())
            color = self._pingColorForSlot(getattr(self, 'mySlot', 0))
            self._drawArrow(ms, drag[0], drag[1], mx, my, color, alpha=180)

    def _battleplanVisibleToMe(self, bp):
        """Same team-only visibility rule as pings."""
        if self.netRole is None:
            return True
        return self._slotSide(bp['fromSlot']) == self.mySide

    def _drawArrow(self, ms, x1, y1, x2, y2, color, alpha=140):
        """Draw a thick translucent line + arrowhead from (x1,y1) to (x2,y2)."""
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 4:
            return
        # Translucent layer covering just the bbox to keep alpha cheap.
        pad = 18
        minx = int(min(x1, x2) - pad);  miny = int(min(y1, y2) - pad)
        maxx = int(max(x1, x2) + pad);  maxy = int(max(y1, y2) + pad)
        w, h = maxx - minx, maxy - miny
        if w <= 0 or h <= 0:
            return
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        rgba  = (*color, alpha)
        sx, sy = x1 - minx, y1 - miny
        ex, ey = x2 - minx, y2 - miny
        # Shaft
        pygame.draw.line(layer, rgba, (sx, sy), (ex, ey), 6)
        # Arrowhead — triangle at the tip
        ux, uy = dx / length, dy / length
        # Perpendicular
        px, py = -uy, ux
        head = 16
        side = 9
        bx = ex - ux * head
        by = ey - uy * head
        pts = [
            (ex, ey),
            (bx + px * side, by + py * side),
            (bx - px * side, by - py * side),
        ]
        pygame.draw.polygon(layer, rgba, pts)
        ms.blit(layer, (minx, miny))

    def _drawPings(self, ms):
        """Draw active map-pings (team-only). Outer ring expands+fades over
        the first 30 frames, inner dot pulses for the remaining lifetime."""
        if not self.pings:
            return
        full = self._PING_LIFE
        for pg in self.pings:
            if not self._pingVisibleToMe(pg):
                continue
            elapsed = full - pg['life']
            slot    = pg['fromSlot']
            color   = self._pingColorForSlot(slot)
            x, y    = int(pg['x']), int(pg['y'])
            # Expanding outer ring (first 30 frames only)
            if elapsed < 30:
                t = elapsed / 30.0
                r = int(8 + 28 * t)
                a = int(220 * (1.0 - t))
                ring = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (*color, a),
                                   (r + 2, r + 2), r, 3)
                ms.blit(ring, (x - r - 2, y - r - 2))
            # Inner pulsing dot (full life)
            pulse = 4 + int(2 * abs(math.sin(elapsed * 0.25)))
            pygame.draw.circle(ms, color, (x, y), pulse)
            pygame.draw.circle(ms, (20, 20, 20), (x, y), pulse, 1)

    def _pingColorForSlot(self, slot):
        """Use the slot's lobby colour so teammates can tell who pinged."""
        if (0 <= slot < len(getattr(self, 'slotColors', []))):
            idx = self.slotColors[slot]
            if 0 <= idx < len(PLAYER_COLORS):
                return PLAYER_COLORS[idx][1]
        return (255, 220, 90)   # neutral yellow fallback

    def _drawBattleStartBanner(self):
        """One-shot banner near the top: fades in over the first 15 frames,
        holds, then fades out over the last 30."""
        total  = self._BATTLE_BANNER_TOTAL
        frames = self._battleBannerFrames
        elapsed = total - frames
        if elapsed < 15:
            alpha = int(255 * (elapsed / 15))
        elif frames < 30:
            alpha = int(255 * (frames / 30))
        else:
            alpha = 255
        text = "THE BATTLE HAS BEGUN"
        font = _getBigFont()
        surf = font.render(text, True, (255, 220, 90))
        # Slight dark backing strip so it reads on busy terrain
        bx = SCREEN_WIDTH // 2 - surf.get_width() // 2
        by = 60
        bg = pygame.Surface((surf.get_width() + 40, surf.get_height() + 16),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, int(alpha * 0.55)))
        self.screen.blit(bg, (bx - 20, by - 8))
        surf.set_alpha(alpha)
        self.screen.blit(surf, (bx, by))

    def _drawFog(self, ms):
        """Draw an opaque dark layer over the whole map, then 'punch' soft
        circular holes around every friendly vision source (own units,
        captured outposts, own HQ). What's left covered is foggy and hides
        enemy units underneath."""
        fog = getattr(self, '_fogSurf', None)
        if fog is None or fog.get_size() != (self.mapWidth, self.mapHeight):
            fog = pygame.Surface((self.mapWidth, self.mapHeight),
                                 pygame.SRCALPHA)
            self._fogSurf = fog
        # Full-opacity off-white mist — outside vision you see absolutely
        # nothing through it. Soft edges come from the vision sprite blend.
        fog.fill((*_FOG_RGB, 255))

        my_side = self.mySide

        def _punch(x, y, r):
            sprite = _getVisionSprite(r)
            fog.blit(sprite, (int(x) - r - 1, int(y) - r - 1),
                     special_flags=pygame.BLEND_RGBA_MIN)

        for u in self.units:
            if u.team != my_side:
                continue
            r = _VISION_RANGE.get(u.unitType, 130)
            _punch(u.x, u.y, r)
        for op in self.outposts:
            # Use the same team-mapping the rest of the renderer relies on
            if getattr(op, 'team', None) == my_side:
                _punch(op.x, op.y, _VISION_RANGE['_outpost'])
        for hq in self.headquarters:
            if hq.team == my_side:
                _punch(hq.x, hq.y, _VISION_RANGE['_hq'])

        ms.blit(fog, (0, 0))

    def _gatherScoreRows(self):
        """Return [(label, base_color, counts_dict, is_me), ...] for the
        scoreboard. One row per side in single-player, one per active slot
        in multiplayer."""
        empty = lambda: {'infantry': 0, 'heavy_infantry': 0,
                         'cavalry': 0, 'artillery': 0}
        rows = []
        if self.netRole is None:
            for team in ('player', 'enemy'):
                counts = empty()
                for u in self.units:
                    if u.team == team and u.unitType in counts:
                        counts[u.unitType] += 1
                label = 'You' if team == self.mySide else 'Enemy'
                color = UNIT_COLORS[team]['infantry']
                rows.append((label, color, counts, team == self.mySide))
            return rows
        active = self._activeSlots()
        for slot in active:
            counts = empty()
            for u in self.units:
                if (getattr(u, 'controller', -1) == slot
                        and u.unitType in counts):
                    counts[u.unitType] += 1
            idx   = (self.slotColors[slot]
                     if 0 <= slot < len(self.slotColors) else 0)
            color = (PLAYER_COLORS[idx][1]
                     if 0 <= idx < len(PLAYER_COLORS)
                     else UNIT_COLORS['player']['infantry'])
            name = (self.slotNames[slot]
                    if 0 <= slot < len(self.slotNames) else '') or ''
            if not name:
                name = f'Player {slot + 1}'
            if slot in getattr(self, 'botSlots', set()):
                name += ' (AI)'
            rows.append((name, color, counts, slot == self.mySlot))
        return rows

    def _drawScoreboard(self):
        rows = self._gatherScoreRows()
        if not rows:
            return
        row_h, pad = 26, 10
        w          = 310
        h          = pad * 2 + row_h * len(rows)
        x          = SCREEN_WIDTH - w - 12
        y          = 12

        # Parchment-style panel
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((238, 228, 208, 210))
        self.screen.blit(panel, (x, y))
        # Copper double border
        pygame.draw.rect(self.screen, (168, 110, 50), (x, y, w, h), 2)
        pygame.draw.rect(self.screen, (205, 145, 75), (x + 2, y + 2, w - 4, h - 4), 1)

        # Map each emote to the slot/team it came from for placement next
        # to the right scoreboard row.
        emote_for_slot = {em['fromSlot']: em for em in getattr(self, 'emotes', [])}
        emote_for_team = {}     # SP fallback: {'player': em, 'enemy': em}
        for em in getattr(self, 'emotes', []):
            side = self._slotSide(em['fromSlot']) if self.netRole else 'player'
            emote_for_team[side] = em

        for i, (label, color, counts, is_me) in enumerate(rows):
            ry = y + pad + i * row_h
            # Highlight row for local player
            if is_me:
                hl = pygame.Surface((w - 6, row_h - 2), pygame.SRCALPHA)
                hl.fill((168, 110, 50, 45))
                self.screen.blit(hl, (x + 3, ry))
            # Color dot with outline
            pygame.draw.circle(self.screen, color, (x + 15, ry + 12), 8)
            pygame.draw.circle(self.screen, (25, 25, 25), (x + 15, ry + 12), 8, 1)
            if is_me:
                pygame.draw.circle(self.screen, (255, 230, 80), (x + 15, ry + 12), 9, 1)
            name_col = (30, 20, 10) if is_me else (50, 40, 30)
            name_fnt = pygame.font.SysFont('georgia', 14, bold=is_me)
            name_txt = label if len(label) <= 14 else label[:13] + '…'
            self.screen.blit(
                name_fnt.render(name_txt, True, name_col), (x + 30, ry + 4))
            inf   = counts['infantry'] + counts['heavy_infantry']
            cav   = counts['cavalry']
            art   = counts['artillery']
            total = inf + cav + art
            self._drawTroopBreakdown(x + w - 10, ry + 10,
                                     inf, cav, art, total, color)

            # Emote bubble — left of the panel so it doesn't sit on the icons.
            slot_for_row = self._slotForRow(i, rows)
            em = (emote_for_slot.get(slot_for_row)
                  or (emote_for_team.get('player' if i == 0 else 'enemy')
                      if self.netRole is None else None))
            if em:
                self._drawEmoteBubble(x - 6, ry + 10, em)

    def _drawTroopBreakdown(self, right_x, mid_y, inf, cav, art, total, color):
        """Render `<icon> N` triplets right-aligned at (right_x, mid_y),
        followed by a parenthesised total. Icons match the in-world unit
        shapes: circle = infantry, triangle = cavalry, square = artillery."""
        cnt_col = (220, 220, 220)
        total_surf = self.font.render(f"({total:>2})", True, cnt_col)
        right_x -= total_surf.get_width()
        self.screen.blit(total_surf, (right_x, mid_y - 8))
        right_x -= 12   # gap before the icons

        def _paint(kind, n):
            nonlocal right_x
            num = self.font.render(f"{n:>2}", True, cnt_col)
            right_x -= num.get_width()
            self.screen.blit(num, (right_x, mid_y - 8))
            right_x -= 14
            ix, iy = right_x + 4, mid_y
            if kind == 'inf':
                pygame.draw.circle(self.screen, color,        (ix, iy), 5)
                pygame.draw.circle(self.screen, (20, 20, 20), (ix, iy), 5, 1)
            elif kind == 'cav':
                pts = [(ix - 5, iy + 4), (ix + 5, iy), (ix - 5, iy - 4)]
                pygame.draw.polygon(self.screen, color,        pts)
                pygame.draw.polygon(self.screen, (20, 20, 20), pts, 1)
            else:  # 'art'
                rect = pygame.Rect(ix - 5, iy - 5, 10, 10)
                pygame.draw.rect(self.screen, color,        rect)
                pygame.draw.rect(self.screen, (20, 20, 20), rect, 1)
            right_x -= 6

        _paint('art', art)
        _paint('cav', cav)
        _paint('inf', inf)

    def _slotForRow(self, row_idx, rows):
        """Map a scoreboard row index back to the slot index it represents.
        SP rows aren't bound to a slot, return -1."""
        if self.netRole is None:
            return -1
        active = self._activeSlots()
        return active[row_idx] if row_idx < len(active) else -1

    def _drawEmoteBar(self):
        """Strip of 6 emote slots near the bottom centre — visible while T
        is held. Press 1..6 to send the corresponding emote."""
        items = EMOTE_TEXTS
        cell_w, cell_h, gap = 80, 36, 6
        total = len(items) * cell_w + (len(items) - 1) * gap
        x = SCREEN_WIDTH // 2 - total // 2
        y = SCREEN_HEIGHT - 90
        bg = pygame.Surface((total + 24, cell_h + 24), pygame.SRCALPHA)
        bg.fill((10, 10, 20, 200))
        self.screen.blit(bg, (x - 12, y - 12))
        for i, text in enumerate(items):
            cx = x + i * (cell_w + gap)
            pygame.draw.rect(self.screen, (40, 40, 60),
                             (cx, y, cell_w, cell_h), border_radius=4)
            pygame.draw.rect(self.screen, (200, 200, 220),
                             (cx, y, cell_w, cell_h), 1, border_radius=4)
            n = self.font.render(str(i + 1), True, (255, 220, 90))
            self.screen.blit(n, (cx + 6, y + 4))
            t = self.font.render(text, True, (240, 240, 240))
            self.screen.blit(t, (cx + cell_w // 2 - t.get_width() // 2,
                                 y + cell_h // 2 - t.get_height() // 2))

    def _drawEmoteBubble(self, anchor_x, anchor_y, em):
        text = EMOTE_TEXTS[em['idx']]
        # Fade out in the last 30 frames of life
        alpha = 255 if em['life'] > 30 else int(255 * em['life'] / 30)
        surf = self.font.render(text, True, (255, 255, 255))
        bx = anchor_x - surf.get_width() - 18
        by = anchor_y - surf.get_height() // 2 - 2
        bg = pygame.Surface((surf.get_width() + 14, surf.get_height() + 6),
                            pygame.SRCALPHA)
        bg.fill((30, 30, 50, int(alpha * 0.85)))
        self.screen.blit(bg, (bx - 7, by - 3))
        pygame.draw.rect(self.screen, (200, 200, 220, alpha),
                         (bx - 7, by - 3, surf.get_width() + 14,
                          surf.get_height() + 6), 1)
        surf.set_alpha(alpha)
        self.screen.blit(surf, (bx, by))
