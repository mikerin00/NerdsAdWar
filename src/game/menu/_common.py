# Module: menu._common
# Shared palette, background ornaments, fonts, and small draw helpers for
# menu screens.
#
# Visual theme: topographic old map.
#   - Ivory paper background with faint contour lines
#   - Navy primary text + copper accent borders
#   - Small compass rose ornament in the corner
#   - Warm sepia ink-dots drift upward as "atmosphere"

import math
import os
import random
import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT


# ── Palette (names kept for back-compat with existing menus) ──────────────
# Semantic roles:
#   _DARK_BG     → main page background (ivory paper)
#   _PARCHMENT   → primary text (navy ink)
#   _GOLD        → accent borders/dividers (copper)
#   _GOLD_LIGHT  → hover/highlight (bright copper)
#   _MUTED       → de-emphasised text
#   _DIM         → disabled / placeholder text
#   _WHITE       → strongest contrast text (deep navy-black)
#   _RED / _MUTED_RED / _BLUE → team and status colors (kept readable)
_DARK_BG    = (244, 236, 219)   # ivory paper
_PARCHMENT  = ( 29,  53,  87)   # navy ink
_GOLD       = (168, 110,  50)   # copper
_GOLD_LIGHT = (205, 140,  70)   # bright copper
_RED        = (158,  55,  55)
_MUTED_RED  = (130,  70,  70)
_BLUE       = ( 29,  53,  87)
_MUTED      = (120, 100,  75)
_DIM        = (175, 158, 128)
_WHITE      = ( 15,  25,  45)   # near-black navy (strongest contrast on ivory)

# New — parchment-tone button fills. Use these in menu helpers so buttons
# read as slightly-darker paper patches rather than black inkblots.
_BTN_BG          = (232, 220, 196)
_BTN_BG_HOVER    = (248, 232, 204)
_BTN_BG_DISABLED = (222, 213, 192)


# ── Drifting sepia ink dots (replaces the old dark particles) ──────────────

_PARTICLE_COLOR = (140, 100,  55)   # sepia ink

class _Particle:
    def __init__(self, rng):
        self.reset(rng, fresh=False)

    def reset(self, rng, fresh=True):
        # Dots drift upward now — feels like warm air rising from the paper.
        self.x  = rng.uniform(0, SCREEN_WIDTH)
        self.y  = rng.uniform(0, SCREEN_HEIGHT) if not fresh else SCREEN_HEIGHT + 4
        self.vy = -rng.uniform(0.10, 0.28)
        self.vx = rng.uniform(-0.05, 0.05)
        self.r  = rng.randint(1, 2)
        self.a  = rng.randint(25, 70)

    def update(self, rng):
        self.x += self.vx
        self.y += self.vy
        if self.y < -6:
            self.reset(rng)

    def draw(self, surf):
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*_PARTICLE_COLOR, self.a), (self.r, self.r), self.r)
        surf.blit(s, (int(self.x - self.r), int(self.y - self.r)))


def _makeParticles(n=40):
    rng = random.Random()
    return [_Particle(rng) for _ in range(n)], rng


def _updateParticles(particles, rng):
    for p in particles:
        p.update(rng)


def _drawParticles(surf, particles):
    for p in particles:
        p.draw(surf)


# ── Topographic contour lines ──────────────────────────────────────────────

_CONTOUR_CACHE = None

def _getContourLayer():
    """Build the contour overlay once and reuse. Cached per screen size."""
    global _CONTOUR_CACHE
    key = (SCREEN_WIDTH, SCREEN_HEIGHT)
    if _CONTOUR_CACHE is not None and _CONTOUR_CACHE[0] == key:
        return _CONTOUR_CACHE[1]

    layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    color = (150, 115,  75, 28)      # very faint sepia
    for i in range(9):
        y0    = int(SCREEN_HEIGHT * (i + 0.5) / 9)
        amp   = 10 + i * 4
        freq  = 0.0035 + i * 0.0007
        phase = i * 1.21
        pts   = []
        for x in range(-20, SCREEN_WIDTH + 20, 8):
            y = y0 + int(math.sin(x * freq + phase) * amp)
            pts.append((x, y))
        if len(pts) >= 2:
            pygame.draw.lines(layer, color, False, pts, 1)
    _CONTOUR_CACHE = (key, layer)
    return layer


