# Module: menu.settings
# Settings screen — audio volume sliders. Changes apply immediately and
# persist to settings.json via src.audio.
#
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


SLIDERS = [
    # (key, label)
    ('master', 'Totaal volume'),
    ('music',  'Muziek'),
    ('sfx',    'Geluidseffecten'),
]

_SETTERS = {
    'master': audio.set_master,
    'music':  audio.set_music,
    'sfx':    audio.set_sfx,
}


class SettingsMenu:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self._dragging = None   # key currently being dragged

    def run(self):
        cx = SCREEN_WIDTH // 2
        slider_w = 440
        slider_x = cx - slider_w // 2
        slider_y0 = 240
        slider_dy = 92

        # Display-mode toggle sits below the audio sliders.
        display_y    = slider_y0 + len(SLIDERS) * slider_dy + 30
        display_rect = pygame.Rect(cx - 220, display_y, 440, 50)

        back_rect = pygame.Rect(cx - 90, SCREEN_HEIGHT - 90, 180, 44)

        # Build slider hit-rects
        slider_rects = {}
        for i, (key, _) in enumerate(SLIDERS):
            y = slider_y0 + i * slider_dy
            slider_rects[key] = pygame.Rect(slider_x, y, slider_w, 14)

        # Preview-click sfx with a small cooldown so dragging doesn't spam
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
                        audio.play_sfx('select')        # preview sfx on release
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
            _renderShadow(self.screen, "INSTELLINGEN", tf, _GOLD_LIGHT,
                          cx - tf.size("INSTELLINGEN")[0] // 2, 80, offset=3)
            _drawDivider(self.screen, 145)

            _drawCenteredText(self.screen, "Audio", _font(22, bold=True),
                              _PARCHMENT, 180)

            vols = audio.get_volumes()
            for i, (key, label) in enumerate(SLIDERS):
                y = slider_y0 + i * slider_dy
                # Label + percentage
                lt = _font(18).render(label, True, _PARCHMENT)
                self.screen.blit(lt, (slider_x, y - 28))
                pct = f"{int(vols.get(key, 0.0) * 100):3d}%"
                pt = _font(18, bold=True).render(pct, True, _GOLD_LIGHT)
                self.screen.blit(pt, (slider_x + slider_w - pt.get_width(), y - 28))

                # Track (parchment inlay with copper border)
                track = slider_rects[key]
                pygame.draw.rect(self.screen, (228, 216, 190), track,
                                 border_radius=7)
                pygame.draw.rect(self.screen, _GOLD, track, 1,
                                 border_radius=7)
                # Filled portion (copper)
                v = vols.get(key, 0.0)
                fill_w = int(track.width * v)
                if fill_w > 0:
                    pygame.draw.rect(self.screen, _GOLD_LIGHT,
                                     pygame.Rect(track.x, track.y,
                                                 fill_w, track.height),
                                     border_radius=7)
                # Knob — ivory disc with copper rim
                knob_x = track.x + fill_w
                pygame.draw.circle(self.screen, (250, 242, 220),
                                   (knob_x, track.centery), 10)
                pygame.draw.circle(self.screen, _GOLD,
                                   (knob_x, track.centery), 10, 2)

            # Display-mode label + toggle button
            cur_mode = displaymode.loadMode()
            label    = ("Schermmodus: VOLLEDIG SCHERM"
                        if cur_mode == displaymode.FULLSCREEN
                        else "Schermmodus: VENSTER")
            _drawCenteredText(self.screen, "Beeld", _font(22, bold=True),
                              _PARCHMENT, display_y - 38)
            disp_hover = _drawButton(self.screen, display_rect, label,
                                     mx, my)

            # Back button
            back_hover = _drawButton(self.screen, back_rect, "Terug", mx, my)

            if click and disp_hover:
                new_mode = (displaymode.WINDOWED
                            if cur_mode == displaymode.FULLSCREEN
                            else displaymode.FULLSCREEN)
                displaymode.saveMode(new_mode)
                # Re-create the display surface in the new mode and update
                # our local reference so subsequent blits hit the live one.
                self.screen = displaymode.applyMode(
                    new_mode, SCREEN_WIDTH, SCREEN_HEIGHT)
                audio.play_sfx('click')
                continue

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
