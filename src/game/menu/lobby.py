# Module: menu.lobby
# LobbyScreen — pre-game biome / difficulty / gamemode picker

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT

from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED_RED, _MUTED, _DIM, _WHITE,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _drawDivider,
)


# ══════════════════════════════════════════════════════════════════════════════
# LobbyScreen  — biome / difficulty / gamemode picker before singleplayer
# ══════════════════════════════════════════════════════════════════════════════

_BIOMES = [
    # (key,            label)
    ('RANDOM',        'Random'),
    ('GRASSLAND',     'Grassland'),
    ('RIVER_VALLEY',  'River Valley'),
    ('LAKELANDS',     'Lakelands'),
    ('HIGHLANDS',     'Highlands'),
    ('FOREST',        'Forest'),
    ('MIXED',         'Mixed'),
    ('DRY_PLAINS',    'Dry Plains'),
    ('TWIN_RIVERS',   'Twin Rivers'),
]

_DIFFICULTIES = [
    # (key,         label,       color hint)
    ('MAKKELIJK',  'Easy',       (100, 200, 100)),
    ('NORMAAL',    'Normal',     (180, 200, 120)),
    ('MOEILIJK',   'Hard',       (220, 180,  60)),
    ('VETERAAN',   'Veteran',    (220, 120,  40)),
    ('NAPOLEON',   'Napoleon',   (220,  60,  60)),
]

_GAMEMODES = [
    # (key,           label,                  enabled)
    ('STANDAARD',    'Standard Battle',        True),
    ('ASSAULT',      'Assault',                True),
    ('LAST_STAND',   'Last Stand',             True),
    ('COMMANDER',    'Hunt the Commander',     True),
    ('FOG',          'Fog of War',             True),
    ('CONQUEST',     'Conquest',               True),
]

_BIOME_DESC = {
    'RANDOM':       'Let fate decide.',
    'GRASSLAND':    'Open plains, no rivers. Cavalry dominates.',
    'RIVER_VALLEY': 'One river with bridges. Bridges are strategic objectives.',
    'LAKELANDS':    'Lakes narrow the routes. Find the gaps.',
    'HIGHLANDS':    'Rocks and ridgelines. High ground grants advantage.',
    'FOREST':       'Dense forest slows movement and covers flanking maneuvers.',
    'MIXED':        'Varied terrain with river and forest.',
    'DRY_PLAINS':   'Dry and rocky. Little cover for infantry.',
    'TWIN_RIVERS':  'Two rivers divide the battlefield into three zones.',
}

# Parameters driving the procedural thumbnail for each biome
_BIOME_THUMB_PARAMS = {
    #                       base_color          hi  fst lk  rk  riv
    'RANDOM':      {'base': ( 85, 108,  55), 'n_h': 1, 'n_f': 2, 'n_l': 1, 'n_r': 1, 'n_rv': 0},
    'GRASSLAND':   {'base': ( 90, 122,  52), 'n_h': 1, 'n_f': 2, 'n_l': 0, 'n_r': 0, 'n_rv': 0},
    'RIVER_VALLEY':{'base': ( 80, 114,  50), 'n_h': 1, 'n_f': 3, 'n_l': 1, 'n_r': 0, 'n_rv': 1},
    'LAKELANDS':   {'base': ( 75, 110,  52), 'n_h': 0, 'n_f': 2, 'n_l': 3, 'n_r': 1, 'n_rv': 0},
    'HIGHLANDS':   {'base': (100, 118,  65), 'n_h': 3, 'n_f': 1, 'n_l': 0, 'n_r': 5, 'n_rv': 0},
    'FOREST':      {'base': ( 48,  85,  38), 'n_h': 0, 'n_f': 8, 'n_l': 0, 'n_r': 0, 'n_rv': 1},
    'MIXED':       {'base': ( 80, 112,  52), 'n_h': 1, 'n_f': 3, 'n_l': 1, 'n_r': 2, 'n_rv': 1},
    'DRY_PLAINS':  {'base': (135, 122,  68), 'n_h': 0, 'n_f': 1, 'n_l': 0, 'n_r': 5, 'n_rv': 0},
    'TWIN_RIVERS': {'base': ( 75, 110,  52), 'n_h': 1, 'n_f': 2, 'n_l': 1, 'n_r': 0, 'n_rv': 2},
}

