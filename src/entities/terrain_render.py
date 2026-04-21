# Module: terrain_render
# Pure rendering helper: turns a TerrainMap into a pre-rendered pygame.Surface.

import math
import random

import pygame

from src.entities.terrain_helpers import (
    CELL, RIVER_WIDTH, BRIDGE_HALF, BRIDGE_WIDTH,
)


# Per-biome color palettes.  Keys mirror TerrainMap.BIOMES; 'DEFAULT' is the fallback.
_BIOME_PAL = {
    'GRASSLAND': {
        'base':        (82,  130,  52),
        'hill_hi':     (165, 178,  82),
        'forest':      (36,   85,  24),
        'lake':        (52,  105, 170),
        'rock':        (122, 112, 100),
        'rock_hi':     (158, 148, 132),
        'water':       (55,  105, 158),
        'water_lite':  (88,  142, 192),
        'stipple':     (48,   82,  28),
        'tree':        (26,   68,  16),
    },
    'RIVER_VALLEY': {
        'base':        (62,  118,  40),
        'hill_hi':     (132, 152,  62),
        'forest':      (28,   78,  20),
        'lake':        (45,   92, 152),
        'rock':        (115, 106,  92),
        'rock_hi':     (152, 142, 126),
        'water':       (52,  102, 158),
        'water_lite':  (85,  140, 194),
        'stipple':     (44,   80,  26),
        'tree':        (22,   65,  14),
    },
    'LAKELANDS': {
        'base':        (72,  125,  48),
        'hill_hi':     (148, 164,  76),
        'forest':      (34,   84,  24),
        'lake':        (38,   78, 148),
        'rock':        (118, 108,  96),
        'rock_hi':     (155, 145, 128),
        'water':       (45,   90, 155),
        'water_lite':  (78,  128, 190),
        'stipple':     (46,   82,  28),
        'tree':        (24,   68,  16),
    },
    'HIGHLANDS': {
        'base':        (96,  108,  68),
        'hill_hi':     (155, 152, 128),
        'forest':      (48,   82,  36),
        'lake':        (48,   88, 148),
        'rock':        (138, 128, 112),
        'rock_hi':     (175, 165, 148),
        'water':       (50,   95, 152),
        'water_lite':  (82,  130, 185),
        'stipple':     (78,   92,  54),
        'tree':        (36,   68,  26),
    },
    'FOREST': {
        'base':        (45,   98,  30),
        'hill_hi':     (82,  118,  50),
        'forest':      (22,   68,  14),
        'lake':        (36,   76, 138),
        'rock':        (112, 104,  92),
        'rock_hi':     (148, 140, 124),
        'water':       (42,   88, 145),
        'water_lite':  (72,  122, 178),
        'stipple':     (32,   72,  20),
        'tree':        (18,   58,  10),
    },
    'DRY_PLAINS': {
        'base':        (188, 165,  92),
        'hill_hi':     (208, 190, 118),
        'forest':      (108, 125,  55),
        'lake':        (72,  120, 155),
        'rock':        (172, 155, 128),
        'rock_hi':     (195, 178, 152),
        'water':       (68,  115, 148),
        'water_lite':  (100, 148, 178),
        'stipple':     (162, 140,  72),
        'tree':        (88,  105,  42),
    },
    'MIXED': {
        'base':        (75,  122,  48),
        'hill_hi':     (152, 162,  78),
        'forest':      (34,   84,  24),
        'lake':        (48,   92, 152),
        'rock':        (120, 110,  98),
        'rock_hi':     (156, 146, 130),
        'water':       (52,  100, 155),
        'water_lite':  (86,  138, 190),
        'stipple':     (48,   82,  28),
        'tree':        (24,   68,  16),
    },
    'TWIN_RIVERS': {
        'base':        (60,  112,  38),
        'hill_hi':     (128, 148,  62),
        'forest':      (28,   76,  20),
        'lake':        (44,   88, 148),
        'rock':        (112, 104,  92),
        'rock_hi':     (148, 138, 122),
        'water':       (50,   98, 155),
        'water_lite':  (82,  135, 190),
        'stipple':     (42,   78,  24),
        'tree':        (20,   62,  12),
    },
    'WETLANDS': {
        'base':        (65,   98,  60),
        'hill_hi':     (115, 128,  85),
        'forest':      (32,   72,  28),
        'lake':        (50,   85, 118),
        'rock':        (105, 108,  95),
        'rock_hi':     (140, 142, 125),
        'water':       (52,   86, 118),
        'water_lite':  (78,  115, 145),
        'stipple':     (44,   76,  38),
        'tree':        (24,   60,  20),
    },
}
_BIOME_PAL['DEFAULT'] = _BIOME_PAL['GRASSLAND']


