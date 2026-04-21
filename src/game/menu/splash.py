# Module: menu.splash
# SplashScreen — press-any-key intro for Nerds at War

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT

from src.game.menu._common import (
    _DARK_BG, _PARCHMENT, _GOLD_LIGHT, _MUTED, _DIM,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
)


# ══════════════════════════════════════════════════════════════════════════════
# SplashScreen
# ══════════════════════════════════════════════════════════════════════════════
class SplashScreen:
    """Press-any-key intro screen. Returns when the player presses a key or clicks."""

    def __init__(self, screen, clock):
        self.screen   = screen
        self.clock    = clock
        self.tick     = 0
        self.particles, self.prng = _makeParticles(80)

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return 'menu'

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw()
            self.clock.tick(60)

    def _draw(self):
        surf = self.screen
        t    = self.tick

        _drawBackground(surf, t)
        _drawParticles(surf, self.particles)

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        # Title
        title_font = _font(92, bold=True)
        title = "NERDS AT WAR"
        tw = title_font.size(title)[0]
        _renderShadow(surf, title, title_font, _GOLD_LIGHT,
                      cx - tw // 2, cy - 120, offset=3)

        _drawDivider(surf, cy - 16)

        # Blinking "press to play"
        if (t // 35) % 2 == 0:
            hint_font = _font(22)
            hint = "— Press any key to begin —"
            hw = hint_font.size(hint)[0]
            _renderShadow(surf, hint, hint_font, _MUTED,
                          cx - hw // 2, cy + 50, offset=1)

        # Version / flavour text at bottom
        small = _font(15)
        flavour = "Command the battlefield  ·  Defeat your enemy  ·  Write history"
        fw = small.size(flavour)[0]
        surf.blit(small.render(flavour, True, _DIM), (cx - fw // 2, SCREEN_HEIGHT - 32))

        pygame.display.flip()
