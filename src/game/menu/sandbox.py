# Module: menu.sandbox
# Sandbox hub + grid-based map editor.
#
# Flow:
#   SandboxMenu     — list saved .json maps in ./maps/, new / play / delete
#     └─ MapEditor  — paint forest/lake/rock, save back to ./maps/
#
# Saved-map format (JSON):
#   { "version": 1, "name": "...", "width": W, "height": H,
#     "lake":   [[gx, gy], ...],
#     "rock":   [[gx, gy], ...],
#     "forest": [[gx, gy], ...] }
# Grid coordinates use CELL = 20 (same as TerrainMap's procedural grid).

import json
import os
import time

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT, MAP_WIDTH, MAP_HEIGHT
from src.entities.terrain_helpers import CELL, chaikin, distToSeg
from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _DIM, _WHITE,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _drawButton,
)


MAPS_DIR = os.path.join(os.getcwd(), 'maps')


def _ensureMapsDir():
    try:
        os.makedirs(MAPS_DIR, exist_ok=True)
    except OSError:
        pass


def _listMaps():
    _ensureMapsDir()
    try:
        files = [f for f in os.listdir(MAPS_DIR) if f.lower().endswith('.json')]
    except OSError:
        return []
    files.sort()
    return files


def _loadMap(filename):
    path = os.path.join(MAPS_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _saveMap(filename, data):
    _ensureMapsDir()
    if not filename.lower().endswith('.json'):
        filename += '.json'
    path = os.path.join(MAPS_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return filename


def _deleteMap(filename):
    path = os.path.join(MAPS_DIR, filename)
    try:
        os.remove(path)
        return True
    except OSError:
        return False


# ── Drawing helpers (same style as other menus) ─────────────────────────────

def _button(surf, rect, label, mx, my, enabled=True, hot=False):
    return _drawButton(surf, rect, label, mx, my, enabled=enabled,
                       hot=hot, font_size=20)


# ════════════════════════════════════════════════════════════════════════════
# SandboxMenu — list saved maps, launch editor or play
# ════════════════════════════════════════════════════════════════════════════

class SandboxMenu:
    """Returns one of:
        ('play', map_data)  — user picked a map to play
        ('back',  None)
        ('quit',  None)
    """

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.selected = None                # selected filename

    def run(self):
        while True:
            maps = _listMaps()
            if self.selected not in maps:
                self.selected = maps[0] if maps else None

            result = self._runOneFrameLoop(maps)
            if result is None:
                continue
            action, payload = result
            if action == 'new':
                editor_result = MapEditor(self.screen, self.clock).run()
                if editor_result == 'quit':
                    return 'quit', None
                # else: editor saved or backed out → refresh list
                continue
            if action == 'edit' and self.selected:
                try:
                    data = _loadMap(self.selected)
                except (OSError, json.JSONDecodeError):
                    continue
                editor_result = MapEditor(self.screen, self.clock,
                                          existing=data,
                                          filename=self.selected).run()
                if editor_result == 'quit':
                    return 'quit', None
                continue
            if action == 'delete' and self.selected:
                _deleteMap(self.selected)
                self.selected = None
                continue
            if action == 'play' and self.selected:
                try:
                    data = _loadMap(self.selected)
                except (OSError, json.JSONDecodeError):
                    continue
                return 'play', data
            if action == 'back':
                return 'back', None
            if action == 'quit':
                return 'quit', None

    def _runOneFrameLoop(self, maps):
        """Run until an actionable event occurs; return (action, payload)
        or None to loop again without action."""
        cx = SCREEN_WIDTH // 2

        # Layout
        list_rect = pygame.Rect(cx - 280, 170, 560, 360)
        new_rect  = pygame.Rect(cx - 280, 550, 170, 46)
        edit_rect = pygame.Rect(cx - 85,  550, 170, 46)
        play_rect = pygame.Rect(cx + 110, 550, 170, 46)
        del_rect  = pygame.Rect(cx - 85,  610, 170, 40)
        back_rect = pygame.Rect(cx - 85,  SCREEN_HEIGHT - 70, 170, 40)

        while True:
            mx, my = pygame.mouse.get_pos()
            click = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return ('quit', None)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return ('back', None)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(44, bold=True)
            _renderShadow(self.screen, "SANDBOX", tf, _GOLD_LIGHT,
                          cx - tf.size("SANDBOX")[0] // 2, 60, offset=3)
            _drawDivider(self.screen, 125)

            subtitle = "Draw your own map and save it"
            s = _font(18).render(subtitle, True, _PARCHMENT)
            self.screen.blit(s, (cx - s.get_width() // 2, 140))

            # Map list
            pygame.draw.rect(self.screen, (228, 216, 190), list_rect,
                             border_radius=6)
            pygame.draw.rect(self.screen, _GOLD, list_rect, 1, border_radius=6)
            row_h = 32
            for i, name in enumerate(maps):
                r = pygame.Rect(list_rect.x + 4, list_rect.y + 4 + i * row_h,
                                list_rect.width - 8, row_h - 4)
                hover = r.collidepoint(mx, my)
                sel   = (name == self.selected)
                if sel:
                    pygame.draw.rect(self.screen, (248, 232, 204), r, border_radius=4)
                elif hover:
                    pygame.draw.rect(self.screen, (238, 224, 198), r, border_radius=4)
                nt = _font(18, bold=sel).render(
                    name[:-5] if name.endswith('.json') else name,
                    True, _GOLD_LIGHT if sel else _PARCHMENT)
                self.screen.blit(nt, (r.x + 12, r.y + r.height // 2 - nt.get_height() // 2))
                if click and hover:
                    self.selected = name
            if not maps:
                empty = _font(18).render(
                    "No maps saved yet — click 'New' to begin.",
                    True, _DIM)
                self.screen.blit(empty, (list_rect.centerx - empty.get_width() // 2,
                                         list_rect.centery - empty.get_height() // 2))

            # Buttons
            has_sel = bool(self.selected)
            new_hover  = _button(self.screen, new_rect,  "+ New",   mx, my)
            edit_hover = _button(self.screen, edit_rect, "Edit",    mx, my, enabled=has_sel)
            play_hover = _button(self.screen, play_rect, "Play ▶",  mx, my, enabled=has_sel)
            del_hover  = _button(self.screen, del_rect,  "Delete",  mx, my, enabled=has_sel)
            back_hover = _button(self.screen, back_rect, "Back",    mx, my)

            if click:
                if new_hover:  return ('new', None)
                if edit_hover and has_sel: return ('edit', None)
                if play_hover and has_sel: return ('play', None)
                if del_hover  and has_sel: return ('delete', None)
                if back_hover: return ('back', None)

            pygame.display.flip()
            self.clock.tick(60)


# ════════════════════════════════════════════════════════════════════════════
# MapEditor — paint terrain cells on a CELL×CELL grid
# ════════════════════════════════════════════════════════════════════════════

TOOLS = [
    # (key,       label,     swatch)
    ('erase',     'Empty',   (80, 140, 60)),
    ('forest',    'Forest',  (40,  85, 35)),
    ('lake',      'Water',   (40, 120, 180)),
    ('rock',      'Rock',    (120, 115, 105)),
    ('highland',  'Hill',    (160, 140,  80)),
    ('river',     'River',   (70, 150, 210)),
    ('bridge',    'Bridge',  (175, 130,  70)),
    ('outpost',   'Outpost', (235, 210, 120)),
    ('gum',       'Eraser',  (200,  80,  80)),
]
PAINT_TOOLS = {'erase', 'forest', 'lake', 'rock', 'highland'}   # drag-paint
POINT_TOOLS = {'river', 'bridge', 'outpost', 'gum'}              # click-only
CHAIKIN_PASSES = 4   # must match TerrainMap._loadFromCustom


class MapEditor:
    """Opens a fullscreen paint surface. Mouse paints with the active tool,
    number keys 1-4 switch tools, +/- changes brush size, Ctrl+S saves,
    ESC returns. Returns one of 'back' | 'saved' | 'quit'."""

    def __init__(self, screen, clock, existing=None, filename=None):
        self.screen = screen
        self.clock  = clock

        self.gw = MAP_WIDTH  // CELL + 1
        self.gh = MAP_HEIGHT // CELL + 1

        self.lake     = set()
        self.rock     = set()
        self.forest   = set()
        self.highland = set()
        self.rivers   = []        # list of polylines (list of (x,y) world coords)
        self.bridges  = []        # list of (x,y) world coords
        self.outposts = []        # list of (x,y) world coords
        self._riverDraft = []     # in-progress river control points
        if existing:
            self.lake     = set(tuple(c) for c in existing.get('lake',     []))
            self.rock     = set(tuple(c) for c in existing.get('rock',     []))
            self.forest   = set(tuple(c) for c in existing.get('forest',   []))
            self.highland = set(tuple(c) for c in existing.get('highland', []))
            self.rivers   = [[tuple(p) for p in r]
                             for r in existing.get('rivers', [])]
            self.bridges  = [tuple(b) for b in existing.get('bridges',  [])]
            self.outposts = [tuple(o) for o in existing.get('outposts', [])]
            self.name     = existing.get('name', '')
        else:
            self.name = ''
        self.filename = filename or ''

        self.toolIdx   = 1           # default = forest
        self.brushSize = 2           # radius in cells
        self._dirty    = True
        # Undo/redo: stack of state snapshots (cheap — pure python collections)
        self._undo = []
        self._redo = []
        self._HIST_CAP = 30

        # Scale: draw map_surf once per change and blit to screen
        self._mapSurf  = None

        # UI regions
        self._toolBarY  = SCREEN_HEIGHT - 60
        self._mapScale  = min(SCREEN_WIDTH  / MAP_WIDTH,
                              (SCREEN_HEIGHT - 70) / MAP_HEIGHT)
        self._scaledW   = int(MAP_WIDTH  * self._mapScale)
        self._scaledH   = int(MAP_HEIGHT * self._mapScale)
        self._mapOx     = (SCREEN_WIDTH - self._scaledW) // 2
        self._mapOy     = 10

        # Modal state
        self._saveDialog = False
        self._saveText   = self.name
        self._statusMsg  = ''
        self._statusUntil = 0

    # ── coordinate mapping ──────────────────────────────────────────────────

    def _screenToCell(self, sx, sy):
        if not (self._mapOx <= sx < self._mapOx + self._scaledW
                and self._mapOy <= sy < self._mapOy + self._scaledH):
            return None
        mx = (sx - self._mapOx) / self._mapScale
        my = (sy - self._mapOy) / self._mapScale
        return int(mx) // CELL, int(my) // CELL

    # ── painting ────────────────────────────────────────────────────────────

    def _paint(self, gx, gy):
        tool = TOOLS[self.toolIdx][0]
        if tool not in PAINT_TOOLS:
            return
        r = self.brushSize
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r:
                    continue
                c = (gx + dx, gy + dy)
                if not (0 <= c[0] < self.gw and 0 <= c[1] < self.gh):
                    continue
                # Terrain tools are mutually exclusive; highland overlays.
                if tool == 'highland':
                    if c in self.lake or c in self.rock:
                        continue   # can't stack highland on water/rock
                    self.highland.add(c)
                else:
                    self.lake.discard(c); self.rock.discard(c); self.forest.discard(c)
                    self.highland.discard(c)
                    if tool == 'forest':   self.forest.add(c)
                    elif tool == 'lake':   self.lake.add(c)
                    elif tool == 'rock':   self.rock.add(c)
                    # 'erase' → leave all empty
        self._dirty = True

    # ── snapshot / undo / redo ──────────────────────────────────────────────

    def _snapshot(self):
        """Cheap deep-copy of all editable state."""
        return {
            'lake':     set(self.lake),
            'rock':     set(self.rock),
            'forest':   set(self.forest),
            'highland': set(self.highland),
            'rivers':   [list(r) for r in self.rivers],
            'bridges':  list(self.bridges),
            'outposts': list(self.outposts),
        }

    def _pushUndo(self):
        self._undo.append(self._snapshot())
        if len(self._undo) > self._HIST_CAP:
            self._undo.pop(0)
        self._redo.clear()

    def _applySnap(self, snap):
        self.lake     = snap['lake']
        self.rock     = snap['rock']
        self.forest   = snap['forest']
        self.highland = snap['highland']
        self.rivers   = snap['rivers']
        self.bridges  = snap['bridges']
        self.outposts = snap['outposts']
        self._dirty   = True

    def _undoOne(self):
        if not self._undo: return
        self._redo.append(self._snapshot())
        self._applySnap(self._undo.pop())

    def _redoOne(self):
        if not self._redo: return
        self._undo.append(self._snapshot())
        self._applySnap(self._redo.pop())

    # ── point-tool actions ──────────────────────────────────────────────────

    def _addRiverPoint(self, wx, wy):
        self._riverDraft.append((wx, wy))
        self._dirty = True

    def _finalizeRiver(self):
        if len(self._riverDraft) >= 2:
            self._pushUndo()
            self.rivers.append(list(self._riverDraft))
        self._riverDraft = []
        self._dirty = True

    def _smoothedRiver(self, ctrl):
        """Return the chaikin-smoothed polyline for a river — same passes as
        TerrainMap uses, so snapping in the editor matches the in-game curve."""
        pts = [(float(p[0]), float(p[1])) for p in ctrl]
        for _ in range(CHAIKIN_PASSES):
            pts = chaikin(pts)
        return pts

    def _placeBridge(self, wx, wy):
        """Snap bridge position to the nearest smoothed river segment (within
        60 px). This mirrors what the game renders and uses for pathfinding
        so the bridge sits dead-centre across the water."""
        best_pt, best_d = None, 60.0
        for ctrl in self.rivers:
            smoothed = self._smoothedRiver(ctrl)
            for i in range(len(smoothed) - 1):
                x0, y0 = smoothed[i]; x1, y1 = smoothed[i + 1]
                dx, dy = x1 - x0, y1 - y0
                L2 = dx * dx + dy * dy
                if L2 < 1e-6: continue
                t = max(0.0, min(1.0, ((wx - x0) * dx + (wy - y0) * dy) / L2))
                px, py = x0 + t * dx, y0 + t * dy
                d = ((wx - px) ** 2 + (wy - py) ** 2) ** 0.5
                if d < best_d:
                    best_d = d; best_pt = (px, py)
        if best_pt is None:
            # No river close enough — ignore click (rather than dropping a
            # bridge in open grass where the game can't orient it).
            self._statusMsg   = "No river nearby — click closer to a river."
            self._statusUntil = time.time() + 2.0
            return
        self._pushUndo()
        self.bridges.append(best_pt)
        self._dirty = True

    def _eraseNear(self, wx, wy):
        """Gum: remove the closest river / bridge / outpost within 50 px."""
        R = 50.0
        candidates = []          # (dist, kind, index)

        for i, (bx, by) in enumerate(self.bridges):
            d = ((bx - wx) ** 2 + (by - wy) ** 2) ** 0.5
            if d < R:
                candidates.append((d, 'bridge', i))
        for i, (ox, oy) in enumerate(self.outposts):
            d = ((ox - wx) ** 2 + (oy - wy) ** 2) ** 0.5
            if d < R:
                candidates.append((d, 'outpost', i))
        for ri, ctrl in enumerate(self.rivers):
            smoothed = self._smoothedRiver(ctrl)
            best = R
            for i in range(len(smoothed) - 1):
                best = min(best, distToSeg(wx, wy,
                                           smoothed[i][0], smoothed[i][1],
                                           smoothed[i + 1][0], smoothed[i + 1][1]))
            if best < R:
                candidates.append((best, 'river', ri))

        if not candidates:
            return
        candidates.sort(key=lambda c: c[0])
        _, kind, idx = candidates[0]
        self._pushUndo()
        if kind == 'bridge':
            self.bridges.pop(idx)
        elif kind == 'outpost':
            self.outposts.pop(idx)
        elif kind == 'river':
            # Deleting a river also drops any bridges that now have nothing
            # to sit on — otherwise they'd get placed in grass at game start.
            self.rivers.pop(idx)
            if not self.rivers:
                self.bridges.clear()
        self._dirty = True

    def _placeOutpost(self, wx, wy):
        # Remove any existing outpost within 50 px (toggle-delete behaviour)
        for ox, oy in list(self.outposts):
            if (ox - wx) ** 2 + (oy - wy) ** 2 < 50 * 50:
                self._pushUndo()
                self.outposts.remove((ox, oy))
                self._dirty = True
                return
        self._pushUndo()
        self.outposts.append((wx, wy))
        self._dirty = True

    # ── rendering ───────────────────────────────────────────────────────────

    def _rebuildMapSurf(self):
        surf = pygame.Surface((self._scaledW, self._scaledH))
        surf.fill((80, 140, 60))    # grass
        cs   = CELL * self._mapScale
        cs_i = max(1, int(cs) + 1)
        # Highland first (so forest/water/rock layer on top)
        for (gx, gy) in self.highland:
            px, py = int(gx * cs), int(gy * cs)
            pygame.draw.rect(surf, (160, 140, 80), (px, py, cs_i, cs_i))
        for (gx, gy) in self.forest:
            px, py = int(gx * cs), int(gy * cs)
            pygame.draw.rect(surf, (40, 85, 35), (px, py, cs_i, cs_i))
        for (gx, gy) in self.rock:
            px, py = int(gx * cs), int(gy * cs)
            pygame.draw.rect(surf, (120, 115, 105), (px, py, cs_i, cs_i))
        for (gx, gy) in self.lake:
            px, py = int(gx * cs), int(gy * cs)
            pygame.draw.rect(surf, (40, 120, 180), (px, py, cs_i, cs_i))

        # Rivers (smoothed the same way TerrainMap does so bridge snap matches)
        def _draw_polyline(points, color, width, passes=CHAIKIN_PASSES):
            if len(points) < 2: return
            smoothed = [(float(p[0]), float(p[1])) for p in points]
            for _ in range(passes):
                if len(smoothed) < 3: break
                smoothed = chaikin(smoothed)
            scaled = [(int(x * self._mapScale), int(y * self._mapScale))
                      for x, y in smoothed]
            pygame.draw.lines(surf, color, False, scaled, width)

        for river in self.rivers:
            _draw_polyline(river, (50, 110, 170), max(3, int(28 * self._mapScale)))
        if self._riverDraft:
            _draw_polyline(self._riverDraft, (90, 170, 220),
                           max(2, int(22 * self._mapScale)))
            # Control-point dots
            for (x, y) in self._riverDraft:
                pygame.draw.circle(surf, (255, 255, 255),
                                   (int(x * self._mapScale),
                                    int(y * self._mapScale)), 4)

        # Bridges — simple tan squares
        for (bx, by) in self.bridges:
            sx, sy = int(bx * self._mapScale), int(by * self._mapScale)
            pygame.draw.rect(surf, (175, 130, 70),
                             (sx - 8, sy - 5, 16, 10))
            pygame.draw.rect(surf, (110, 75, 40),
                             (sx - 8, sy - 5, 16, 10), 1)

        # Outposts — yellow circle + star marker
        for (ox, oy) in self.outposts:
            sx, sy = int(ox * self._mapScale), int(oy * self._mapScale)
            pygame.draw.circle(surf, (235, 210, 120), (sx, sy), 8)
            pygame.draw.circle(surf, (120, 100, 40),  (sx, sy), 8, 2)
        # Spawn-zone markers (left/right edges) so the player sees where the
        # armies will come from — editor respects this visually but doesn't
        # prevent painting there.
        zone = pygame.Surface((int(self._scaledW * 0.22), self._scaledH),
                              pygame.SRCALPHA)
        zone.fill((90, 130, 200, 50))
        surf.blit(zone, (0, 0))
        zone2 = pygame.Surface((int(self._scaledW * 0.22), self._scaledH),
                               pygame.SRCALPHA)
        zone2.fill((200, 90, 90, 50))
        surf.blit(zone2, (self._scaledW - int(self._scaledW * 0.22), 0))
        self._mapSurf = surf
        self._dirty   = False

    def _drawBrushCursor(self, mx, my):
        cell = self._screenToCell(mx, my)
        if cell is None:
            return
        cs = CELL * self._mapScale
        r  = (self.brushSize + 0.5) * cs
        px = self._mapOx + (cell[0] + 0.5) * cs
        py = self._mapOy + (cell[1] + 0.5) * cs
        pygame.draw.circle(self.screen, (255, 255, 255),
                           (int(px), int(py)), int(r), 2)

    def _drawToolbar(self, mx, my):
        y = self._toolBarY
        surf = self.screen
        pygame.draw.rect(surf, (214, 204, 182),
                         (0, y, SCREEN_WIDTH, SCREEN_HEIGHT - y))
        pygame.draw.line(surf, _GOLD, (0, y), (SCREEN_WIDTH, y), 1)

        # Tool buttons (8 of them — tighter width)
        tool_w, tool_h = 80, 40
        tool_rects = []
        for i, (_, label, col) in enumerate(TOOLS):
            r = pygame.Rect(10 + i * (tool_w + 4), y + 10, tool_w, tool_h)
            tool_rects.append(r)
            active = (i == self.toolIdx)
            _button(surf, r, f"{i + 1}· {label}", mx, my, hot=active)
            pygame.draw.rect(surf, col,
                             pygame.Rect(r.right - 12, r.y + 5, 8, 8))

        # Brush indicator (only shown for paint tools)
        bx = 10 + len(TOOLS) * (tool_w + 4) + 4
        tool_key = TOOLS[self.toolIdx][0]
        hint = (f"Brush: {self.brushSize + 1}  (+/-)"
                if tool_key in PAINT_TOOLS else "")
        if tool_key == 'river':
            hint = f"River: {len(self._riverDraft)} pts  (Enter: confirm, Esc: cancel)"
        elif tool_key == 'bridge':
            hint = "Click on a river to place a bridge"
        elif tool_key == 'outpost':
            hint = "Click to place or remove an outpost"
        elif tool_key == 'gum':
            hint = "Click on a river / bridge / outpost to erase"
        ht = _font(14).render(hint, True, _PARCHMENT)
        surf.blit(ht, (bx, y + 22))

        # Right-side buttons: Undo / Redo / Save / Back
        undo_rect = pygame.Rect(SCREEN_WIDTH - 430, y + 10, 60, tool_h)
        redo_rect = pygame.Rect(SCREEN_WIDTH - 365, y + 10, 60, tool_h)
        save_rect = pygame.Rect(SCREEN_WIDTH - 280, y + 10, 130, tool_h)
        back_rect = pygame.Rect(SCREEN_WIDTH - 140, y + 10, 130, tool_h)
        _button(surf, undo_rect, "↶", mx, my, enabled=bool(self._undo))
        _button(surf, redo_rect, "↷", mx, my, enabled=bool(self._redo))
        save_hover = _button(surf, save_rect, "Save", mx, my)
        back_hover = _button(surf, back_rect, "Back", mx, my)
        undo_hover = undo_rect.collidepoint(mx, my) and self._undo
        redo_hover = redo_rect.collidepoint(mx, my) and self._redo
        return save_hover, back_hover, undo_hover, redo_hover, tool_rects

    def _drawSaveDialog(self, mx, my):
        # Dim background
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        self.screen.blit(dim, (0, 0))

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        box = pygame.Rect(cx - 230, cy - 100, 460, 200)
        pygame.draw.rect(self.screen, (244, 236, 219), box, border_radius=6)
        pygame.draw.rect(self.screen, _GOLD, box, 2, border_radius=6)

        t = _font(24, bold=True).render("Save Map", True, _GOLD_LIGHT)
        self.screen.blit(t, (cx - t.get_width() // 2, box.y + 14))

        lbl = _font(15).render("Name:", True, _DIM)
        self.screen.blit(lbl, (box.x + 24, box.y + 60))

        name_rect = pygame.Rect(box.x + 24, box.y + 80, box.width - 48, 36)
        pygame.draw.rect(self.screen, (240, 228, 204), name_rect, border_radius=4)
        pygame.draw.rect(self.screen, _GOLD, name_rect, 1, border_radius=4)
        shown = self._saveText or "enter a name…"
        col   = _WHITE if self._saveText else _DIM
        surf  = _font(22).render(shown, True, col)
        self.screen.blit(surf, (name_rect.x + 10,
                                name_rect.centery - surf.get_height() // 2))

        ok_rect     = pygame.Rect(box.right - 230, box.bottom - 52, 100, 36)
        cancel_rect = pygame.Rect(box.right - 120, box.bottom - 52, 100, 36)
        ok_hover     = _button(self.screen, ok_rect, "Save", mx, my,
                               enabled=bool(self._saveText.strip()))
        cancel_hover = _button(self.screen, cancel_rect, "Cancel", mx, my)
        return ok_hover, cancel_hover

    # ── main loop ───────────────────────────────────────────────────────────

    def run(self):
        painting = False
        paint_started = False     # True → we pushed an undo snapshot for this stroke

        while True:
            mx, my = pygame.mouse.get_pos()
            click  = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN:
                    if self._saveDialog:
                        if event.key == pygame.K_ESCAPE:
                            self._saveDialog = False
                        elif event.key == pygame.K_BACKSPACE:
                            self._saveText = self._saveText[:-1]
                        elif event.key == pygame.K_RETURN and self._saveText.strip():
                            self._doSave()
                        elif event.unicode and event.unicode.isprintable() \
                                and len(self._saveText) < 24:
                            ch = event.unicode
                            if ch.isalnum() or ch in ' _-':
                                self._saveText += ch
                    else:
                        tool_key = TOOLS[self.toolIdx][0]
                        mods     = pygame.key.get_mods()
                        if event.key == pygame.K_ESCAPE:
                            if tool_key == 'river' and self._riverDraft:
                                self._riverDraft = []    # cancel in-progress river
                                self._dirty = True
                            else:
                                return 'back'
                        elif event.key == pygame.K_RETURN:
                            if tool_key == 'river':
                                self._finalizeRiver()
                        elif pygame.K_1 <= event.key <= pygame.K_9:
                            idx = event.key - pygame.K_1
                            if idx < len(TOOLS):
                                if tool_key == 'river' and TOOLS[idx][0] != 'river':
                                    self._finalizeRiver()
                                self.toolIdx = idx
                        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS,
                                           pygame.K_KP_PLUS):
                            self.brushSize = min(10, self.brushSize + 1)
                        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                            self.brushSize = max(0, self.brushSize - 1)
                        elif event.key == pygame.K_s and (mods & pygame.KMOD_CTRL):
                            self._openSaveDialog()
                        elif event.key == pygame.K_z and (mods & pygame.KMOD_CTRL):
                            if mods & pygame.KMOD_SHIFT:
                                self._redoOne()
                            else:
                                self._undoOne()
                        elif event.key == pygame.K_y and (mods & pygame.KMOD_CTRL):
                            self._redoOne()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True
                    if not self._saveDialog:
                        tool_key = TOOLS[self.toolIdx][0]
                        if tool_key in PAINT_TOOLS:
                            cell = self._screenToCell(mx, my)
                            if cell is not None:
                                self._pushUndo()
                                paint_started = True
                                painting = True
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    painting = False
                    paint_started = False

            # Paint-drag stroke
            if painting and not self._saveDialog:
                cell = self._screenToCell(mx, my)
                if cell is not None:
                    self._paint(*cell)

            # Draw ------------------------------------------------------------
            self.screen.fill((12, 10, 8))
            if self._dirty:
                self._rebuildMapSurf()
            self.screen.blit(self._mapSurf, (self._mapOx, self._mapOy))
            pygame.draw.rect(self.screen, _GOLD,
                             pygame.Rect(self._mapOx, self._mapOy,
                                         self._scaledW, self._scaledH), 1)

            if TOOLS[self.toolIdx][0] in PAINT_TOOLS:
                self._drawBrushCursor(mx, my)

            save_hover, back_hover, undo_hover, redo_hover, tool_rects = \
                self._drawToolbar(mx, my)

            # Status message
            if self._statusMsg and time.time() < self._statusUntil:
                st = _font(16, bold=True).render(self._statusMsg, True,
                                                 (140, 220, 140))
                self.screen.blit(st, (SCREEN_WIDTH // 2 - st.get_width() // 2,
                                      self._toolBarY - 28))

            # Save dialog overlay
            ok_hover = cancel_hover = False
            if self._saveDialog:
                ok_hover, cancel_hover = self._drawSaveDialog(mx, my)

            if click:
                if self._saveDialog:
                    if ok_hover and self._saveText.strip():
                        self._doSave()
                    elif cancel_hover:
                        self._saveDialog = False
                else:
                    # Toolbar first — take precedence over map clicks
                    toolbar_click = False
                    for i, r in enumerate(tool_rects):
                        if r.collidepoint(mx, my):
                            # Finalize any in-progress river when leaving the river tool
                            if TOOLS[self.toolIdx][0] == 'river' and TOOLS[i][0] != 'river':
                                self._finalizeRiver()
                            self.toolIdx = i
                            painting = False
                            toolbar_click = True
                            break
                    if toolbar_click:
                        pass
                    elif save_hover:
                        self._openSaveDialog(); painting = False
                    elif undo_hover:
                        self._undoOne(); painting = False
                    elif redo_hover:
                        self._redoOne(); painting = False
                    elif back_hover:
                        return 'back'
                    else:
                        # Click on map for point tools
                        cell = self._screenToCell(mx, my)
                        if cell is not None:
                            tool_key = TOOLS[self.toolIdx][0]
                            wx = (cell[0] + 0.5) * CELL
                            wy = (cell[1] + 0.5) * CELL
                            # For points we want finer-than-cell precision
                            wx = (mx - self._mapOx) / self._mapScale
                            wy = (my - self._mapOy) / self._mapScale
                            if tool_key == 'river':
                                self._addRiverPoint(wx, wy)
                            elif tool_key == 'bridge':
                                self._placeBridge(wx, wy)
                            elif tool_key == 'outpost':
                                self._placeOutpost(wx, wy)
                            elif tool_key == 'gum':
                                self._eraseNear(wx, wy)

            pygame.display.flip()
            self.clock.tick(60)

    # ── save dialog plumbing ────────────────────────────────────────────────

    def _openSaveDialog(self):
        self._saveDialog = True
        if not self._saveText:
            self._saveText = self.filename[:-5] if self.filename.endswith('.json') \
                else self.filename or f"map_{int(time.time())}"

    def _doSave(self):
        # Finalize any in-progress river before saving
        if self._riverDraft:
            self._finalizeRiver()
        data = {
            'version':  2,
            'name':     self._saveText.strip(),
            'width':    MAP_WIDTH,
            'height':   MAP_HEIGHT,
            'lake':     [list(c) for c in self.lake],
            'rock':     [list(c) for c in self.rock],
            'forest':   [list(c) for c in self.forest],
            'highland': [list(c) for c in self.highland],
            'rivers':   [[list(p) for p in river] for river in self.rivers],
            'bridges':  [list(b) for b in self.bridges],
            'outposts': [list(o) for o in self.outposts],
        }
        fname = self._saveText.strip().replace(' ', '_') + '.json'
        try:
            _saveMap(fname, data)
            self._statusMsg   = f"Saved as {fname}"
            self._statusUntil = time.time() + 2.5
            self.filename     = fname
            self.name         = self._saveText.strip()
            self._saveDialog  = False
        except OSError as e:
            self._statusMsg   = f"Error saving: {e}"
            self._statusUntil = time.time() + 3.0
