# Module: menu.pause
# PauseMenu — in-game overlay shown when ESC is pressed

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT

from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER, _BTN_BG_DISABLED,
    _font,
)


# ══════════════════════════════════════════════════════════════════════════════
# PauseMenu  — in-game overlay shown when ESC is pressed
# ══════════════════════════════════════════════════════════════════════════════
_PAUSE_BUTTONS = [
    # (return_value, label_nl)
    ('resume',     'Doorgaan'),
    ('surrender',  'Opgeven'),
    ('menu',       'Naar Hoofdmenu'),
    ('quit',       'Afsluiten'),
]

class PauseMenu:
    """In-game pause overlay. Returns 'resume', 'menu', or 'quit'."""

    _PBW = 280
    _PBH = 52
    _PGAP = 14

    def __init__(self, screen, clock, background):
        self.screen     = screen
        self.clock      = clock
        self.background = background  # frozen game frame to show behind overlay

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        # Compute panel geometry first so buttons are always inside it
        PH      = len(_PAUSE_BUTTONS) * (self._PBH + self._PGAP) + 140
        py_panel= cy - PH // 2
        top     = py_panel + 82   # below title (≈46px) + divider + padding

        self._buttons = []
        for i, (val, label) in enumerate(_PAUSE_BUTTONS):
            y = top + i * (self._PBH + self._PGAP)
            r = pygame.Rect(cx - self._PBW // 2, y, self._PBW, self._PBH)
            self._buttons.append({'val': val, 'label': label, 'rect': r, 'hover': False})

    def run(self):
        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 'resume'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for btn in self._buttons:
                        if btn['hover']:
                            return btn['val']

            for btn in self._buttons:
                btn['hover'] = btn['rect'].collidepoint(mx, my)

            self._draw(mx, my)
            self.clock.tick(60)

    def _draw(self, mx, my):
        surf = self.screen
        cx   = SCREEN_WIDTH  // 2
        cy   = SCREEN_HEIGHT // 2

        # Frozen game frame underneath
        surf.blit(self.background, (0, 0))

        # Full-screen dim overlay
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((20, 15, 5, 140))
        surf.blit(dim, (0, 0))

        # Parchment panel on top of the frozen battle — reads as a torn map
        # note pinned over the action.
        PW, PH = self._PBW + 80, len(_PAUSE_BUTTONS) * (self._PBH + self._PGAP) + 140
        panel = pygame.Surface((PW, PH), pygame.SRCALPHA)
        panel.fill((244, 236, 219, 235))
        px = cx - PW // 2
        py = cy - PH // 2
        surf.blit(panel, (px, py))
        pygame.draw.rect(surf, _GOLD, pygame.Rect(px, py, PW, PH), 2, border_radius=6)

        # Title
        tf  = _font(42, bold=True)
        ttx = tf.render("PAUZE", True, _GOLD_LIGHT)
        surf.blit(ttx, (cx - ttx.get_width() // 2, py + 18))
        pygame.draw.line(surf, _GOLD,
                         (cx - 80, py + 66), (cx + 80, py + 66), 1)

        # Buttons
        for btn in self._buttons:
            r     = btn['rect']
            hover = btn['hover']
            is_destructive = btn['val'] in ('quit', 'surrender')

            bg  = _BTN_BG_HOVER if hover else _BTN_BG
            if is_destructive:
                brd = (180, 70, 70) if hover else _DIM
                color = (160, 40, 40) if hover else _MUTED
            else:
                brd = _GOLD_LIGHT if hover else _GOLD
                color = _WHITE if hover else _PARCHMENT

            pygame.draw.rect(surf, bg,  r, border_radius=5)
            pygame.draw.rect(surf, brd, r, 1 if not hover else 2, border_radius=5)

            f   = _font(24, bold=hover)
            txt = f.render(btn['label'], True, color)
            surf.blit(txt, (r.centerx - txt.get_width() // 2,
                            r.centery - txt.get_height() // 2))

        # ESC hint
        hf  = _font(14)
        ht  = hf.render("ESC  —  doorgaan", True, _DIM)
        surf.blit(ht, (cx - ht.get_width() // 2, py + PH - 26))

        pygame.display.flip()
