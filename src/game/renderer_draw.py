# Module: renderer_draw
# Standalone drawing functions: units, headquarters, outposts and geometry helpers

import math

import pygame

from src.constants import UNIT_COLORS, YELLOW, WHITE, BLACK, COMMANDER_AURA_RADIUS

# ── Cached fonts ──────────────────────────────────────────────────────────────
_fontSmall = None

def _getSmallFont():
    global _fontSmall
    if _fontSmall is None:
        _fontSmall = pygame.font.SysFont(None, 18)
    return _fontSmall


# ── Geometry helpers ──────────────────────────────────────────────────────────

def chaikin(pts):
    if len(pts) < 3:
        return pts
    result = [pts[0]]
    for i in range(len(pts) - 1):
        q = (pts[i][0] * 3 / 4 + pts[i + 1][0] / 4,
             pts[i][1] * 3 / 4 + pts[i + 1][1] / 4)
        r = (pts[i][0] / 4 + pts[i + 1][0] * 3 / 4,
             pts[i][1] / 4 + pts[i + 1][1] * 3 / 4)
        result += [q, r]
    result.append(pts[-1])
    return result


def simplify(pts):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        dx1, dy1 = pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1]
        dx2, dy2 = pts[i+1][0] - pts[i][0], pts[i+1][1] - pts[i][1]
        if dx1 * dy2 - dy1 * dx2 != 0:
            out.append(pts[i])
    out.append(pts[-1])
    return out


# ── Selection glow ────────────────────────────────────────────────────────────