# ── Hand-drawn world map (background decoration) ───────────────────────────
# Continents are stored as (longitude, latitude) control points and projected
# equirectangular: x = (lon + 180) / 360, y = (90 - lat) / 180. Each list is
# more heavily sampled than strictly needed so the shapes actually read as
# continents and not random blobs.

def _ll(lon, lat):
    return ((lon + 180.0) / 360.0, (90.0 - lat) / 180.0)

_CONTINENTS = [
    # ── North America (Alaska → Arctic → Atlantic → Gulf → Pacific) ──
    [_ll(-165, 65), _ll(-155, 71), _ll(-140, 70), _ll(-125, 72),
     _ll(-105, 72), _ll(-85,  73), _ll(-75,  72), _ll(-65,  67),
     _ll(-55,  52), _ll(-60,  46), _ll(-67,  44), _ll(-71,  41),
     _ll(-75,  37), _ll(-78,  34), _ll(-80,  30), _ll(-82,  26),
     _ll(-82,  25), _ll(-86,  30), _ll(-90,  30), _ll(-94,  29),
     _ll(-97,  26), _ll(-97,  21), _ll(-100, 19), _ll(-105, 19),
     _ll(-110, 23), _ll(-115, 28), _ll(-121, 32), _ll(-124, 40),
     _ll(-124, 46), _ll(-130, 54), _ll(-138, 58), _ll(-150, 60),
     _ll(-160, 58), _ll(-165, 65)],

    # Central America / Mexico tail
    [_ll(-97,  21), _ll(-93,  18), _ll(-88,  17), _ll(-83,  11),
     _ll(-78,   9), _ll(-78,   7), _ll(-82,   8), _ll(-88,  13),
     _ll(-92,  16), _ll(-97,  18), _ll(-97,  21)],

    # ── South America ────────────────────────────────────────────────
    [_ll(-81,   8), _ll(-75,  11), _ll(-71,  12), _ll(-63,  10),
     _ll(-55,   5), _ll(-50,   0), _ll(-48,  -4), _ll(-42,  -5),
     _ll(-38, -10), _ll(-37, -17), _ll(-40, -23), _ll(-48, -28),
     _ll(-55, -34), _ll(-62, -40), _ll(-67, -48), _ll(-71, -53),
     _ll(-74, -50), _ll(-73, -42), _ll(-73, -32), _ll(-72, -22),
     _ll(-76, -14), _ll(-80,  -4), _ll(-81,   0), _ll(-81,   8)],

    # ── Greenland ────────────────────────────────────────────────────
    [_ll(-52, 60), _ll(-44, 60), _ll(-30, 64), _ll(-20, 72),
     _ll(-18, 80), _ll(-30, 83), _ll(-52, 83), _ll(-65, 78),
     _ll(-60, 68), _ll(-52, 60)],

    # ── Europe + British Isles + Scandinavia ─────────────────────────
    [_ll(-10, 36), _ll(-6, 36), _ll(-1, 36), _ll(3, 43),
     _ll(6, 43),   _ll(12, 45), _ll(18, 40), _ll(22, 39),
     _ll(28, 40),  _ll(30, 40), _ll(35, 42), _ll(40, 43),
     _ll(40, 50),  _ll(32, 55), _ll(30, 60), _ll(26, 65),
     _ll(30, 69),  _ll(25, 71), _ll(15, 69), _ll(10, 66),
     _ll(5,  62),  _ll(12, 58), _ll(12, 55), _ll(8, 54),
     _ll(6, 51),   _ll(3, 50),  _ll(0, 48),  _ll(-2, 48),
     _ll(-3, 44),  _ll(-9, 43), _ll(-9, 38), _ll(-10, 36)],

    # Great Britain + Ireland
    [_ll(-4, 50), _ll(0, 51), _ll(2, 53), _ll(1, 56),
     _ll(-3, 59), _ll(-6, 58), _ll(-5, 54), _ll(-5, 51), _ll(-4, 50)],
    [_ll(-10, 52), _ll(-6, 52), _ll(-6, 55), _ll(-10, 55), _ll(-10, 52)],

    # ── Africa ───────────────────────────────────────────────────────
    [_ll(-17, 14), _ll(-17, 21), _ll(-10, 27), _ll(-6, 31),
     _ll(0,  32), _ll(11,  33), _ll(22,  32), _ll(32,  31),
     _ll(35,  29), _ll(39,  21), _ll(43,  12), _ll(51,  11),
     _ll(51,   2), _ll(45,  -4), _ll(41,  -10), _ll(40, -16),
     _ll(36, -22), _ll(32, -28), _ll(24, -34), _ll(18, -34),
     _ll(15, -28), _ll(13, -22), _ll(12, -12), _ll(9,  -3),
     _ll(5,   2), _ll(0,   4), _ll(-5,   5), _ll(-12, 10),
     _ll(-17, 14)],

    # Madagascar
    [_ll(44, -12), _ll(50, -15), _ll(50, -22), _ll(46, -25),
     _ll(44, -20), _ll(43, -14), _ll(44, -12)],

    # ── Asia ─────────────────────────────────────────────────────────
    [_ll(40, 43),  _ll(48, 41),  _ll(55, 39),  _ll(60, 36),
     _ll(65, 36),  _ll(68, 25),  _ll(72, 25),  _ll(75, 25),
     _ll(78, 23),  _ll(72, 15),  _ll(76, 9),   _ll(80, 8),
     _ll(82, 14),  _ll(85, 20),  _ll(89, 21),  _ll(92, 20),
     _ll(94, 16),  _ll(96, 14),  _ll(100, 14), _ll(102, 10),
     _ll(105, 5),  _ll(107, 2),  _ll(105, 10), _ll(108, 15),
     _ll(110, 21), _ll(115, 22), _ll(118, 23), _ll(122, 30),
     _ll(121, 39), _ll(125, 41), _ll(130, 42), _ll(135, 46),
     _ll(143, 51), _ll(155, 58), _ll(170, 64), _ll(175, 67),
     _ll(172, 70), _ll(155, 71), _ll(140, 73), _ll(120, 73),
     _ll(100, 73), _ll(80, 72),  _ll(65, 70),  _ll(58, 65),
     _ll(50, 62),  _ll(45, 55),  _ll(42, 48),  _ll(40, 43)],

    # Indonesia / Philippines (clustered blobs)
    [_ll(95,  3),  _ll(105, 0),  _ll(110, -3), _ll(115, -4),
     _ll(113, -8), _ll(105, -6), _ll(100, -2), _ll(96,  0), _ll(95,  3)],
    [_ll(116, -2), _ll(122, 0),  _ll(126, -3), _ll(122, -7),
     _ll(118, -5), _ll(116, -2)],
    [_ll(120, 6),  _ll(125, 7),  _ll(127, 10), _ll(124, 14),
     _ll(121, 12), _ll(120, 6)],
    [_ll(131, -4), _ll(138, -3), _ll(140, -6), _ll(134, -7),
     _ll(131, -4)],

    # Japan
    [_ll(131, 33), _ll(136, 35), _ll(140, 38), _ll(142, 42),
     _ll(140, 42), _ll(135, 36), _ll(131, 33)],
    [_ll(143, 43), _ll(145, 44), _ll(146, 45), _ll(143, 45), _ll(143, 43)],

    # Sri Lanka
    [_ll(80, 7), _ll(82, 8), _ll(82, 6), _ll(80, 5), _ll(80, 7)],

    # ── Australia + Tasmania + New Zealand ────────────────────────────
    [_ll(113, -22), _ll(115, -20), _ll(122, -18), _ll(130, -12),
     _ll(135, -12), _ll(137, -15), _ll(141, -12), _ll(145, -15),
     _ll(150, -20), _ll(153, -26), _ll(151, -33), _ll(148, -38),
     _ll(143, -39), _ll(138, -37), _ll(132, -33), _ll(127, -33),
     _ll(120, -34), _ll(114, -33), _ll(113, -26), _ll(113, -22)],
    [_ll(144, -41), _ll(148, -41), _ll(148, -43), _ll(145, -43),
     _ll(144, -41)],   # Tasmania
    [_ll(172, -34), _ll(176, -37), _ll(179, -41), _ll(174, -42),
     _ll(171, -37), _ll(172, -34)],   # NZ north
    [_ll(167, -42), _ll(174, -42), _ll(174, -47), _ll(167, -47),
     _ll(167, -42)],   # NZ south
]

