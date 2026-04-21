# Module: menu.multiplayer
# Multiplayer lobby — name entry → Host/Join → per-role lobby with 2 or 4
# slots (1v1 or 2v2), map picker on host, ready handshake, game start.

import os
import random
import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT, PLAYER_COLORS
from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _DIM, _WHITE,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _drawButton,
)
from src.game.menu.lobby import _BIOMES, _BIOME_DESC, _drawBiomeThumbnail
from src.game.menu.sandbox import _listMaps, _loadMap
from src.net.protocol import (
    PROTOCOL_VERSION, DEFAULT_PORT, getLocalIp,
    MSG_HELLO, MSG_LOBBY, MSG_READY, MSG_START, MSG_PICK,
)
from src.net.session import HostServer, ClientConnector
from src.net.discovery import HostBeacon, scan as discoveryScan
from src.net.internet import InternetHost, InternetClient, fetchLobbies


# Match modes: (key, label, total_human_players)
MATCH_MODES = [
    ('1v1',  '1v1',  2),
    ('2v2',  '2v2',  4),
    ('COOP', 'Coop', 4),   # 1–4 humans vs AI
]

# Gamemodes available in multiplayer
_MP_GAMEMODES = [
    ('STANDAARD', 'Standard Battle'),
    ('COMMANDER', 'Hunt the Commander'),
    ('FOG',       'Fog of War'),
    ('CONQUEST',  'Conquest'),
    ('LAST_STAND','Waves (Coop)'),
]

# Slot↔side logic lives in src/constants.py so Game and the lobby share it.
from src.constants import MODE_SLOT_COUNT, slotCountForMode, teamOfSlot  # noqa: F401


# ── Name persistence ────────────────────────────────────────────────────────

_NAME_FILE = os.path.join(os.getcwd(), 'mp_name.txt')

def _loadName(default: str = '') -> str:
    try:
        with open(_NAME_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()[:16] or default
    except OSError:
        return default

def _saveName(name: str) -> None:
    try:
        with open(_NAME_FILE, 'w', encoding='utf-8') as f:
            f.write(name.strip()[:16])
    except OSError:
        pass


# ── Drawing helpers ─────────────────────────────────────────────────────────

def _drawCenteredText(surf, text, font, color, y):
    s = font.render(text, True, color)
    surf.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, y))


def _button(surf, rect, label, mx, my, enabled=True):
    return _drawButton(surf, rect, label, mx, my, enabled=enabled)


TEAM_COLOR = {'player': (70, 130, 200), 'enemy': (200, 80, 80)}

# Default color preference order per (mode, slot). First entry = preferred
# default when connecting / after mode switch. Entries further down are
# fallbacks when earlier ones are already taken by another slot.
DEFAULT_COLOR_ORDER = {
    # 1v1: host blauw, tegenstander rood
    ('1v1', 0): [0, 6, 2, 4],
    ('1v1', 1): [1, 5, 3, 7],
    # 2v2: teammates share a blue/red hue family so team identification stays clear
    ('2v2', 0): [0, 6, 2, 4],
    ('2v2', 1): [6, 2, 4, 0],
    ('2v2', 2): [1, 5, 3, 7],
    ('2v2', 3): [5, 3, 7, 1],
    # COOP: 1–4 teammates vs AI — maximise *contrast between teammates*.
    ('COOP', 0): [0, 2, 4, 7],   # blauw
    ('COOP', 1): [5, 3, 7, 2],   # oranje
    ('COOP', 2): [2, 4, 0, 7],   # groen
    ('COOP', 3): [3, 7, 5, 2],   # geel
    # 3v3: blauw-familie (cool) versus rood-familie (warm), 3 per team
    ('3v3', 0): [0, 6, 2, 4],    # blauw  / turkoois / groen / paars
    ('3v3', 1): [6, 2, 0, 4],    # turkoois / groen  / blauw / paars
    ('3v3', 2): [2, 0, 6, 4],    # groen   / blauw   / turk  / paars
    ('3v3', 3): [1, 5, 3, 7],    # rood    / oranje  / geel  / roze
    ('3v3', 4): [5, 3, 1, 7],    # oranje  / geel    / rood  / roze
    ('3v3', 5): [3, 1, 5, 7],    # geel    / rood    / oranje/ roze
    # 4v4: spread the 8-color palette so each team has 4 distinct picks
    ('4v4', 0): [0, 6, 2, 4],
    ('4v4', 1): [6, 2, 0, 4],
    ('4v4', 2): [2, 0, 6, 4],
    ('4v4', 3): [4, 0, 2, 6],
    ('4v4', 4): [1, 5, 3, 7],
    ('4v4', 5): [5, 3, 1, 7],
    ('4v4', 6): [3, 1, 5, 7],
    ('4v4', 7): [7, 1, 5, 3],
}


def _pickDefaultColor(slot: int, mode: str, takenByOthers) -> int:
    """First colour in the mode-specific order that isn't already claimed."""
    order = DEFAULT_COLOR_ORDER.get((mode, slot),
             list(range(len(PLAYER_COLORS))))
    for idx in order:
        if idx not in takenByOthers:
            return idx
    for idx in range(len(PLAYER_COLORS)):
        if idx not in takenByOthers:
            return idx
    return 0


# Legacy single-default lookup. 4v4 already has entries for every slot 0-7,
# so it's our fallback when callers don't know the exact mode.
DEFAULT_COLOR_IDX = {
    s: DEFAULT_COLOR_ORDER.get(('4v4', s), [s % len(PLAYER_COLORS)])[0]
    for s in range(8)
}


