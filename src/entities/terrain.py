# Module: terrain
# TerrainMap — heightmap, forest, rivers, bridges, lakes, rocks, terrain queries, pre-rendered surface

import math
import random

import pygame

from src.entities.terrain_helpers import (
    CELL, RIVER_WIDTH, BRIDGE_HALF, BRIDGE_WIDTH,
    LAKE_THRESH, ROCK_THRESH, OBSTACLE_MIN_CELLS,
    smoothNoise, chaikin, distToSeg, floodFill, filterSmallPatches,
    astarGrid, simplifyPath,
)


class TerrainMap:

    # ── Biome definitions ───────────────────────────────────────────────────
    # Each biome controls which features appear and how aggressively.
    #   has_river      – generate a river with bridges
    #   lake_thresh    – noise threshold for lakes (lower = more lakes, None = no lakes)
    #   rock_thresh    – noise threshold for rocks (lower = more rocks, None = no rocks)
    #   forest_thresh  – noise threshold for forests (lower = more forest)
    #   highland_thresh– height above which terrain counts as high ground
    #   min_cells      – minimum patch size for lake/rock (bigger = fewer but larger)

    # n_rivers: 0 = no river, 1 = single river, 2 = twin rivers
    # lake_thresh: higher value = fewer/smaller lakes  (None = no lakes)
    # min_cells: smallest patch kept (cells × 20×20 px each)
    BIOMES = {
        'GRASSLAND':   {'n_rivers': 0, 'lake_thresh': None,  'rock_thresh': None,
                        'forest_thresh': 0.62, 'highland_thresh': 0.65, 'min_cells': 12},
        'RIVER_VALLEY':{'n_rivers': 1, 'lake_thresh': 0.80,  'rock_thresh': 0.80,
                        'forest_thresh': 0.54, 'highland_thresh': 0.58, 'min_cells': 12},
        'LAKELANDS':   {'n_rivers': 0, 'lake_thresh': 0.74,  'rock_thresh': 0.82,
                        'forest_thresh': 0.58, 'highland_thresh': 0.60, 'min_cells': 14},
        'HIGHLANDS':   {'n_rivers': 0, 'lake_thresh': 0.84,  'rock_thresh': 0.64,
                        'forest_thresh': 0.60, 'highland_thresh': 0.48, 'min_cells': 12},
        'FOREST':      {'n_rivers': 1, 'lake_thresh': 0.80,  'rock_thresh': 0.84,
                        'forest_thresh': 0.46, 'highland_thresh': 0.62, 'min_cells': 14},
        'MIXED':       {'n_rivers': 1, 'lake_thresh': 0.78,  'rock_thresh': 0.76,
                        'forest_thresh': 0.56, 'highland_thresh': 0.60, 'min_cells': 12},
        'DRY_PLAINS':  {'n_rivers': 0, 'lake_thresh': None,  'rock_thresh': 0.68,
                        'forest_thresh': 0.68, 'highland_thresh': 0.55, 'min_cells': 14},
        'TWIN_RIVERS': {'n_rivers': 2, 'lake_thresh': 0.84,  'rock_thresh': 0.80,
                        'forest_thresh': 0.54, 'highland_thresh': 0.58, 'min_cells': 14},
    }

    # Maximum generation attempts before accepting (prevents infinite loop)
    MAX_GEN_ATTEMPTS = 40

    def __init__(self, width, height, seed=17, biome=None, customMap=None):
        self.width  = width
        self.height = height

        rng = random.Random(seed)
        if customMap is not None:
            # Sandbox: rehydrate terrain from a saved JSON dict instead of
            # the procedural pipeline. No rivers/bridges (editor doesn't draw
            # them yet); heightmap is smooth noise so grass isn't totally flat.
            self.biome = 'CUSTOM'
            self._biomeParams = self.BIOMES['GRASSLAND']
            self._loadFromCustom(customMap, seed)
        else:
            if biome and biome != 'RANDOM' and biome in self.BIOMES:
                self.biome = biome
            else:
                self.biome = rng.choice(list(self.BIOMES.keys()))
            self._biomeParams = self.BIOMES[self.biome]

            for attempt in range(self.MAX_GEN_ATTEMPTS):
                trySeed = seed + attempt
                self._generate(width, height, trySeed)
                if self._validatePath():
                    break
            else:
                self._lake.clear()
                self._rock.clear()

        self._buildPassGrid()
        self.surface = None

    def _loadFromCustom(self, data, seed):
        """Build terrain state from a saved-map dict (sandbox v1/v2).
        Keys:
          lake, rock, forest : list of [gx, gy] cells (CELL=20 grid)
          highland           : list of [gx, gy] cells → forced high ground
          rivers             : list of polylines (list of [x, y] control pts)
          bridges            : list of [x, y] for bridge placements"""
        self.FOREST_THRESH   = 0.5
        self.HIGHLAND_THRESH = 0.65

        # Base height: smooth noise so grass isn't dead-flat.
        h1 = smoothNoise(self.width, self.height, 220, seed)
        h2 = smoothNoise(self.width, self.height, 90,  seed + 3)
        self._height = {k: h1[k] * 0.65 + h2[k] * 0.35 for k in h1}
        # Stamp highland cells — force height above the threshold
        for c in data.get('highland', []):
            self._height[tuple(c)] = 0.85

        self._lake   = set(tuple(c) for c in data.get('lake',   []))
        self._rock   = set(tuple(c) for c in data.get('rock',   []))
        forest_cells = set(tuple(c) for c in data.get('forest', []))
        self._forest = {k: (k in forest_cells) for k in self._height}
        self._forestStrength = {k: (0.9 if self._forest.get(k) else 0.0)
                                for k in self._forest}

        # ── Rivers: smooth each polyline via chaikin (same as _generateRivers)
        raw_rivers = data.get('rivers', []) or []
        self.rivers = []
        for ctrl in raw_rivers:
            if len(ctrl) < 2:
                continue
            pts = [(float(p[0]), float(p[1])) for p in ctrl]
            for _ in range(4):
                pts = chaikin(pts)
            self.rivers.append(pts)

        # ── Bridges: compute an angle by sampling the nearest river segment
        self.bridges = []
        for b in data.get('bridges', []) or []:
            bx, by = float(b[0]), float(b[1])
            best_ang, best_d = 0.0, float('inf')
            for river in self.rivers:
                for i in range(len(river) - 1):
                    (x0, y0), (x1, y1) = river[i], river[i + 1]
                    d = distToSeg(bx, by, x0, y0, x1, y1)
                    if d < best_d:
                        best_d = d
                        best_ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) + 90
            # Perpendicular to river = bridge direction
            self.bridges.append({'x': bx, 'y': by, 'angle': best_ang})

        self._buildRiverGrid()
        if self.bridges:
            self._clearAroundBridges()

    def _generate(self, width, height, seed):
        rng    = random.Random(seed)
        params = self._biomeParams

        # ── heightmap ─────────────────────────────────────────────────────────
        h1 = smoothNoise(width, height, 220, seed)
        h2 = smoothNoise(width, height, 90,  seed + 3)
        self._height = {k: h1[k] * 0.65 + h2[k] * 0.35 for k in h1}

        # ── forest ────────────────────────────────────────────────────────────
        forestThresh   = params['forest_thresh']
        highlandThresh = params['highland_thresh']

        f1   = smoothNoise(width, height, 150, seed + 11)
        f2   = smoothNoise(width, height, 60,  seed + 13)
        fRaw = {k: f1[k] * 0.55 + f2[k] * 0.45 for k in f1}
        self._forest = {
            k: fRaw[k] > forestThresh and self._height.get(k, 0) < highlandThresh
            for k in fRaw
        }
        self._forestStrength = {
            k: max(0.0, min(1.0, (fRaw[k] - forestThresh) / 0.12))
               if self._forest.get(k) else 0.0
            for k in fRaw
        }

        # Store thresholds for terrain queries
        self.HIGHLAND_THRESH = highlandThresh
        self.FOREST_THRESH   = forestThresh

        # ── rivers (randomised, optional) ────────────────────────────────────
        n_rivers = params['n_rivers']
        if n_rivers > 0:
            self._generateRivers(random.Random(seed + 50), n=n_rivers)
        else:
            self.rivers  = []
            self.bridges = []

        # ── lakes (optional) ─────────────────────────────────────────────────
        if params['lake_thresh'] is not None:
            self._generateLakes(seed, params['lake_thresh'], params['min_cells'])
        else:
            self._lake = set()

        # ── rocks (optional) ─────────────────────────────────────────────────
        if params['rock_thresh'] is not None:
            self._generateRocks(seed, params['rock_thresh'], params['min_cells'])
        else:
            self._rock = set()

        # ── clear obstacles near bridges ──────────────────────────────────────
        if self.bridges:
            self._clearAroundBridges()

        # ── clear obstacles from spawn zones ──────────────────────────────────
        self._clearSpawnZones()

        # ── build river grid cache for fast isOnRiver ─────────────────────────
        self._buildRiverGrid()

    # ── river generation (randomised) ─────────────────────────────────────────

    def _generateRivers(self, rng, n=1):
        """Generate n rivers at evenly-spaced X positions, each with 2-3 bridges."""
        W, H = self.width, self.height
        self.rivers  = []
        self.bridges = []
        PLAINS_RADIUS = 48
        gw = self.width  // CELL + 2
        gh = self.height // CELL + 2

        for ri in range(n):
            # Space rivers evenly across the map centre zone
            frac  = (ri + 1) / (n + 1)
            baseX = W * (0.20 + frac * 0.60 + rng.uniform(-0.06, 0.06))
            baseX = max(W * 0.22, min(W * 0.78, baseX))

            nCtrl = rng.randint(4, 6)
            ctrl  = []
            for j in range(nCtrl):
                t    = j / (nCtrl - 1)
                y    = -10 + t * (H + 20)
                xOff = rng.uniform(-W * 0.12, W * 0.12)
                x    = max(W * 0.15, min(W * 0.85, baseX + xOff))
                ctrl.append((x, y))

            river = ctrl
            for _ in range(5):
                river = chaikin(river)
            self.rivers.append(river)

            # Clear terrain along river banks
            for gy in range(gh):
                for gx in range(gw):
                    cx, cy = gx * CELL, gy * CELL
                    for k in range(len(river) - 1):
                        if distToSeg(cx, cy, river[k][0], river[k][1],
                                     river[k+1][0], river[k+1][1]) < PLAINS_RADIUS:
                            self._height[(gx, gy)]         = 0.30
                            self._forest[(gx, gy)]         = False
                            self._forestStrength[(gx, gy)] = 0.0
                            break

            # Build bridges (2-3 per river at randomised positions)
            arcLen = [0.0]
            for j in range(1, len(river)):
                arcLen.append(arcLen[-1] + math.hypot(
                    river[j][0] - river[j-1][0], river[j][1] - river[j-1][1]))
            total       = arcLen[-1]
            nBridges    = rng.randint(2, 3)
            bridgeFracs = sorted(rng.uniform(0.10, 0.90) for _ in range(nBridges))
            for frac in bridgeFracs:
                target = total * frac
                for j in range(1, len(river)):
                    if arcLen[j] >= target:
                        seg = arcLen[j] - arcLen[j-1]
                        s   = (target - arcLen[j-1]) / max(seg, 0.001)
                        bx  = river[j-1][0] + s * (river[j][0] - river[j-1][0])
                        by  = river[j-1][1] + s * (river[j][1] - river[j-1][1])
                        ang = math.atan2(river[j][1] - river[j-1][1],
                                         river[j][0] - river[j-1][0])
                        self.bridges.append({'x': bx, 'y': by, 'angle': ang})
                        break

    # ── lake generation ───────────────────────────────────────────────────────

    def _generateLakes(self, seed, threshold, minCells):
        gw = self.width  // CELL + 2
        gh = self.height // CELL + 2

        # Smaller noise scale → smaller, more natural lake shapes (not giant blobs)
        lk1 = smoothNoise(self.width, self.height, 100, seed + 30)
        lk2 = smoothNoise(self.width, self.height, 50,  seed + 33)
        lkRaw = {k: lk1[k] * 0.6 + lk2[k] * 0.4 for k in lk1}

        self._lake = set()
        SPAWN_MARGIN_X = self.width * 0.22 // CELL   # keep lakes away from spawn zones
        for (gx, gy), v in lkRaw.items():
            if v <= threshold:
                continue
            # Not on river, not near spawn areas
            if gx < SPAWN_MARGIN_X or gx > (gw - SPAWN_MARGIN_X):
                continue
            px, py = gx * CELL, gy * CELL
            if self.rivers and self._isNearRiver(px, py, RIVER_WIDTH + 30):
                continue
            self._lake.add((gx, gy))

        # Remove tiny patches — only keep big lakes
        filterSmallPatches(self._lake, minCells)

        # Clear forest/highland under lakes
        for c in self._lake:
            self._forest[c]         = False
            self._forestStrength[c] = 0.0
            self._height[c]         = 0.25

    # ── rock generation ───────────────────────────────────────────────────────

    def _generateRocks(self, seed, threshold, minCells):
        gw = self.width  // CELL + 2
        gh = self.height // CELL + 2

        rk1 = smoothNoise(self.width, self.height, 200, seed + 40)
        rk2 = smoothNoise(self.width, self.height, 80,  seed + 43)
        rkRaw = {k: rk1[k] * 0.55 + rk2[k] * 0.45 for k in rk1}

        self._rock = set()
        SPAWN_MARGIN_X = self.width * 0.22 // CELL
        for (gx, gy), v in rkRaw.items():
            if v <= threshold:
                continue
            if gx < SPAWN_MARGIN_X or gx > (gw - SPAWN_MARGIN_X):
                continue
            px, py = gx * CELL, gy * CELL
            if self.rivers and self._isNearRiver(px, py, RIVER_WIDTH + 20):
                continue
            # Not overlapping with a lake
            if (gx, gy) in self._lake:
                continue
            self._rock.add((gx, gy))

        filterSmallPatches(self._rock, minCells)

        # Rocks get high elevation
        for c in self._rock:
            self._forest[c]         = False
            self._forestStrength[c] = 0.0
            self._height[c]         = 0.85

    # ── path validation (BFS from left edge to right edge) ────────────────────

    # Minimum corridor width in grid cells (~5 cells × 20px = 100px)
    MIN_CORRIDOR_CELLS = 5

    def _validatePath(self):
        """Check that passable terrain connects left to right with corridors
        wide enough for troop movement (at least MIN_CORRIDOR_CELLS wide)."""
        gw = self.width  // CELL + 2
        gh = self.height // CELL + 2
        pad = self.MIN_CORRIDOR_CELLS // 2  # dilate obstacles by this many cells

        # Build set of blocked cells = lakes + rocks + river (dilated by pad)
        blocked = set()
        for cell in self._lake:
            for dy in range(-pad, pad + 1):
                for dx in range(-pad, pad + 1):
                    blocked.add((cell[0] + dx, cell[1] + dy))
        for cell in self._rock:
            for dy in range(-pad, pad + 1):
                for dx in range(-pad, pad + 1):
                    blocked.add((cell[0] + dx, cell[1] + dy))
        # River cells (dilated)
        for gy in range(gh):
            for gx in range(gw):
                px, py = gx * CELL, gy * CELL
                if self._isNearRiver(px, py, RIVER_WIDTH):
                    for dy in range(-pad, pad + 1):
                        for dx in range(-pad, pad + 1):
                            blocked.add((gx + dx, gy + dy))

        # Bridges carve out passable corridors (wider than pad)
        bridgeCells = set()
        bridgePad   = pad + 2
        for b in self.bridges:
            bgx, bgy = int(b['x']) // CELL, int(b['y']) // CELL
            for dx in range(-bridgePad, bridgePad + 1):
                for dy in range(-bridgePad, bridgePad + 1):
                    bridgeCells.add((bgx + dx, bgy + dy))

        allCells = set()
        for gy in range(gh):
            for gx in range(gw):
                allCells.add((gx, gy))

        def passable(cell):
            if cell in bridgeCells:
                return True
            return cell not in blocked

        leftEdge  = {(0, gy)      for gy in range(gh) if passable((0, gy))}
        rightEdge = {(gw - 1, gy) for gy in range(gh) if passable((gw - 1, gy))}

        if not leftEdge or not rightEdge:
            return False

        reachable = floodFill(allCells, leftEdge, passable)
        if not (reachable & rightEdge):
            return False

        # Require routes in at least 2 of the 3 vertical thirds so troops
        # always have two distinct approach corridors (top & bottom, etc.)
        thirds_reached = sum(
            1 for b in range(3)
            if reachable & {(gw - 1, gy)
                            for gy in range(gh * b // 3, gh * (b + 1) // 3)
                            if passable((gw - 1, gy))}
        )
        return thirds_reached >= 2

    # ── helper ────────────────────────────────────────────────────────────────

    def _buildRiverGrid(self):
        """Pre-compute which grid cells are river (not bridge) for fast O(1) lookup."""
        gw = self.width  // CELL + 2
        gh = self.height // CELL + 2
        self._riverCells  = set()
        self._bridgeCells = set()
        # Mark bridge cells
        for b in self.bridges:
            cos_a = math.cos(b['angle'])
            sin_a = math.sin(b['angle'])
            # Sample bridge rectangle
            for along in range(-BRIDGE_HALF, BRIDGE_HALF + 1, CELL // 2):
                for across in range(-BRIDGE_WIDTH - 4, BRIDGE_WIDTH + 5, CELL // 2):
                    bx = b['x'] + (-sin_a * along + cos_a * across)
                    by = b['y'] + ( cos_a * along + sin_a * across)
                    self._bridgeCells.add((int(bx) // CELL, int(by) // CELL))
        # Mark river cells
        for river in self.rivers:
            for i in range(len(river) - 1):
                x0, y0 = river[i]
                x1, y1 = river[i + 1]
                segLen = math.hypot(x1 - x0, y1 - y0)
                steps  = max(1, int(segLen / (CELL // 2)))
                for s in range(steps + 1):
                    t  = s / steps
                    px = x0 + (x1 - x0) * t
                    py = y0 + (y1 - y0) * t
                    for offset in range(-RIVER_WIDTH, RIVER_WIDTH + 1, CELL):
                        if segLen > 0:
                            nx = px + (-(y1 - y0) / segLen) * offset
                            ny = py + ((x1 - x0) / segLen) * offset
                        else:
                            nx, ny = px, py
                        cell = (int(nx) // CELL, int(ny) // CELL)
                        if cell not in self._bridgeCells:
                            self._riverCells.add(cell)

    def _clearSpawnZones(self):
        """Remove lake/rock cells from the left and right spawn areas.
        Uses a 22% margin so troops have plenty of room to deploy."""
        gw = self.width  // CELL + 2
        margin = int(gw * 0.22)
        for (gx, gy) in list(self._lake):
            if gx < margin or gx >= gw - margin:
                self._lake.discard((gx, gy))
                self._height[(gx, gy)] = 0.30
        for (gx, gy) in list(self._rock):
            if gx < margin or gx >= gw - margin:
                self._rock.discard((gx, gy))

    def _clearAroundBridges(self):
        """Remove lake/rock cells that are too close to any bridge."""
        CLEAR_RADIUS = 5   # grid cells (~100px)
        for b in self.bridges:
            bgx, bgy = int(b['x']) // CELL, int(b['y']) // CELL
            for dy in range(-CLEAR_RADIUS, CLEAR_RADIUS + 1):
                for dx in range(-CLEAR_RADIUS, CLEAR_RADIUS + 1):
                    cell = (bgx + dx, bgy + dy)
                    self._lake.discard(cell)
                    self._rock.discard(cell)

    def _isNearRiver(self, px, py, threshold):
        for river in self.rivers:
            for i in range(len(river) - 1):
                if distToSeg(px, py, river[i][0], river[i][1],
                             river[i+1][0], river[i+1][1]) < threshold:
                    return True
        return False

    def isNearObstacle(self, x, y, radius=60):
        """True if (x,y) is within radius px of any lake or rock cell."""
        gx0 = int(x) // CELL
        gy0 = int(y) // CELL
        check = int(radius // CELL) + 1
        for dy in range(-check, check + 1):
            for dx in range(-check, check + 1):
                cell = (gx0 + dx, gy0 + dy)
                if cell in self._lake or cell in self._rock:
                    cx, cy = cell[0] * CELL + CELL // 2, cell[1] * CELL + CELL // 2
                    if math.hypot(x - cx, y - cy) < radius:
                        return True
        return False

    # ── pathfinding ────────────────────────────────────────────────────────────

    # Pathfinding grid: 2x CELL = 40px — fine enough to keep narrow corridors,
    # coarse enough to keep A* fast (48x27 ≈ 1300 cells on a 1920x1080 map).
    PATH_CELL = CELL * 2

    def _buildPassGrid(self):
        """Build and cache the set of passable grid cells for A* (coarse grid).

        Each coarse cell (80×80 px) is marked passable only when:
          - none of its 9 sample points (centre + 8 near-corners) overlaps lake/rock
          - it is not near a river (unless it is a bridge cell)
        After the initial pass, we inflate every obstacle by 1 cell so that
        A* paths always have at least one cell-width (~80 px) of clearance
        from obstacle edges.  Bridge cells are exempted from removal during
        inflation (Step 3), so they naturally survive without a restore step.
        """
        if hasattr(self, '_passGrid'):
            return self._passGrid
        PC = self.PATH_CELL
        gw = self.width  // PC + 2
        gh = self.height // PC + 2
        M  = PC // 2 - 4   # inset from cell edge for corner samples

        # ── Step 1: mark raw passable cells ──────────────────────────────────
        lake_cells = set()   # cells whose centre is on water
        grid = set()
        for gy in range(gh):
            for gx in range(gw):
                cx, cy = gx * PC + PC // 2, gy * PC + PC // 2
                # 9-point sampling (centre + 8 near-corners)
                blocked = False
                for sx in (cx - M, cx, cx + M):
                    for sy in (cy - M, cy, cy + M):
                        if self.isLake(sx, sy) or self.isRock(sx, sy):
                            blocked = True
                            break
                    if blocked:
                        break
                if blocked:
                    if self.isLake(cx, cy):
                        lake_cells.add((gx, gy))
                    continue
                if self._isNearRiver(cx, cy, RIVER_WIDTH + 6):
                    onBridge = any(
                        math.hypot(cx - b['x'], cy - b['y']) < BRIDGE_HALF + 20
                        for b in self.bridges
                    )
                    if not onBridge:
                        continue
                grid.add((gx, gy))

        # ── Step 2: collect bridge cells (must survive inflation) ─────────────
        bridge_cells = set()
        for b in self.bridges:
            bgx, bgy = int(b['x']) // PC, int(b['y']) // PC
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    bridge_cells.add((bgx + dx, bgy + dy))

        # ── Step 3: inflate lakes only (rocks are small + _steer handles them)
        # Inflating rocks created 80-px safety buffers that chopped up corridors
        # and made findPath return []. Lake shores stay inflated to keep units
        # from routing across water edges where speedMultiplier is crippling.
        to_remove = set()
        for (gx, gy) in grid:
            if (gx, gy) in bridge_cells:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (gx + dx, gy + dy) in lake_cells:
                    to_remove.add((gx, gy))
                    break
        grid -= to_remove

        # ── Step 4: pre-compute terrain cost per cell for weighted A* ───────────
        # Cost = 1 / speedMultiplier so that fast terrain has low cost.
        # River cells are rare in the grid (bridge only), keep them traversable
        # but expensive so A* avoids them when alternatives exist.
        cellCost = {}
        for (gx, gy) in grid:
            cx, cy = gx * PC + PC // 2, gy * PC + PC // 2
            spd = self.speedMultiplier(cx, cy)
            cellCost[(gx, gy)] = 1.0 / max(spd, 0.15)   # cap at river cost

        self._passGrid  = grid
        self._cellCost  = cellCost
        self._passGW    = gw
        self._passGH    = gh
        return grid

    def findPath(self, x1, y1, x2, y2):
        """Find a path from (x1,y1) to (x2,y2) avoiding obstacles.
        Returns a list of (px, py) waypoints in world coordinates,
        or empty list if no path exists."""
        PC   = self.PATH_CELL
        grid = self._buildPassGrid()
        start = (int(x1) // PC, int(y1) // PC)
        goal  = (int(x2) // PC, int(y2) // PC)
        gw, gh = self._passGW, self._passGH
        start  = (max(0, min(gw - 1, start[0])), max(0, min(gh - 1, start[1])))
        goal   = (max(0, min(gw - 1, goal[0])),  max(0, min(gh - 1, goal[1])))
        if start not in grid:
            start = self._nearestPassable(start, grid)
        if goal not in grid:
            goal = self._nearestPassable(goal, grid)
        if start is None or goal is None:
            return []
        raw = astarGrid(grid, gw, gh, start, goal,
                        maxNodes=6000, costGrid=self._cellCost)
        if not raw:
            return []
        return simplifyPath(raw, grid, PC)

    def _nearestPassable(self, cell, grid, radius=16):
        """Find nearest passable cell within radius of cell."""
        cx, cy = cell
        best, bestD = None, float('inf')
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nb = (cx + dx, cy + dy)
                if nb in grid:
                    d = abs(dx) + abs(dy)
                    if d < bestD:
                        bestD = d
                        best  = nb
        return best

    # ── terrain queries ───────────────────────────────────────────────────────

    def heightAt(self, x, y):
        gx, gy = int(x) // CELL, int(y) // CELL
        return self._height.get((gx, gy), 0.5)

    def isHighGround(self, x, y):
        return self.heightAt(x, y) >= self.HIGHLAND_THRESH

    def isForest(self, x, y):
        gx, gy = int(x) // CELL, int(y) // CELL
        return self._forest.get((gx, gy), False)

    def isLake(self, x, y):
        gx, gy = int(x) // CELL, int(y) // CELL
        return (gx, gy) in self._lake

    def isRock(self, x, y):
        gx, gy = int(x) // CELL, int(y) // CELL
        return (gx, gy) in self._rock

    def isPassable(self, x, y):
        """False for lakes, rocks, and river water (unless on a bridge)."""
        gx, gy = int(x) // CELL, int(y) // CELL
        if (gx, gy) in self._lake or (gx, gy) in self._rock:
            return False
        if (gx, gy) in self._riverCells:
            return False
        return True

    def isOnRiver(self, x, y):
        """True when standing in river water (not on a bridge). Uses cached grid."""
        gx, gy = int(x) // CELL, int(y) // CELL
        return (gx, gy) in self._riverCells

    def isOnBridge(self, x, y):
        """True when close enough to a bridge centre to be considered on the bridge."""
        return any(math.hypot(x - b['x'], y - b['y']) < BRIDGE_HALF + 10
                   for b in self.bridges)

    def speedMultiplier(self, x, y):
        if self.isLake(x, y) or self.isRock(x, y):
            return 0.0   # impassable
        if self.isOnRiver(x, y):
            # Bridge crossing: normal speed, not river water speed
            if self.isOnBridge(x, y):
                return 1.0
            return 0.15
        if self.isHighGround(x, y): return 0.70
        if self.isForest(x, y):     return 0.60
        return 1.0

    def damageMultiplier(self, x, y):
        return 0.40 if self.isOnRiver(x, y) else 1.0

    def heightBonus(self, attacker, target):
        diff = self.heightAt(attacker.x, attacker.y) - self.heightAt(target.x, target.y)
        if diff > 0.12:  return 1.25
        if diff < -0.12: return 0.80
        return 1.0

    # ── rendering ─────────────────────────────────────────────────────────────

    def buildSurface(self):
        from src.entities.terrain_render import buildTerrainSurface
        return buildTerrainSurface(self)