def _selectionGlow(screen, ix, iy, r):
    """Soft pulsing gold aura around selected units."""
    t     = pygame.time.get_ticks()
    pulse = 0.55 + 0.45 * math.sin(t * 0.005)
    for expand, base_alpha in ((r + 10, 28), (r + 6, 55), (r + 3, 95)):
        expand = int(expand)
        size   = (expand + 3) * 2
        s      = pygame.Surface((size, size), pygame.SRCALPHA)
        a      = max(0, min(255, int(base_alpha * pulse)))
        pygame.draw.circle(s, (255, 230, 50, a), (size // 2, size // 2),
                           expand, max(2, expand // 4))
        screen.blit(s, (ix - size // 2, iy - size // 2))


# ── HP / morale / supply bars ─────────────────────────────────────────────────

def _drawBars(screen, bx, by, bw, unit):
    """Draw three status bars above the unit.
    Bars stack upward from `by`: HP (7px) → morale (4px) → supply (3px)."""

    # HP — gradient green → yellow → red
    ratio = max(0.0, unit.hp / unit.maxHp)
    if ratio > 0.5:
        t        = (ratio - 0.5) * 2.0
        hp_color = (int(255 * (1.0 - t)), int(160 + 60 * t), 0)
    else:
        t        = ratio * 2.0
        hp_color = (210, int(160 * t), 0)

    pygame.draw.rect(screen, (18, 18, 18), (bx, by, bw, 7), border_radius=3)
    fill_w = int(bw * ratio)
    if fill_w > 1:
        pygame.draw.rect(screen, hp_color, (bx, by, fill_w, 7), border_radius=3)
    pygame.draw.rect(screen, (75, 75, 75), (bx, by, bw, 7), 1, border_radius=3)

    # Morale — blue
    pygame.draw.rect(screen, (18, 18, 18), (bx, by - 6, bw, 4), border_radius=2)
    mo_w = int(bw * unit.morale / 100)
    if mo_w > 1:
        pygame.draw.rect(screen, (70, 135, 255), (bx, by - 6, mo_w, 4), border_radius=2)
    pygame.draw.rect(screen, (40, 40, 65), (bx, by - 6, bw, 4), 1, border_radius=2)

    # Supply — amber → green
    s         = unit.supplyStrength
    sup_color = (int(200 * (1.0 - s)), int(70 + 130 * s), 0)
    pygame.draw.rect(screen, (18, 18, 18), (bx, by - 11, bw, 3), border_radius=1)
    sup_w = int(bw * s)
    if sup_w > 1:
        pygame.draw.rect(screen, sup_color, (bx, by - 11, sup_w, 3), border_radius=1)


# ── Stars helper ──────────────────────────────────────────────────────────────

def _drawStar(screen, cx, cy, r_outer, r_inner, color, points=5):
    pts = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        r     = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    pygame.draw.polygon(screen, color, pts)


# ── Outpost ───────────────────────────────────────────────────────────────────

def drawOutpost(screen, outpost):
    ix, iy = int(outpost.x), int(outpost.y)

    STONE    = (108, 96, 78)
    STONE_HI = (150, 136, 112)
    STONE_DK = (68,  60, 46)
    FLOOR    = (88,  78, 62)

    # ── Top-down tower: thick outer ring + inner floor ────────────────────────
    pygame.draw.circle(screen, STONE,    (ix, iy), 13)   # wall fill
    pygame.draw.circle(screen, FLOOR,    (ix, iy), 8)    # inner courtyard
    pygame.draw.circle(screen, STONE_DK, (ix, iy), 8,  1)  # inner wall edge
    pygame.draw.circle(screen, STONE_HI, (ix, iy), 13, 2)  # outer wall highlight

    # ── Merlons: 6 small squares around the outer rim ────────────────────────
    for i in range(6):
        a  = math.radians(i * 60)
        mx = ix + int(math.cos(a) * 12)
        my = iy + int(math.sin(a) * 12)
        pygame.draw.rect(screen, STONE_HI, (mx - 2, my - 2, 4, 4))
        pygame.draw.rect(screen, STONE_DK, (mx - 2, my - 2, 4, 4), 1)

    # ── Flag ──────────────────────────────────────────────────────────────────
    if outpost.team is not None:
        flagColor = (70, 130, 180) if outpost.team == 'player' else (220, 80, 80)
        flag_hi   = tuple(min(255, c + 55) for c in flagColor)
        flag_dk   = tuple(max(0,   c - 40) for c in flagColor)
        pygame.draw.line(screen, (85, 72, 52), (ix, iy), (ix, iy - 20), 2)
        pts = [(ix, iy - 20), (ix + 11, iy - 14), (ix, iy - 9)]
        pygame.draw.polygon(screen, flagColor, pts)
        pygame.draw.line(screen, flag_hi, (ix, iy - 20), (ix + 4, iy - 17), 1)
        pygame.draw.polygon(screen, flag_dk, pts, 1)

    # ── Capture bar ───────────────────────────────────────────────────────────
    barW = 32
    barX = ix - barW // 2
    barY = iy + 16
    pygame.draw.rect(screen, (22, 22, 22), (barX, barY, barW, 6), border_radius=3)
    ctrl = outpost.control
    half = barW // 2
    if ctrl > 0:
        fw = int(half * ctrl)
        pygame.draw.rect(screen, (70, 130, 180), (barX + half, barY, fw, 6), border_radius=2)
    elif ctrl < 0:
        fw = int(half * abs(ctrl))
        pygame.draw.rect(screen, (220, 80, 80), (barX + half - fw, barY, fw, 6), border_radius=2)
    pygame.draw.rect(screen, (140, 135, 120), (barX, barY, barW, 6), 1, border_radius=3)
    pygame.draw.line(screen, (140, 135, 120),
                     (barX + barW // 2, barY - 1), (barX + barW // 2, barY + 7), 1)

    # ── Strategic star ────────────────────────────────────────────────────────
    if getattr(outpost, 'strategic', False):
        _drawStar(screen, ix, iy - 32, 9, 4, (200, 165, 30))
        _drawStar(screen, ix, iy - 32, 8, 3, (255, 220, 70))
        pygame.draw.circle(screen, (255, 220, 70), (ix, iy - 32), 11, 1)
    else:
        label = _getSmallFont().render("OP", True, (185, 178, 158))
        screen.blit(label, (ix - label.get_width() // 2, iy + 25))


# ── Headquarters ──────────────────────────────────────────────────────────────

def drawHeadquarters(screen, hq):
    ix, iy    = int(hq.x), int(hq.y)
    teamColor = (70, 130, 180) if hq.team == 'player' else (220, 80, 80)
    hi_col    = tuple(min(255, c + 55) for c in teamColor)
    dk_col    = tuple(max(0,   c - 50) for c in teamColor)

    STONE    = (95,  84, 66)
    STONE_HI = (134, 120, 96)
    STONE_DK = (58,  50, 38)
    FLOOR    = (78,  70, 54)

    # ── Capture radius ring ────────────────────────────────────────────────────
    pygame.draw.circle(screen, (*teamColor, 40), (ix, iy), hq.CAPTURE_RADIUS, 1)

    # ── Outer walls: thick square ring (fill + hollow interior) ───────────────
    W = 22   # half-width of the whole fortress
    pygame.draw.rect(screen, STONE,  (ix - W, iy - W, W*2, W*2))
    pygame.draw.rect(screen, FLOOR,  (ix - 13, iy - 13, 26, 26))   # inner courtyard

    # Wall edges (bevel)
    pygame.draw.rect(screen, STONE_HI, (ix - W, iy - W, W*2, W*2), 2)
    pygame.draw.rect(screen, STONE_DK, (ix - 13, iy - 13, 26, 26), 1)

    # ── Corner towers: circles at the 4 true corners, slightly protruding ─────
    for cx2, cy2 in ((ix - W, iy - W), (ix + W, iy - W),
                     (ix - W, iy + W), (ix + W, iy + W)):
        pygame.draw.circle(screen, STONE_HI, (cx2, cy2), 7)
        pygame.draw.circle(screen, STONE_DK, (cx2, cy2), 7, 1)
        # Small inner dot to suggest a hollow top
        pygame.draw.circle(screen, FLOOR,    (cx2, cy2), 3)

    # ── Central keep: raised square tower ─────────────────────────────────────
    K = 9
    pygame.draw.rect(screen, STONE_HI, (ix - K, iy - K, K*2, K*2))
    pygame.draw.rect(screen, STONE_DK, (ix - K, iy - K, K*2, K*2), 2)
    # Keep floor detail: small inner square
    pygame.draw.rect(screen, FLOOR, (ix - 5, iy - 5, 10, 10))

    # ── Flag on central keep ───────────────────────────────────────────────────
    pygame.draw.line(screen, (80, 68, 50), (ix, iy - K), (ix, iy - K - 22), 2)
    flag_pts = [(ix, iy - K - 22), (ix + 14, iy - K - 15), (ix, iy - K - 8)]
    pygame.draw.polygon(screen, teamColor, flag_pts)
    pygame.draw.line(screen, hi_col, (ix, iy - K - 22), (ix + 5, iy - K - 19), 1)
    pygame.draw.polygon(screen, dk_col, flag_pts, 1)

    # ── Capture progress arc ───────────────────────────────────────────────────
    if hq.captureProgress > 0:
        enemy_col = (220, 80, 80) if hq.team == 'player' else (70, 130, 180)
        frac      = hq.captureProgress / hq.CAPTURE_TIME
        r         = hq.CAPTURE_RADIUS
        pygame.draw.arc(screen, enemy_col,
                        (ix - r, iy - r, r * 2, r * 2),
                        math.pi / 2, math.pi / 2 + frac * 2 * math.pi, 4)

    label = _getSmallFont().render("HQ", True, hi_col)
    screen.blit(label, (ix - label.get_width() // 2, iy + W + 4))


# ── Unit dispatch ─────────────────────────────────────────────────────────────

def drawUnit(screen, unit):
    ix, iy = int(unit.x), int(unit.y)
    color  = getattr(unit, '_drawColor', None) \
             or UNIT_COLORS[unit.team][unit.unitType]
    if unit.routing:
        color = (200, 200, 200)
    if unit.reformTimer > 0:
        color = tuple(max(0, c - 70) for c in color)

    if unit.unitType == 'commander':
        _drawCommander(screen, unit, ix, iy, color)
    elif unit.unitType == 'heavy_infantry':
        _drawHeavyInfantry(screen, unit, ix, iy, color)
    elif unit.unitType == 'infantry':
        _drawInfantry(screen, unit, ix, iy, color)
    elif unit.unitType == 'cavalry':
        _drawCavalry(screen, unit, ix, iy, color)
    elif unit.unitType == 'artillery':
        _drawArtillery(screen, unit, ix, iy, color)


# ── Infantry ──────────────────────────────────────────────────────────────────

def _drawInfantry(screen, unit, ix, iy, color):
    bright = tuple(min(255, c + 55) for c in color)
    dark   = tuple(max(0,   c - 50) for c in color)

    if unit.inSquare:
        s, hs = 26, 13
        if unit.selected:
            _selectionGlow(screen, ix, iy, hs + 2)
            sel = [(ix - hs - 4, iy - hs - 4), (ix + hs + 4, iy - hs - 4),
                   (ix + hs + 4, iy + hs + 4), (ix - hs - 4, iy + hs + 4)]
            pygame.draw.polygon(screen, YELLOW, sel, 2)

        pygame.draw.rect(screen, color, (ix - hs, iy - hs, s, s))
        # Bevel
        pygame.draw.line(screen, bright, (ix - hs, iy - hs), (ix + hs, iy - hs), 2)
        pygame.draw.line(screen, bright, (ix - hs, iy - hs), (ix - hs, iy + hs), 2)
        pygame.draw.line(screen, dark,   (ix - hs, iy + hs - 1), (ix + hs, iy + hs - 1), 2)
        pygame.draw.line(screen, dark,   (ix + hs - 1, iy - hs), (ix + hs - 1, iy + hs), 2)
        # Rank lines
        pygame.draw.line(screen, WHITE, (ix - hs + 2, iy - hs + 5), (ix + hs - 2, iy - hs + 5), 1)
        pygame.draw.line(screen, WHITE, (ix - hs + 2, iy + hs - 5), (ix + hs - 2, iy + hs - 5), 1)
        pygame.draw.line(screen, WHITE, (ix - hs + 5, iy - hs + 2), (ix - hs + 5, iy + hs - 2), 1)
        pygame.draw.line(screen, WHITE, (ix + hs - 5, iy - hs + 2), (ix + hs - 5, iy + hs - 2), 1)
        bx, by, fw = ix - hs, iy - hs - 10, s

    else:
        fw, fh   = 32, 18
        rad      = math.radians(unit.angle + 90)
        cosA, sinA = math.cos(rad), math.sin(rad)

        def rot(lx, ly):
            return (ix + lx * cosA - ly * sinA, iy + lx * sinA + ly * cosA)

        hw, hh  = fw / 2, fh / 2
        corners = [rot(-hw, -hh), rot(hw, -hh), rot(hw, hh), rot(-hw, hh)]

        if unit.selected:
            _selectionGlow(screen, ix, iy, max(hw, hh) + 2)
            sel = [rot(-hw - 4, -hh - 4), rot(hw + 4, -hh - 4),
                   rot(hw + 4,  hh + 4),  rot(-hw - 4, hh + 4)]
            pygame.draw.polygon(screen, YELLOW, sel, 2)

        pygame.draw.polygon(screen, color, corners)

        # Rank lines
        for row in range(1, 3):
            t  = row / 3
            ly = -hh + t * fh
            pygame.draw.line(screen, WHITE,
                             (int(rot(-hw + 2, ly)[0]), int(rot(-hw + 2, ly)[1])),
                             (int(rot(hw - 2,  ly)[0]), int(rot(hw - 2,  ly)[1])), 1)

        # Row of muskets along the front edge
        num_rifles = 5
        for ni in range(num_rifles):
            t_r   = (ni + 0.5) / num_rifles          # 0.1, 0.3, 0.5, 0.7, 0.9
            lx    = -hw + 4 + t_r * (hw * 2 - 8)    # spread across front, inset 4px
            rs    = rot(lx, -hh)
            re    = rot(lx, -hh - 6)
            pygame.draw.line(screen, (190, 190, 190),
                             (int(rs[0]), int(rs[1])), (int(re[0]), int(re[1])), 1)
            # Small bayonet tip
            rb = rot(lx, -hh - 8)
            pygame.draw.line(screen, (220, 220, 220),
                             (int(re[0]), int(re[1])), (int(rb[0]), int(rb[1])), 1)

        # Bevel: bright front edge, dark rear edge
        fe = [rot(-hw, -hh), rot(hw, -hh)]
        re_edge = [rot(-hw, hh), rot(hw, hh)]
        pygame.draw.line(screen, bright, (int(fe[0][0]), int(fe[0][1])),
                                         (int(fe[1][0]), int(fe[1][1])), 2)
        pygame.draw.line(screen, dark,   (int(re_edge[0][0]), int(re_edge[0][1])),
                                         (int(re_edge[1][0]), int(re_edge[1][1])), 1)

        # Outline
        pygame.draw.polygon(screen, WHITE, corners, 2)

        bx, by = ix - fw // 2, iy - fh // 2 - 10

    _drawBars(screen, bx, by, fw, unit)


# ── Heavy infantry ────────────────────────────────────────────────────────────

def _drawHeavyInfantry(screen, unit, ix, iy, color):
    s, hs = 28, 14
    bright = tuple(min(255, c + 60) for c in color)
    dark   = tuple(max(0,   c - 55) for c in color)

    if unit.selected:
        _selectionGlow(screen, ix, iy, hs + 2)
        sel = [(ix - hs - 4, iy - hs - 4), (ix + hs + 4, iy - hs - 4),
               (ix + hs + 4, iy + hs + 4), (ix - hs - 4, iy + hs + 4)]
        pygame.draw.polygon(screen, YELLOW, sel, 2)

    pygame.draw.rect(screen, color, (ix - hs, iy - hs, s, s))

    # Bevel
    pygame.draw.line(screen, bright, (ix - hs, iy - hs),     (ix + hs, iy - hs),     2)
    pygame.draw.line(screen, bright, (ix - hs, iy - hs),     (ix - hs, iy + hs),     2)
    pygame.draw.line(screen, dark,   (ix - hs, iy + hs - 1), (ix + hs, iy + hs - 1), 2)
    pygame.draw.line(screen, dark,   (ix + hs - 1, iy - hs), (ix + hs - 1, iy + hs), 2)

    # Inner shield frame
    inner = 5
    pygame.draw.rect(screen, WHITE,
                     (ix - hs + inner, iy - hs + inner,
                      s - inner * 2, s - inner * 2), 1)

    # Cross bars
    pygame.draw.line(screen, WHITE, (ix, iy - hs + inner), (ix, iy + hs - inner), 1)
    pygame.draw.line(screen, WHITE, (ix - hs + inner, iy), (ix + hs - inner, iy), 1)

    # Shield boss (raised center circle)
    pygame.draw.circle(screen, bright, (ix, iy), 5)
    pygame.draw.circle(screen, (25, 25, 25), (ix, iy), 5, 1)

    # Outer border — gold when shield wall is active
    border_col = (255, 215, 0) if getattr(unit, 'shieldWall', False) else WHITE
    pygame.draw.rect(screen, border_col, (ix - hs, iy - hs, s, s), 2)

    _drawBars(screen, ix - hs, iy - hs - 10, s, unit)


# ── Cavalry ───────────────────────────────────────────────────────────────────

def _drawCavalry(screen, unit, ix, iy, color):
    r      = unit.radius   # 10
    rad    = math.radians(unit.angle + 90)
    cosA, sinA = math.cos(rad), math.sin(rad)
    bright = tuple(min(255, c + 55) for c in color)
    dark   = tuple(max(0,   c - 50) for c in color)

    def rot(lx, ly):
        return (int(ix + lx * cosA - ly * sinA),
                int(iy + lx * sinA + ly * cosA))

    if unit.selected:
        _selectionGlow(screen, ix, iy, r + 4)

    # Body: forward-pointing arrowhead / lance shape
    body = [
        rot( 0, -13),   # front tip
        rot( 9,  -3),   # right shoulder
        rot( 6,   7),   # right rear
        rot( 0,   5),   # rear notch center
        rot(-6,   7),   # left rear
        rot(-9,  -3),   # left shoulder
    ]

    # Charge glow — drawn behind body
    if unit.chargeFrames > 45:
        t   = pygame.time.get_ticks()
        a   = int(180 + 75 * math.sin(t * 0.01))
        glow_pts = [
            rot( 0, -17), rot(12, -4), rot(9, 10),
            rot( 0,  8),  rot(-9, 10), rot(-12, -4),
        ]
        gs = pygame.Surface(((r + 14) * 2, (r + 14) * 2), pygame.SRCALPHA)
        shifted = [(p[0] - (ix - r - 14), p[1] - (iy - r - 14)) for p in glow_pts]
        pygame.draw.polygon(gs, (255, 160, 0, a), shifted)
        screen.blit(gs, (ix - r - 14, iy - r - 14))
        pygame.draw.polygon(screen, (255, 140, 0), body, 3)

    pygame.draw.polygon(screen, color, body)

    # Front-half highlight stripe
    front = [rot(0, -13), rot(9, -3), rot(0, -1), rot(-9, -3)]
    hl_s  = pygame.Surface(((r + 14) * 2, (r + 14) * 2), pygame.SRCALPHA)
    sh    = [(p[0] - (ix - r - 14), p[1] - (iy - r - 14)) for p in front]
    pygame.draw.polygon(hl_s, (*bright, 80), sh)
    screen.blit(hl_s, (ix - r - 14, iy - r - 14))

    # Center spine line
    tip  = rot(0, -13)
    base = rot(0, 5)
    pygame.draw.line(screen, dark, (int(tip[0]), int(tip[1])),
                                   (int(base[0]), int(base[1])), 1)

    # Outline
    pygame.draw.polygon(screen, WHITE, body, 1)

    if unit.selected:
        pygame.draw.polygon(screen, YELLOW, body, 2)

    _drawBars(screen, ix - r, iy - r - 8, r * 2, unit)


# ── Artillery ─────────────────────────────────────────────────────────────────

def _drawArtillery(screen, unit, ix, iy, color):
    r      = unit.radius   # 12
    rad    = math.radians(unit.angle + 90)
    cosA, sinA = math.cos(rad), math.sin(rad)
    bright = tuple(min(255, c + 50) for c in color)
    dark   = tuple(max(0,   c - 55) for c in color)
    wood   = (120, 85, 45)
    wood_hi= (165, 125, 75)

    def rot(lx, ly):
        return (int(ix + lx * cosA - ly * sinA),
                int(iy + lx * sinA + ly * cosA))

    if unit.selected:
        _selectionGlow(screen, ix, iy, r + 4)

    # Wheels (two circles on the sides, always drawn first)
    for side in (-1, 1):
        wx, wy = rot(side * 10, 2)
        pygame.draw.circle(screen, wood,    (wx, wy), 6)
        pygame.draw.circle(screen, wood_hi, (wx, wy), 6, 1)
        # Spokes
        for spoke_a in range(0, 180, 60):
            sa  = math.radians(spoke_a)
            sx1 = int(wx + math.cos(sa) * 4)
            sy1 = int(wy + math.sin(sa) * 4)
            sx2 = int(wx - math.cos(sa) * 4)
            sy2 = int(wy - math.sin(sa) * 4)
            pygame.draw.line(screen, wood_hi, (sx1, sy1), (sx2, sy2), 1)

    # Carriage body
    body = [rot(-8, -4), rot(8, -4), rot(8, 5), rot(-8, 5)]
    pygame.draw.polygon(screen, color, body)
    # Bevel
    top = [rot(-8, -4), rot(8, -4)]
    pygame.draw.line(screen, bright,
                     (int(top[0][0]), int(top[0][1])),
                     (int(top[1][0]), int(top[1][1])), 2)
    pygame.draw.polygon(screen, WHITE, body, 1)

    # Barrel (points forward)
    b_root = rot(0, -4)
    b_tip  = rot(0, -20)
    pygame.draw.line(screen, dark,  (int(b_root[0]), int(b_root[1])),
                                    (int(b_tip[0]),  int(b_tip[1])), 6)
    pygame.draw.line(screen, color, (int(b_root[0]), int(b_root[1])),
                                    (int(b_tip[0]),  int(b_tip[1])), 4)
    pygame.draw.line(screen, WHITE, (int(b_root[0]), int(b_root[1])),
                                    (int(b_tip[0]),  int(b_tip[1])), 1)
    # Muzzle cap
    pygame.draw.circle(screen, bright, rot(0, -20), 3)
    pygame.draw.circle(screen, WHITE,  rot(0, -20), 3, 1)

    # Deploy state
    if unit.deployed:
        pygame.draw.polygon(screen, (0, 215, 0), body, 2)
    elif unit.undeploying:
        arcFrac = unit.undeployTimer / 75
        pygame.draw.arc(screen, (220, 80, 0),
                        (ix - r - 5, iy - r - 5, (r + 5) * 2, (r + 5) * 2),
                        0, arcFrac * 2 * math.pi, 2)
    elif unit.deployTimer > 0:
        arcFrac = unit.deployTimer / 90
        pygame.draw.arc(screen, (200, 200, 0),
                        (ix - r - 5, iy - r - 5, (r + 5) * 2, (r + 5) * 2),
                        0, arcFrac * 2 * math.pi, 2)

    if unit.selected:
        pygame.draw.polygon(screen, YELLOW, body, 2)

    _drawBars(screen, ix - r, iy - r - 8, r * 2, unit)


# ── Commander ─────────────────────────────────────────────────────────────────

def _drawCommander(screen, unit, ix, iy, color):
    GOLD  = (218, 165, 32)
    GOLD2 = (255, 210, 60)
    r     = unit.radius + 2   # ~16 px
    t     = pygame.time.get_ticks()

    # Aura — pulsing
    pulse  = 0.5 + 0.5 * math.sin(t * 0.003)
    aura_a = int(14 + 10 * pulse)
    aura_s = pygame.Surface((COMMANDER_AURA_RADIUS * 2, COMMANDER_AURA_RADIUS * 2),
                            pygame.SRCALPHA)
    team_tint = (80, 120, 220, aura_a) if unit.team == 'player' else (220, 80, 80, aura_a)
    pygame.draw.circle(aura_s, team_tint,
                       (COMMANDER_AURA_RADIUS, COMMANDER_AURA_RADIUS),
                       COMMANDER_AURA_RADIUS)
    screen.blit(aura_s, (ix - COMMANDER_AURA_RADIUS, iy - COMMANDER_AURA_RADIUS))

    # Aura ring — two nested rings for depth
    ring_a = int(50 + 30 * pulse)
    pygame.draw.circle(screen, (*GOLD,  ring_a),       (ix, iy), COMMANDER_AURA_RADIUS,     1)
    pygame.draw.circle(screen, (*GOLD2, ring_a // 2),  (ix, iy), COMMANDER_AURA_RADIUS - 3, 1)

    # Selection glow
    if unit.selected:
        _selectionGlow(screen, ix, iy, r + 2)

    # Diamond body
    bright = tuple(min(255, c + 60) for c in color)
    dark   = tuple(max(0,   c - 50) for c in color)
    diamond = [(ix, iy - r), (ix + r, iy), (ix, iy + r), (ix - r, iy)]

    # Subtle inner fill for depth
    inner_r = r - 4
    inner   = [(ix, iy - inner_r), (ix + inner_r, iy),
               (ix, iy + inner_r), (ix - inner_r, iy)]
    pygame.draw.polygon(screen, color,  diamond)
    pygame.draw.polygon(screen, bright, inner)

    # Gold border — double line for weight
    pygame.draw.polygon(screen, GOLD,  diamond, 3)
    pygame.draw.polygon(screen, GOLD2, diamond, 1)

    # Crown: three triangular points at top
    crown_y = iy - r + 3
    for dx, height in ((-7, 6), (0, 8), (7, 6)):
        tip = [(ix + dx - 3, crown_y), (ix + dx + 3, crown_y),
               (ix + dx,     crown_y - height)]
        pygame.draw.polygon(screen, GOLD,  tip)
        pygame.draw.polygon(screen, GOLD2, tip, 1)

    if unit.selected:
        pygame.draw.polygon(screen, YELLOW, diamond, 2)

    _drawBars(screen, ix - r, iy - r - 12, r * 2, unit)
