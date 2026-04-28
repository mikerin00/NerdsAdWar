# Module: events
# EventsMixin — keyboard and mouse input handling for the Game class

import math

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src import keybinds as KB


class EventsMixin:

    def _screenToMap(self, sx, sy):
        """Convert screen pixel coordinates to logical map coordinates."""
        scale = self._mapScale
        scaledW = int(self.mapWidth  * scale)
        scaledH = int(self.mapHeight * scale)
        ox = (SCREEN_WIDTH  - scaledW) // 2
        oy = (SCREEN_HEIGHT - scaledH) // 2
        mx = (sx - ox) / scale
        my = (sy - oy) / scale
        return mx, my

    def _handleEvents(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quitGame = True
                self.running   = False

            elif event.type == getattr(pygame, 'WINDOWFOCUSLOST', -1):
                # Key-hold toggles (B, T) miss their KEYUP on alt-tab, which
                # left the player stuck drawing arrows or in the emote menu.
                self._planMode      = False
                self._planDragStart = None
                self._emoteBarOpen  = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._paused = True
                elif event.key == KB.get('carre'):
                    self._cmdToggleSquare()
                elif event.key == KB.get('ai_log'):
                    self.showAiLog = not getattr(self, 'showAiLog', False)
                elif event.key == KB.get('start_gevecht'):
                    if self.freezeTimer > 0:
                        self.issueCommand('rdy', {})
                elif getattr(self, '_emoteBarOpen', False) and pygame.K_1 <= event.key <= pygame.K_6:
                    self._cmdEmote(event.key - pygame.K_1)
                elif event.key in (KB.get('sel_all'), KB.get('sel_inf'), KB.get('sel_cav'),
                                   KB.get('sel_heavy'), KB.get('sel_art')):
                    add = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    self._selectByCategory(event.key, additive=add)
                elif event.key == KB.get('ping'):
                    mx, my = self._screenToMap(*pygame.mouse.get_pos())
                    self._cmdPing(mx, my)
                elif event.key == KB.get('battleplan'):
                    self._planMode = True
                elif event.key == KB.get('emote'):
                    self._emoteBarOpen = True

            elif event.type == pygame.KEYUP:
                if event.key == KB.get('battleplan'):
                    self._planMode      = False
                    self._planDragStart = None
                elif event.key == KB.get('emote'):
                    self._emoteBarOpen = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if getattr(self, '_planMode', False):
                        self._planDragStart = self._screenToMap(*event.pos)
                    else:
                        self.selStart = self._screenToMap(*event.pos)
                        self._deselectAll()
                elif event.button == 3:
                    if getattr(self, '_planMode', False):
                        # RMB while holding B clears your own arrows.
                        self._cmdClearBattleplans()
                        continue
                    mx, my = self._screenToMap(*event.pos)
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_CTRL:
                        self.patrolPath = [(mx, my)]
                    elif mods & pygame.KMOD_SHIFT:
                        self.formPath = [(mx, my)]
                    else:
                        clickedFoe = next(
                            (u for u in self.units
                             if u.team == self._foeSide
                             and math.hypot(u.x - mx, u.y - my) <= u.radius + 16),
                            None
                        )
                        if clickedFoe:
                            self._cmdAttack(clickedFoe)
                        else:
                            self._cmdMove(mx, my)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and getattr(self, '_planDragStart', None):
                    sx, sy = self._planDragStart
                    ex, ey = self._screenToMap(*event.pos)
                    if (ex - sx) ** 2 + (ey - sy) ** 2 > 400:   # ≥20px
                        self._cmdBattleplan(sx, sy, ex, ey)
                    self._planDragStart = None
                elif event.button == 1 and self.selStart:
                    self._finishSelection(self._screenToMap(*event.pos))
                    self.selStart = None
                    self.selRect  = None
                elif event.button == 3:
                    if self.patrolPath:
                        self._cmdPatrol(self.patrolPath)
                        self.patrolPath = []
                    elif self.formPath:
                        self._cmdFormation(self.formPath)
                        self.formPath = []

            elif event.type == pygame.MOUSEMOTION:
                if self.patrolPath and pygame.mouse.get_pressed()[2]:
                    mx, my = self._screenToMap(*event.pos)
                    last   = self.patrolPath[-1]
                    if math.hypot(mx - last[0], my - last[1]) > 8:
                        self.patrolPath.append((mx, my))
                elif self.formPath and pygame.mouse.get_pressed()[2]:
                    mx, my = self._screenToMap(*event.pos)
                    last   = self.formPath[-1]
                    if math.hypot(mx - last[0], my - last[1]) > 8:
                        self.formPath.append((mx, my))
                if self.selStart:
                    sx, sy = self.selStart
                    mx, my = self._screenToMap(*event.pos)
                    self.selRect = pygame.Rect(
                        min(sx, mx), min(sy, my),
                        abs(mx - sx), abs(my - sy)
                    )

    def _deselectAll(self):
        for u in self.units:
            u.selected = False
        self.selectedUnits = []

    def _myUnits(self):
        """Units the local player commands. SP: own side; MP: own slot."""
        if self.netRole is None:
            return [u for u in self.units if u.team == self.mySide]
        return [u for u in self.units
                if getattr(u, 'controller', -1) == self.mySlot]

    def _selectByCategory(self, key, additive=False):
        cat_map = {
            KB.get('sel_all'):   {'infantry', 'heavy_infantry', 'cavalry', 'artillery'},
            KB.get('sel_inf'):   {'infantry'},
            KB.get('sel_cav'):   {'cavalry'},
            KB.get('sel_heavy'): {'heavy_infantry'},
            KB.get('sel_art'):   {'artillery'},
        }
        types = cat_map.get(key)
        if not types:
            return
        if not additive:
            for u in self.units:
                u.selected = False
            self.selectedUnits = []
        added = False
        for u in self._myUnits():
            if u.unitType in types and not u.selected:
                u.selected = True
                self.selectedUnits.append(u)
                added = True
        if added:
            from src import audio
            audio.play_sfx('select')

    def _finishSelection(self, endPos):
        sx, sy = self.selStart
        ex, ey = endPos
        # Multiplayer: only select units whose controller matches my slot.
        # Single-player: all 'player' units (no controller filter needed).
        def mine(u):
            if self.netRole is None:
                return u.team == self.mySide
            return getattr(u, 'controller', -1) == self.mySlot
        if abs(ex - sx) < 8 and abs(ey - sy) < 8:
            for u in self.units:
                if mine(u) and math.hypot(u.x - sx, u.y - sy) <= u.radius + 5:
                    u.selected = True
                    self.selectedUnits.append(u)
        else:
            rect = pygame.Rect(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy))
            for u in self.units:
                if mine(u) and rect.collidepoint(int(u.x), int(u.y)):
                    u.selected = True
                    self.selectedUnits.append(u)
        if self.selectedUnits:
            from src import audio
            audio.play_sfx('select')

    # ── Command helpers — route through dispatcher ──────────────────────────

    def _selectedIds(self):
        return [u.netId for u in self.selectedUnits
                if getattr(u, 'netId', None) is not None]

    def _cmdMove(self, mx, my):
        ids = self._selectedIds()
        if not ids and self.netRole is None:
            # Single-player path used to mutate directly — preserve behaviour
            # for units without netIds (shouldn't happen in MP).
            for u in self.selectedUnits:
                u.attackTarget = None
            self._moveSelected((mx, my))
            return
        if not ids:
            return
        self.issueCommand('move', {'ids': ids, 'x': mx, 'y': my})

    def _cmdAttack(self, target):
        ids = self._selectedIds()
        tid = getattr(target, 'netId', None)
        if not ids or tid is None:
            # Singleplayer and host: mutate directly (client can't — no authority)
            if self.netRole != 'client':
                for u in self.selectedUnits:
                    u.patrolPath   = []
                    u.attackTarget = target
            return
        self.issueCommand('atk', {'ids': ids, 'tid': tid})

    def _cmdToggleSquare(self):
        ids = self._selectedIds()
        if not ids:
            # Single-player has no netIds — mutate directly
            if self.netRole is None:
                self._toggleInfantrySquare()
            return
        self.issueCommand('sq', {'ids': ids})

    def _cmdFormation(self, path):
        if len(path) < 2:
            return
        ids = self._selectedIds()
        if not ids:
            if self.netRole is None:
                self._applyFormationPath(path)
            return
        self.issueCommand('form', {'ids': ids, 'path': list(path)})

    def _cmdPatrol(self, path):
        if len(path) < 2:
            return
        ids = self._selectedIds()
        if not ids:
            if self.netRole is None:
                self._applyPatrolPath(path)
            return
        self.issueCommand('patrol', {'ids': ids, 'path': list(path)})

    def _cmdPing(self, mx, my):
        # Single-player: drop locally + audible cue. Multiplayer: dispatcher
        # routes to host which broadcasts to teammates via snapshot.
        if self.netRole is None:
            self.pings.append({'x': float(mx), 'y': float(my),
                               'fromSlot': 0, 'life': self._PING_LIFE})
            from src import audio
            audio.play_sfx('click')
            return
        self.issueCommand('ping', {'x': float(mx), 'y': float(my)})

    def _cmdBattleplan(self, x1, y1, x2, y2):
        if self.netRole is None:
            self.battleplans.append({'fromSlot': 0,
                                     'x1': float(x1), 'y1': float(y1),
                                     'x2': float(x2), 'y2': float(y2)})
            self.battleplans = self.battleplans[-32:]
            return
        self.issueCommand('plan', {'x1': float(x1), 'y1': float(y1),
                                   'x2': float(x2), 'y2': float(y2)})

    def _cmdClearBattleplans(self):
        if self.netRole is None:
            self.battleplans = []
            return
        self.issueCommand('planClr', {})

    def _cmdEmote(self, idx):
        from src.constants import EMOTE_TEXTS
        idx = max(0, min(len(EMOTE_TEXTS) - 1, int(idx)))
        if self.netRole is None:
            self.emotes = [em for em in self.emotes if em['fromSlot'] != 0]
            self.emotes.append({'fromSlot': 0, 'idx': idx,
                                'life': self._EMOTE_LIFE})
            return
        self.issueCommand('emote', {'idx': idx})
