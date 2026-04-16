# Module: menu.main_menu
# MainMenu — top-level mode picker for Nerds ad War

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src import audio
from src.version import VERSION

from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED_RED, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER, _BTN_BG_DISABLED,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
)


# ══════════════════════════════════════════════════════════════════════════════
# MainMenu
# ══════════════════════════════════════════════════════════════════════════════
_BUTTONS = [
    # (key,           label_nl,      enabled)
    ('tutorial',    'Tutorial',      True),
    ('campaign',    'Campagne',      True),
    ('singleplayer','Één Speler',    True),
    ('multiplayer', 'Multiplayer',   True),
    ('sandbox',     'Sandbox',       True),
    ('settings',    'Instellingen',  True),
]

_BTN_W   = 340
_BTN_H   = 56
_BTN_GAP = 18


class _Button:
    def __init__(self, key, label, enabled, cx, y):
        self.key     = key
        self.label   = label
        self.enabled = enabled
        self.rect    = pygame.Rect(cx - _BTN_W // 2, y, _BTN_W, _BTN_H)
        self.hover   = False

    def update(self, mx, my):
        self.hover = self.rect.collidepoint(mx, my) and self.enabled

    def draw(self, surf, tick):
        r = self.rect
        if self.hover:
            # Soft copper halo behind the button on hover
            glow = pygame.Surface((_BTN_W + 12, _BTN_H + 12), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*_GOLD[:3], 40), glow.get_rect(),
                             border_radius=8)
            surf.blit(glow, (r.x - 6, r.y - 6))
            bg_color  = _BTN_BG_HOVER
            brd_color = _GOLD_LIGHT
        elif self.enabled:
            bg_color  = _BTN_BG
            brd_color = _GOLD
        else:
            bg_color  = _BTN_BG_DISABLED
            brd_color = _DIM

        pygame.draw.rect(surf, bg_color,  r, border_radius=4)
        pygame.draw.rect(surf, brd_color, r, 1, border_radius=4)

        # Label — deep navy (high contrast) on hover, navy ink otherwise
        font  = _font(26, bold=self.hover)
        color = _WHITE if self.hover else (_PARCHMENT if self.enabled else _DIM)
        text  = font.render(self.label, True, color)
        surf.blit(text, (r.centerx - text.get_width() // 2,
                         r.centery - text.get_height() // 2))

        # "binnenkort" badge for disabled
        if not self.enabled:
            bf    = _font(13)
            badge = bf.render("binnenkort", True, _MUTED_RED)
            surf.blit(badge, (r.right - badge.get_width() - 10,
                              r.bottom - badge.get_height() - 6))


class MainMenu:
    """4-button main menu. Returns a mode key string or 'quit'."""

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(60)

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2
        total_h = len(_BUTTONS) * _BTN_H + (len(_BUTTONS) - 1) * _BTN_GAP
        top     = cy - total_h // 2 + 30   # shift down a little for title room

        self.buttons = []
        for i, (key, label, enabled) in enumerate(_BUTTONS):
            y = top + i * (_BTN_H + _BTN_GAP)
            self.buttons.append(_Button(key, label, enabled, cx, y))

    def run(self):
        # Start menu music once; play_music is idempotent when already on 'menu'
        audio.play_music('menu')
        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 'quit'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for btn in self.buttons:
                        if btn.hover:
                            audio.play_sfx('click')
                            return btn.key

            for btn in self.buttons:
                btn.update(mx, my)

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw()
            self.clock.tick(60)

    def _draw(self):
        surf = self.screen
        t    = self.tick
        cx   = SCREEN_WIDTH // 2

        _drawBackground(surf, t)
        _drawParticles(surf, self.particles)

        # Title block
        tf   = _font(58, bold=True)
        title = "WAR OF DOTS"
        tw   = tf.size(title)[0]
        _renderShadow(surf, title, tf, _GOLD_LIGHT, cx - tw // 2, 52, offset=3)

        _drawDivider(surf, 120)

        # Buttons
        for btn in self.buttons:
            btn.draw(surf, t)

        # Footer
        small = _font(15)
        foot  = f"© 2025 NerdsAdWar  ·  {VERSION}"
        fw    = small.size(foot)[0]
        surf.blit(small.render(foot, True, _DIM), (cx - fw // 2, SCREEN_HEIGHT - 28))

        pygame.display.flip()
