# Module: menu.settings
# Settings screen — audio sliders, display toggle, keybind editor.
# Returns 'back' or 'quit'.

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _drawButton,
)
from src import audio
from src import display as displaymode
from src import keybinds as KB


SLIDERS = [
    ('master', 'Master Volume'),
    ('music',  'Music'),
    ('sfx',    'Sound Effects'),
]

_SETTERS = {
    'master': audio.set_master,
    'music':  audio.set_music,
    'sfx':    audio.set_sfx,
}

# Order in which keybinds are shown in the editor
_KB_ORDER = [
    'carre', 'start_gevecht', 'ping', 'battleplan',
    'emote', 'sel_all', 'sel_inf', 'sel_cav', 'sel_heavy', 'sel_art', 'ai_log',
]


class SettingsMenu:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self._dragging = None

    def run(self):
        cx = SCREEN_WIDTH // 2
        slider_w = 440
        slider_x = cx - slider_w // 2
        slider_y0 = 240
        slider_dy = 92

        display_y    = slider_y0 + len(SLIDERS) * slider_dy + 30
        display_rect = pygame.Rect(cx - 220, display_y, 440, 50)

        keys_rect = pygame.Rect(cx - 220, display_y + 72, 440, 44)
        back_rect = pygame.Rect(cx - 90, SCREEN_HEIGHT - 76, 180, 44)

        slider_rects = {}
        for i, (key, _) in enumerate(SLIDERS):
            y = slider_y0 + i * slider_dy
            slider_rects[key] = pygame.Rect(slider_x, y, slider_w, 14)

        sfx_cooldown = 0

        while True:
            mx, my = pygame.mouse.get_pos()
            click = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 'back'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True
                    for key, r in slider_rects.items():
                        expanded = r.inflate(10, 20)
                        if expanded.collidepoint(mx, my):
                            self._dragging = key
                            self._applyFromMouse(key, mx, slider_rects[key])
                            break
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if self._dragging == 'sfx':
                        audio.play_sfx('select')
                    self._dragging = None

            if self._dragging and pygame.mouse.get_pressed()[0]:
                self._applyFromMouse(self._dragging, mx,
                                     slider_rects[self._dragging])

            # ── draw ─────────────────────────────────────────────────────
            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(44, bold=True)
            _renderShadow(self.screen, "SETTINGS", tf, _GOLD_LIGHT,
                          cx - tf.size("SETTINGS")[0] // 2, 80, offset=3)
            _drawDivider(self.screen, 145)

            _drawCenteredText(self.screen, "Audio", _font(22, bold=True),
                              _PARCHMENT, 185)

            vols = audio.get_volumes()
            for i, (key, label) in enumerate(SLIDERS):
                y = slider_y0 + i * slider_dy
                lt = _font(18).render(label, True, _PARCHMENT)
                self.screen.blit(lt, (slider_x, y - 28))
                pct = f"{int(vols.get(key, 0.0) * 100):3d}%"
                pt = _font(18, bold=True).render(pct, True, _GOLD_LIGHT)
                self.screen.blit(pt, (slider_x + slider_w - pt.get_width(), y - 28))

                track = slider_rects[key]
                pygame.draw.rect(self.screen, (228, 216, 190), track, border_radius=7)
                pygame.draw.rect(self.screen, _GOLD, track, 1, border_radius=7)
                v = vols.get(key, 0.0)
                fill_w = int(track.width * v)
                if fill_w > 0:
                    pygame.draw.rect(self.screen, _GOLD_LIGHT,
                                     pygame.Rect(track.x, track.y,
                                                 fill_w, track.height),
                                     border_radius=7)
                knob_x = track.x + fill_w
                pygame.draw.circle(self.screen, (250, 242, 220),
                                   (knob_x, track.centery), 10)
                pygame.draw.circle(self.screen, _GOLD,
                                   (knob_x, track.centery), 10, 2)

            # Display toggle
            cur_mode = displaymode.loadMode()
            label    = ("Display: FULLSCREEN"
                        if cur_mode == displaymode.FULLSCREEN
                        else "Display: WINDOWED")
            _drawCenteredText(self.screen, "Display", _font(22, bold=True),
                              _PARCHMENT, display_y - 38)
            disp_hover = _drawButton(self.screen, display_rect, label, mx, my)

            # Keybinds button
            keys_hover = _drawButton(self.screen, keys_rect,
                                     "Keybindings →", mx, my)

            back_hover = _drawButton(self.screen, back_rect, "Back", mx, my)

            ct = _font(14).render("Made with Claude :)", True, _DIM)
            self.screen.blit(ct, (cx - ct.get_width() // 2, SCREEN_HEIGHT - 28))

            if click and disp_hover:
                new_mode = (displaymode.WINDOWED
                            if cur_mode == displaymode.FULLSCREEN
                            else displaymode.FULLSCREEN)
                displaymode.saveMode(new_mode)
                self.screen = displaymode.applyMode(
                    new_mode, SCREEN_WIDTH, SCREEN_HEIGHT)
                audio.play_sfx('click')
                continue

            if click and keys_hover:
                audio.play_sfx('click')
                result = self._keybindsScreen()
                if result == 'quit':
                    return 'quit'
                continue

            if click and back_hover:
                audio.play_sfx('click')
                return 'back'

            pygame.display.flip()
            self.clock.tick(60)

    def _keybindsScreen(self):
        cx   = SCREEN_WIDTH  // 2
        cy   = SCREEN_HEIGHT // 2

        row_h   = 46
        col_w   = 360
        total_h = len(_KB_ORDER) * row_h
        panel   = pygame.Rect(cx - col_w, cy - total_h // 2 - 10,
                              col_w * 2, total_h + 20)

        reset_rect = pygame.Rect(cx - 260, SCREEN_HEIGHT - 76, 200, 44)
        back_rect  = pygame.Rect(cx + 60,  SCREEN_HEIGHT - 76, 200, 44)

        waiting_for = None   # action name currently being rebound

        while True:
            mx, my = pygame.mouse.get_pos()
            click  = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'

                if event.type == pygame.KEYDOWN:
                    if waiting_for:
                        if event.key != pygame.K_ESCAPE:
                            KB.set_key(waiting_for, event.key)
                        waiting_for = None
                        audio.play_sfx('click')
                    elif event.key == pygame.K_ESCAPE:
                        return 'back'

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not waiting_for:
                        click = True

            # ── draw ─────────────────────────────────────────────────────
            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(38, bold=True)
            _renderShadow(self.screen, "KEYBINDINGS", tf, _GOLD_LIGHT,
                          cx - tf.size("KEYBINDINGS")[0] // 2, 70, offset=3)
            _drawDivider(self.screen, 130)

            # Panel background
            pygame.draw.rect(self.screen, (244, 236, 219), panel, border_radius=8)
            pygame.draw.rect(self.screen, _GOLD, panel, 2, border_radius=8)

            for i, action in enumerate(_KB_ORDER):
                row_y  = panel.y + 10 + i * row_h
                row_r  = pygame.Rect(panel.x + 4, row_y, panel.width - 8, row_h - 4)
                hover  = row_r.collidepoint(mx, my)
                active = (waiting_for == action)

                bg = (200, 230, 200) if active else ((248, 232, 204) if hover else (244, 236, 219))
                pygame.draw.rect(self.screen, bg, row_r, border_radius=4)
                if hover or active:
                    pygame.draw.rect(self.screen, _GOLD_LIGHT, row_r, 1, border_radius=4)

                # Label (left half)
                lbl = _font(16).render(KB.LABELS[action], True, _GOLD_LIGHT if active else _PARCHMENT)
                self.screen.blit(lbl, (row_r.x + 14, row_r.centery - lbl.get_height() // 2))

                # Key name (right half)
                if active:
                    key_txt = "Press a key…"
                    key_col = (80, 160, 80)
                else:
                    key_txt = pygame.key.name(KB.get(action)).upper()
                    key_col = _GOLD_LIGHT
                kt = _font(16, bold=True).render(key_txt, True, key_col)
                self.screen.blit(kt, (row_r.right - kt.get_width() - 14,
                                      row_r.centery - kt.get_height() // 2))

                if click and hover:
                    waiting_for = action
                    audio.play_sfx('select')

            # Buttons
            reset_hover = _drawButton(self.screen, reset_rect, "Reset all", mx, my)
            back_hover  = _drawButton(self.screen, back_rect,  "Back", mx, my)

            hint = _font(14).render(
                "Click an action → press the desired key  |  ESC = cancel",
                True, _DIM)
            self.screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_HEIGHT - 28))

            if click and reset_hover:
                KB.reset()
                audio.play_sfx('click')
            if click and back_hover:
                audio.play_sfx('click')
                return 'back'

            pygame.display.flip()
            self.clock.tick(60)

    def _applyFromMouse(self, key, mx, track):
        v = (mx - track.x) / track.width
        v = max(0.0, min(1.0, v))
        _SETTERS[key](v)


def _drawCenteredText(surf, text, font, color, y):
    s = font.render(text, True, color)
    surf.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, y))
