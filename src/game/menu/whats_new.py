# Module: menu.whats_new
# "What's New" popup — shown once per version on first launch.
#
# To add notes for a future release, append an entry to CHANGELOG below.
# The key must match the VERSION string in src/version.py exactly.

import json
import os

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game.menu._common import (
    _DARK_BG, _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _makeParticles, _updateParticles, _drawParticles,
)

# ── Changelog ─────────────────────────────────────────────────────────────
# Add a new key here for every release that has player-facing changes.
CHANGELOG = {
    "v1.35": [
        "Accounts werken nu volledig lokaal — geen serververbinding nodig om in te loggen",
        "Registreren en inloggen werkt altijd, ook zonder internet",
        "Campaign en tutorial voortgang opgeslagen per account",
    ],
    "v1.34": [
        "Custom artwork: menu background, all 5 campaign worlds, and all 9 biome map previews",
        "Multiplayer: always 8 slots (4v4), clear Team 1 / Team 2 layout with divider",
        "Waves mode: playable with up to 8 players — all on the same team against the enemy",
        "Waves lobby: team headers replaced by a single ALLIES banner, no red slots",
        "Campaign: world backgrounds now painted landscapes instead of generated gradients",
        "Campaign: mission numbers shown per-world (1, 2, 3…) instead of globally",
        "Campaign: boss missions use the Hunt the Commander game mode",
        "Campaign: world map is a straight left-to-right route through the terrain",
        "Biome thumbnails in the lobby now show hand-drawn map previews",
        "Fixed: broken Unicode symbols throughout menus replaced with readable alternatives",
    ],
    "v1.29": [
        "Waves: artillery deploys and fires — no more marching straight past your line",
        "Waves: enemy AI pushes aggressively instead of clustering at bridges",
        "Waves: faster escalation — cavalry appears from wave 2, heavy infantry from wave 3",
        "Multiplayer: wave number now visible for all players, not just the host",
        "Multiplayer: cannon, musket, and cavalry sounds now play for joined players",
        "Multiplayer: Settings now accessible from the pause menu mid-game",
        "Per-player unit cap of 40 — each player manages their own army in team modes",
        "Performance: unit simulation much faster when many troops are on screen",
        "Bug report screen: messages now reliably delivered to Discord",
    ],
    "v1.25": [
        "Waves (Coop) added to multiplayer — survive enemy waves together with up to 4 players",
        "2v2 partial lobby: start with fewer than 4 players, solo player commands the full team army",
        "In-game bug report button in the pause menu — reports go straight to Discord",
        "Character portraits auto-download on first launch — no manual installation needed",
        "ESC skips story dialogs instantly; speaker name moved closer to the text",
        "AI is less passive: DEFENSIVE personality switches tactics faster and pushes forward more",
        "Bot partner in 2v2 now actually fights — fixed player-side bot standing still",
        "Attack click radius increased — easier to target enemies in multiplayer",
        "VPS relay server: host internet lobbies without port forwarding or room codes",
    ],
    "v1.24": [
        "Campaign story: 5 worlds each with a unique villain, themed background, and unlock chain",
        "Prologue screen: 'Het Paleis' world shows the full story intro before the first mission",
        "Story dialogs: Fire Emblem-style portrait scenes before and after key missions",
        "All 8 characters have hand-drawn portraits with transparent backgrounds",
        "World select backgrounds are now painted landscapes: fields, river valley, dry plains, highlands, and a night-time fortress",
        "Star rating reworked: combined kill-efficiency and survival score — no more 3 stars for a pyrrhic HQ rush",
        "Angry Birds-style star reveal: stars bounce in one by one with a glow burst on the results screen",
        "Stars rendered as proper polygon shapes everywhere — no more square placeholders",
        "Multiplayer fix: projectile crash when drawing musket streaks on client side",
    ],
    "v1.22": [
        "New game mode: Conquest — capture outposts to score points, first to 1000 wins",
        "Conquest AI: units spread across outposts, defend under pressure, cavalry rushes captures",
        "Battle results screen: shows winner, duration, units lost, and conquest score",
        "Full English translation: all menus, tutorials, campaign, and UI strings",
        "Cavalry and heavy infantry spawn rates increased for more varied armies",
        "HQ capture disabled in Conquest — only annihilation or points decide the winner",
        "File structure cleaned up: docs/, tools/, assets/ folders organised",
        "Build script translated to English and updated for new folder layout",
    ],
    "v1.19": [
        "COOP bugfix: enemy units are no longer taken over by the AI",
        "What's New popup added — appears once with each update",
        "Music now loops smoothly: fade-out and fade-in on repeat",
        "Quit button and ESC confirmation dialog added to the main menu",
        "Fully redesigned unit visuals: infantry, heavy infantry, cavalry, artillery, and commander",
        "Improved cannon explosions with flash, fireball, smoke, and sparks",
        "Musket bullets now show a direction streak; cannonballs have a 3D highlight",
        "Spear thrust for heavy infantry and sword swing for cavalry as melee effects",
        "Blood particles on all damage types (musket, cannon, and melee)",
        "Water splashes when units move through rivers",
        "Outpost redesigned as a round tower; HQ as a castle with corner towers",
        "Terrain: borders removed for rocks and lakes; highlands show stipple pattern",
    ],
}