_WORLD_CACHE = None

def _getWorldMapLayer():
    """Render the hand-drawn continents once at current screen size."""
    global _WORLD_CACHE
    key = (SCREEN_WIDTH, SCREEN_HEIGHT)
    if _WORLD_CACHE is not None and _WORLD_CACHE[0] == key:
        return _WORLD_CACHE[1]

    layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    # Fill, outer outline (stroke twice with slight offset for "hand-drawn"
    # wobble), inner outline. Alphas kept low so UI text stays readable.
    fill_col     = (155, 110,  65,  60)
    outline_col  = ( 90,  55,  25, 140)
    outline_col2 = ( 95,  60,  30,  85)

    for poly in _CONTINENTS:
        scaled = [(int(x * SCREEN_WIDTH), int(y * SCREEN_HEIGHT))
                  for x, y in poly]
        if len(scaled) < 3:
            continue
        pygame.draw.polygon(layer, fill_col, scaled)
        # Main outline
        pygame.draw.polygon(layer, outline_col,  scaled, 2)
        # Wobble stroke 1 px offset — reads as hand-drawn ink line
        wobble = [(x + 1, y + 1) for x, y in scaled]
        pygame.draw.polygon(layer, outline_col2, wobble, 1)

    # Faint latitude / longitude grid
    grid_col = (125,  85,  50,  22)
    for i in range(1, 8):
        y = int(SCREEN_HEIGHT * i / 8)
        pygame.draw.line(layer, grid_col, (0, y), (SCREEN_WIDTH, y), 1)
    for i in range(1, 12):
        x = int(SCREEN_WIDTH * i / 12)
        pygame.draw.line(layer, grid_col, (x, 0), (x, SCREEN_HEIGHT), 1)

    _WORLD_CACHE = (key, layer)
    return layer