def buildTerrainSurface(terrain):
    gw  = terrain.width  // CELL + 2
    gh  = terrain.height // CELL + 2
    rng = random.Random(99)

    pal = _BIOME_PAL.get(getattr(terrain, 'biome', None), _BIOME_PAL['DEFAULT'])

    BASE      = pal['base']
    HILL_HI   = pal['hill_hi']
    FOREST    = pal['forest']
    LAKE_COL  = pal['lake']
    ROCK_COL  = pal['rock']
    ROCK_HI   = pal['rock_hi']

    small = pygame.Surface((gw, gh))
    for gy in range(gh):
        for gx in range(gw):
            cell = (gx, gy)
            if cell in terrain._lake:
                small.set_at((gx, gy), LAKE_COL)
                continue
            if cell in terrain._rock:
                # Rock color with slight height variation
                h  = terrain._height.get(cell, 0.5)
                t  = max(0.0, min(1.0, (h - 0.6) / 0.3))
                color = tuple(int(ROCK_COL[i] + (ROCK_HI[i] - ROCK_COL[i]) * t) for i in range(3))
                small.set_at((gx, gy), color)
                continue
            h  = terrain._height.get((gx, gy), 0.5)
            fs = terrain._forestStrength.get((gx, gy), 0.0)
            t  = max(0.0, min(1.0, (h - 0.28) / 0.55))
            color = tuple(int(BASE[i] + (HILL_HI[i] - BASE[i]) * t) for i in range(3))
            if fs > 0:
                color = tuple(int(color[i] * (1 - fs) + FOREST[i] * fs) for i in range(3))
            small.set_at((gx, gy), color)

    surf = pygame.transform.smoothscale(small, (terrain.width, terrain.height))

    # ── river ────────────────────────────────────────────────────────────
    WATER      = pal['water']
    WATER_LITE = pal['water_lite']
    for river in terrain.rivers:
        ipts = [(int(p[0]), int(p[1])) for p in river]
        if len(ipts) >= 2:
            pygame.draw.lines(surf, WATER,      False, ipts, RIVER_WIDTH * 2 + 2)
            pygame.draw.lines(surf, WATER_LITE, False, ipts, max(3, RIVER_WIDTH - 4))

    # ── bridges ──────────────────────────────────────────────────────────
    BRIDGE_COL  = (145, 112, 68)
    BRIDGE_DARK = (100,  76, 44)
    PLANK_COL   = (130,  98, 58)
    for b in terrain.bridges:
        bx, by  = b['x'], b['y']
        ang     = b['angle']
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        pdx, pdy = -sin_a, cos_a
        rdx, rdy =  cos_a, sin_a
        BL, BW   = BRIDGE_HALF, BRIDGE_WIDTH
        corners  = [
            (int(bx + pdx*BL + rdx*BW), int(by + pdy*BL + rdy*BW)),
            (int(bx - pdx*BL + rdx*BW), int(by - pdy*BL + rdy*BW)),
            (int(bx - pdx*BL - rdx*BW), int(by - pdy*BL - rdy*BW)),
            (int(bx + pdx*BL - rdx*BW), int(by + pdy*BL - rdy*BW)),
        ]
        pygame.draw.polygon(surf, BRIDGE_COL,  corners)
        pygame.draw.polygon(surf, BRIDGE_DARK, corners, 2)
        for step in range(-3, 4):
            t  = step / 4
            mx = int(bx + pdx * BL * t)
            my = int(by + pdy * BL * t)
            pygame.draw.line(surf, PLANK_COL,
                             (mx + int(rdx * BW), my + int(rdy * BW)),
                             (mx - int(rdx * BW), my - int(rdy * BW)), 1)

    # ── highland stipple dots ────────────────────────────────────────────
    sx, sy = terrain.width / gw, terrain.height / gh
    STIPPLE = pal['stipple']
    for gy in range(gh):
        for gx in range(gw):
            cell = (gx, gy)
            if cell in terrain._lake or cell in terrain._rock:
                continue
            if terrain._height.get((gx, gy), 0.5) >= terrain.HIGHLAND_THRESH:
                rx, ry = int(gx * sx), int(gy * sy)
                cw, ch = int(sx), int(sy)
                step = 5
                for dy in range(2, ch - 1, step):
                    for dx in range(2 + (dy // step % 2) * (step // 2), cw - 1, step):
                        surf.set_at((rx + dx, ry + dy), STIPPLE)

    # ── forest trees ─────────────────────────────────────────────────────
    for gy in range(gh):
        for gx in range(gw):
            if terrain._forest.get((gx, gy), False):
                rx, ry = int(gx * sx), int(gy * sy)
                cw, ch = int(sx), int(sy)
                for _ in range(5):
                    tx = rx + rng.randint(3, cw - 3)
                    ty = ry + rng.randint(3, ch - 3)
                    pygame.draw.circle(surf, pal['tree'], (tx, ty), rng.randint(3, 6))

    # ── lake shore detail ────────────────────────────────────────────────
    SHORE_LITE = (100, 150, 190)
    for (gx, gy) in terrain._lake:
        rx, ry = int(gx * sx), int(gy * sy)
        cw, ch = int(sx), int(sy)
        # Water shimmer
        if rng.random() < 0.3:
            lx = rx + rng.randint(2, max(3, cw - 2))
            ly = ry + rng.randint(2, max(3, ch - 2))
            pygame.draw.line(surf, SHORE_LITE, (lx, ly), (lx + rng.randint(2, 5), ly), 1)

    # ── rock detail ──────────────────────────────────────────────────────
    ROCK_SHADOW = (90, 82, 72)
    ROCK_LITE   = (170, 162, 148)
    for (gx, gy) in terrain._rock:
        rx, ry = int(gx * sx), int(gy * sy)
        cw, ch = int(sx), int(sy)
        # Rock texture — small dots and cracks
        for _ in range(3):
            tx = rx + rng.randint(1, max(2, cw - 1))
            ty = ry + rng.randint(1, max(2, ch - 1))
            col = ROCK_LITE if rng.random() > 0.5 else ROCK_SHADOW
            pygame.draw.circle(surf, col, (tx, ty), rng.randint(1, 3))

    terrain.surface = surf