# Pre-render thumbnails once so they don't need redrawn every frame
_thumbCache = {}

def _drawBiomeThumbnail(surf, rect, biome_key):
    """Draw a schematic mini-map preview for biome_key into rect on surf."""
    import random as _rmod

    # Serve from cache (surface keyed by biome + size)
    cache_key = (biome_key, rect.width, rect.height)
    if cache_key not in _thumbCache:
        _thumbCache[cache_key] = _buildBiomeThumbnail(biome_key, rect.width, rect.height)
    surf.blit(_thumbCache[cache_key], rect.topleft)


_BIOME_IMAGE_FILES = {
    'GRASSLAND':   'grassland.png',
    'FOREST':      'forest.png',
    'RIVER_VALLEY':'river.png',
    'HIGHLANDS':   'highlands.png',
    'DRY_PLAINS':  'dryplanes.png',
    'MIXED':       'mixed.png',
    'WETLANDS':    'wetlands.png',
    'TWIN_RIVERS': 'twinrivers.png',
    'LAKELANDS':   'lakelands.png',
}


def _buildBiomeThumbnail(biome_key, W, H):
    import os as _os
    import random as _rmod

    if biome_key == 'RANDOM':
        surf = pygame.Surface((W, H))
        surf.fill((45, 38, 28))
        qf = _font(H // 2, bold=True)
        qt = qf.render("?", True, _GOLD_LIGHT)
        surf.blit(qt, (W // 2 - qt.get_width() // 2, H // 2 - qt.get_height() // 2))
        pygame.draw.rect(surf, _GOLD, surf.get_rect(), 2, border_radius=4)
        return surf

    fname = _BIOME_IMAGE_FILES.get(biome_key)
    if fname:
        path = _os.path.join(_os.getcwd(), 'game_visuals', 'map_minis', fname)
        try:
            img = pygame.image.load(path).convert()
            img = pygame.transform.scale(img, (W, H))
            pygame.draw.rect(img, _GOLD, img.get_rect(), 2, border_radius=4)
            return img
        except Exception:
            pass

    p   = _BIOME_THUMB_PARAMS.get(biome_key, _BIOME_THUMB_PARAMS['MIXED'])
    rng = _rmod.Random(abs(hash(biome_key)) % (2**31))

    base = pygame.Surface((W, H))
    base.fill(p['base'])

    def _blob(surf, color_rgba, cx, cy, rx, ry):
        s = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, color_rgba, s.get_rect())
        surf.blit(s, (cx - rx, cy - ry))

    br, bg, bb = p['base']

    # Highland tinting
    for _ in range(p['n_h']):
        cx = rng.randint(W//8, W*7//8)
        cy = rng.randint(H//8, H*7//8)
        _blob(base, (min(255,br+22), min(255,bg+18), min(255,bb+12), 150),
              cx, cy, rng.randint(W//7, W//3), rng.randint(H//6, H//3))

    # Forest patches
    for _ in range(p['n_f']):
        cx = rng.randint(W//10, W*9//10)
        cy = rng.randint(H//10, H*9//10)
        _blob(base, (30, 68, 26, 215),
              cx, cy, rng.randint(W//10, W//5), rng.randint(H//7, H//3))

    # Lakes
    for _ in range(p['n_l']):
        cx = rng.randint(W//5, W*4//5)
        cy = rng.randint(H//5, H*4//5)
        _blob(base, (52, 118, 195, 235),
              cx, cy, rng.randint(W//10, W//5), rng.randint(H//8, H//4))

    # Rocks
    for _ in range(p['n_r']):
        cx = rng.randint(W//8, W*7//8)
        cy = rng.randint(H//8, H*7//8)
        _blob(base, (108, 102, 95, 205),
              cx, cy, rng.randint(W//14, W//7), rng.randint(H//10, H//6))

    # Rivers — drawn on the base surface
    for ri in range(p['n_rv']):
        frac  = (ri + 1) / (p['n_rv'] + 1)
        base_x = int(W * (0.33 + frac * 0.34))
        pts = []
        for j in range(6):
            t = j / 5
            y = int(t * H)
            x = base_x + int(rng.uniform(-W * 0.09, W * 0.09))
            x = max(6, min(W - 6, x))
            pts.append((x, y))
        if len(pts) >= 2:
            pygame.draw.lines(base, (55, 128, 210), False, pts, max(2, W // 90))

    # Army start markers
    dot_r = max(3, W // 38)
    pygame.draw.circle(base, (60, 130, 220), (W // 10,     H // 2), dot_r)
    pygame.draw.circle(base, (210, 55, 55),  (W * 9 // 10, H // 2), dot_r)

    # RANDOM overlay
    if biome_key == 'RANDOM':
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 95))
        base.blit(ov, (0, 0))
        qf = _font(H // 2, bold=True)
        qt = qf.render("?", True, _GOLD_LIGHT)
        base.blit(qt, (W // 2 - qt.get_width() // 2, H // 2 - qt.get_height() // 2))

    # Border
    pygame.draw.rect(base, _GOLD, base.get_rect(), 2, border_radius=4)

    return base


class _SelectBox:
    """A rectangular selectable tile."""
    def __init__(self, key, label, x, y, w, h, color=None):
        self.key      = key
        self.label    = label
        self.rect     = pygame.Rect(x, y, w, h)
        self.color    = color
        self.selected = False
        self.hover    = False
        self._enabled = True

    def update(self, mx, my):
        self.hover = self.rect.collidepoint(mx, my)

    def draw(self, surf):
        r = self.rect
        if self.selected:
            bg  = (248, 232, 204)
            brd = self.color or _GOLD_LIGHT
            bw  = 2
        elif self.hover and self._enabled:
            bg  = (238, 224, 198)
            brd = self.color or _GOLD
            bw  = 1
        else:
            bg  = (228, 216, 190)
            brd = _DIM
            bw  = 1

        pygame.draw.rect(surf, bg,  r, border_radius=4)
        pygame.draw.rect(surf, brd, r, bw, border_radius=4)

        fc    = _font(17, bold=self.selected)
        # Navy text on parchment reads well; accent color only when a box
        # carries one (e.g. difficulty tier) and is selected.
        if self.selected:
            color = self.color or _PARCHMENT
        elif self.hover and self._enabled:
            color = _WHITE
        else:
            color = _MUTED
        txt = fc.render(self.label, True, color)
        surf.blit(txt, (r.centerx - txt.get_width() // 2,
                        r.centery - txt.get_height() // 2))


def _sectionTitle(surf, text, cx, y):
    f  = _font(18, bold=True)
    t  = f.render(text.upper(), True, _GOLD)
    surf.blit(t, (cx - t.get_width() // 2, y))
    pygame.draw.line(surf, _GOLD, (cx - 80, y + 22), (cx + 80, y + 22), 1)


def _drawFooterBtn(surf, rect, label, mx, my, gold=True):
    hover = rect.collidepoint(mx, my)
    bg    = (248, 232, 204) if hover else (232, 220, 196)
    brd   = _GOLD_LIGHT if (gold and hover) else (_GOLD if gold else (_PARCHMENT if hover else _DIM))
    pygame.draw.rect(surf, bg,  rect, border_radius=5)
    pygame.draw.rect(surf, brd, rect, 2 if hover else 1, border_radius=5)
    f     = _font(22, bold=hover and gold)
    color = (15, 25, 45) if hover else (_PARCHMENT if gold else _MUTED)
    txt   = f.render(label, True, color)
    surf.blit(txt, (rect.centerx - txt.get_width() // 2,
                    rect.centery - txt.get_height() // 2))


class LobbyScreen:
    """Pre-game setup: biome, difficulty, game mode. Returns a config dict or 'back'/'quit'."""

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)

        self._selectedBiome = 'RANDOM'
        self._selectedDiff  = 'NORMAAL'
        self._selectedMode  = 'STANDAARD'
        # Optional override: custom sandbox map. When set, biome is ignored.
        self._customMap     = None
        self._customMapName = None

        W, H = SCREEN_WIDTH, SCREEN_HEIGHT

        TITLE_H  = 110
        FOOTER_H =  75
        BODY_TOP = TITLE_H + 10
        BODY_H   = H - TITLE_H - FOOTER_H - 10
        COL_W    = W // 3

        # ── Biome grid (left col, 3×3) ────────────────────────────────────────
        BW, BH = 170, 44
        BGAP   = 8
        b_cols = 3
        b_rows = 3
        b_total_w = b_cols * BW + (b_cols - 1) * BGAP
        b_total_h = b_rows * BH + (b_rows - 1) * BGAP
        b_cx  = COL_W // 2
        b_top = BODY_TOP + 32   # anchor at top of section, leave room for preview below

        self._biomeBoxes = []
        for i, (key, label) in enumerate(_BIOMES):
            col = i % b_cols
            row = i // b_cols
            x   = b_cx - b_total_w // 2 + col * (BW + BGAP)
            y   = b_top + row * (BH + BGAP)
            box = _SelectBox(key, label, x, y, BW, BH,
                             color=_GOLD if key == 'RANDOM' else None)
            self._biomeBoxes.append(box)
        self._biomeBoxes[0].selected = True

        # ── Biome preview panel (below grid) ──────────────────────────────────
        PW = min(310, COL_W - 44)
        PH = PW * 9 // 16
        self._previewRect = pygame.Rect(
            b_cx - PW // 2,
            b_top + b_total_h + 14,
            PW, PH,
        )

        # ── Difficulty list (middle col) ──────────────────────────────────────
        DW, DH = 200, 52
        DGAP   = 10
        d_total_h = len(_DIFFICULTIES) * DH + (len(_DIFFICULTIES) - 1) * DGAP
        d_cx  = COL_W + COL_W // 2
        d_top = BODY_TOP + (BODY_H - d_total_h) // 2 + 16

        self._diffBoxes = []
        for i, (key, label, color) in enumerate(_DIFFICULTIES):
            x   = d_cx - DW // 2
            y   = d_top + i * (DH + DGAP)
            box = _SelectBox(key, label, x, y, DW, DH, color=color)
            if key == 'NORMAAL':
                box.selected = True
            self._diffBoxes.append(box)

        # ── Game mode list (right col) ────────────────────────────────────────
        MW, MH = 200, 52
        MGAP   = 10
        m_total_h = len(_GAMEMODES) * MH + (len(_GAMEMODES) - 1) * MGAP
        m_cx  = COL_W * 2 + COL_W // 2
        m_top = BODY_TOP + (BODY_H - m_total_h) // 2 + 16

        self._modeBoxes = []
        for i, (key, label, enabled) in enumerate(_GAMEMODES):
            x        = m_cx - MW // 2
            y        = m_top + i * (MH + MGAP)
            box      = _SelectBox(key, label, x, y, MW, MH,
                                  color=_PARCHMENT if enabled else None)
            box._enabled = enabled
            if key == 'STANDAARD':
                box.selected = True
            self._modeBoxes.append(box)

        # ── Custom sandbox-map selector (below biome preview) ─────────────
        self._customMapRect = pygame.Rect(
            self._previewRect.x,
            self._previewRect.bottom + 44,
            self._previewRect.width, 34,
        )

        # ── Footer buttons ────────────────────────────────────────────────────
        self._btnStart = pygame.Rect(W // 2 + 20,  H - 62, 210, 46)
        self._btnBack  = pygame.Rect(W // 2 - 230, H - 62, 200, 46)

    def _cycleCustomMap(self):
        """Cycle through None → first sandbox map → second → … → None."""
        from src.game.menu.sandbox import _listMaps, _loadMap
        maps = _listMaps()
        if not maps:
            self._customMap     = None
            self._customMapName = None
            return
        choices = [None] + maps
        cur = (self._customMapName + '.json') if self._customMapName else None
        try:
            idx = choices.index(cur)
        except ValueError:
            idx = 0
        nxt = choices[(idx + 1) % len(choices)]
        if nxt is None:
            self._customMap     = None
            self._customMapName = None
        else:
            try:
                self._customMap     = _loadMap(nxt)
                self._customMapName = nxt[:-5] if nxt.endswith('.json') else nxt
            except Exception:
                self._customMap     = None
                self._customMapName = None

    def run(self):
        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 'back'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for box in self._biomeBoxes:
                        if box.rect.collidepoint(mx, my):
                            for b in self._biomeBoxes: b.selected = False
                            box.selected = True
                            self._selectedBiome = box.key
                    for box in self._diffBoxes:
                        if box.rect.collidepoint(mx, my):
                            for b in self._diffBoxes: b.selected = False
                            box.selected = True
                            self._selectedDiff = box.key
                    for box in self._modeBoxes:
                        if box.rect.collidepoint(mx, my) and box._enabled:
                            for b in self._modeBoxes: b.selected = False
                            box.selected = True
                            self._selectedMode = box.key
                    if self._customMapRect.collidepoint(mx, my):
                        self._cycleCustomMap()
                    if self._btnStart.collidepoint(mx, my):
                        return {
                            'biome':      self._selectedBiome,
                            'difficulty': self._selectedDiff,
                            'gamemode':   self._selectedMode,
                            'customMap':  self._customMap,
                        }
                    if self._btnBack.collidepoint(mx, my):
                        return 'back'

            for box in self._biomeBoxes:
                box.update(mx, my)
            for box in self._diffBoxes:
                box.update(mx, my)
            for box in self._modeBoxes:
                box.update(mx, my)

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(mx, my)
            self.clock.tick(60)

    def _draw(self, mx, my):
        surf = self.screen
        W, H = SCREEN_WIDTH, SCREEN_HEIGHT
        cx   = W // 2
        COL_W = W // 3

        _drawBackground(surf, self.tick)
        _drawParticles(surf, self.particles)

        # Title
        tf  = _font(44, bold=True)
        ttx = tf.render("Battle Setup", True, _GOLD_LIGHT)
        surf.blit(ttx, (cx - ttx.get_width() // 2, 22))
        _drawDivider(surf, 78)

        # Section headers
        _sectionTitle(surf, "Map / Biome",             COL_W // 2,              90)
        _sectionTitle(surf, "Difficulty",              COL_W + COL_W // 2,      90)
        _sectionTitle(surf, "Game Mode",               COL_W * 2 + COL_W // 2,  90)

        # Column separators
        for x in (COL_W, COL_W * 2):
            pygame.draw.line(surf, _DIM, (x, 85), (x, H - 80), 1)

        # Biome grid
        for box in self._biomeBoxes:
            box.draw(surf)

        # Preview — always shows selected biome; hover immediately previews that biome
        hover_key = next((b.key for b in self._biomeBoxes if b.hover), None)
        preview_key = hover_key if hover_key else self._selectedBiome
        _drawBiomeThumbnail(surf, self._previewRect, preview_key)

        # Description text below preview
        desc_text = _BIOME_DESC.get(preview_key, '')
        if desc_text:
            df   = _font(15)
            desc = df.render(desc_text, True, _MUTED)
            dy   = self._previewRect.bottom + 8
            surf.blit(desc, (COL_W // 2 - desc.get_width() // 2, dy))

        # Custom sandbox-map selector (overrides biome when set)
        r = self._customMapRect
        hover = r.collidepoint(mx, my)
        bg  = (248, 232, 204) if hover else (232, 220, 196)
        brd = _GOLD_LIGHT if hover else _GOLD
        pygame.draw.rect(surf, bg,  r, border_radius=4)
        pygame.draw.rect(surf, brd, r, 2 if hover else 1, border_radius=4)
        if self._customMapName:
            label = f"Custom map: {self._customMapName}"
            color = _GOLD_LIGHT
        else:
            label = "Choose custom sandbox map"
            color = _PARCHMENT if hover else _MUTED
        lf = _font(16, bold=hover or bool(self._customMapName))
        lt = lf.render(label, True, color)
        surf.blit(lt, (r.centerx - lt.get_width() // 2,
                       r.centery - lt.get_height() // 2))

        if self._customMap:
            note = _font(12).render("(biome choice ignored)", True, _DIM)
            surf.blit(note, (r.centerx - note.get_width() // 2, r.bottom + 4))

        # Difficulty
        for box in self._diffBoxes:
            box.draw(surf)

        # Game modes
        for box in self._modeBoxes:
            box.draw(surf)
            if not box._enabled:
                bf    = _font(13)
                badge = bf.render("coming soon", True, _MUTED_RED)
                surf.blit(badge, (box.rect.right - badge.get_width() - 6,
                                  box.rect.bottom - badge.get_height() - 4))

        # Footer buttons
        _drawFooterBtn(surf, self._btnBack,  "< Back",        mx, my, gold=False)
        _drawFooterBtn(surf, self._btnStart, "Start Battle!", mx, my, gold=True)

        pygame.display.flip()