_SETTINGS = os.path.join(os.getcwd(), 'settings.json')


def shouldShowWhatsNew(version: str) -> bool:
    """Return True if this version hasn't been seen yet and has changelog entries."""
    if version not in CHANGELOG:
        return False
    try:
        with open(_SETTINGS, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('last_seen_version') != version
    except (OSError, json.JSONDecodeError):
        return True


def markWhatsNewSeen(version: str):
    """Persist the current version so the popup isn't shown again."""
    data = {}
    try:
        with open(_SETTINGS, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    data['last_seen_version'] = version
    try:
        with open(_SETTINGS, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ── Popup ──────────────────────────────────────────────────────────────────

def _wrapText(text, font, max_w):
    """Split text into lines that fit within max_w pixels."""
    words  = text.split()
    lines  = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip()
        if font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class WhatsNewScreen:
    """Modal "What's New" overlay. Call .run() — returns when dismissed."""

    _BOX_W   = 620
    _TEXT_X  = 46    # left indent for bullet text
    _DOT_X   = 28    # x of the bullet dot

    def __init__(self, screen, clock, version: str):
        self.screen  = screen
        self.clock   = clock
        self.version = version
        self.particles, self.prng = _makeParticles(40)
        self.tick    = 0

        # Pre-wrap bullets so layout is stable
        bf         = _font(17)
        max_text_w = self._BOX_W - self._TEXT_X - 20
        raw        = CHANGELOG.get(version, [])
        # Each entry: (wrapped_lines, is_first_line_of_bullet)
        self._lines = []
        for bullet in raw:
            wrapped = _wrapText(bullet, bf, max_text_w)
            for j, ln in enumerate(wrapped):
                self._lines.append((ln, j == 0))   # (text, show_dot)

    def run(self):
        cx, cy   = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        line_h   = 24
        pad      = 20
        header_h = 100
        footer_h = 68
        max_box_h = SCREEN_HEIGHT - 80

        box_h    = header_h + len(self._lines) * line_h + pad * 2 + footer_h
        box_h    = max(min(box_h, max_box_h), 260)

        box_rect = pygame.Rect(cx - self._BOX_W // 2,
                               cy - box_h // 2,
                               self._BOX_W, box_h)
        btn_rect = pygame.Rect(cx - 80, box_rect.bottom - 54, 160, 40)

        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    markWhatsNewSeen(self.version)
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_SPACE):
                    markWhatsNewSeen(self.version)
                    return 'ok'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_rect.collidepoint(mx, my):
                        markWhatsNewSeen(self.version)
                        return 'ok'

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(box_rect, btn_rect, mx, my, line_h, pad, header_h)
            self.clock.tick(60)

    def _draw(self, box_rect, btn_rect, mx, my, line_h, pad, header_h):
        surf = self.screen
        _drawBackground(surf, self.tick)
        _drawParticles(surf, self.particles)

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 30, 15, 160))
        surf.blit(overlay, (0, 0))

        pygame.draw.rect(surf, _DARK_BG, box_rect, border_radius=8)
        pygame.draw.rect(surf, _GOLD,    box_rect, 2, border_radius=8)

        cx = box_rect.centerx

        # Title
        title_f = _font(26, bold=True)
        title   = f"What's New in Nerds at War  \u2014  {self.version}"
        tw = title_f.size(title)[0]
        _renderShadow(surf, title, title_f, _PARCHMENT,
                      cx - tw // 2, box_rect.top + 18, offset=2)

        sub_f = _font(15)
        sub   = "This appears once with each update."
        sw    = sub_f.size(sub)[0]
        surf.blit(sub_f.render(sub, True, _MUTED), (cx - sw // 2, box_rect.top + 58))

        _drawDivider(surf, box_rect.top + header_h - 8)

        # Bullet lines
        bf = _font(17)
        for i, (text, show_dot) in enumerate(self._lines):
            y = box_rect.top + header_h + pad + i * line_h
            if show_dot:
                pygame.draw.circle(surf, _GOLD_LIGHT,
                                   (box_rect.left + self._DOT_X,
                                    y + bf.get_height() // 2), 3)
            surf.blit(bf.render(text, True, _WHITE),
                      (box_rect.left + self._TEXT_X, y))

        # Sluiten button
        hover = btn_rect.collidepoint(mx, my)
        pygame.draw.rect(surf, _BTN_BG_HOVER if hover else _BTN_BG,
                         btn_rect, border_radius=4)
        pygame.draw.rect(surf, _GOLD_LIGHT if hover else _GOLD,
                         btn_rect, 2 if hover else 1, border_radius=4)
        lf    = _font(20, bold=hover)
        label = lf.render("Close", True, _WHITE if hover else _PARCHMENT)
        surf.blit(label, (btn_rect.centerx - label.get_width() // 2,
                          btn_rect.centery - label.get_height() // 2))

        pygame.display.flip()
