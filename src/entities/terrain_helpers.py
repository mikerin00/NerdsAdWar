# Module: terrain_helpers
# Shared constants and procedural generation helpers for TerrainMap

import math
import random
from collections import deque

CELL         = 20    # terrain grid resolution in pixels
RIVER_WIDTH  = 16    # half-width of river collision (px)
BRIDGE_HALF  = 58    # half-length of bridge along river (px)
BRIDGE_WIDTH = 14    # half-width of bridge across river (px)

# Lake / rock generation parameters
LAKE_THRESH  = 0.72  # noise value above which a cell becomes lake
ROCK_THRESH  = 0.74  # noise value above which a cell becomes rock
OBSTACLE_MIN_CELLS = 12   # discard obstacle patches smaller than this


def smoothNoise(width, height, scale, seed):
    """Bilinear smooth-step interpolation over a sparse random grid."""
    rng  = random.Random(seed)
    cols = width  // scale + 2
    rows = height // scale + 2
    ctrl = [[rng.random() for _ in range(cols)] for _ in range(rows)]

    gw = width  // CELL + 2
    gh = height // CELL + 2
    out = {}
    for gy in range(gh):
        for gx in range(gw):
            wx = gx * CELL / scale
            wy = gy * CELL / scale
            ix, iy = int(wx), int(wy)
            fx, fy = wx - ix, wy - iy
            fx = fx * fx * (3 - 2 * fx)
            fy = fy * fy * (3 - 2 * fy)

            def safe(r, c):
                return ctrl[min(r, rows - 1)][min(c, cols - 1)]

            out[(gx, gy)] = (safe(iy,     ix)   * (1 - fx) * (1 - fy) +
                             safe(iy,     ix+1) * fx       * (1 - fy) +
                             safe(iy + 1, ix)   * (1 - fx) * fy       +
                             safe(iy + 1, ix+1) * fx       * fy)
    return out


def chaikin(pts):
    if len(pts) < 3:
        return pts
    result = [pts[0]]
    for i in range(len(pts) - 1):
        q = (pts[i][0] * 0.75 + pts[i+1][0] * 0.25,
             pts[i][1] * 0.75 + pts[i+1][1] * 0.25)
        r = (pts[i][0] * 0.25 + pts[i+1][0] * 0.75,
             pts[i][1] * 0.25 + pts[i+1][1] * 0.75)
        result += [q, r]
    result.append(pts[-1])
    return result


def distToSeg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx*dx + dy*dy)))
    return math.hypot(px - (ax + t*dx), py - (ay + t*dy))


def floodFill(grid, startSet, passable_fn):
    """BFS flood fill from startSet. Returns set of all reachable cells."""
    visited = set(startSet)
    queue   = deque(startSet)
    while queue:
        gx, gy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (gx + dx, gy + dy)
            if nb not in visited and nb in grid and passable_fn(nb):
                visited.add(nb)
                queue.append(nb)
    return visited


def astarGrid(passGrid, gw, gh, start, goal, maxNodes=2000, costGrid=None):
    """A* on the terrain grid. Returns list of (gx,gy) cells from start to goal,
    or empty list if no path exists. passGrid is a set of passable cells.
    costGrid is an optional dict mapping cell → terrain cost (1.0 = open, higher = slower).
    maxNodes limits search to prevent stalls on complex maps."""
    import heapq
    if start == goal:
        return [start]
    if start not in passGrid or goal not in passGrid:
        return []

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    openSet  = [(heuristic(start, goal), 0.0, start)]
    gScore   = {start: 0.0}
    cameFrom = {}
    closed   = set()

    while openSet:
        if len(closed) >= maxNodes:
            return []   # bail out — too complex
        _, cost, current = heapq.heappop(openSet)
        if current == goal:
            path = [current]
            while current in cameFrom:
                current = cameFrom[current]
                path.append(current)
            path.reverse()
            return path
        if current in closed:
            continue
        closed.add(current)
        cx, cy = current
        for dx, dy, moveDist in ((1,0,1.0),(-1,0,1.0),(0,1,1.0),(0,-1,1.0),
                                  (1,1,1.41),(-1,1,1.41),(1,-1,1.41),(-1,-1,1.41)):
            nb = (cx + dx, cy + dy)
            if nb in closed or nb not in passGrid:
                continue
            # scale move distance by terrain cost so A* prefers faster terrain
            terrainCost = costGrid.get(nb, 1.0) if costGrid else 1.0
            ng = cost + moveDist * terrainCost
            if ng < gScore.get(nb, float('inf')):
                gScore[nb] = ng
                cameFrom[nb] = current
                heapq.heappush(openSet, (ng + heuristic(nb, goal), ng, nb))
    return []


def simplifyPath(gridPath, passGrid, cell):
    """Reduce grid path to key waypoints using line-of-sight checks.
    Returns list of (px, py) world coordinates."""
    if len(gridPath) <= 2:
        return [(gx * cell + cell // 2, gy * cell + cell // 2) for gx, gy in gridPath]

    def lineOfSight(a, b):
        """Check if all grid cells along the line from a to b are passable."""
        x0, y0 = a
        x1, y1 = b
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x1 > x0 else -1
        sy = 1 if y1 > y0 else -1
        err = dx - dy
        steps = dx + dy + 1
        while steps > 0:
            if (x0, y0) not in passGrid:
                return False
            if x0 == x1 and y0 == y1:
                return True
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
            steps -= 1
        return True

    # Greedy waypoint reduction: skip nodes that have line-of-sight
    waypoints = [gridPath[0]]
    i = 0
    while i < len(gridPath) - 1:
        furthest = i + 1
        for j in range(len(gridPath) - 1, i, -1):
            if lineOfSight(gridPath[i], gridPath[j]):
                furthest = j
                break
        waypoints.append(gridPath[furthest])
        i = furthest

    return [(gx * cell + cell // 2, gy * cell + cell // 2) for gx, gy in waypoints]


def filterSmallPatches(cellSet, minSize):
    """Remove connected components smaller than minSize from cellSet (in-place).
    Returns the set of removed cells."""
    remaining = set(cellSet)
    removed   = set()
    while remaining:
        seed  = next(iter(remaining))
        queue = deque([seed])
        patch = {seed}
        while queue:
            c = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (c[0] + dx, c[1] + dy)
                if nb in remaining and nb not in patch:
                    patch.add(nb)
                    queue.append(nb)
        remaining -= patch
        if len(patch) < minSize:
            cellSet -= patch
            removed |= patch
    return removed
