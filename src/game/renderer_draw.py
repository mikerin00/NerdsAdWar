# Module: renderer_draw
# Standalone drawing functions: units, headquarters, outposts and geometry helpers

import math

import pygame

from src.constants import UNIT_COLORS, YELLOW, WHITE, BLACK, COMMANDER_AURA_RADIUS

# ── Cached fonts (created once, reused every frame) ──────────────────────────
_fontSmall = None

def _getSmallFont():
    global _fontSmall
    if _fontSmall is None:
        _fontSmall = pygame.font.SysFont(None, 18)
    return _fontSmall


# ── Geometry helpers used by territory rendering ──────────────────────────────

def chaikin(pts):
    """One round of Chaikin subdivision — rounds sharp corners into smooth curves."""
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
    """Remove collinear intermediate points — keeps only actual turning points."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        dx1, dy1 = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        dx2, dy2 = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        if dx1 * dy2 - dy1 * dx2 != 0:
            out.append(pts[i])
    out.append(pts[-1])
    return out


# ── Entity draw functions ─────────────────────────────────────────────────────

def _drawStar(screen, cx, cy, r_outer, r_inner, color, points=5):
    """Draw a filled star polygon centred on (cx, cy)."""
    pts = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        r     = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    pygame.draw.polygon(screen, color, pts)


def drawOutpost(screen, outpost):
    ix, iy = int(outpost.x), int(outpost.y)

    pygame.draw.rect(screen, (95, 85, 70),   (ix - 10, iy - 8, 20, 16))
    pygame.draw.rect(screen, (130, 118, 98), (ix - 10, iy - 8, 20, 16), 2)

    for bx in (ix - 9, ix - 1, ix + 7):
        pygame.draw.rect(screen, (95, 85, 70), (bx, iy - 14, 6, 7))

    if outpost.team is not None:
        flagColor = (70, 130, 180) if outpost.team == 'player' else (220, 80, 80)
        pygame.draw.line(screen, (80, 70, 55), (ix - 4, iy - 14), (ix - 4, iy - 28), 2)
        pts = [(ix - 4, iy - 28), (ix + 9, iy - 23), (ix - 4, iy - 18)]
        pygame.draw.polygon(screen, flagColor, pts)

    barW = 28
    barX = ix - barW // 2
    barY = iy + 11
    pygame.draw.rect(screen, (60, 60, 60), (barX, barY, barW, 5))
    ctrl = outpost.control
    half = barW // 2
    if ctrl > 0:
        pygame.draw.rect(screen, (70, 130, 180), (barX + half, barY, int(half * ctrl), 5))
    elif ctrl < 0:
        fillW = int(half * abs(ctrl))
        pygame.draw.rect(screen, (220, 80, 80), (barX + half - fillW, barY, fillW, 5))
    pygame.draw.rect(screen, (200, 200, 200), (barX, barY, barW, 5), 1)
    pygame.draw.line(screen, (200, 200, 200),
                     (barX + barW // 2, barY - 1), (barX + barW // 2, barY + 6), 1)

    # Strategic outpost: gold star above the structure
    if getattr(outpost, 'strategic', False):
        _drawStar(screen, ix, iy - 38, 9, 4, (220, 190, 50))
        _drawStar(screen, ix, iy - 38, 9, 4, (255, 220, 80), points=5)  # bright fill
        pygame.draw.circle(screen, (255, 220, 80), (ix, iy - 38), 10, 1)  # ring
        label = _getSmallFont().render("★", True, (255, 220, 80))
    else:
        label = _getSmallFont().render("OP", True, (180, 180, 180))
    screen.blit(label, (ix - label.get_width() // 2, iy + 22))


def drawHeadquarters(screen, hq):
    ix, iy    = int(hq.x), int(hq.y)
    teamColor = (70, 130, 180) if hq.team == 'player' else (220, 80, 80)

    pygame.draw.circle(screen, (*teamColor, 60), (ix, iy), hq.CAPTURE_RADIUS, 1)
    pygame.draw.rect(screen, (90, 80, 65),   (ix - 18, iy - 10, 36, 20))
    pygame.draw.rect(screen, (120, 110, 90), (ix - 18, iy - 10, 36, 20), 2)

    for bx in (ix - 12, ix - 2, ix + 8):
        pygame.draw.rect(screen, (90, 80, 65),   (bx, iy - 17, 8, 8))
        pygame.draw.rect(screen, (120, 110, 90), (bx, iy - 17, 8, 8), 1)

    pygame.draw.line(screen, (80, 70, 55), (ix, iy - 10), (ix, iy - 32), 2)
    pts = [(ix, iy - 32), (ix + 14, iy - 26), (ix, iy - 20)]
    pygame.draw.polygon(screen, teamColor, pts)

    if hq.captureProgress > 0:
        enemyColor = (220, 80, 80) if hq.team == 'player' else (70, 130, 180)
        frac       = hq.captureProgress / hq.CAPTURE_TIME
        r          = hq.CAPTURE_RADIUS
        pygame.draw.arc(screen, enemyColor,
                        (ix - r, iy - r, r * 2, r * 2),
                        math.pi / 2, math.pi / 2 + frac * 2 * math.pi, 4)

    label = _getSmallFont().render("HQ", True, teamColor)
    screen.blit(label, (ix - label.get_width() // 2, iy + 14))


def drawUnit(screen, unit):
    ix, iy = int(unit.x), int(unit.y)
    # Prefer a per-unit color override (set by the renderer when MP slot colors
    # are in play); fall back to the default team palette.
    color  = getattr(unit, '_drawColor', None) \
             or UNIT_COLORS[unit.team][unit.unitType]
    if unit.routing:
        color = (230, 230, 230)
    if unit.reformTimer > 0:
        color = tuple(max(0, c - 80) for c in color)
    if unit.unitType == 'commander':
        _drawCommander(screen, unit, ix, iy, color)
    elif unit.unitType == 'heavy_infantry':
        _drawHeavyInfantry(screen, unit, ix, iy, color)
    elif unit.unitType == 'infantry':
        _drawInfantry(screen, unit, ix, iy, color)
    else:
        _drawCircleUnit(screen, unit, ix, iy, color)


def _drawCommander(screen, unit, ix, iy, color):
    """Diamond shape with a gold star and aura ring — the most important unit."""
    GOLD = (218, 165, 32)
    r    = unit.radius + 2   # 16 px

    # Aura circle (always visible, faint)
    aura_surf = pygame.Surface((COMMANDER_AURA_RADIUS * 2, COMMANDER_AURA_RADIUS * 2),
                               pygame.SRCALPHA)
    team_tint = (80, 120, 220, 18) if unit.team == 'player' else (220, 80, 80, 18)
    pygame.draw.circle(aura_surf, team_tint,
                       (COMMANDER_AURA_RADIUS, COMMANDER_AURA_RADIUS), COMMANDER_AURA_RADIUS)
    screen.blit(aura_surf, (ix - COMMANDER_AURA_RADIUS, iy - COMMANDER_AURA_RADIUS))
    pygame.draw.circle(screen, (*GOLD[:3], 60),
                       (ix, iy), COMMANDER_AURA_RADIUS, 1)

    # Selection ring
    if unit.selected:
        pygame.draw.circle(screen, YELLOW, (ix, iy), r + 6, 2)

    # Diamond body (rotated square)
    diamond = [(ix, iy - r), (ix + r, iy), (ix, iy + r), (ix - r, iy)]
    pygame.draw.polygon(screen, color, diamond)
    pygame.draw.polygon(screen, GOLD,  diamond, 2)

    # Crown: three small gold triangles on top
    crown_y = iy - r + 2
    for dx in (-6, 0, 6):
        tip = [(ix + dx - 3, crown_y), (ix + dx + 3, crown_y),
               (ix + dx,     crown_y - 5)]
        pygame.draw.polygon(screen, GOLD, tip)

    # HP / morale bars (same helper as other units)
    _drawBars(screen, ix - r, iy - r - 10, r * 2, unit)


def _drawHeavyInfantry(screen, unit, ix, iy, color):
    """Square shield-wall block, slightly larger than regular infantry."""
    s, hs = 28, 14
    if unit.selected:
        sel = [(ix - hs - 4, iy - hs - 4), (ix + hs + 4, iy - hs - 4),
               (ix + hs + 4, iy + hs + 4), (ix - hs - 4, iy + hs + 4)]
        pygame.draw.polygon(screen, YELLOW, sel, 2)

    pygame.draw.rect(screen, color, (ix - hs, iy - hs, s, s))

    # Shield symbol: rounded inner rect + cross bars
    inner = 5
    pygame.draw.rect(screen, WHITE, (ix - hs + inner, iy - hs + inner,
                                     s - inner * 2, s - inner * 2), 1)
    pygame.draw.line(screen, WHITE, (ix, iy - hs + inner), (ix, iy + hs - inner), 1)
    pygame.draw.line(screen, WHITE, (ix - hs + inner, iy), (ix + hs - inner, iy), 1)

    # Shield wall glow when active
    if getattr(unit, 'shieldWall', False):
        pygame.draw.rect(screen, (255, 215, 0), (ix - hs, iy - hs, s, s), 2)
    else:
        pygame.draw.rect(screen, WHITE, (ix - hs, iy - hs, s, s), 2)

    _drawBars(screen, ix - hs, iy - hs - 10, s, unit)


def _drawInfantry(screen, unit, ix, iy, color):
    if unit.inSquare:
        s, hs = 26, 13
        if unit.selected:
            sel = [(ix - hs - 4, iy - hs - 4), (ix + hs + 4, iy - hs - 4),
                   (ix + hs + 4, iy + hs + 4), (ix - hs - 4, iy + hs + 4)]
            pygame.draw.polygon(screen, YELLOW, sel, 2)
        pygame.draw.rect(screen, color, (ix - hs, iy - hs, s, s))
        pygame.draw.line(screen, WHITE, (ix - hs + 2, iy - hs + 5), (ix + hs - 2, iy - hs + 5), 1)
        pygame.draw.line(screen, WHITE, (ix - hs + 2, iy + hs - 5), (ix + hs - 2, iy + hs - 5), 1)
        pygame.draw.line(screen, WHITE, (ix - hs + 5, iy - hs + 2), (ix - hs + 5, iy + hs - 2), 1)
        pygame.draw.line(screen, WHITE, (ix + hs - 5, iy - hs + 2), (ix + hs - 5, iy + hs - 2), 1)
        pygame.draw.rect(screen, (255, 165, 0), (ix - hs, iy - hs, s, s), 2)
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
            sel = [rot(-hw - 4, -hh - 4), rot(hw + 4, -hh - 4),
                   rot(hw + 4, hh + 4),   rot(-hw - 4, hh + 4)]
            pygame.draw.polygon(screen, YELLOW, sel, 2)
        pygame.draw.polygon(screen, color, corners)
        for row in range(1, 3):
            t  = row / 3
            ly = -hh + t * fh
            pygame.draw.line(screen, WHITE,
                             (int(rot(-hw + 2, ly)[0]), int(rot(-hw + 2, ly)[1])),
                             (int(rot(hw - 2,  ly)[0]), int(rot(hw - 2,  ly)[1])), 1)
        bx, by = ix - fw // 2, iy - fh // 2 - 10

    _drawBars(screen, bx, by, fw, unit)


def _drawCircleUnit(screen, unit, ix, iy, color):
    r = unit.radius
    if unit.selected:
        pygame.draw.circle(screen, YELLOW, (ix, iy), r + 4, 2)
    pygame.draw.circle(screen, color, (ix, iy), r)

    if unit.unitType == 'cavalry':
        pygame.draw.line(screen, WHITE, (ix - r + 2, iy), (ix + r - 2, iy), 2)
        if unit.chargeFrames > 45:
            pygame.draw.circle(screen, (255, 140, 0), (ix, iy), r + 6, 2)
    elif unit.unitType == 'artillery':
        pygame.draw.line(screen, WHITE, (ix - r + 3, iy), (ix + r - 3, iy), 2)
        pygame.draw.line(screen, WHITE, (ix, iy - r + 3), (ix, iy + r - 3), 2)
        if unit.deployed:
            pygame.draw.circle(screen, (0, 220, 0), (ix, iy), r + 5, 2)
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

    _drawBars(screen, ix - r, iy - r - 8, r * 2, unit)


def _drawBars(screen, bx, by, bw, unit):
    ratio    = max(unit.hp / unit.maxHp, 0)
    barColor = (int(255 * (1 - ratio)), int(255 * ratio), 0)
    pygame.draw.rect(screen, BLACK,    (bx, by, bw, 4))
    pygame.draw.rect(screen, barColor, (bx, by, int(bw * ratio), 4))

    pygame.draw.rect(screen, BLACK,          (bx, by - 5, bw, 3))
    pygame.draw.rect(screen, (100, 160, 255), (bx, by - 5, int(bw * unit.morale / 100), 3))

    s           = unit.supplyStrength
    supplyColor = (int(160 * (1 - s)), int(80 + 120 * s), 0)
    pygame.draw.rect(screen, BLACK,       (bx, by - 10, bw, 3))
    pygame.draw.rect(screen, supplyColor, (bx, by - 10, int(bw * s), 3))
