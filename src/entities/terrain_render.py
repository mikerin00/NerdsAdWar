# Module: terrain_render
# Pure rendering helper: turns a TerrainMap into a pre-rendered pygame.Surface.

import math
import random

import pygame

from src.entities.terrain_helpers import (
    CELL, RIVER_WIDTH, BRIDGE_HALF, BRIDGE_WIDTH,
)


def buildTerrainSurface(terrain):
    gw  = terrain.width  // CELL + 2
    gh  = terrain.height // CELL + 2
    rng = random.Random(99)

    BASE       = (74,  117,  44)
    HILL_HI    = (148, 158,  72)
    FOREST     = (38,   88,  28)
    SHADOW_COL = (50,   78,  28)
    LAKE_COL   = (42,   82, 135)
    ROCK_COL   = (120, 110, 100)
    ROCK_HI    = (155, 145, 130)

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
    WATER      = (58,  100, 150)
    WATER_LITE = (88,  138, 182)
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

    # ── highland contour lines ───────────────────────────────────────────
    sx, sy = terrain.width / gw, terrain.height / gh
    for gy in range(gh):
        for gx in range(gw):
            cell = (gx, gy)
            if cell in terrain._lake or cell in terrain._rock:
                continue
            if terrain._height.get((gx, gy), 0.5) >= terrain.HIGHLAND_THRESH:
                rx, ry = int(gx * sx), int(gy * sy)
                cw, ch = int(sx), int(sy)
                for n in range(1, 4):
                    ox = n * (cw // 4)
                    pygame.draw.line(surf, SHADOW_COL,
                                     (rx + ox, ry + ch - 2), (rx + cw - 2, ry + ox), 1)

    # ── forest trees ─────────────────────────────────────────────────────
    for gy in range(gh):
        for gx in range(gw):
            if terrain._forest.get((gx, gy), False):
                rx, ry = int(gx * sx), int(gy * sy)
                cw, ch = int(sx), int(sy)
                for _ in range(5):
                    tx = rx + rng.randint(3, cw - 3)
                    ty = ry + rng.randint(3, ch - 3)
                    pygame.draw.circle(surf, (28, 70, 18), (tx, ty), rng.randint(3, 6))

    # ── lake shore detail ────────────────────────────────────────────────
    SHORE_COL  = (70, 115, 155)
    SHORE_LITE = (100, 150, 190)
    for (gx, gy) in terrain._lake:
        rx, ry = int(gx * sx), int(gy * sy)
        cw, ch = int(sx), int(sy)
        # Check if this is an edge cell (has a non-lake neighbour)
        isEdge = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (gx + dx, gy + dy) not in terrain._lake:
                isEdge = True
                break
        if isEdge:
            pygame.draw.rect(surf, SHORE_COL, (rx, ry, cw, ch), 1)
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
        # Edge highlight
        isEdge = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (gx + dx, gy + dy) not in terrain._rock:
                isEdge = True
                break
        if isEdge:
            pygame.draw.rect(surf, ROCK_SHADOW, (rx, ry, cw, ch), 1)
        # Rock texture — small dots and cracks
        for _ in range(3):
            tx = rx + rng.randint(1, max(2, cw - 1))
            ty = ry + rng.randint(1, max(2, ch - 1))
            col = ROCK_LITE if rng.random() > 0.5 else ROCK_SHADOW
            pygame.draw.circle(surf, col, (tx, ty), rng.randint(1, 3))

    terrain.surface = surf