def _drawColorSwatches(surf, x, y, sw, gap, selectedIdx, mine, takenByOthers,
                       mx, my):
    """Draw the palette swatches. `takenByOthers` is a set of color indices
    already chosen by OTHER players — those get dimmed and aren't clickable
    even for the local player. Returns the index hovered+clickable or -1."""
    hovered = -1
    for i, (_, col) in enumerate(PLAYER_COLORS):
        r      = pygame.Rect(x + i * (sw + gap), y, sw, sw)
        taken  = (i in takenByOthers)
        clickable = mine and not taken
        # Dim taken swatches; they stay visible so you see what others picked
        if taken:
            col = tuple(c // 3 for c in col)
        brd = (255, 255, 255) if i == selectedIdx else (40, 40, 40)
        if r.collidepoint(mx, my) and clickable:
            hovered = i
            brd = _GOLD_LIGHT
        pygame.draw.rect(surf, col, r, border_radius=3)
        pygame.draw.rect(surf, brd, r, 2, border_radius=3)
        if taken:
            # Diagonal line to make "unavailable" obvious
            pygame.draw.line(surf, (200, 60, 60),
                             (r.x + 2, r.y + 2), (r.right - 3, r.bottom - 3), 2)
    return hovered


def _drawPlayerSlot(surf, rect, name, slot, ready, mine, team, colorIdx,
                    active=True, isBot=False):
    """Draw a slot card. `colorIdx` picks the left-edge stripe color from
    PLAYER_COLORS so the card always reflects the player's actual choice.
    `isBot=True` renders a gray bot-style card instead of a human slot."""
    if isBot:
        brd_col = (150, 150, 165)
        bg_col  = (195, 192, 205)
    else:
        brd_col = _GOLD_LIGHT if mine else _GOLD if active else _DIM
        bg_col  = (232, 220, 196) if active else (214, 204, 182)
    pygame.draw.rect(surf, bg_col, rect, border_radius=6)
    pygame.draw.rect(surf, brd_col, rect, 2, border_radius=6)

    # Left-edge stripe = player's picked color. Falls back to team default
    # if no valid pick yet (e.g. waiting slot before connection).
    if 0 <= colorIdx < len(PLAYER_COLORS):
        stripe_col = PLAYER_COLORS[colorIdx][1]
        color_name = PLAYER_COLORS[colorIdx][0]
    else:
        stripe_col = TEAM_COLOR[team]
        color_name = 'BLAUW' if team == 'player' else 'ROOD'
    pygame.draw.rect(surf, stripe_col,
                     pygame.Rect(rect.x, rect.y, 6, rect.height),
                     border_top_left_radius=6, border_bottom_left_radius=6)

    team_word = 'BLUE' if team == 'player' else 'RED'
    role_label = f"Slot {slot + 1} · Team {team_word} · {color_name}"
    role_surf = _font(12).render(role_label, True, _DIM)
    surf.blit(role_surf, (rect.x + 14, rect.y + 8))

    if isBot:
        bot_surf = _font(24, bold=True).render("BOT", True, (80, 78, 110))
        surf.blit(bot_surf, (rect.x + 14, rect.y + 24))
        # Bot is always ready — show green indicator
        pygame.draw.circle(surf, (120, 220, 120),
                           (rect.right - 24, rect.y + 22), 7)
        rd = _font(12, bold=True).render("READY", True, (120, 220, 120))
        surf.blit(rd, (rect.right - rd.get_width() - 10, rect.y + 36))
        # Hint that host can click to remove
        hint = _font(10).render("click to remove", True, (120, 115, 140))
        surf.blit(hint, (rect.x + 14, rect.y + rect.height - 14))
    elif active:
        name_str  = (name or '—')[:16]
        name_surf = _font(24, bold=True).render(
            name_str, True, _WHITE if name else _DIM)
        surf.blit(name_surf, (rect.x + 14, rect.y + 24))
        if ready:
            pygame.draw.circle(surf, (120, 220, 120),
                               (rect.right - 24, rect.y + 22), 7)
            rd = _font(12, bold=True).render("READY", True, (120, 220, 120))
            surf.blit(rd, (rect.right - rd.get_width() - 10, rect.y + 36))
        else:
            pygame.draw.circle(surf, (90, 80, 60),
                               (rect.right - 24, rect.y + 22), 7, 2)
            rd = _font(11).render("waiting…", True, _DIM)
            surf.blit(rd, (rect.right - rd.get_width() - 10, rect.y + 36))
    else:
        empty = _font(16).render("empty", True, _DIM)
        surf.blit(empty, (rect.centerx - empty.get_width() // 2,
                          rect.centery - empty.get_height() // 2))


# ════════════════════════════════════════════════════════════════════════════
# MultiplayerMenu — name, then Host/Join.
# ════════════════════════════════════════════════════════════════════════════

class MultiplayerMenu:
    """Returns (outcome, config, sessions) where `sessions` is:
        - None for single-player
        - a list of _Session (host side, may contain 1 or 3 sessions)
        - a single _Session in a 1-element list (client side)
    Outcome values: 'start' | 'back' | 'quit'.
    """

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.name = _loadName(default='')

    def run(self):
        while True:
            choice = self._pickRoleAndName()
            if choice in ('back', 'quit'):
                return choice, None, None
            if not self.name.strip():
                continue
            _saveName(self.name)

            if choice == 'host':
                result = _HostLobby(self.screen, self.clock, self.name).run()
            else:
                result = _JoinLobby(self.screen, self.clock, self.name).run()
            if result[0] in ('start', 'quit'):
                return result

    def _pickRoleAndName(self):
        cx = SCREEN_WIDTH // 2
        name_rect = pygame.Rect(cx - 200, 235, 400, 46)
        host_rect = pygame.Rect(cx - 170, 330, 340, 56)
        join_rect = pygame.Rect(cx - 170, 410, 340, 56)
        back_rect = pygame.Rect(cx - 80,  505, 160, 40)

        while True:
            mx, my = pygame.mouse.get_pos()
            click = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'back'
                    if event.key == pygame.K_BACKSPACE:
                        self.name = self.name[:-1]
                    elif event.unicode and event.unicode.isprintable() \
                            and len(self.name) < 16:
                        if event.unicode.isalnum() or event.unicode in " _-.":
                            self.name += event.unicode
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            name_ok = bool(self.name.strip())
            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(44, bold=True)
            _renderShadow(self.screen, "MULTIPLAYER", tf, _GOLD_LIGHT,
                          cx - tf.size("MULTIPLAYER")[0] // 2, 80, offset=3)
            _drawDivider(self.screen, 145)
            _drawCenteredText(self.screen, "Play 1v1, 2v2 or Coop (1-4 vs AI) over LAN",
                              _font(20), _PARCHMENT, 175)

            _drawCenteredText(self.screen, "Your name", _font(16), _DIM, 215)
            pygame.draw.rect(self.screen, (240, 228, 204), name_rect, border_radius=4)
            pygame.draw.rect(self.screen, _GOLD, name_rect, 1, border_radius=4)
            shown = self.name if self.name else "enter your name…"
            surf  = _font(26, bold=name_ok).render(
                shown, True, _WHITE if name_ok else _DIM)
            self.screen.blit(surf, (name_rect.x + 14,
                                    name_rect.centery - surf.get_height() // 2))
            if name_ok and (self.tick // 30) % 2 == 0:
                cx_blink = name_rect.x + 14 + surf.get_width() + 2
                pygame.draw.line(self.screen, _PARCHMENT,
                                 (cx_blink, name_rect.y + 10),
                                 (cx_blink, name_rect.bottom - 10), 2)

            host_hover = _button(self.screen, host_rect,
                                 "Host (start a game)", mx, my, enabled=name_ok)
            join_hover = _button(self.screen, join_rect,
                                 "Join (connect to a host)", mx, my,
                                 enabled=name_ok)
            back_hover = _button(self.screen, back_rect, "Back", mx, my)

            if not name_ok:
                _drawCenteredText(self.screen, "Please enter a name first",
                                  _font(14), (200, 120, 120), 480)

            if click:
                if host_hover and name_ok: return 'host'
                if join_hover and name_ok: return 'join'
                if back_hover: return 'back'

            pygame.display.flip()
            self.clock.tick(60)


# ════════════════════════════════════════════════════════════════════════════
# Host lobby — accepts up to 3 clients, picks mode + biome, broadcasts state.
# ════════════════════════════════════════════════════════════════════════════

class _HostLobby:
    def __init__(self, screen, clock, myName):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.myName = myName

        # Start with 1v1 capacity; resizing up to 2v2 will need to bind a new
        # server if we go over — simplest: always allocate for 2v2 capacity,
        # but only require the 1v1 count to start.
        try:
            # 8 slots total → 7 possible clients (host is slot 0). Full
            # capacity always open; game-start gates on mode head-count.
            self.server = HostServer(DEFAULT_PORT, name=myName, maxClients=7)
            self.server.setAllowedClients(7)
            self.bindError = None
        except OSError as e:
            self.server    = None
            self.bindError = str(e)

        self.localIp = getLocalIp()
        self.beacon  = HostBeacon(myName, DEFAULT_PORT)
        self.internet = InternetHost(myName, maxClients=7)

        # slot → (name, ready, colorIdx); slot 0 = me (host). Color is picked
        # with the 1v1 ordering here and will be re-defaulted on mode switch.
        self.slots = {0: {'name': myName, 'ready': False, 'alive': True,
                          'color': _pickDefaultColor(0, '1v1', set())}}
        # session cache keyed by slot
        self.sessions_by_slot = {}

        self.seed        = random.randint(0, 99999)
        self.biomeIdx    = 0
        self.gamemodeIdx = 0
        self.gamemode    = _MP_GAMEMODES[0][0]
        self.modeKey   = '1v1'
        self.status    = 'waiting'
        self.statusMsg = None
        # Slots that are filled by a bot instead of a human connection.
        self.bot_slots: set = set()
        # Custom map override (sandbox). When set, biome is ignored.
        self.customMap     = None
        self.customMapName = None

    @property
    def biomeKey(self):   return _BIOMES[self.biomeIdx][0]
    @property
    def biomeLabel(self): return _BIOMES[self.biomeIdx][1]
    @property
    def requiredPlayers(self):
        return slotCountForMode(self.modeKey)

    def _activeSlots(self):
        """Slots that will be used in the current match mode."""
        return list(range(self.requiredPlayers))

    def _displayedSlots(self):
        """Slots to render — always covers the mode's needs plus any extra
        already-occupied slots (so over-capacity players stay visible until
        the host either switches mode or removes them)."""
        n = self.requiredPlayers
        for s, info in self.slots.items():
            if info and info.get('alive') and s + 1 > n:
                n = s + 1
        return list(range(min(n, 8)))

    def _aliveCount(self):
        return sum(1 for s, info in self.slots.items()
                   if info and info.get('alive'))

    def _broadcastLobby(self):
        """Send the full lobby snapshot to all connected clients."""
        slot_info = []
        # Include every slot that's either part of the chosen mode or
        # currently occupied — the joiner UI uses this to render extras.
        for s in self._displayedSlots():
            info = self.slots.get(s, {})
            slot_info.append({
                'slot': s,
                'name': info.get('name', ''),
                'ready': info.get('ready', False),
                'active': info.get('alive', False),
                'team': teamOfSlot(s, self.modeKey),
                'color': info.get('color', DEFAULT_COLOR_IDX.get(s, 0)),
                'isBot': s in self.bot_slots,
            })
        msg = {
            'seed': self.seed,
            'biome': self.biomeKey,
            'biomeLabel': self.biomeLabel,
            'gamemode': self.gamemode,
            'mode': self.modeKey,
            'slots': slot_info,
            'customMap':     self.customMap,
            'customMapName': self.customMapName,
        }
        # Send personalised copy so each recipient knows their current slot
        # — needed after a team-shuffle reassigns them.
        for s, sess in list(self.sessions_by_slot.items()):
            if sess.alive:
                m = dict(msg)
                m['yourSlot'] = s
                sess.send(MSG_LOBBY, m)

    def _shuffleTeams(self):
        """Randomly permute non-host slot assignments. Each player keeps
        their name + colour; only their slot index (and thus team) changes.
        Host stays in slot 0 so the lobby owner is stable."""
        active = self._activeSlots()
        # Block: collect (info, sess|None, was_bot) for every non-host slot
        bundles = []
        for s in active:
            if s == 0:
                continue
            info  = self.slots.get(s)
            sess  = self.sessions_by_slot.get(s)
            isbot = s in self.bot_slots
            if info or sess:
                bundles.append((info, sess, isbot))
        if len(bundles) < 2:
            return
        random.shuffle(bundles)
        # Reassign to the open non-host slots in active order
        new_slots          = {0: self.slots.get(0)}
        new_sessions       = {}
        new_bots           = set()
        target_slots       = [s for s in active if s != 0]
        for new_s, (info, sess, isbot) in zip(target_slots, bundles):
            if info is not None:
                new_slots[new_s] = info
            if sess is not None:
                sess.slot = new_s
                new_sessions[new_s] = sess
            if isbot:
                new_bots.add(new_s)
        self.slots            = new_slots
        self.sessions_by_slot = new_sessions
        self.bot_slots        = new_bots
        self._broadcastLobby()

    def _dropSession(self, slot):
        self.slots.pop(slot, None)
        self.sessions_by_slot.pop(slot, None)
        self._broadcastLobby()

    def run(self):
        cx = SCREEN_WIDTH // 2

        # Slot cards laid out as two team columns: player team on the left,
        # enemy team on the right. Number of rows per column scales with the
        # selected mode (1v1: 1 row, 2v2: 2, 3v3: 3, 4v4: 4).
        slot_w, slot_h = 320, 70
        swatch_sz, swatch_gap = 22, 4
        row_h  = slot_h + 6 + swatch_sz     # card + small gap + swatches
        slot_gap_x, slot_gap_y = 20, 16
        slots_left = 60
        slots_top  = 172

        def _layoutSlots(req):
            half = max(1, req // 2)
            rects, swatches = {}, {}
            for s in range(req):
                if s < half:
                    col, row = 0, s
                else:
                    col, row = 1, s - half
                x = slots_left + col * (slot_w + slot_gap_x)
                y = slots_top  + row * (row_h + slot_gap_y)
                rects[s]    = pygame.Rect(x, y, slot_w, slot_h)
                swatches[s] = (x, y + slot_h + 6)
            return rects, swatches, half

        # Initial layout — recomputed each frame inside the draw loop so it
        # picks up newly-arrived joiners that push the display past
        # requiredPlayers.
        slot_rects, swatch_origin, half_n = _layoutSlots(
            max(self.requiredPlayers, len(self._displayedSlots())))

        # Mode toggle buttons sit below the tallest slot column. We anchor
        # them at the 4-row position so they don't jump around when the
        # lobby grows; mode_y is recalculated per frame anyway.
        mode_y = slots_top + half_n * (row_h + slot_gap_y) + 4
        mode_btn_w, mode_btn_gap = 100, 10
        mode1_rect = pygame.Rect(slots_left,                                            mode_y, mode_btn_w, 40)
        mode2_rect = pygame.Rect(slots_left + 1 * (mode_btn_w + mode_btn_gap),          mode_y, mode_btn_w, 40)
        modeC_rect = pygame.Rect(slots_left + 2 * (mode_btn_w + mode_btn_gap),          mode_y, mode_btn_w, 40)
        mode3_rect = pygame.Rect(slots_left + 3 * (mode_btn_w + mode_btn_gap),          mode_y, mode_btn_w, 40)
        mode4_rect = pygame.Rect(slots_left + 4 * (mode_btn_w + mode_btn_gap),          mode_y, mode_btn_w, 40)

        # Shuffle-teams button — randomizes non-host slot assignments so
        # players don't have to manually negotiate teams. Host-only.
        shuffle_rect = pygame.Rect(slots_left + 5 * (mode_btn_w + mode_btn_gap),
                                   mode_y, 130, 40)

        # Biome picker (right side)
        thumb_rect = pygame.Rect(SCREEN_WIDTH - 60 - 340, 180, 340, 200)
        prev_rect  = pygame.Rect(thumb_rect.x - 10, thumb_rect.bottom + 12, 60, 38)
        next_rect  = pygame.Rect(thumb_rect.right - 50, thumb_rect.bottom + 12, 60, 38)

        ready_rect = pygame.Rect(cx - 170, SCREEN_HEIGHT - 140, 340, 50)
        back_rect  = pygame.Rect(cx - 80,  SCREEN_HEIGHT - 80,  160, 36)

        # Custom-map selector (below biome panel)
        custom_rect = pygame.Rect(thumb_rect.x, thumb_rect.bottom + 82,
                                  thumb_rect.width, 36)

        # Gamemode picker (below custom-map selector)
        gm_y       = custom_rect.bottom + 10
        gm_rect    = pygame.Rect(thumb_rect.x + 40, gm_y, thumb_rect.width - 80, 36)
        gm_prev_rect = pygame.Rect(thumb_rect.x,           gm_y, 36, 36)
        gm_next_rect = pygame.Rect(thumb_rect.right - 36,  gm_y, 36, 36)

        try:
            while True:
                mx, my = pygame.mouse.get_pos()
                click = False
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return 'quit', None, None
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        return 'back', None, None
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        click = True

                # Accept new connections (LAN + internet)
                new_sessions = []
                if self.server:
                    new_sessions += self.server.newSessions()
                if self.internet:
                    new_sessions += self.internet.newSessions()
                for sess in new_sessions:
                    slot = sess.slot
                    # If a bot was holding this slot, evict it first
                    if slot in self.bot_slots:
                        self.bot_slots.discard(slot)
                        self.slots.pop(slot, None)
                    taken = {info.get('color') for s, info in self.slots.items()
                             if s != slot and info.get('alive', False)}
                    self.slots[slot] = {
                        'name': '', 'ready': False, 'alive': True,
                        'color': _pickDefaultColor(slot, self.modeKey, taken),
                    }
                    self.sessions_by_slot[slot] = sess

                # Drain each client's inbox
                dead = []
                for slot, sess in list(self.sessions_by_slot.items()):
                    if not sess.alive:
                        dead.append(slot)
                        continue
                    for mt, data in sess.poll():
                        if mt == '__error__':
                            dead.append(slot); break
                        elif mt == MSG_HELLO:
                            self.slots[slot]['name'] = data.get('name') \
                                or f'Player {slot + 1}'
                            if data.get('version') != PROTOCOL_VERSION:
                                self.statusMsg = (f"Protocol-mismatch slot {slot + 1}")
                            self._broadcastLobby()
                        elif mt == MSG_READY:
                            self.slots[slot]['ready'] = bool(data.get('ready', False))
                            self._broadcastLobby()
                        elif mt == MSG_PICK:
                            idx = int(data.get('idx', 0))
                            idx = max(0, min(len(PLAYER_COLORS) - 1, idx))
                            # Reject if another active slot already has that color
                            active = self._activeSlots()
                            if any(other != slot
                                   and other in active
                                   and self.slots.get(other, {}).get('color') == idx
                                   for other in active):
                                # Silently ignore — client's UI should have
                                # prevented this, so this is just a safety net.
                                pass
                            else:
                                self.slots[slot]['color'] = idx
                                self._broadcastLobby()
                for slot in dead:
                    self._dropSession(slot)

                # Count active+ready in the slots that matter for this mode
                active_slots = self._activeSlots()
                ready_count  = sum(1 for s in active_slots
                                   if self.slots.get(s, {}).get('ready', False))
                filled = sum(1 for s in active_slots
                             if self.slots.get(s, {}).get('alive', False))
                # Total connected (incl. extras outside the current mode)
                total_alive = self._aliveCount()

                # COOP: start as soon as all connected slots (≥1) are ready.
                # 2v2/3v3: full lobby OR at least 1 active per team (bigger army).
                # Other modes: require exactly the right head-count.
                is_coop = (self.modeKey in ('COOP', 'LAST_STAND'))
                if is_coop:
                    can_start = (total_alive >= 1
                                 and ready_count == total_alive
                                 and filled == total_alive)
                elif self.modeKey in ('2v2', '3v3', '4v4'):
                    # Full lobby: everyone must be ready
                    full_lobby = (filled == self.requiredPlayers
                                  and ready_count == self.requiredPlayers
                                  and total_alive == self.requiredPlayers)
                    # Partial: at least 1 active per team, all present are ready
                    half = self.requiredPlayers // 2
                    p_active = sum(1 for s in range(half)
                                   if self.slots.get(s, {}).get('alive', False))
                    e_active = sum(1 for s in range(half, self.requiredPlayers)
                                   if self.slots.get(s, {}).get('alive', False))
                    partial_ok = (p_active >= 1 and e_active >= 1
                                  and total_alive >= 2
                                  and ready_count == total_alive
                                  and filled == total_alive)
                    can_start = full_lobby or partial_ok
                else:
                    can_start = (filled == self.requiredPlayers
                                 and ready_count == self.requiredPlayers
                                 and total_alive == self.requiredPlayers)

                if can_start:
                    # Broadcast START with mySlot specialised per recipient
                    for slot, sess in self.sessions_by_slot.items():
                        if slot in active_slots and sess.alive:
                            sess.send(MSG_START, {})
                    # COOP: only include actually connected slots in the config.
                    n = total_alive if is_coop else self.requiredPlayers
                    slotColors = [self.slots.get(s, {}).get('color',
                                   DEFAULT_COLOR_IDX.get(s, 0)) for s in range(n)]
                    diff = 'MOEILIJK' if is_coop else 'NORMAAL'
                    config = {'biome': self.biomeKey, 'difficulty': diff,
                              'gamemode': self.gamemode, 'seed': self.seed,
                              'role': 'host', 'mode': self.modeKey,
                              'mySlot': 0,
                              'slotNames':  [self.slots.get(s, {}).get('name', '')
                                             for s in range(n)],
                              'slotColors': slotColors,
                              'customMap':  self.customMap,
                              'botSlots':   list(self.bot_slots),
                              'coopPlayers': n if is_coop else None}
                    # Return the sessions list for active slots (excluding slot 0 = host itself)
                    active_sessions = [self.sessions_by_slot[s]
                                       for s in active_slots
                                       if s != 0 and s in self.sessions_by_slot]
                    return 'start', config, active_sessions

                # ── draw ────────────────────────────────────────────────────
                self.tick += 1
                _updateParticles(self.particles, self.prng)
                _drawBackground(self.screen, self.tick)
                _drawParticles(self.screen, self.particles)

                tf = _font(34, bold=True)
                title = "HOST LOBBY"
                _renderShadow(self.screen, title, tf, _GOLD_LIGHT,
                              cx - tf.size(title)[0] // 2, 50, offset=3)
                _drawDivider(self.screen, 102)

                if self.bindError:
                    _drawCenteredText(self.screen,
                        f"Cannot listen on port {DEFAULT_PORT}: {self.bindError}",
                        _font(16), (255, 120, 120), 132)
                else:
                    addr_str = f"Your address:  {self.localIp} : {DEFAULT_PORT}"
                    _drawCenteredText(self.screen, addr_str,
                                      _font(19, bold=True), _GOLD_LIGHT, 132)
                    _drawCenteredText(self.screen,
                        "(share this IP with your teammates)",
                        _font(13), _DIM, 156)

                # Slots
                # Build the "already chosen" set per slot (everybody else's picks)
                picks = {s: self.slots.get(s, {}).get('color',
                            DEFAULT_COLOR_IDX.get(s, 0))
                         for s in active_slots
                         if self.slots.get(s, {}).get('alive', s == 0)}

                # Re-layout in case a joiner pushed display past requiredPlayers
                displayed = self._displayedSlots()
                slot_rects, swatch_origin, half_n = _layoutSlots(
                    max(self.requiredPlayers, len(displayed)))
                mode_y = slots_top + half_n * (row_h + slot_gap_y) + 4
                # Reposition mode buttons (they live on a row below the grid)
                for r, x_idx in [(mode1_rect, 0), (mode2_rect, 1),
                                 (modeC_rect, 2), (mode3_rect, 3),
                                 (mode4_rect, 4)]:
                    r.y = mode_y
                shuffle_rect.y = mode_y

                # Mode-toggle is disabled once host is ready — needed inside
                # the slot loop below (for "+ BOT" gating) so hoist it.
                m_enabled = not self.slots[0]['ready']

                swatch_hover = {}     # slot → hovered color idx
                bot_btn_hover = set()  # slots whose "BOT" button is hovered
                for s in displayed:
                    is_active_mode = s in active_slots
                    info = self.slots.get(s, {}) if is_active_mode else {}
                    is_bot = s in self.bot_slots
                    slot_alive = info.get('alive', s == 0)
                    _drawPlayerSlot(self.screen, slot_rects[s],
                                    info.get('name', ''), s,
                                    info.get('ready', False),
                                    mine=(s == 0),
                                    team=teamOfSlot(s, self.modeKey),
                                    colorIdx=info.get('color',
                                                      DEFAULT_COLOR_IDX.get(s, -1)),
                                    active=is_active_mode and slot_alive,
                                    isBot=is_bot)
                    if is_active_mode:
                        sx, sy = swatch_origin[s]
                        sel_idx = info.get('color', DEFAULT_COLOR_IDX.get(s, 0))
                        mine_here = (s == 0) and not self.slots[0]['ready']
                        taken = {c for o, c in picks.items() if o != s}
                        swatch_hover[s] = _drawColorSwatches(
                            self.screen, sx, sy, swatch_sz, swatch_gap,
                            sel_idx, mine_here, taken, mx, my)

                    # "+ BOT" on every empty non-host slot in any 2+ team mode.
                    can_add_bot = (self.modeKey in ('2v2', '3v3', '4v4')
                                   and s != 0 and is_active_mode
                                   and not slot_alive and not is_bot
                                   and m_enabled)
                    if can_add_bot:
                        r = slot_rects[s]
                        btn_r = pygame.Rect(r.centerx - 46, r.centery - 12, 92, 24)
                        hov = _button(self.screen, btn_r, "+ BOT", mx, my)
                        if hov:
                            bot_btn_hover.add(s)

                # Mode toggle — uses m_enabled hoisted above the slot loop
                m1_hover  = _button(self.screen, mode1_rect, "1v1",  mx, my,
                                    enabled=m_enabled)
                m2_hover  = _button(self.screen, mode2_rect, "2v2",  mx, my,
                                    enabled=m_enabled)
                mC_hover  = _button(self.screen, modeC_rect, "Coop", mx, my,
                                    enabled=m_enabled)
                m3_hover  = _button(self.screen, mode3_rect, "3v3",  mx, my,
                                    enabled=m_enabled)
                m4_hover  = _button(self.screen, mode4_rect, "4v4",  mx, my,
                                    enabled=m_enabled)
                # Shuffle teams (only meaningful when ≥2 non-host slots)
                shuffle_enabled = m_enabled and self.requiredPlayers >= 4
                shuffle_hover = _button(self.screen, shuffle_rect,
                                        "🎲 Shuffle", mx, my,
                                        enabled=shuffle_enabled)
                # Active mode highlight
                active_rect = {'1v1':  mode1_rect, '2v2':  mode2_rect,
                               'COOP': modeC_rect, '3v3':  mode3_rect,
                               '4v4':  mode4_rect}.get(self.modeKey,
                                                       mode1_rect)
                pygame.draw.rect(self.screen, _GOLD_LIGHT, active_rect, 3,
                                 border_radius=4)

                # Biome picker panel
                label_surf = _font(15).render("Map Choice", True, _DIM)
                self.screen.blit(label_surf, (thumb_rect.x, thumb_rect.y - 20))
                _drawBiomeThumbnail(self.screen, thumb_rect, self.biomeKey)
                pygame.draw.rect(self.screen, _GOLD, thumb_rect, 2, border_radius=4)
                bname = _font(20, bold=True).render(self.biomeLabel, True, _GOLD_LIGHT)
                self.screen.blit(bname, (thumb_rect.centerx - bname.get_width() // 2,
                                         thumb_rect.bottom - 32))
                desc = _BIOME_DESC.get(self.biomeKey, '')
                ds   = _font(13).render(desc, True, _PARCHMENT)
                self.screen.blit(ds, (thumb_rect.centerx - ds.get_width() // 2,
                                      thumb_rect.bottom + 58))
                _button(self.screen, prev_rect, "◀", mx, my,
                        enabled=m_enabled and not self.customMap)
                _button(self.screen, next_rect, "▶", mx, my,
                        enabled=m_enabled and not self.customMap)
                prev_hover = (prev_rect.collidepoint(mx, my) and m_enabled
                              and not self.customMap)
                next_hover = (next_rect.collidepoint(mx, my) and m_enabled
                              and not self.customMap)

                # Custom map selector — cycles: None → sandbox_map_A → B … → None
                cust_label = ("Custom map: " + self.customMapName
                              if self.customMapName
                              else "Choose custom sandbox map")
                cust_hover = _button(self.screen, custom_rect, cust_label,
                                     mx, my, enabled=m_enabled)
                if self.customMap:
                    # Note on biome panel when overridden
                    note = _font(12).render("(biome choice ignored)", True, _DIM)
                    self.screen.blit(note, (thumb_rect.centerx - note.get_width() // 2,
                                            thumb_rect.bottom + 58))

                # Gamemode picker
                gm_label_txt = _font(13).render("Game Mode", True, _DIM)
                self.screen.blit(gm_label_txt,
                                 (gm_rect.centerx - gm_label_txt.get_width() // 2,
                                  gm_y - 16))
                gm_prev_hover = _button(self.screen, gm_prev_rect, "◀", mx, my,
                                        enabled=m_enabled)
                gm_next_hover = _button(self.screen, gm_next_rect, "▶", mx, my,
                                        enabled=m_enabled)
                gm_name = _MP_GAMEMODES[self.gamemodeIdx][1]
                pygame.draw.rect(self.screen, (40, 35, 25), gm_rect, border_radius=4)
                pygame.draw.rect(self.screen, _GOLD, gm_rect, 1, border_radius=4)
                gm_surf = _font(16, bold=True).render(gm_name, True, _GOLD_LIGHT)
                self.screen.blit(gm_surf,
                                 (gm_rect.centerx - gm_surf.get_width() // 2,
                                  gm_rect.centery - gm_surf.get_height() // 2))

                # Ready button
                if self.modeKey == 'COOP':
                    rdy_enabled = (filled >= 1 and not self.slots[0]['ready'])
                else:
                    rdy_enabled = (filled == self.requiredPlayers
                                   and total_alive == self.requiredPlayers
                                   and not self.slots[0]['ready'])
                rdy_label = ("Ready" if not self.slots[0]['ready']
                             else "Ready ✓")
                rdy_hover = _button(self.screen, ready_rect, rdy_label,
                                    mx, my, enabled=rdy_enabled)
                back_hover = _button(self.screen, back_rect, "Back", mx, my)

                status_y = SCREEN_HEIGHT - 175
                if self.statusMsg:
                    _drawCenteredText(self.screen, f"ERROR: {self.statusMsg}",
                                      _font(15), (255, 120, 120), status_y)
                elif self.modeKey == 'COOP':
                    _drawCenteredText(self.screen,
                        f"COOP: {total_alive}/4 players connected  —  "
                        f"host can start with 1 to 4 players",
                        _font(16), _PARCHMENT, status_y)
                elif self.modeKey == 'LAST_STAND':
                    _drawCenteredText(self.screen,
                        f"Waves Coop: {total_alive} player(s) connected  —  "
                        f"host can start with 1 to 4 players",
                        _font(16), _PARCHMENT, status_y)
                elif total_alive > self.requiredPlayers:
                    extra = total_alive - self.requiredPlayers
                    _drawCenteredText(self.screen,
                        f"{extra} player(s) too many for {self.modeKey} — "
                        f"choose a larger mode or have someone leave",
                        _font(16), (255, 180, 100), status_y)
                elif filled < self.requiredPlayers:
                    half = self.requiredPlayers // 2
                    p_ok = any(self.slots.get(s, {}).get('alive') for s in range(half))
                    e_ok = any(self.slots.get(s, {}).get('alive') for s in range(half, self.requiredPlayers))
                    if self.modeKey in ('2v2', '3v3', '4v4') and p_ok and e_ok:
                        _drawCenteredText(self.screen,
                            f"Partial lobby — empty slots give the solo player a bigger army. Ready to start!",
                            _font(16), (180, 220, 140), status_y)
                    else:
                        need = self.requiredPlayers - filled
                        _drawCenteredText(self.screen,
                            f"Waiting for {need} player(s)…",
                            _font(16), _PARCHMENT, status_y)

                if click:
                    # Swatch click (only slot 0 allowed here, but loop is cheap)
                    clicked_swatch = False
                    for s, idx in swatch_hover.items():
                        if idx >= 0 and s == 0 and not self.slots[0]['ready']:
                            self.slots[0]['color'] = idx
                            self._broadcastLobby()
                            clicked_swatch = True
                            break
                    if clicked_swatch:
                        pygame.display.flip(); self.clock.tick(60); continue
                    def _switchMode(new_mode):
                        # Drop bots that fall outside the new mode's slot
                        # range; humans stay parked even if their slot is now
                        # over-capacity (host will see a "too many players"
                        # warning instead of silently kicking them).
                        new_active = set(range(slotCountForMode(new_mode)))
                        for bs in list(self.bot_slots):
                            if bs not in new_active:
                                self.bot_slots.discard(bs)
                                self.slots.pop(bs, None)
                        self.modeKey = new_mode
                        # Re-default every active slot's colour for the new
                        # mode so team/contrast defaults apply. Preserves
                        # uniqueness via the running 'taken' set.
                        used = set()
                        for s in self._displayedSlots():
                            info = self.slots.get(s)
                            if not info: continue
                            info['color'] = _pickDefaultColor(s, new_mode, used)
                            used.add(info['color'])
                        self._broadcastLobby()

                    if m1_hover and m_enabled and self.modeKey != '1v1':
                        _switchMode('1v1')
                    elif m2_hover and m_enabled and self.modeKey != '2v2':
                        _switchMode('2v2')
                    elif mC_hover and m_enabled and self.modeKey != 'COOP':
                        _switchMode('COOP')
                    elif m3_hover and m_enabled and self.modeKey != '3v3':
                        _switchMode('3v3')
                    elif m4_hover and m_enabled and self.modeKey != '4v4':
                        _switchMode('4v4')
                    elif shuffle_hover and shuffle_enabled:
                        self._shuffleTeams()
                    elif prev_hover:
                        self.biomeIdx = (self.biomeIdx - 1) % len(_BIOMES)
                        self._broadcastLobby()
                    elif next_hover:
                        self.biomeIdx = (self.biomeIdx + 1) % len(_BIOMES)
                        self._broadcastLobby()
                    elif gm_prev_hover and m_enabled:
                        self.gamemodeIdx = (self.gamemodeIdx - 1) % len(_MP_GAMEMODES)
                        self.gamemode = _MP_GAMEMODES[self.gamemodeIdx][0]
                        self._broadcastLobby()
                    elif gm_next_hover and m_enabled:
                        self.gamemodeIdx = (self.gamemodeIdx + 1) % len(_MP_GAMEMODES)
                        self.gamemode = _MP_GAMEMODES[self.gamemodeIdx][0]
                        self._broadcastLobby()
                    elif cust_hover and m_enabled:
                        maps = _listMaps()
                        if not maps:
                            self.statusMsg = "No sandbox maps found (save one first)."
                        else:
                            # Cycle through ['none', map1, map2, ...]
                            choices = [None] + maps
                            cur = (self.customMapName + '.json'
                                   if self.customMapName else None)
                            try:
                                idx = choices.index(cur)
                            except ValueError:
                                idx = 0
                            nxt = choices[(idx + 1) % len(choices)]
                            if nxt is None:
                                self.customMap = None
                                self.customMapName = None
                            else:
                                try:
                                    data = _loadMap(nxt)
                                except Exception as e:
                                    self.statusMsg = f"Load error: {e}"
                                else:
                                    self.customMap = data
                                    self.customMapName = nxt[:-5] if nxt.endswith('.json') else nxt
                            self._broadcastLobby()
                    elif bot_btn_hover and m_enabled:
                        # Add bot to any hovered empty slot
                        for s in bot_btn_hover:
                            taken = {info.get('color') for sl, info
                                     in self.slots.items()
                                     if sl != s and info.get('alive', False)}
                            self.bot_slots.add(s)
                            self.slots[s] = {
                                'name': 'BOT', 'ready': True, 'alive': True,
                                'color': _pickDefaultColor(s, self.modeKey, taken),
                                'isBot': True,
                            }
                            self._broadcastLobby()
                    elif m_enabled and not self.slots[0]['ready']:
                        # Click on a bot slot card removes the bot
                        for s in active_slots:
                            if s != 0 and s in self.bot_slots:
                                if slot_rects[s].collidepoint(mx, my):
                                    self.bot_slots.discard(s)
                                    self.slots.pop(s, None)
                                    self._broadcastLobby()
                                    break
                    if rdy_hover and rdy_enabled:
                        self.slots[0]['ready'] = True
                        self._broadcastLobby()
                    elif back_hover:
                        return 'back', None, None

                pygame.display.flip()
                self.clock.tick(60)
        finally:
            self.beacon.stop()
            if self.server:
                self.server.close()
            if self.internet:
                self.internet.close()


# ════════════════════════════════════════════════════════════════════════════
# Join lobby — enter IP, connect, wait for other players + host's choices.
# ════════════════════════════════════════════════════════════════════════════

class _JoinLobby:
    def __init__(self, screen, clock, myName):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.myName = myName

        self.ipText      = ""
        self.connector   = None
        self.session     = None
        self.selfReady   = False
        self.mySlot      = None
        self.peerVersion = None
        self.lobbyData   = None
        self.status      = 'scanning'   # start with LAN scan
        self.statusMsg   = None

        # Discovery state
        self._scanResults  = []
        self._scanThread   = None
        self._scanDone     = False
        self._startScan()

    def _startScan(self):
        import threading
        self._scanDone    = False
        self._scanResults = []
        def _worker():
            lan      = discoveryScan(timeout=2.0)
            internet = fetchLobbies(timeout=3.0)
            self._scanResults = lan + internet
            self._scanDone    = True
        self._scanThread = threading.Thread(target=_worker, daemon=True)
        self._scanThread.start()

    def _parseHostPort(self, txt: str):
        txt = txt.strip()
        if ':' in txt:
            host, _, port = txt.rpartition(':')
            try:
                return host.strip(), int(port)
            except ValueError:
                return None, None
        return txt, DEFAULT_PORT

    def _beginConnectTo(self, host, port, relay_id=None):
        if relay_id:
            self.connector = InternetClient(relay_id, name=self.myName)
        else:
            self.connector = ClientConnector(host, port, name=self.myName)
        self.status = 'connecting'

    def _beginConnect(self):
        host, port = self._parseHostPort(self.ipText)
        if not host or port is None:
            self.status    = 'error'
            self.statusMsg = "Invalid IP format (e.g. 192.168.1.42)"
            return
        self._beginConnectTo(host, port)

    def run(self):
        cx = SCREEN_WIDTH // 2
        ip_rect      = pygame.Rect(cx - 200, 220, 400, 44)
        connect_rect = pygame.Rect(cx - 110, 290, 220, 50)

        slot_w, slot_h = 320, 70
        swatch_sz, swatch_gap = 22, 4
        row_h  = slot_h + 6 + swatch_sz
        slot_gap_x, slot_gap_y = 20, 16
        slots_left = 60
        slots_top  = 172

        def _layoutJoinSlots(req):
            half = max(1, req // 2)
            rects, swatches = {}, {}
            for s in range(req):
                if s < half:
                    col, row = 0, s
                else:
                    col, row = 1, s - half
                x = slots_left + col * (slot_w + slot_gap_x)
                y = slots_top  + row * (row_h + slot_gap_y)
                rects[s]    = pygame.Rect(x, y, slot_w, slot_h)
                swatches[s] = (x, y + slot_h + 6)
            return rects, swatches

        thumb_rect = pygame.Rect(SCREEN_WIDTH - 60 - 340, 180, 340, 200)

        ready_rect = pygame.Rect(cx - 170, SCREEN_HEIGHT - 140, 340, 50)
        back_rect  = pygame.Rect(cx - 80,  SCREEN_HEIGHT - 80,  160, 36)

        try:
            while True:
                mx, my = pygame.mouse.get_pos()
                click = False
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return 'quit', None, None
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if self.status == 'entering':
                                self.status = 'discovered'
                            else:
                                return 'back', None, None
                        if self.status == 'entering':
                            if event.key == pygame.K_BACKSPACE:
                                self.ipText = self.ipText[:-1]
                            elif event.key == pygame.K_RETURN:
                                self._beginConnect()
                            elif event.unicode and event.unicode in '0123456789.:':
                                if len(self.ipText) < 32:
                                    self.ipText += event.unicode
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        click = True

                # Scan finished → switch to discovered list
                if self.status == 'scanning' and self._scanDone:
                    self.status = 'discovered'

                if self.connector and self.status == 'connecting':
                    if self.connector.status == 'connected':
                        self.session = self.connector.session
                        self.status  = 'connected'
                    elif self.connector.status == 'failed':
                        self.status    = 'error'
                        self.statusMsg = self.connector.error or 'connect failed'

                if self.session and self.session.alive:
                    for mt, data in self.session.poll():
                        if mt == '__error__':
                            self.status    = 'error'
                            self.statusMsg = data.get('reason', 'unknown error')
                        elif mt == MSG_HELLO:
                            self.peerVersion = data.get('version')
                            self.mySlot      = data.get('slot')
                            if self.peerVersion != PROTOCOL_VERSION:
                                self.status = 'error'
                                self.statusMsg = "Protocol-mismatch"
                        elif mt == MSG_LOBBY:
                            self.lobbyData = data
                            # Host can shuffle teams which moves us to a new
                            # slot — keep our local mySlot in sync.
                            ys = data.get('yourSlot')
                            if isinstance(ys, int):
                                self.mySlot = ys
                        elif mt == MSG_START:
                            if self.lobbyData:
                                lobby_slots = self.lobbyData.get('slots', [])
                                mode = self.lobbyData.get('mode', '1v1')
                                # 8 slots covers up to 4v4; Game pads further if needed.
                                slot_colors = [0, 1] * 4
                                for s in lobby_slots:
                                    idx = s.get('slot')
                                    if isinstance(idx, int) and 0 <= idx < 8:
                                        slot_colors[idx] = s.get('color', slot_colors[idx])
                                bot_slots = [s.get('slot') for s in lobby_slots
                                             if s.get('isBot', False)]
                                # COOP: count only active human slots so Game
                                # assigns controllers correctly.
                                coop_players = None
                                if mode == 'COOP':
                                    coop_players = sum(
                                        1 for s in lobby_slots
                                        if s.get('active', False) and not s.get('isBot', False))
                                    coop_players = max(1, coop_players)
                                diff = 'MOEILIJK' if mode == 'COOP' else 'NORMAAL'
                                cfg = {
                                    'biome':       self.lobbyData.get('biome', 'RANDOM'),
                                    'difficulty':  diff,
                                    'gamemode':    self.lobbyData.get('gamemode', 'STANDAARD'),
                                    'seed':        self.lobbyData.get('seed', 0),
                                    'role':        'client',
                                    'mode':        mode,
                                    'mySlot':      self.mySlot,
                                    'slotNames':   [s.get('name', '') for s in lobby_slots],
                                    'slotColors':  slot_colors,
                                    'customMap':   self.lobbyData.get('customMap'),
                                    'botSlots':    bot_slots,
                                    'coopPlayers': coop_players,
                                }
                                return 'start', cfg, [self.session]

                # ── draw ────────────────────────────────────────────────────
                self.tick += 1
                _updateParticles(self.particles, self.prng)
                _drawBackground(self.screen, self.tick)
                _drawParticles(self.screen, self.particles)

                tf = _font(34, bold=True)
                title = "JOIN LOBBY"
                _renderShadow(self.screen, title, tf, _GOLD_LIGHT,
                              cx - tf.size(title)[0] // 2, 50, offset=3)
                _drawDivider(self.screen, 102)

                if self.status == 'scanning':
                    dots = '.' * ((self.tick // 20) % 4)
                    _drawCenteredText(self.screen,
                        f"Scanning for hosts on the network{dots}",
                        _font(22), _PARCHMENT, SCREEN_HEIGHT // 2 - 30)
                    back_hover = _button(self.screen, back_rect, "Back", mx, my)
                    if click and back_hover:
                        return 'back', None, None

                elif self.status == 'discovered':
                    results = self._scanResults
                    btn_w, btn_h, btn_gap = 380, 52, 12
                    list_top = 160
                    host_rects = []
                    for i, h in enumerate(results):
                        r = pygame.Rect(cx - btn_w // 2,
                                        list_top + i * (btn_h + btn_gap),
                                        btn_w, btn_h)
                        host_rects.append(r)
                        hover = r.collidepoint(mx, my)
                        bg = (80, 100, 60) if hover else (40, 55, 30)
                        pygame.draw.rect(self.screen, bg, r, border_radius=6)
                        pygame.draw.rect(self.screen, _GOLD, r, 1, border_radius=6)
                        via_relay = h.get('via_relay', False)
                        loc_tag   = "Internet" if via_relay else h.get('ip', '')
                        label     = f"{h['name']}  —  {h.get('mode','1v1')}  —  {loc_tag}"
                        ls = _font(22, bold=hover).render(label, True,
                                                           _WHITE if hover else _PARCHMENT)
                        self.screen.blit(ls, (r.centerx - ls.get_width() // 2,
                                              r.centery - ls.get_height() // 2))
                        if via_relay:
                            badge = _font(13).render("Internet", True, (100, 200, 255))
                            self.screen.blit(badge, (r.right - badge.get_width() - 8,
                                                     r.top + 6))

                    if not results:
                        _drawCenteredText(self.screen,
                            "No hosts found on this network.",
                            _font(20), _DIM, list_top + 20)

                    rescan_rect = pygame.Rect(cx - 200, SCREEN_HEIGHT - 130, 180, 40)
                    manual_rect = pygame.Rect(cx + 20,  SCREEN_HEIGHT - 130, 180, 40)
                    rescan_hover = _button(self.screen, rescan_rect,
                                           "Scan again", mx, my)
                    manual_hover = _button(self.screen, manual_rect,
                                           "Manual IP", mx, my)
                    back_hover   = _button(self.screen, back_rect, "Back", mx, my)
                    if click:
                        for i, r in enumerate(host_rects):
                            if r.collidepoint(mx, my):
                                h = results[i]
                                self._beginConnectTo(
                                    h.get('ip', ''), h.get('port', DEFAULT_PORT),
                                    relay_id=h.get('id') if h.get('via_relay') else None,
                                )
                                break
                        else:
                            if rescan_hover:
                                self._startScan()
                                self.status = 'scanning'
                            elif manual_hover:
                                self.status = 'entering'
                            elif back_hover:
                                return 'back', None, None

                elif self.status == 'entering':
                    _drawCenteredText(self.screen,
                        "IP address of the host (port optional):",
                        _font(18), _PARCHMENT, 180)
                    pygame.draw.rect(self.screen, (240, 228, 204), ip_rect,
                                     border_radius=4)
                    pygame.draw.rect(self.screen, _GOLD, ip_rect, 1,
                                     border_radius=4)
                    display = self.ipText or "192.168.x.x"
                    col     = _WHITE if self.ipText else _DIM
                    surf    = _font(24).render(display, True, col)
                    self.screen.blit(surf,
                        (ip_rect.x + 12,
                         ip_rect.centery - surf.get_height() // 2))
                    can_connect = bool(self.ipText.strip())
                    conn_hover  = _button(self.screen, connect_rect, "Connect",
                                          mx, my, enabled=can_connect)
                    back_hover  = _button(self.screen, back_rect, "Back", mx, my)
                    if click and conn_hover and can_connect:
                        self._beginConnect()
                    elif click and back_hover:
                        self.status = 'discovered'

                else:
                    mode = (self.lobbyData or {}).get('mode', '1v1')
                    n_required = slotCountForMode(mode)
                    slot_list = (self.lobbyData or {}).get('slots', [])
                    by_slot = {s['slot']: s for s in slot_list}
                    # Display either the mode-required slot count OR the
                    # highest slot the host actually sent (covers the
                    # over-capacity case where extras are still parked).
                    n_slots = max(n_required,
                                  (max(by_slot.keys()) + 1) if by_slot else 0)
                    n_slots = min(n_slots, 8)
                    active_slots = list(range(n_slots))
                    slot_rects, swatch_origin = _layoutJoinSlots(n_slots)

                    # Build picks map for "taken" logic
                    picks = {}
                    for s in active_slots:
                        info = by_slot.get(s, {})
                        if info.get('active', False):
                            picks[s] = info.get('color', DEFAULT_COLOR_IDX.get(s, 0))

                    swatch_hover = {}
                    for s in range(n_slots):
                        is_active = s in active_slots
                        info = by_slot.get(s, {}) if is_active else {}
                        _drawPlayerSlot(self.screen, slot_rects[s],
                                        info.get('name', ''), s,
                                        info.get('ready', False),
                                        mine=(s == self.mySlot),
                                        team=teamOfSlot(s, mode),
                                        colorIdx=info.get('color',
                                                          DEFAULT_COLOR_IDX.get(s, -1)),
                                        active=is_active and info.get('active', False),
                                        isBot=info.get('isBot', False))
                        if is_active:
                            sx, sy = swatch_origin[s]
                            sel_idx = info.get('color',
                                               DEFAULT_COLOR_IDX.get(s, 0))
                            mine_here = (s == self.mySlot) and not self.selfReady
                            taken = {c for o, c in picks.items() if o != s}
                            swatch_hover[s] = _drawColorSwatches(
                                self.screen, sx, sy, swatch_sz, swatch_gap,
                                sel_idx, mine_here, taken, mx, my)

                    _drawCenteredText(self.screen, f"Mode: {mode}",
                                      _font(18, bold=True), _GOLD_LIGHT,
                                      slots_top + 2 * (slot_h + slot_gap_y) + 14)

                    # Biome readout
                    label_surf = _font(15).render("Map (host chooses)", True, _DIM)
                    self.screen.blit(label_surf, (thumb_rect.x, thumb_rect.y - 20))
                    biome_key = (self.lobbyData or {}).get('biome', 'RANDOM')
                    biome_lab = (self.lobbyData or {}).get('biomeLabel',
                                                           biome_key.title())
                    _drawBiomeThumbnail(self.screen, thumb_rect, biome_key)
                    pygame.draw.rect(self.screen, _GOLD, thumb_rect, 2,
                                     border_radius=4)
                    bname = _font(20, bold=True).render(biome_lab, True, _GOLD_LIGHT)
                    self.screen.blit(bname,
                        (thumb_rect.centerx - bname.get_width() // 2,
                         thumb_rect.bottom - 32))
                    desc = _BIOME_DESC.get(biome_key, '')
                    ds   = _font(13).render(desc, True, _PARCHMENT)
                    self.screen.blit(ds,
                        (thumb_rect.centerx - ds.get_width() // 2,
                         thumb_rect.bottom + 58))

                    # Gamemode readout
                    gm_key = (self.lobbyData or {}).get('gamemode', 'STANDAARD')
                    gm_lab = next((lab for k, lab in _MP_GAMEMODES if k == gm_key),
                                  gm_key)
                    gm_lbl_surf = _font(13).render("Game Mode", True, _DIM)
                    self.screen.blit(gm_lbl_surf,
                                     (thumb_rect.centerx - gm_lbl_surf.get_width() // 2,
                                      thumb_rect.bottom + 80))
                    gm_val_surf = _font(16, bold=True).render(gm_lab, True, _GOLD_LIGHT)
                    self.screen.blit(gm_val_surf,
                                     (thumb_rect.centerx - gm_val_surf.get_width() // 2,
                                      thumb_rect.bottom + 96))

                    if self.status == 'error':
                        _drawCenteredText(self.screen, f"ERROR: {self.statusMsg}",
                                          _font(15), (255, 120, 120),
                                          SCREEN_HEIGHT - 175)

                    rdy_enabled = (self.status == 'connected' and not self.selfReady)
                    rdy_label   = "Ready" if not self.selfReady else "Ready ✓"
                    rdy_hover   = _button(self.screen, ready_rect, rdy_label,
                                          mx, my, enabled=rdy_enabled)
                    back_hover  = _button(self.screen, back_rect, "Back", mx, my)
                    if click:
                        # Swatch click — pick own color
                        clicked_swatch = False
                        for s, idx in swatch_hover.items():
                            if idx >= 0 and s == self.mySlot and not self.selfReady:
                                if self.session and self.session.alive:
                                    self.session.send(MSG_PICK, {'idx': idx})
                                clicked_swatch = True
                                break
                        if clicked_swatch:
                            pygame.display.flip(); self.clock.tick(60); continue
                        if rdy_hover and rdy_enabled:
                            self.selfReady = True
                            if self.session:
                                self.session.send(MSG_READY, {'ready': True})
                        elif back_hover:
                            return 'back', None, None

                pygame.display.flip()
                self.clock.tick(60)
        finally:
            if self.connector and self.status != 'connected':
                self.connector.cancel()
