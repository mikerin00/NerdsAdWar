# Module: menu.main_menu
# MainMenu — top-level mode picker for Nerds at War

import math

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src import audio, accounts
from src.version import VERSION

from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED_RED, _DIM, _WHITE, _MUTED,
    _BTN_BG, _BTN_BG_HOVER, _BTN_BG_DISABLED, _DARK_BG,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
)
from src.game.menu.account_menu import _loadAvatarCircle, _drawDefaultAvatar


# ══════════════════════════════════════════════════════════════════════════════
# MainMenu
# ══════════════════════════════════════════════════════════════════════════════
_BUTTONS = [
    # (key,           label,           enabled)
    ('tutorial',    'Tutorial',        True),
    ('campaign',    'Campaign',        True),
    ('singleplayer','Single Player',   True),
    ('multiplayer', 'Multiplayer',     True),
    ('sandbox',     'Sandbox',         True),
    ('quit',        'Quit Game',       True),
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
            badge = bf.render("coming soon", True, _MUTED_RED)
            surf.blit(badge, (r.right - badge.get_width() - 10,
                              r.bottom - badge.get_height() - 6))


def _confirmQuit(screen, clock):
    """Modal 'Do you want to exit?' dialog. Returns True if confirmed."""
    cx, cy  = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    box     = pygame.Rect(cx - 220, cy - 90, 440, 180)
    yes_r   = pygame.Rect(cx - 180, cy + 30, 160, 44)
    no_r    = pygame.Rect(cx + 20,  cy + 30, 160, 44)

    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return True
                if event.key == pygame.K_ESCAPE:
                    return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if yes_r.collidepoint(mx, my):
                    audio.play_sfx('click')
                    return True
                if no_r.collidepoint(mx, my):
                    audio.play_sfx('click')
                    return False

        # Dim overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 30, 15, 170))
        screen.blit(overlay, (0, 0))

        # Box
        pygame.draw.rect(screen, _DARK_BG, box, border_radius=8)
        pygame.draw.rect(screen, _GOLD,    box, 2,  border_radius=8)

        # Text
        tf  = _font(24, bold=True)
        msg = "Do you want to quit the game?"
        tw  = tf.size(msg)[0]
        _renderShadow(screen, msg, tf, _PARCHMENT, cx - tw // 2, cy - 62, offset=2)

        sub_f = _font(16)
        sub   = "Unsaved progress will be lost."
        sw    = sub_f.size(sub)[0]
        screen.blit(sub_f.render(sub, True, _DIM), (cx - sw // 2, cy - 22))

        # Yes / No buttons
        for rect, label in ((yes_r, "Yes, quit"), (no_r, "No, go back")):
            hover = rect.collidepoint(mx, my)
            pygame.draw.rect(screen, _BTN_BG_HOVER if hover else _BTN_BG,
                             rect, border_radius=4)
            pygame.draw.rect(screen, _GOLD_LIGHT if hover else _GOLD,
                             rect, 2 if hover else 1, border_radius=4)
            bf    = _font(18, bold=hover)
            color = _WHITE if hover else _PARCHMENT
            bt    = bf.render(label, True, color)
            screen.blit(bt, (rect.centerx - bt.get_width() // 2,
                             rect.centery - bt.get_height() // 2))

        pygame.display.flip()
        clock.tick(60)


_ICON_R  = 22   # radius of corner icon buttons
_ICON_PAD = 18  # padding from screen edge to centre


def _drawGearIcon(surf, cx, cy, r, color, hover):
    """Draw a cogwheel icon centred at (cx, cy)."""
    bg = _BTN_BG_HOVER if hover else _BTN_BG
    pygame.draw.circle(surf, bg,    (cx, cy), r)
    pygame.draw.circle(surf, color, (cx, cy), r, 1)
    # Teeth: 8 small rectangles radiating outward
    tooth_w, tooth_h = 4, 5
    for i in range(8):
        a  = math.radians(i * 45)
        tx = cx + int(math.cos(a) * (r - 2))
        ty = cy + int(math.sin(a) * (r - 2))
        ts = pygame.Surface((tooth_w * 2, tooth_h * 2), pygame.SRCALPHA)
        pygame.draw.rect(ts, color, (0, 0, tooth_w * 2, tooth_h * 2), border_radius=1)
        surf.blit(ts, (tx - tooth_w, ty - tooth_h))
    # Inner hub circle
    pygame.draw.circle(surf, color, (cx, cy), r - 7, 2)
    pygame.draw.circle(surf, bg,    (cx, cy), r - 9)


def _drawQuestionIcon(surf, cx, cy, r, color, hover):
    """Draw a '?' help icon centred at (cx, cy)."""
    bg = _BTN_BG_HOVER if hover else _BTN_BG
    pygame.draw.circle(surf, bg,    (cx, cy), r)
    pygame.draw.circle(surf, color, (cx, cy), r, 1)
    f   = _font(r + 4, bold=True)
    lbl = f.render("?", True, color)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy - lbl.get_height() // 2))


class MainMenu:
    """Main menu. Returns a mode key string or 'quit'."""

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(60)

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2
        total_h = len(_BUTTONS) * _BTN_H + (len(_BUTTONS) - 1) * _BTN_GAP
        top     = cy - total_h // 2 + 30

        self.buttons = []
        for i, (key, label, enabled) in enumerate(_BUTTONS):
            y = top + i * (_BTN_H + _BTN_GAP)
            self.buttons.append(_Button(key, label, enabled, cx, y))

        # Corner icon hit-rects
        p = _ICON_PAD + _ICON_R
        self._gear_rect = pygame.Rect(SCREEN_WIDTH  - p - _ICON_R, _ICON_PAD,
                                      _ICON_R * 2,  _ICON_R * 2)
        self._help_rect = pygame.Rect(_ICON_PAD,    _ICON_PAD,
                                      _ICON_R * 2,  _ICON_R * 2)

        # Profile badge (bottom-left corner)
        self._profile_rect = pygame.Rect(12, SCREEN_HEIGHT - 58, 220, 46)
        self._avatarCache: tuple | None = None   # (path, surface)

    def run(self):
        audio.play_music('menu')
        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if _confirmQuit(self.screen, self.clock):
                        return 'quit'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._gear_rect.collidepoint(mx, my):
                        audio.play_sfx('click')
                        return 'settings'
                    if self._help_rect.collidepoint(mx, my):
                        audio.play_sfx('click')
                        return 'whats_new'
                    if self._profile_rect.collidepoint(mx, my):
                        audio.play_sfx('click')
                        return 'account'
                    for btn in self.buttons:
                        if btn.hover:
                            audio.play_sfx('click')
                            if btn.key == 'quit':
                                if _confirmQuit(self.screen, self.clock):
                                    return 'quit'
                            else:
                                return btn.key

            for btn in self.buttons:
                btn.update(mx, my)

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(mx, my)
            self.clock.tick(60)

    def _drawProfileBadge(self, surf, mx, my):
        user   = accounts.getActiveUser()
        rect   = self._profile_rect
        hover  = rect.collidepoint(mx, my)
        bg     = _BTN_BG_HOVER if hover else _BTN_BG
        brd    = _GOLD_LIGHT   if hover else _GOLD
        pygame.draw.rect(surf, bg,  rect, border_radius=6)
        pygame.draw.rect(surf, brd, rect, 1, border_radius=6)

        av_r  = 17
        av_cx = rect.x + 4 + av_r
        av_cy = rect.centery

        if user:
            av_path = user.get('avatar')
            if av_path:
                if not (self._avatarCache and self._avatarCache[0] == av_path):
                    self._avatarCache = (av_path, _loadAvatarCircle(av_path, av_r * 2))
                av_surf = self._avatarCache[1] if self._avatarCache else None
                if av_surf:
                    surf.blit(av_surf, (av_cx - av_r, av_cy - av_r))
                else:
                    _drawDefaultAvatar(surf, av_cx, av_cy, av_r)
            else:
                _drawDefaultAvatar(surf, av_cx, av_cy, av_r)
            pygame.draw.circle(surf, brd, (av_cx, av_cy), av_r + 1, 1)

            nf = _font(16, bold=hover)
            nt = nf.render(user['username'], True, _WHITE if hover else _PARCHMENT)
            surf.blit(nt, (av_cx + av_r + 8, av_cy - nt.get_height() // 2))
        else:
            _drawDefaultAvatar(surf, av_cx, av_cy, av_r)
            nf = _font(15)
            nt = nf.render("Geen account", True, _MUTED)
            surf.blit(nt, (av_cx + av_r + 8, av_cy - nt.get_height() // 2))

    def _draw(self, mx, my):
        surf = self.screen
        t    = self.tick
        cx   = SCREEN_WIDTH // 2

        _drawBackground(surf, t)
        _drawParticles(surf, self.particles)

        # Title block
        tf    = _font(58, bold=True)
        title = "NERDS AT WAR"
        tw    = tf.size(title)[0]
        _renderShadow(surf, title, tf, _GOLD_LIGHT, cx - tw // 2, 52, offset=3)

        _drawDivider(surf, 120)

        for btn in self.buttons:
            btn.draw(surf, t)

        # Corner icon buttons
        p = _ICON_PAD + _ICON_R
        gear_cx = SCREEN_WIDTH - p
        help_cx = _ICON_PAD + _ICON_R
        icon_cy = _ICON_PAD + _ICON_R

        gear_hover = self._gear_rect.collidepoint(mx, my)
        help_hover = self._help_rect.collidepoint(mx, my)

        _drawGearIcon    (surf, gear_cx, icon_cy, _ICON_R,
                          _GOLD_LIGHT if gear_hover else _GOLD, gear_hover)
        _drawQuestionIcon(surf, help_cx, icon_cy, _ICON_R,
                          _GOLD_LIGHT if help_hover else _GOLD, help_hover)

        # Tooltips on hover
        tf2 = _font(14)
        if gear_hover:
            tip = tf2.render("Settings", True, _MUTED)
            surf.blit(tip, (gear_cx - tip.get_width() - _ICON_R - 6, icon_cy - tip.get_height() // 2))
        if help_hover:
            tip = tf2.render("What's New in v" + VERSION.lstrip('v'), True, _MUTED)
            surf.blit(tip, (help_cx + _ICON_R + 6, icon_cy - tip.get_height() // 2))

        # Footer
        small = _font(15)
        foot  = f"© 2025 Nerds at War  ·  {VERSION}  ·  All rights reserved"
        fw    = small.size(foot)[0]
        surf.blit(small.render(foot, True, _DIM), (cx - fw // 2, SCREEN_HEIGHT - 28))

        # Profile badge (bottom-left)
        self._drawProfileBadge(surf, mx, my)

        pygame.display.flip()