# ── Compass rose ornament ─────────────────────────────────────────────────

_ROSE_CACHE = None

def _getCompassRose(r=52):
    global _ROSE_CACHE
    if _ROSE_CACHE is not None and _ROSE_CACHE[0] == r:
        return _ROSE_CACHE[1]
    surf = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
    cx = cy = r + 3
    col_outline  = (155, 105,  55,  95)
    col_fill     = (190, 140,  85,  55)
    pygame.draw.circle(surf, col_outline, (cx, cy), r,            1)
    pygame.draw.circle(surf, col_outline, (cx, cy), int(r * 0.72), 1)
    pygame.draw.circle(surf, col_outline, (cx, cy), int(r * 0.12), 1)

    # 4 cardinal + 4 intercardinal points as elongated triangles
    def _star(angle_deg, length, width):
        rad = math.radians(angle_deg)
        tip  = (cx + math.cos(rad) * length, cy + math.sin(rad) * length)
        base = (cx + math.cos(rad + math.pi / 2) * width,
                cy + math.sin(rad + math.pi / 2) * width)
        base2 = (cx + math.cos(rad - math.pi / 2) * width,
                 cy + math.sin(rad - math.pi / 2) * width)
        pygame.draw.polygon(surf, col_fill,    [tip, base, base2])
        pygame.draw.polygon(surf, col_outline, [tip, base, base2], 1)

    for ang in (-90, 0, 90, 180):
        _star(ang, r, r * 0.14)
    for ang in (-45, 45, 135, -135):
        _star(ang, r * 0.65, r * 0.10)

    # Cardinal letters
    f = pygame.font.SysFont('georgia', max(10, int(r * 0.26)), bold=True)
    txt_color = (120,  80,  40,  160)
    for letter, (dx, dy) in (('N', (0, -r + 14)), ('E', (r - 14, 0)),
                             ('S', (0, r - 14)),  ('W', (-r + 14, 0))):
        t = f.render(letter, True, txt_color[:3])
        t.set_alpha(txt_color[3])
        surf.blit(t, (cx + dx - t.get_width() // 2,
                     cy + dy - t.get_height() // 2))
    _ROSE_CACHE = (r, surf)
    return surf


# ── Menu background image ──────────────────────────────────────────────────

_BG_IMAGE_CACHE = None

def _getBgImage():
    global _BG_IMAGE_CACHE
    key = (SCREEN_WIDTH, SCREEN_HEIGHT)
    if _BG_IMAGE_CACHE is not None and _BG_IMAGE_CACHE[0] == key:
        return _BG_IMAGE_CACHE[1]
    path = os.path.join(os.getcwd(), 'game_visuals', 'menu_background.png')
    try:
        img = pygame.image.load(path).convert()
        img = pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
    except Exception:
        img = None
    _BG_IMAGE_CACHE = (key, img)
    return img


# ── Background composition ─────────────────────────────────────────────────

def _drawBackground(surf, tick):
    """Menu background: custom image if available, otherwise fallback to
    the old ivory-paper + world-map style."""
    bg = _getBgImage()
    if bg is not None:
        surf.blit(bg, (0, 0))
        return

    # Fallback: ivory paper + vignette + world map + contours + compass rose
    surf.fill(_DARK_BG)
    cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    for r in range(max(cx, cy), 0, -90):
        alpha = max(0, int(14 * (1 - r / max(cx, cy))))
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (185, 140,  85, alpha), (r, r), r)
        surf.blit(s, (cx - r, cy - r))
    surf.blit(_getWorldMapLayer(), (0, 0))
    surf.blit(_getContourLayer(), (0, 0))
    rose = _getCompassRose(52)
    surf.blit(rose, (SCREEN_WIDTH - rose.get_width() - 24,
                     SCREEN_HEIGHT - rose.get_height() - 24))


# ── Fonts (lazy init) ──────────────────────────────────────────────────────

_fonts = {}

def _font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont('georgia', size, bold=bold)
    return _fonts[key]


def _renderShadow(surf, text, font, color, x, y, shadow=(210, 180, 135), offset=2):
    """Soft beige drop-shadow reads better than black on ivory."""
    sh = font.render(text, True, shadow)
    surf.blit(sh, (x + offset, y + offset))
    tx = font.render(text, True, color)
    surf.blit(tx, (x, y))
    return tx.get_width(), tx.get_height()


# ── Decorative divider line ────────────────────────────────────────────────

def _drawStars(surf, cx, cy, count, earned, r_outer=12, r_inner=5,
               col_lit=(255, 210, 40), col_dim=(90, 80, 60)):
    """Draw `count` stars centred on (cx, cy). First `earned` are lit."""
    import math as _m
    gap   = r_outer * 2 + 6
    total = (count - 1) * gap
    for i in range(count):
        sx = cx - total // 2 + i * gap
        pts = []
        for j in range(10):
            angle = _m.radians(-90 + j * 36)
            r = r_outer if j % 2 == 0 else r_inner
            pts.append((sx + r * _m.cos(angle), cy + r * _m.sin(angle)))
        pygame.draw.polygon(surf, col_lit if i < earned else col_dim, pts)


def _drawDivider(surf, y, color=_GOLD):
    cx = SCREEN_WIDTH // 2
    w  = int(SCREEN_WIDTH * 0.45)
    pygame.draw.line(surf, color, (cx - w, y), (cx + w, y), 1)
    pygame.draw.circle(surf, color, (cx, y), 4, 1)
    pygame.draw.circle(surf, color, (cx - w, y), 2)
    pygame.draw.circle(surf, color, (cx + w, y), 2)


# ── Shared button draw (opt-in — menus that use this stay on-theme) ──────

def _drawButton(surf, rect, label, mx, my, enabled=True, hot=False,
                font_size=22):
    """Draw a parchment-tone button and return its hover state.
    `hot=True` forces the highlight state (used for selected toggles)."""
    hover = enabled and rect.collidepoint(mx, my)
    bg    = (_BTN_BG_HOVER if (hover or hot)
             else (_BTN_BG if enabled else _BTN_BG_DISABLED))
    brd   = (_GOLD_LIGHT if (hover or hot)
             else (_GOLD if enabled else _DIM))
    pygame.draw.rect(surf, bg,  rect, border_radius=4)
    pygame.draw.rect(surf, brd, rect, 2 if hot else 1, border_radius=4)

    f     = _font(font_size, bold=(hover or hot))
    color = (_WHITE if (hover or hot)
             else (_PARCHMENT if enabled else _DIM))
    t     = f.render(label, True, color)
    surf.blit(t, (rect.centerx - t.get_width() // 2,
                  rect.centery  - t.get_height() // 2))
    return hover
