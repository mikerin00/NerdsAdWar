# Module: game
# Game class — orchestrates the main loop, update logic and unit management

import math
import random

import pygame

from src.constants import (SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
                           TERR_CLAIM_RADIUS, MAP_WIDTH, MAP_HEIGHT,
                           PLAYER_COLORS, UNIT_COLORS, unitColorFromBase,
                           slotCountForMode)
from src.entities.unit import Unit, _advanceGridFrame
from src.entities.headquarters import Headquarters
from src.entities.outpost import Outpost
from src.entities.terrain import TerrainMap
from src.game.events import EventsMixin
from src.game.formation import FormationMixin
from src.game.renderer import RendererMixin
from src.game.ai import EnemyAI
from src.game.ai_log import aiLogSetFrame, aiLogWrite


class _BotGameProxy:
    """Wraps Game.units so EnemyAI only commands units assigned to specific bot
    slots.  All other game attributes pass through to the real game unchanged.

    The AI sees:
      - All 'player' units  (the opponents it tries to destroy)
      - Only 'enemy' units whose controller is in bot_slots (its own units)

    This prevents the bot AI from overriding orders issued by a human teammate
    who occupies the other slot on the same team.
    """

    def __init__(self, game, bot_slots):
        object.__setattr__(self, '_game',      game)
        object.__setattr__(self, '_bot_slots', frozenset(bot_slots))

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_game'), name)

    @property
    def units(self):
        game      = object.__getattribute__(self, '_game')
        bot_slots = object.__getattribute__(self, '_bot_slots')
        return [u for u in game.units
                if u.team == 'player' or
                   (u.team == 'enemy' and u.controller in bot_slots)]


class _TeamView:
    """Lightweight wrapper that overrides the .team attribute on any game entity."""
    __slots__ = ('_obj', 'team')

    def __init__(self, obj, team):
        object.__setattr__(self, '_obj',  obj)
        object.__setattr__(self, 'team',  team)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_obj'), name)

    def __setattr__(self, name, val):
        if name in ('_obj', 'team'):
            object.__setattr__(self, name, val)
        else:
            setattr(object.__getattribute__(self, '_obj'), name, val)


class _PlayerBotProxy:
    """Wraps Game so EnemyAI can drive player-team bot slots by swapping team
    perspective: bot-controlled player units appear as 'enemy' (AI's own) and
    all enemy units appear as 'player' (opponents).  Human partner units on
    the player team are hidden so the AI never overrides their orders."""

    def __init__(self, game, bot_slots):
        object.__setattr__(self, '_game',      game)
        object.__setattr__(self, '_bot_slots', frozenset(bot_slots))

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_game'), name)

    @property
    def units(self):
        game      = object.__getattribute__(self, '_game')
        bot_slots = object.__getattribute__(self, '_bot_slots')
        result = []
        for u in game.units:
            if u.team == 'player' and u.controller in bot_slots:
                result.append(_TeamView(u, 'enemy'))
            elif u.team == 'enemy':
                result.append(_TeamView(u, 'player'))
        return result

    @property
    def headquarters(self):
        game = object.__getattribute__(self, '_game')
        return [_TeamView(h, 'player' if h.team == 'enemy' else 'enemy')
                for h in game.headquarters]

    @property
    def outposts(self):
        game = object.__getattribute__(self, '_game')
        swap = {'player': 'enemy', 'enemy': 'player', 'neutral': 'neutral'}
        return [_TeamView(op, swap.get(op.team, op.team)) for op in game.outposts]


class Game(EventsMixin, FormationMixin, RendererMixin):
    def __init__(self, seed=42, screen=None, clock=None, biome=None, difficulty='NORMAAL',
                 gamemode='STANDAARD', netRole=None, session=None,
                 sessions=None, mode='1v1', mySlot=0, slotNames=None,
                 slotColors=None, customMap=None,
                 forces=None, aiPersonality=None, botSlots=None,
                 coopPlayers=None):
        if screen is None:
            screen = pygame.display.set_mode(
                (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
            pygame.display.set_caption(TITLE)
        if clock is None:
            clock = pygame.time.Clock()
        self.screen = screen
        self.clock  = clock
        self.font      = pygame.font.SysFont(None, 24)
        self.running   = True
        self._paused   = False
        self._quitGame = False   # True → exit the whole app, not just return to menu

        self.units         = []
        self.selectedUnits = []
        self.projectiles   = []
        self.effects       = []
        self.selStart      = None
        self.selRect       = None
        self.formPath      = []
        self.patrolPath    = []
        self.headquarters  = []
        self.outposts      = []
        self.winner        = None
        self._terrBoundary = {'player': [], 'enemy': [], 'contact': []}
        self._terrTimer    = 0
        self._terrGrid     = {}
        self._terrGridCELL = 14
        self.freezeTimer   = FPS * 60   # 60-second initial planning phase
        self.showAiLog     = False
        self._frameCount   = 0
        # Battle-start detection: one-shot banner + SFX when the first shot
        # is fired. Renderer reads _BATTLE_BANNER_TOTAL for fade timings.
        self._battleStarted       = False
        self._battleBannerFrames  = 0
        self._BATTLE_BANNER_TOTAL = int(FPS * 2.5)

        # Map-pings: short-lived markers a teammate can drop on the map
        # (V key). Each entry: {'x','y','fromSlot','life'}.
        self.pings = []
        self._PING_LIFE = FPS * 3       # 3 seconds visible

        # Battleplans: persistent translucent arrows teammates can co-draw
        # to plan attacks. Each: {'fromSlot','x1','y1','x2','y2'}.
        self.battleplans = []

        # Emotes: short text bubbles appearing next to a player's scoreboard
        # row. Visible to everyone (trash-talk friendly).
        # Each entry: {'fromSlot','idx','life'}.
        self.emotes = []
        self._EMOTE_LIFE = FPS * 3

        # ── Game mode state ──────────────────────────────────────────────────
        self.gamemode      = gamemode

        # ── Multiplayer ──────────────────────────────────────────────────────
        #  None   : single-player (AI opponent).
        #  'host' : authoritative — runs full simulation, broadcasts snapshots.
        #  'client': mirror — no simulation, rebuilds state from snapshots.
        self.netRole    = netRole
        # Sessions: host holds a list of _Session (one per connected client);
        # client holds a single-element list pointing at the host. Legacy
        # `session=` kwarg still accepted for 1v1 call sites that haven't
        # migrated to the list form.
        if sessions is None and session is not None:
            sessions = [session]
        self.sessions   = list(sessions) if sessions else []
        self.session    = self.sessions[0] if self.sessions else None  # legacy alias
        self._netIdSeq  = 0
        self._snapEvery = 2
        self._snapEveryFreeze = 15

        # Match layout
        self.matchMode = mode            # '1v1' | 'COOP' | '2v2' | '3v3' | '4v4'
        self.mySlot    = int(mySlot)     # 0..3, identifies which player I am
        # Up to 8 slots (4v4). Pad whatever the lobby handed us so indexing
        # by slot is always safe even before everyone has picked a colour.
        _MAX = 8
        self.slotNames = list(slotNames) if slotNames else []
        self.slotNames += [''] * (_MAX - len(self.slotNames))
        # Per-slot color indices (into PLAYER_COLORS). In single-player we have
        # no slot picks — leave None and fall back to the default UNIT_COLORS.
        self.slotColors = list(slotColors) if slotColors else []
        # Pad with alternating defaults so unfilled slots still draw sanely.
        while len(self.slotColors) < _MAX:
            self.slotColors.append(0 if len(self.slotColors) % 2 == 0 else 1)
        # Slots controlled by a bot AI rather than a human network peer.
        self.botSlots = set(botSlots) if botSlots else set()
        # Actual number of human players in COOP (1-4); ignored for other modes.
        self._coopPlayers = int(coopPlayers) if coopPlayers else slotCountForMode('COOP')

        # Team derived from slot and mode — unified via _slotSide so all
        # modes (1v1/COOP/2v2/3v3/4v4) follow the same first-half/second-half
        # convention. COOP forces 'player' for any human slot.
        self.mySide   = self._slotSide(self.mySlot)
        self._foeSide = 'enemy' if self.mySide == 'player' else 'player'

        # Ready flags: one per active slot. Planning ends when all are True.
        self._readyBySlot = {}

        # After a winner is declared we linger for a few seconds so the victory
        # banner is readable, then auto-return to the lobby / main menu.
        self._postGameFrames = 0
        self._POSTGAME_HOLD  = FPS * 3   # 3 seconds before results screen

        # Battle stats — used by the results screen
        self._casualties  = {'player': 0, 'enemy': 0}
        self._startCounts = {'player': 0, 'enemy': 0}

        # Conquest
        self._conquestScore = {'player': 0.0, 'enemy': 0.0}
        self._CONQUEST_WIN  = 1000

        # Last Stand
        self._waveNumber    = 0
        self._waveTimer     = 0
        self._FIRST_WAVE    = FPS * 15  # first wave 15 s after planning ends
        self._INTER_WAVE    = FPS * 5   # countdown after defeating a wave before next

        # Assault: no hold timer — player must capture every keypoint AND the HQ.

        self.mapWidth  = MAP_WIDTH
        self.mapHeight = MAP_HEIGHT
        self._mapScale = min(SCREEN_WIDTH / MAP_WIDTH, SCREEN_HEIGHT / MAP_HEIGHT)

        self.customMap = customMap
        # Campaign mission overrides (optional).  `forces` is a dict:
        #   { 'player': {infantry: N, heavy_infantry: N, cavalry: N, artillery: N},
        #     'enemy':  {...} }
        # Only STANDAARD spawn honours this at the moment — ASSAULT/LAST_STAND
        # keep their own scripted layouts.
        self.forcesOverride  = forces
        self.aiPersonalityOverride = aiPersonality
        self.terrain = TerrainMap(MAP_WIDTH, MAP_HEIGHT, seed=seed, biome=biome,
                                  customMap=customMap)
        self.terrain.buildSurface()

        # Pre-scale the terrain surface to screen size
        self._scaledTerrain = pygame.transform.smoothscale(
            self.terrain.surface, (int(MAP_WIDTH * self._mapScale),
                                   int(MAP_HEIGHT * self._mapScale)))

        rng = random.Random(seed)
        if self.netRole != 'client':
            # Host or single-player: spawn the world normally
            self._spawnUnits(rng)
            # Fallback controller: any unit that didn't get one during spawn
            # (e.g. ASSAULT/LAST_STAND paths) gets slot-0 for its team.
            for u in self.units:
                if not hasattr(u, 'controller'):
                    u.controller = 0 if u.team == 'player' else \
                                   (1 if self.matchMode == '1v1' else 2)
            if self.netRole == 'host':
                for u in self.units:
                    self._netIdSeq += 1
                    u.netId = self._netIdSeq

        # AI: single-player always, MP host in COOP/LAST_STAND (AI plays the enemy team).
        # Client never runs AI — it only mirrors host snapshots.
        spawn_ai = self.netRole is None or \
                   (self.netRole == 'host' and self.matchMode in ('COOP', 'LAST_STAND'))
        if spawn_ai:
            self.ai = EnemyAI(self, difficulty=difficulty)
            if self.aiPersonalityOverride:
                self.ai._personality = self.aiPersonalityOverride
            elif self.gamemode == 'LAST_STAND':
                self.ai._personality = 'AGGRESSIVE'
        else:
            self.ai = None

        # Bot AIs for bot-filled slots in 2v2/3v3/4v4.
        # Enemy-side bots: _BotGameProxy restricts the AI to their units.
        # Player-side bots: _PlayerBotProxy swaps team perspective so EnemyAI
        # can drive player-team slots without touching human partners.
        self.botAIs = []
        if (self.netRole in (None, 'host') and self.botSlots
                and self.matchMode in ('2v2', '3v3', '4v4')):
            enemy_team_slots  = set(self._teamSlots('enemy'))
            player_team_slots = set(self._teamSlots('player'))
            enemy_bots  = {s for s in self.botSlots if s in enemy_team_slots}
            player_bots = {s for s in self.botSlots if s in player_team_slots}
            if enemy_bots:
                proxy  = _BotGameProxy(self, enemy_bots)
                bot_ai = EnemyAI(proxy, difficulty=difficulty)
                self.botAIs.append(bot_ai)
            if player_bots:
                proxy  = _PlayerBotProxy(self, player_bots)
                bot_ai = EnemyAI(proxy, difficulty=difficulty)
                self.botAIs.append(bot_ai)

    def _spawnUnits(self, rng):
        W, H  = self.mapWidth, self.mapHeight
        cy    = H // 2

        # Army scales with match size — totals grow per side, but per-player
        # shrinks so 3v3/4v4 don't turn into chaos. Tuned per side:
        #   1 player  → 32 units    (1v1)
        #   2 players → 50 units    (2v2 / COOP)        — 25/player
        #   3 players → 57 units    (3v3)               — 19/player
        #   4 players → 64 units    (4v4)               — 16/player
        per_side = max(1, len(self._teamSlots('player')) or 1)
        if per_side >= 4:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 15, 13, 11, 4
        elif per_side == 3:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 14, 11,  9, 3
        elif per_side == 2:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 12,  9,  7, 4
        else:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT =  8,  7,  6, 2
        COLS      = 2

        # Campaign forces override — replaces counts (PLAYER side only for the
        # left-spawn block; enemy override applied in the symmetric branch).
        fp = (self.forcesOverride or {}).get('player') if self.forcesOverride else None
        if fp:
            INF_ROWS  = max(1, fp.get('infantry', INF_ROWS * COLS) // COLS)
            CAV_COUNT = fp.get('cavalry',        CAV_COUNT)
            HVY_COUNT = fp.get('heavy_infantry', HVY_COUNT)
            ART_COUNT = fp.get('artillery',      ART_COUNT)

        INF_SPACING = min(50, (H - 120) // INF_ROWS)
        inf_top     = cy - (INF_ROWS - 1) * INF_SPACING // 2

        # Track y-coordinate for each player-team unit so we can later split
        # by upper/lower half between slot 0 and slot 1.
        spawned = []

        # --- Player units (left side) ---
        for col in range(COLS):
            x = 170 + col * 45
            for row in range(INF_ROWS):
                y = inf_top + row * INF_SPACING
                u = Unit(x, y, 'player', 'infantry')
                self.units.append(u); spawned.append(u)

        CAV_SPACING = min(55, (H - 120) // CAV_COUNT) if CAV_COUNT else 55
        cav_top     = cy - (CAV_COUNT - 1) * CAV_SPACING // 2
        for i in range(CAV_COUNT):
            u = Unit(280, cav_top + i * CAV_SPACING, 'player', 'cavalry')
            self.units.append(u); spawned.append(u)

        HVY_SPACING = min(40, (H - 120) // HVY_COUNT) if HVY_COUNT else 40
        hvy_top     = cy - (HVY_COUNT - 1) * HVY_SPACING // 2
        for i in range(HVY_COUNT):
            u = Unit(120, hvy_top + i * HVY_SPACING, 'player', 'heavy_infantry')
            self.units.append(u); spawned.append(u)

        for i in range(ART_COUNT):
            y = cy - (ART_COUNT - 1) * 50 + i * 100
            u = Unit(75, y, 'player', 'artillery')
            self.units.append(u); spawned.append(u)

        # --- Commanders (COMMANDER gamemode only) ---
        if self.gamemode == 'COMMANDER':
            pc = Unit(130, cy, 'player', 'commander')
            ec = Unit(W - 130, cy, 'enemy', 'commander')
            self.units.append(pc); spawned.append(pc)
            self.units.append(ec); spawned.append(ec)

        # --- Headquarters (not used in COMMANDER mode) ---
        if self.gamemode != 'COMMANDER':
            self.headquarters.append(Headquarters(65, cy, 'player'))
        if self.gamemode not in ('LAST_STAND', 'COMMANDER'):
            self.headquarters.append(Headquarters(W - 65, cy, 'enemy'))

        # --- Outposts (must come before enemy spawn in Assault) ---
        if self.gamemode == 'ASSAULT':
            self._generateAssaultKeypoints(rng)
        else:
            self._generateOutposts(rng)

        # --- Enemy units ---
        if self.gamemode == 'ASSAULT':
            self._spawnAssaultEnemies(rng)
        elif self.gamemode == 'LAST_STAND':
            pass   # no starting enemies — waves spawn during gameplay
        else:
            # Enemy forces may be overridden independently from the player.
            fe = (self.forcesOverride or {}).get('enemy') if self.forcesOverride else None
            e_inf_rows = max(1, (fe.get('infantry', INF_ROWS * COLS) // COLS)
                             if fe else INF_ROWS)
            e_cav  = fe.get('cavalry',        CAV_COUNT) if fe else CAV_COUNT
            e_hvy  = fe.get('heavy_infantry', HVY_COUNT) if fe else HVY_COUNT
            e_art  = fe.get('artillery',      ART_COUNT) if fe else ART_COUNT
            e_inf_top = cy - (e_inf_rows - 1) * INF_SPACING // 2

            e_cav_spacing = min(55, (H - 120) // e_cav) if e_cav else 55
            e_cav_top     = cy - (e_cav - 1) * e_cav_spacing // 2
            e_hvy_spacing = min(40, (H - 120) // e_hvy) if e_hvy else 40
            e_hvy_top     = cy - (e_hvy - 1) * e_hvy_spacing // 2

            for col in range(COLS):
                x = W - 170 - col * 45
                for row in range(e_inf_rows):
                    y = e_inf_top + row * INF_SPACING
                    u = Unit(x, y, 'enemy', 'infantry')
                    self.units.append(u); spawned.append(u)
            for i in range(e_cav):
                u = Unit(W - 280, e_cav_top + i * e_cav_spacing, 'enemy', 'cavalry')
                self.units.append(u); spawned.append(u)
            for i in range(e_hvy):
                u = Unit(W - 120, e_hvy_top + i * e_hvy_spacing, 'enemy', 'heavy_infantry')
                self.units.append(u); spawned.append(u)
            for i in range(e_art):
                y = cy - (e_art - 1) * 50 + i * 100
                u = Unit(W - 75, y, 'enemy', 'artillery')
                self.units.append(u); spawned.append(u)

        # Split each team's units spatially so rectangle-select stays
        # intuitive: sort by Y, chunk into K equal groups, assign to each
        # team slot in turn. COOP's enemy side has no humans → -1 (AI only).
        # Partial 2v2: slots with no human AND no bot are skipped — their units
        # go to the active player(s) on the same team (bigger army).
        def _active_slots_for(team):
            all_s = self._teamSlots(team)
            active = [s for s in all_s
                      if s in self.botSlots
                      or (s < len(self.slotNames) and bool(self.slotNames[s].strip()))]
            return active if active else all_s  # fallback: use all

        side_slots = {
            'player': _active_slots_for('player'),
            'enemy':  _active_slots_for('enemy'),
        }
        for team, slots in side_slots.items():
            team_units = [u for u in self.units if u.team == team]
            if not team_units:
                continue
            if not slots:
                for u in team_units:
                    u.controller = -1   # AI-only side (e.g. COOP enemy)
                continue
            for utype in ('infantry', 'heavy_infantry',
                          'cavalry',  'artillery'):
                group = sorted([u for u in team_units if u.unitType == utype],
                               key=lambda u: u.y)
                n, k = len(group), len(slots)
                if n == 0:
                    continue
                for i, u in enumerate(group):
                    u.controller = slots[(i * k) // n]

        # Record starting unit counts for the results screen
        for team in ('player', 'enemy'):
            self._startCounts[team] = sum(1 for u in self.units if u.team == team)

    def _generateOutposts(self, rng):
        # Sandbox override: if the custom map declares explicit outpost
        # positions, use those verbatim instead of the procedural layout.
        if self.customMap and self.customMap.get('outposts'):
            for (ox, oy) in self.customMap['outposts']:
                self.outposts.append(Outpost(float(ox), float(oy)))
            return
        W, H      = self.mapWidth, self.mapHeight
        cx, cy    = W // 2, H // 2
        MIN_DIST  = 200   # minimum px between any two outposts
        MARGIN    = 120   # keep away from map edges
        OBS_CLEAR = 60    # minimum distance from lake/rock
        placed    = []

        def _tryPlace(x, y):
            x = max(MARGIN, min(W - MARGIN, x))
            y = max(MARGIN, min(H - MARGIN, y))
            if not self.terrain.isPassable(x, y) or self.terrain.isForest(x, y):
                return False
            if self.terrain.isNearObstacle(x, y, radius=OBS_CLEAR):
                return False
            if all(math.hypot(x - px, y - py) >= MIN_DIST for px, py in placed):
                placed.append((x, y))
                self.outposts.append(Outpost(x, y))
                return True
            return False

        # Centre outpost — wider search area
        for _ in range(40):
            x = cx + rng.randint(-160, 160)
            y = cy + rng.randint(-160, 160)
            if _tryPlace(x, y):
                break

        def _validPos(x, y):
            x = max(MARGIN, min(W - MARGIN, x))
            y = max(MARGIN, min(H - MARGIN, y))
            if not self.terrain.isPassable(x, y) or self.terrain.isForest(x, y):
                return False
            if self.terrain.isNearObstacle(x, y, radius=OBS_CLEAR):
                return False
            return all(math.hypot(x - px, y - py) >= MIN_DIST for px, py in placed)

        # Four point-symmetric pairs — both must be valid before placing either
        for _ in range(4):
            for attempt in range(120):
                dx = rng.randint(W // 6, W // 3)
                dy = rng.randint(-H // 3, H // 3)
                x1, y1 = cx + dx, cy + dy
                x2, y2 = cx - dx, cy - dy
                if _validPos(x1, y1) and _validPos(x2, y2):
                    _tryPlace(x1, y1)
                    _tryPlace(x2, y2)
                    break

    def _generateAssaultKeypoints(self, rng):
        """Place 4 strategic keypoints across the enemy half, depth-staged.

        Layout (AI on the right):
          - 1 forward outpost (~55% W, mid-y)         — first objective
          - 2 mid-line keypoints (~70% W, top+bottom) — flank objectives
          - 1 inner keypoint (~85% W, mid-y)          — last bastion before HQ
        All keypoints start at control = -1.0 (fully enemy-owned). Player must
        capture every keypoint AND the HQ to win.
        """
        W, H      = self.mapWidth, self.mapHeight
        MARGIN    = 140
        OBS_CLEAR = 60
        MIN_DIST  = 200
        placed    = []

        def _tryPlace(x, y, role):
            x = max(MARGIN, min(W - MARGIN, x))
            y = max(MARGIN, min(H - MARGIN, y))
            if not self.terrain.isPassable(x, y) or self.terrain.isForest(x, y):
                return False
            if self.terrain.isNearObstacle(x, y, radius=OBS_CLEAR):
                return False
            if all(math.hypot(x - px, y - py) >= MIN_DIST for px, py in placed):
                placed.append((x, y))
                op = Outpost(x, y, strategic=True)
                op.control       = -1.0   # fully enemy-owned at start
                op.assaultRole   = role   # 'forward' | 'mid' | 'inner'
                self.outposts.append(op)
                return True
            return False

        # Target positions in (target_x, target_y, role) form.
        targets = [
            (W * 0.55, H * 0.50, 'forward'),
            (W * 0.70, H * 0.25, 'mid'),
            (W * 0.70, H * 0.75, 'mid'),
            (W * 0.85, H * 0.50, 'inner'),
        ]
        for tx, ty, role in targets:
            for _ in range(80):
                x = tx + rng.randint(-90, 90)
                y = ty + rng.randint(-90, 90)
                if _tryPlace(x, y, role):
                    break

    def _spawnAssaultEnemies(self, rng):
        """Spawn the defending enemy army for ASSAULT mode (~44 units).

        Composition is depth-staged so each keypoint has a proper garrison:
          - forward keypoint : 5 infantry
          - mid keypoints (×2): 6 infantry + 1 artillery each
          - inner keypoint    : 4 heavy infantry + 1 artillery
          - HQ defenders      : 4 heavy infantry + 2 artillery (rear bastion)
          - mobile reserve    : 6 cavalry behind HQ
          - skirmisher screen : 4 infantry between forward and mid
        Garrisons spawn in a tight ring around their assigned keypoint so the
        defensive formation is visible from the start.
        """
        W, H = self.mapWidth, self.mapHeight
        cy   = H // 2

        keypoints = [op for op in self.outposts if getattr(op, 'assaultRole', None)]
        forward   = [op for op in keypoints if op.assaultRole == 'forward']
        mid       = [op for op in keypoints if op.assaultRole == 'mid']
        inner     = [op for op in keypoints if op.assaultRole == 'inner']

        def _ring(op, count, radius=55):
            """Return `count` (x, y) positions in a forward-facing arc on the
            PLAYER side of the keypoint (low-x side), so defenders face the
            attack direction instead of away from it."""
            out = []
            for i in range(count):
                ang = math.pi * (-0.5 + (i / max(count - 1, 1)))   # -90°..+90° fan
                x   = op.x - math.cos(ang) * radius   # negate cos → arc opens left
                y   = op.y + math.sin(ang) * radius
                x   = max(80, min(W - 80, x))
                y   = max(60, min(H - 60, y))
                out.append((x, y))
            return out

        # Forward keypoint garrison: 5 infantry
        for op in forward:
            for x, y in _ring(op, 5, radius=50):
                u = Unit(x, y, 'enemy', 'infantry')
                u.assaultPost = id(op); self.units.append(u)

        # Mid keypoints: 6 infantry + 1 artillery each
        for op in mid:
            for x, y in _ring(op, 6, radius=58):
                u = Unit(x, y, 'enemy', 'infantry')
                u.assaultPost = id(op); self.units.append(u)
            # Artillery slightly behind the keypoint
            ax = max(80, min(W - 80, op.x + 50))
            ay = op.y
            a  = Unit(ax, ay, 'enemy', 'artillery')
            a.assaultPost = id(op); self.units.append(a)

        # Inner keypoint: 4 heavy infantry + 1 artillery
        for op in inner:
            for x, y in _ring(op, 4, radius=46):
                u = Unit(x, y, 'enemy', 'heavy_infantry')
                u.assaultPost = id(op); self.units.append(u)
            ax = max(80, min(W - 80, op.x + 60))
            a  = Unit(ax, op.y, 'enemy', 'artillery')
            a.assaultPost = id(op); self.units.append(a)

        # HQ rear bastion: 4 heavy infantry in a wall + 2 artillery
        HVY_SPACING = min(44, (H - 120) // 5)
        hvy_top = cy - int(1.5 * HVY_SPACING)
        for i in range(4):
            self.units.append(
                Unit(W - 130, hvy_top + i * HVY_SPACING, 'enemy', 'heavy_infantry'))
        for i in range(2):
            self.units.append(
                Unit(W - 75, cy - 50 + i * 100, 'enemy', 'artillery'))

        # Mobile cavalry reserve behind HQ — counterattacks threatened keypoints
        CAV_SPACING = min(50, (H - 120) // 6)
        cav_top = cy - int(2.5 * CAV_SPACING)
        for i in range(6):
            self.units.append(
                Unit(W - 95, cav_top + i * CAV_SPACING, 'enemy', 'cavalry'))

        # Skirmisher screen between forward and mid line
        for i in range(4):
            sx = W * 0.62 + rng.randint(-20, 20)
            sy = 120 + i * (H - 240) // 3 + rng.randint(-20, 20)
            self.units.append(Unit(sx, sy, 'enemy', 'infantry'))

    def _spawnWave(self):
        """Spawn the next enemy wave from the right edge (Last Stand mode)."""
        self._waveNumber += 1
        W, H = self.mapWidth, self.mapHeight
        n    = self._waveNumber

        # Faster escalation — stays interesting from wave 1
        # Wave 1: 8inf | Wave 2: 10inf+2cav | Wave 3: 12inf+4cav+2hvy | Wave 4+: adds art
        composition = {
            'infantry':       6 + n * 2,
            'cavalry':        max(0, n - 1) * 2,
            'heavy_infantry': max(0, n - 2) * 2,
            'artillery':      max(0, n - 3),
        }
        spawn_x  = W - 60
        cy       = H // 2
        playerHq = next((h for h in self.headquarters if h.team == 'player'), None)
        hqx      = playerHq.x if playerHq else 65
        hqy      = playerHq.y if playerHq else cy

        new_units = []
        for utype, count in composition.items():
            for i in range(count):
                y = cy + (i - count // 2) * 48 + (hash((utype, i, n)) % 20 - 10)
                y = max(60, min(H - 60, y))
                u = Unit(spawn_x, y, 'enemy', utype)
                u.controller = -1   # AI-only; no human commands these
                # Point directly at player HQ from spawn
                spread = (hash((utype, i)) % 300) - 150
                u.targetX = hqx + 30
                u.targetY = hqy + spread
                new_units.append(u)
        self.units.extend(new_units)

    # ── Drawing helpers — per-slot player colors ───────────────────────────

    def colorForUnit(self, unit):
        """Return the RGB color a unit should be drawn in.
        Multiplayer: derived from its controller's picked slot color.
        Single-player: falls back to the hard-coded team palette."""
        if self.netRole is None:
            return UNIT_COLORS[unit.team][unit.unitType]
        slot = getattr(unit, 'controller', None)
        if slot is None or slot < 0 or slot >= len(self.slotColors):
            return UNIT_COLORS[unit.team][unit.unitType]
        idx  = self.slotColors[slot]
        if idx < 0 or idx >= len(PLAYER_COLORS):
            return UNIT_COLORS[unit.team][unit.unitType]
        base = PLAYER_COLORS[idx][1]
        return unitColorFromBase(base, unit.unitType)

    # ── Outpost reinforcements ──────────────────────────────────────────────
    # Every captured outpost trickles fresh troops to its owning team. Rates
    # tuned so a team holding 3 outposts gets roughly one unit every 7-8 s,
    # which keeps a back-and-forth match flowing without runaway snowballs.

    _OUTPOST_SPAWN_INTERVAL = FPS * 30     # one reinforcement per outpost every 30s
    _OUTPOST_WEIGHTS = (
        ('infantry',       0.80),
        ('cavalry',        0.075),
        ('heavy_infantry', 0.075),
        ('artillery',      0.05),
    )

    _PER_PLAYER_CAP = 40

    def _teamCap(self, team: str) -> int:
        """Max units a team is allowed to field at once (single-player / COOP).
        In slot-based modes each player has their own cap checked per-slot."""
        return self._PER_PLAYER_CAP

    def _pickSpawnUnitType(self) -> str:
        r   = random.random()
        acc = 0.0
        for utype, w in self._OUTPOST_WEIGHTS:
            acc += w
            if r < acc:
                return utype
        return 'infantry'   # shouldn't hit but safe default

    def _updateOutpostSpawns(self):
        """Called once per simulated frame on the host / single-player side.
        The client never runs this — reinforcement units arrive via snapshots."""
        if self.netRole == 'client':
            return
        if self.winner is not None or self.freezeTimer > 0:
            return
        from src.entities.effect import Effect

        for op in self.outposts:
            if op.team is None:
                op.spawnTimer = 0
                continue
            # In LAST_STAND the enemy spawns via waves only — outposts must not
            # generate additional enemy reinforcements.
            if self.gamemode == 'LAST_STAND' and op.team == 'enemy':
                op.spawnTimer = 0
                continue
            op.spawnTimer = getattr(op, 'spawnTimer', 0) + 1
            if op.spawnTimer < self._OUTPOST_SPAWN_INTERVAL:
                continue
            op.spawnTimer = 0

            # Determine next slot in round-robin before cap check
            team_slots = self._teamSlots(op.team)
            if team_slots:
                op._spawnRot = (getattr(op, '_spawnRot', -1) + 1) % len(team_slots)
                next_slot = team_slots[op._spawnRot]
                # Per-player cap: count only units owned by this slot
                slot_count = sum(1 for u in self.units
                                 if getattr(u, 'controller', -1) == next_slot)
                if slot_count >= self._PER_PLAYER_CAP:
                    continue
            else:
                # AI-only side (e.g. COOP enemy) — check whole-team cap
                team_count = sum(1 for u in self.units if u.team == op.team)
                if team_count >= self._teamCap(op.team):
                    continue
                next_slot = -1

            utype = self._pickSpawnUnitType()
            offX  = random.uniform(-24, 24)
            offY  = random.uniform(-24, 24)
            u = Unit(op.x + offX, op.y + offY, op.team, utype)
            u.controller = next_slot

            if self.netRole == 'host':
                self._netIdSeq += 1
                u.netId = self._netIdSeq

            self.units.append(u)
            # Little smoke puff so the spawn reads visually
            self.effects.append(Effect(op.x, op.y, 'smoke'))

    # ── Surrender ───────────────────────────────────────────────────────────

    def _surrender(self):
        """Player gave up via the pause menu. Route through the command
        dispatcher so in multiplayer the host applies it authoritatively."""
        self.issueCommand('surr', {})

    # ── Multiplayer: command dispatch ───────────────────────────────────────

    def issueCommand(self, cmdType: str, data: dict):
        """Called from input handlers. On single-player / host, apply locally
        and immediately; on client, ship it to the host where the simulation
        lives. All input goes through this choke point so the two paths stay
        in lockstep."""
        if self.netRole == 'client':
            if self.session and self.session.alive:
                self.session.send('cmd', {'t': cmdType, 'd': data})
            return
        # host or single-player: I'm slot self.mySlot
        self._applyCommand(cmdType, data, fromSlot=self.mySlot)

    def _applyCommand(self, cmdType: str, data: dict, fromSlot: int):
        """Execute a command authoritatively. `fromSlot` says which player
        issued it — ownership check filters the affected units to those whose
        `controller` matches. Prevents a client from moving enemy units."""
        fromSide = self._slotSide(fromSlot)

        if cmdType == 'surr':
            # Whoever surrenders gives the win to the OTHER TEAM, not just the
            # other player. A teammate in 2v2 also loses when one gives up.
            if self.winner is None:
                self.winner = 'enemy' if fromSide == 'player' else 'player'
            return

        if cmdType == 'ping':
            x, y = float(data.get('x', 0)), float(data.get('y', 0))
            self.pings.append({'x': x, 'y': y,
                               'fromSlot': int(fromSlot),
                               'life': self._PING_LIFE})
            # Give the host audible confirmation too. Clients hear theirs
            # when the new ping arrives via snapshot (see _applySnapshot).
            if fromSlot == self.mySlot:
                try:
                    from src import audio
                    audio.play_sfx('click')
                except Exception:
                    pass
            return

        if cmdType == 'plan':
            self.battleplans.append({
                'fromSlot': int(fromSlot),
                'x1': float(data.get('x1', 0)), 'y1': float(data.get('y1', 0)),
                'x2': float(data.get('x2', 0)), 'y2': float(data.get('y2', 0)),
            })
            # Cap so a spammer can't fill the screen with arrows.
            self.battleplans = self.battleplans[-32:]
            return

        if cmdType == 'planClr':
            # Clear only the issuer's own arrows — teammates' plans stay.
            self.battleplans = [bp for bp in self.battleplans
                                if bp['fromSlot'] != int(fromSlot)]
            return

        if cmdType == 'emote':
            idx = int(data.get('idx', 0))
            # Drop any earlier emote from the same player so spam doesn't pile up.
            self.emotes = [em for em in self.emotes
                           if em['fromSlot'] != int(fromSlot)]
            self.emotes.append({'fromSlot': int(fromSlot),
                                'idx': idx, 'life': self._EMOTE_LIFE})
            return

        if cmdType == 'rdy':
            self._readyBySlot[fromSlot] = True
            # Only count human-controlled slots: bot slots never send 'rdy'.
            all_slots    = self._activeSlots()
            human_slots  = [s for s in all_slots if s not in self.botSlots]
            if self.freezeTimer > 0:
                if self.netRole is None:
                    self.freezeTimer = 0
                elif all(self._readyBySlot.get(s, False) for s in human_slots):
                    self.freezeTimer = 0
            return

        ids = data.get('ids', [])
        units = [u for u in self.units
                 if getattr(u, 'netId', None) in ids
                 and getattr(u, 'controller', -1) == fromSlot]
        if not units:
            return

        if cmdType == 'move':
            mx, my = data['x'], data['y']
            self._prepForRedeploy(units)
            # Group offset relative to centroid, like the local path does
            cx = sum(u.x for u in units) / len(units)
            cy = sum(u.y for u in units) / len(units)
            for u in units:
                u.attackTarget = None
                u.patrolPath   = []
                u.targetX = mx + (u.x - cx)
                u.targetY = my + (u.y - cy)

        elif cmdType == 'atk':
            tid = data.get('tid')
            target = next((t for t in self.units
                           if getattr(t, 'netId', None) == tid
                           and t.team != fromSide), None)
            if target is None:
                return
            for u in units:
                u.patrolPath   = []
                u.attackTarget = target

        elif cmdType == 'sq':
            # Delegate to existing toggle but with a filtered selection list.
            orig = self.selectedUnits
            self.selectedUnits = units
            try:
                self._toggleInfantrySquare()
            finally:
                self.selectedUnits = orig

        elif cmdType == 'form':
            path = [tuple(p) for p in data.get('path', [])]
            orig = self.selectedUnits
            self.selectedUnits = units
            try:
                for u in units:
                    u.patrolPath = []
                self._applyFormationPath(path)
            finally:
                self.selectedUnits = orig

        elif cmdType == 'patrol':
            path = [tuple(p) for p in data.get('path', [])]
            orig = self.selectedUnits
            self.selectedUnits = units
            try:
                self._applyPatrolPath(path)
            finally:
                self.selectedUnits = orig

    def _drainClientCommands(self):
        """Host: drain queued command messages from every connected client.
        Each client has a `slot` attribute from the lobby; that slot determines
        which units they may command (ownership enforced in _applyCommand)."""
        for sess in list(self.sessions):
            if not sess.alive:
                continue
            for mt, data in sess.poll():
                if mt == '__error__':
                    # Ignore — the missing client can just spectate the rest
                    # of the match from where they last saw it. No auto-loss.
                    break
                if mt == 'cmd':
                    self._applyCommand(data.get('t', ''), data.get('d', {}),
                                       fromSlot=getattr(sess, 'slot', 1))
                elif mt == 'bye':
                    break

    # ── Map pings ───────────────────────────────────────────────────────────

    # ── Match-mode geometry ─────────────────────────────────────────────────
    # Slot↔side logic lives in src/constants.py so the lobby and the game
    # share one truth table (see MODE_SLOT_COUNT / teamOfSlot).

    def _modeSlotCount(self):
        if self.matchMode == 'COOP':
            return self._coopPlayers
        return slotCountForMode(self.matchMode)

    def _activeSlots(self):
        return list(range(self._modeSlotCount()))

    def _teamSlots(self, team):
        """Slot indices belonging to a given team for the current matchMode.
        COOP is a special case: all human slots share the player team; enemy
        side is AI-driven (no human slot)."""
        if self.matchMode == 'COOP':
            return list(range(self._coopPlayers)) if team == 'player' else []
        n    = self._modeSlotCount()
        half = n // 2
        return list(range(half)) if team == 'player' else list(range(half, n))

    def _slotSide(self, slot):
        from src.constants import teamOfSlot
        return teamOfSlot(slot, self.matchMode)

    def _pingVisibleToMe(self, ping):
        """Pings are team-only — enemy markers would defeat the purpose."""
        if self.netRole is None:
            return True
        return self._slotSide(ping['fromSlot']) == self.mySide

    def _tickPings(self):
        """Decay each ping's life, drop the expired ones. Host-side only."""
        for pg in self.pings:
            pg['life'] -= 1
        self.pings = [p for p in self.pings if p['life'] > 0]
        for em in self.emotes:
            em['life'] -= 1
        self.emotes = [e for e in self.emotes if e['life'] > 0]

    # ── Battle-start banner ─────────────────────────────────────────────────

    def _tickBattleBanner(self):
        """Fire a one-shot 'SLAG BEGINT' banner + SFX the moment combat
        actually starts (first projectile in flight). Runs on host, single-
        player, and client (client picks up projectiles via snapshot)."""
        if not self._battleStarted and self.projectiles:
            self._battleStarted      = True
            self._battleBannerFrames = self._BATTLE_BANNER_TOTAL
            try:
                from src import audio
                audio.play_sfx('cannon')
            except Exception:
                pass
        if self._battleBannerFrames > 0:
            self._battleBannerFrames -= 1

    # ── Multiplayer: snapshot I/O ───────────────────────────────────────────

    def _assignNetIds(self):
        """Give every unit without a netId a fresh stable id. Host-only —
        called once after initial spawn, and again for units created later
        (waves, reinforcements)."""
        for u in self.units:
            if not hasattr(u, 'netId') or u.netId is None:
                self._netIdSeq += 1
                u.netId = self._netIdSeq

    def _sendSnapshot(self):
        self._assignNetIds()
        units = []
        for u in self.units:
            tgt = u.attackTarget
            atId = getattr(tgt, 'netId', None) if (tgt and tgt.hp > 0) else None
            units.append({
                'id': u.netId,
                'x': round(u.x, 1), 'y': round(u.y, 1),
                't': u.team[0],                     # 'p' or 'e'
                'u': u.unitType[:3],                # 'inf','hea','cav','art'
                'hp': round(u.hp, 1),
                'mx': u.maxHp,
                'a':  round(u.angle, 1),
                'tx': round(u.targetX, 1), 'ty': round(u.targetY, 1),
                'sq': 1 if u.inSquare else 0,
                'dp': 1 if u.deployed else 0,
                'rt': 1 if u.routing else 0,
                'c':  getattr(u, 'controller', 0),
                'at': atId,                         # netId of attack target, if any
            })
        outposts = [{'x': op.x, 'y': op.y,
                     'tm': (op.team[0] if op.team else 'n'),
                     'c':  round(op.control, 2),
                     's':  1 if op.strategic else 0}
                    for op in self.outposts]
        hqs = [{'x': h.x, 'y': h.y, 't': h.team[0],
                'cp': round(h.captureProgress, 1),
                'cap': 1 if h.captured else 0}
               for h in self.headquarters]
        projs = [{'x': round(p.x, 1), 'y': round(p.y, 1), 'k': p.type,
                  'dx': round(p.destX, 1), 'dy': round(p.destY, 1)}
                 for p in self.projectiles]
        effs  = [{'x': round(e.x, 1), 'y': round(e.y, 1),
                  'k': e.type, 'tm': e.timer}
                 for e in self.effects]
        pings = [{'x': round(pg['x'], 1), 'y': round(pg['y'], 1),
                  'c': pg['fromSlot'], 'l': pg['life']}
                 for pg in self.pings]
        plans = [{'c':  bp['fromSlot'],
                  'x1': round(bp['x1'], 1), 'y1': round(bp['y1'], 1),
                  'x2': round(bp['x2'], 1), 'y2': round(bp['y2'], 1)}
                 for bp in self.battleplans]
        emotes = [{'c': em['fromSlot'], 'i': em['idx'], 'l': em['life']}
                  for em in self.emotes]
        data = {
            'f':  self._frameCount,
            'fz': self.freezeTimer,
            'w':  self.winner,
            'wv': self._waveNumber,
            'wt': self._waveTimer,
            'u':  units,
            'o':  outposts,
            'h':  hqs,
            'p':  projs,
            'e':  effs,
            'pg': pings,
            'bp': plans,
            'em': emotes,
        }
        # Broadcast to every connected client (1 in 1v1, up to 3 in 2v2)
        for sess in self.sessions:
            if sess.alive:
                sess.send('snap', data)

    def _clientTick(self):
        """Drain inbound messages from host and apply the most recent snapshot.
        Applies state by rebuilding the world from scratch — 60 units per tick
        is cheap, and sidesteps any attempt to track dead/spawned entities.
        Between snapshots we locally tick effects so smoke/slashes animate
        smoothly at 60 fps instead of 'stuttering' at the 15 Hz snapshot rate."""
        if self.session is None or not self.session.alive:
            self.running = False
            return
        latest = None
        for mt, data in self.session.poll():
            if mt == '__error__':
                self.running = False
                return
            if mt == 'snap':
                latest = data             # keep only the newest snapshot
            elif mt == 'bye':
                self.running = False
                return
        if latest is not None:
            self._applySnapshot(latest)
        self._tickBattleBanner()
        # Locally tick effects so they fade smoothly between snapshots
        for e in self.effects:
            e.update()
        self.effects = [e for e in self.effects if not e.done]
        # Smooth unit motion between snapshots with exponential lerp. At 30 Hz
        # snapshots this settles each step in ~3 frames → no visible popping.
        BLEND = 0.30
        for u in self.units:
            sx = getattr(u, '_snapX', None)
            if sx is None:
                continue
            u.x += (sx       - u.x) * BLEND
            u.y += (u._snapY - u.y) * BLEND

    def _applySnapshot(self, data):
        # Freeze timer + winner are straight copies
        self.freezeTimer  = data.get('fz', 0)
        self.winner       = data.get('w')
        self._waveNumber  = data.get('wv', self._waveNumber)
        self._waveTimer   = data.get('wt', self._waveTimer)

        # Rebuild units. Preserve selection across ticks by mapping netId →
        # new Unit instance (phase 3 lets the client select and issue commands).
        _type_map = {'inf': 'infantry', 'hea': 'heavy_infantry',
                     'cav': 'cavalry',  'art': 'artillery'}
        _team_map = {'p': 'player', 'e': 'enemy'}
        prev_sel  = {u.netId for u in self.selectedUnits if hasattr(u, 'netId')}
        # Remember each unit's last rendered position so we can interpolate
        # toward the new snapshot pos instead of teleporting every 2 frames.
        prev_pos = {u.netId: (u.x, u.y) for u in self.units if hasattr(u, 'netId')}
        new_units = []
        new_sel   = []
        for ud in data.get('u', []):
            team  = _team_map.get(ud['t'], 'player')
            utype = _type_map.get(ud['u'], 'infantry')
            # Spawn at last-known render position so interpolation starts from
            # where the player saw the unit, not where the host says it is now.
            start_x, start_y = prev_pos.get(ud['id'], (ud['x'], ud['y']))
            u = Unit(start_x, start_y, team, utype)
            u.netId   = ud['id']
            u.hp      = ud['hp']
            u.maxHp   = ud['mx']
            u.angle   = ud['a']
            u.targetX = ud['tx']; u.targetY = ud['ty']
            u._snapX, u._snapY = ud['x'], ud['y']   # authoritative position
            u.inSquare = bool(ud['sq'])
            u.deployed = bool(ud['dp'])
            u.routing  = bool(ud['rt'])
            u.controller = ud.get('c', 0)
            u._attackTargetId = ud.get('at')   # resolve in second pass below
            if u.netId in prev_sel:
                u.selected = True
                new_sel.append(u)
            new_units.append(u)
        self.units         = new_units
        self.selectedUnits = new_sel

        # Resolve attackTarget references now that every Unit exists.
        # Required for the orange attack-marker to appear on the client.
        by_id = {u.netId: u for u in new_units}
        for u in new_units:
            tid = getattr(u, '_attackTargetId', None)
            u.attackTarget = by_id.get(tid) if tid is not None else None

        # Outposts: rebuild by order (positions are stable per seeded world)
        from src.entities.outpost import Outpost
        new_ops = []
        for od in data.get('o', []):
            op = Outpost(od['x'], od['y'], strategic=bool(od['s']))
            op.control = od['c']   # .team is a @property derived from control
            new_ops.append(op)
        self.outposts = new_ops

        # HQs
        new_hqs = []
        for hd in data.get('h', []):
            hq = Headquarters(hd['x'], hd['y'],
                              'player' if hd['t'] == 'p' else 'enemy')
            hq.captureProgress = hd['cp']
            hq.captured = bool(hd['cap'])
            new_hqs.append(hq)
        self.headquarters = new_hqs

        # Projectiles — reconstructed without invoking Projectile.__init__
        # because that expects a live target Unit reference we don't have.
        # We only need x/y/colour/radius for drawing; damage logic stays on host.
        from src.entities.projectile import Projectile
        new_projs = []
        for pd in data.get('p', []):
            p = object.__new__(Projectile)
            p.x, p.y = pd['x'], pd['y']
            p.destX  = pd.get('dx', pd['x'])
            p.destY  = pd.get('dy', pd['y'])
            p.type   = pd['k']
            style    = Projectile.STYLES.get(p.type, Projectile.STYLES['musket'])
            p.radius = style['radius']
            p.color  = style['color']
            p.done   = False
            new_projs.append(p)
        self.projectiles = new_projs

        # Effects — replace with the host's list. Local per-frame decay in
        # _clientTick keeps the animation smooth between snapshots.
        # Also detect newly appeared effect types to play matching sounds.
        from src.entities.effect import Effect
        prev_eff_types = {e.type for e in self.effects}
        new_effs = []
        for ed in data.get('e', []):
            e = Effect(ed['x'], ed['y'], ed['k'])
            e.timer = ed['tm']
            new_effs.append(e)
        self.effects = new_effs
        new_eff_types = {e.type for e in new_effs}
        appeared = new_eff_types - prev_eff_types
        if appeared:
            try:
                from src import audio
                if 'smoke' in appeared or 'explosion' in appeared or 'impact' in appeared:
                    audio.play_sfx('cannon')
                if 'slash' in appeared:
                    audio.play_sfx('musket')
                if 'sword' in appeared or 'spear' in appeared:
                    audio.play_sfx('cavalry')
            except Exception:
                pass

        # Battleplans — replace wholesale (host is authoritative).
        self.battleplans = [
            {'fromSlot': bd['c'],
             'x1': bd['x1'], 'y1': bd['y1'],
             'x2': bd['x2'], 'y2': bd['y2']}
            for bd in data.get('bp', [])
        ]
        self.emotes = [{'fromSlot': em['c'], 'idx': em['i'], 'life': em['l']}
                       for em in data.get('em', [])]

        # Pings (only present when teammates dropped a marker recently).
        # Detect freshly-arrived pings to fire the local SFX once.
        prev_keys = {(round(p['x'], 1), round(p['y'], 1), p['fromSlot'])
                     for p in self.pings}
        new_pings = []
        for pd in data.get('pg', []):
            new_pings.append({'x': pd['x'], 'y': pd['y'],
                              'fromSlot': pd['c'], 'life': pd['l']})
        self.pings = new_pings
        for pg in new_pings:
            key = (round(pg['x'], 1), round(pg['y'], 1), pg['fromSlot'])
            if key not in prev_keys and self._pingVisibleToMe(pg):
                try:
                    from src import audio
                    audio.play_sfx('click')
                except Exception:
                    pass
                break   # one beep per snapshot is enough

    def run(self):
        from src.game.menu import PauseMenu
        while self.running:
            self._frameCount += 1
            aiLogSetFrame(self._frameCount)
            self._handleEvents()

            if self._paused:
                self._paused = False
                bg     = self.screen.copy()
                result = PauseMenu(self.screen, self.clock, bg).run()
                if result == 'quit':
                    self._quitGame = True
                    self.running   = False
                elif result == 'menu':
                    self.running = False
                elif result == 'surrender':
                    self._surrender()
                # 'resume' → just continue the loop
                continue

            self._update()
            self._draw()

            # When someone has won, hold the banner for a short grace period
            # and then exit back to the lobby / main menu automatically.
            if self.winner is not None:
                if self._postGameFrames == 0:
                    from src import audio
                    audio.play_sfx('victory' if self.winner == self.mySide
                                   else 'defeat')
                self._postGameFrames += 1
                if self._postGameFrames >= self._POSTGAME_HOLD:
                    result = self._showResultsScreen()
                    if result == 'quit':
                        self._quitGame = True
                    self.running = False

            self.clock.tick(FPS)
        aiLogWrite()
        return 'quit' if self._quitGame else 'menu'

    def _update(self):
        # ── Multiplayer client: no simulation, just apply snapshots ──────────
        if self.netRole == 'client':
            self._clientTick()
            return

        # Host: process any pending client commands BEFORE the tick so a move
        # issued this frame is visible in the snapshot we emit at the end.
        if self.netRole == 'host':
            self._drainClientCommands()

        if self.freezeTimer > 0:
            self.freezeTimer -= 1
            if self.gamemode == 'LAST_STAND':
                # Let player reposition units freely during the planning phase
                for u in self.units:
                    if u.team == 'player':
                        u.update(self.units, [], [], self.terrain)
            # Keep the client in sync even during planning so their preview
            # move orders + countdown update visibly (low rate — nothing moves).
            if self.netRole == 'host' and self.session and self.session.alive \
                    and self._frameCount % self._snapEveryFreeze == 0:
                self._sendSnapshot()
            return

        # ── Last Stand: wave spawning ────────────────────────────────────────
        if self.gamemode == 'LAST_STAND' and self.winner is None:
            enemies = [u for u in self.units if u.team == 'enemy']
            if self._waveNumber == 0:
                # First wave: brief countdown after planning ends
                self._waveTimer += 1
                if self._waveTimer >= self._FIRST_WAVE:
                    self._waveTimer = 0
                    self._spawnWave()
            elif not enemies:
                # All enemies defeated — count down to next wave
                self._waveTimer += 1
                if self._waveTimer >= self._INTER_WAVE:
                    self._waveTimer = 0
                    self._spawnWave()
            else:
                # Enemies still alive — hold timer at 0
                self._waveTimer = 0

        _advanceGridFrame()
        dead = [u for u in self.units if u.hp <= 0]
        for d in dead:
            self._casualties[d.team] += 1
            self._notifyAllyDeath(d)
            if d.team == 'enemy':
                if hasattr(self.ai, 'recordCasualty'):
                    self.ai.recordCasualty(d.x, d.y)
                for _bai in self.botAIs:
                    _bai.recordCasualty(d.x, d.y)
        self.units         = [u for u in self.units         if u.hp > 0]
        self.selectedUnits = [u for u in self.selectedUnits if u.hp > 0]

        # Pre-split by team once — avoids O(n) filter inside every unit's update()
        _player_units = [u for u in self.units if u.team == 'player']
        _enemy_units  = [u for u in self.units if u.team == 'enemy']
        _team_foes    = {'player': _enemy_units, 'enemy': _player_units}
        for u in self.units:
            u.update(self.units, self.projectiles, self.effects, self.terrain,
                     enemies=_team_foes.get(u.team))
        self._applyCommanderAura()
        for p in self.projectiles:
            p.update(self.effects, self.units)
        self.projectiles = [p for p in self.projectiles if not p.done]
        for e in self.effects:
            e.update()
        self.effects = [e for e in self.effects if not e.done]

        for op in self.outposts:
            op.update(self.units)
        self._updateOutpostSpawns()
        self._tickBattleBanner()
        self._tickPings()
        # Supply recalculated every 20 frames — values change slowly
        if self._frameCount % 20 == 0:
            self._computeSupply()
        # AI runs every other frame — decisions at 30 Hz is indistinguishable from 60 Hz
        if self._frameCount % 2 == 0:
            if self.ai is not None:
                self.ai.update()
            for _bai in self.botAIs:
                _bai.update()

        if self.winner is None:
            self._checkWinCondition()

        # Multiplayer host: broadcast a snapshot a few times per second.
        if self.netRole == 'host' and self.session and self.session.alive \
                and self._frameCount % self._snapEvery == 0:
            self._sendSnapshot()

    def _computeSupply(self):
        SUPPLY_FALLOFF = 300
        grid     = getattr(self, '_terrGrid',     {})
        gridCELL = getattr(self, '_terrGridCELL', 14)
        teamCode = {'player': 'P', 'enemy': 'E'}

        for u in self.units:
            # Unit standing in its own territory → always full supply
            gx, gy = int(u.x) // gridCELL, int(u.y) // gridCELL
            if grid.get((gx, gy)) == teamCode.get(u.team):
                u.supplyStrength = 1.0
                continue

            sources = [(hq.x, hq.y) for hq in self.headquarters if hq.team == u.team]
            sources += [(op.x, op.y) for op in self.outposts    if op.team == u.team]

            if not sources:
                u.supplyStrength = 0.0
            else:
                nearestDist = min(math.hypot(u.x - sx, u.y - sy) for sx, sy in sources)
                if nearestDist <= TERR_CLAIM_RADIUS:
                    u.supplyStrength = 1.0
                else:
                    u.supplyStrength = max(
                        0.0, 1.0 - (nearestDist - TERR_CLAIM_RADIUS) / SUPPLY_FALLOFF)

    def _applyCommanderAura(self):
        """Boost morale and HP of units close to a friendly commander.
        Works in every gamemode whenever a commander unit is on the field."""
        from src.constants import (COMMANDER_AURA_RADIUS,
                                   COMMANDER_MORALE_BOOST,
                                   COMMANDER_HP_BOOST)
        commanders = [u for u in self.units if u.unitType == 'commander']
        if not commanders:
            return
        for cmd in commanders:
            for u in self.units:
                if u is cmd or u.team != cmd.team:
                    continue
                if math.hypot(u.x - cmd.x, u.y - cmd.y) > COMMANDER_AURA_RADIUS:
                    continue
                # Morale boost: pushes toward 100 faster
                u.morale = min(100.0, u.morale + COMMANDER_MORALE_BOOST)
                # HP regen: only when below max
                if u.hp < u.maxHp:
                    u.hp = min(u.maxHp, u.hp + COMMANDER_HP_BOOST)

    def _checkWinCondition(self):
        playerHq = next((h for h in self.headquarters if h.team == 'player'), None)
        enemyHq  = next((h for h in self.headquarters if h.team == 'enemy'),  None)

        for hq in self.headquarters:
            hq.update(self.units)

        # COMMANDER mode: win by killing the enemy commander
        if self.gamemode == 'COMMANDER':
            player_cmd = next((u for u in self.units
                               if u.team == 'player' and u.unitType == 'commander'), None)
            enemy_cmd  = next((u for u in self.units
                               if u.team == 'enemy'  and u.unitType == 'commander'), None)
            if player_cmd is None:
                self.winner = 'enemy'
            elif enemy_cmd is None:
                self.winner = 'player'
            return

        # Player always loses if army is wiped out; HQ capture only counts outside Conquest
        hq_loss = self.gamemode != 'CONQUEST' and playerHq and playerHq.captured
        if not any(u.team == 'player' for u in self.units) or hq_loss:
            self.winner = 'enemy'
            return

        if self.gamemode == 'LAST_STAND':
            # Player can never "win" — they just survive as long as possible.
            # Defeat handled above.
            return

        if self.gamemode == 'ASSAULT':
            # Win = capture EVERY keypoint AND the enemy HQ. No timers, no
            # partial dominance. Also win by total annihilation as a fallback.
            keypoints = [op for op in self.outposts if op.strategic]
            all_taken = keypoints and all(op.team == 'player' for op in keypoints)
            hq_taken  = enemyHq and enemyHq.captured
            if all_taken and hq_taken:
                self.winner = 'player'
                return
            if not any(u.team == 'enemy' for u in self.units):
                self.winner = 'player'
            return

        if self.gamemode == 'CONQUEST':
            # Each outpost owned scores 1 point/second for its team.
            for op in self.outposts:
                if op.team == 'player':
                    self._conquestScore['player'] += 1 / FPS
                elif op.team == 'enemy':
                    self._conquestScore['enemy'] += 1 / FPS
            if self._conquestScore['player'] >= self._CONQUEST_WIN:
                self.winner = 'player'
            elif self._conquestScore['enemy'] >= self._CONQUEST_WIN:
                self.winner = 'enemy'
            # Annihilation only — HQ capture does NOT count in Conquest
            elif not any(u.team == 'enemy' for u in self.units):
                self.winner = 'player'
            return

        # STANDAARD
        if not any(u.team == 'enemy' for u in self.units) or (enemyHq and enemyHq.captured):
            self.winner = 'player'

    # Combined score = kill_efficiency * 0.55 + survival_rate * 0.45
    # kill_efficiency = min(e_killed / max(p_lost, 1), 4) / 4   → 0.0–1.0
    # survival_rate   = 1 - p_lost / p_start                    → 0.0–1.0
    _STAR3_SCORE = 0.55
    _STAR2_SCORE = 0.30

    def calcStars(self) -> int:
        """1-3 stars based on combined kill-efficiency + survival score. 0 if lost."""
        if self.winner != 'player':
            return 0
        p_lost  = self._casualties.get('player', 0)
        e_lost  = self._casualties.get('enemy',  0)
        p_start = max(1, self._startCounts.get('player', 1))
        eff   = min(e_lost / max(p_lost, 1), 4.0) / 4.0
        surv  = max(0.0, 1.0 - p_lost / p_start)
        score = eff * 0.55 + surv * 0.45
        if score >= self._STAR3_SCORE:
            return 3
        if score >= self._STAR2_SCORE:
            return 2
        return 1

    def _showResultsScreen(self):
        """Blocking pygame loop — shows battle stats with animated star reveal, returns 'menu' or 'quit'."""
        import math as _math
        import pygame as _pg
        from src.game.menu._common import _font, _GOLD, _GOLD_LIGHT, _PARCHMENT, _MUTED

        def _draw_star(surf, scx, scy, r_outer, r_inner, color):
            pts = []
            for i in range(10):
                angle = _math.radians(-90 + i * 36)
                r = r_outer if i % 2 == 0 else r_inner
                pts.append((scx + r * _math.cos(angle), scy + r * _math.sin(angle)))
            if r_outer >= 2:
                _pg.draw.polygon(surf, color, pts)

        won       = self.winner == self.mySide
        dur_s     = self._frameCount // FPS
        mins, sec = dur_s // 60, dur_s % 60
        stars     = self.calcStars() if won else 0

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        extra_h   = 30 if self.gamemode == 'CONQUEST' else 0
        extra_h  += 80 if won else 0
        panel_w   = 500
        panel_h   = 330 + extra_h
        panel     = _pg.Rect(cx - panel_w // 2, cy - panel_h // 2, panel_w, panel_h)
        btn_rect  = _pg.Rect(cx - 130, panel.bottom - 62, 260, 46)

        overlay = _pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), _pg.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        bg_snap = self.screen.copy()

        # Star animation — each star starts at a different delay (frames)
        STAR_DELAYS   = [45, 90, 135]
        ANIM_FRAMES   = 36
        LABEL_DELAY   = (STAR_DELAYS[stars - 1] + ANIM_FRAMES + 15) if (won and stars > 0) else 0
        anim_frame    = 0
        anim_done     = not won

        COL_LIT  = (255, 210, 40)
        COL_DIM  = (90,  80,  60)
        COL_GLOW = (255, 240, 130)
        R_OUTER  = 28
        R_INNER  = 12

        while True:
            mx, my = _pg.mouse.get_pos()
            click  = False
            for ev in _pg.event.get():
                if ev.type == _pg.QUIT:
                    return 'quit'
                if ev.type == _pg.KEYDOWN and ev.key in (
                        _pg.K_RETURN, _pg.K_SPACE, _pg.K_ESCAPE):
                    if not anim_done:
                        anim_done = True
                        anim_frame = 9999
                    else:
                        return 'menu'
                if ev.type == _pg.MOUSEBUTTONDOWN and ev.button == 1:
                    click = True
            if click:
                if not anim_done:
                    anim_done = True
                    anim_frame = 9999
                elif btn_rect.collidepoint(mx, my):
                    return 'menu'

            anim_frame += 1
            if won and anim_frame >= LABEL_DELAY + 25:
                anim_done = True

            # ── Draw ─────────────────────────────────────────────────────────
            self.screen.blit(bg_snap, (0, 0))
            self.screen.blit(overlay, (0, 0))

            _pg.draw.rect(self.screen, (244, 236, 219), panel, border_radius=8)
            _pg.draw.rect(self.screen, _GOLD, panel, 2, border_radius=8)

            # Title
            title     = "VICTORY!" if won else "DEFEAT!"
            title_col = (80, 220, 100) if won else (220, 80, 80)
            tf  = _font(52, bold=True)
            ts  = tf.render(title, True, title_col)
            sh  = tf.render(title, True, (0, 0, 0))
            self.screen.blit(sh, (cx - ts.get_width() // 2 + 2, panel.y + 17))
            self.screen.blit(ts, (cx - ts.get_width() // 2,     panel.y + 15))

            # Duration
            dur = _font(17).render(
                f"Battle duration:  {mins}m {sec:02d}s", True, _PARCHMENT)
            self.screen.blit(dur, (cx - dur.get_width() // 2, panel.y + 82))

            _pg.draw.line(self.screen, _GOLD,
                          (panel.x + 20, panel.y + 106),
                          (panel.right - 20, panel.y + 106))

            # Stats table
            ty    = panel.y + 116
            hf    = _font(15, bold=True)
            sf    = _font(15)
            col_l = panel.x + 36
            col_p = cx - 40
            col_e = cx + 90

            self.screen.blit(hf.render("",      True, _GOLD_LIGHT),     (col_l, ty))
            self.screen.blit(hf.render("You",   True, (80,  140, 220)), (col_p, ty))
            self.screen.blit(hf.render("Enemy", True, (220,  80,  80)), (col_e, ty))
            ty += 22

            p_start = self._startCounts.get('player', 0)
            e_start = self._startCounts.get('enemy',  0)
            p_lost  = self._casualties.get('player',  0)
            e_lost  = self._casualties.get('enemy',   0)

            for label, pv, ev in [
                ("Started",   p_start,           e_start),
                ("Lost",      p_lost,             e_lost),
                ("Remaining", p_start - p_lost,   e_start - e_lost),
            ]:
                self.screen.blit(sf.render(label,   True, _MUTED),     (col_l, ty))
                self.screen.blit(sf.render(str(pv), True, _PARCHMENT), (col_p, ty))
                self.screen.blit(sf.render(str(ev), True, _PARCHMENT), (col_e, ty))
                ty += 22

            if self.gamemode == 'CONQUEST':
                ty += 4
                _pg.draw.line(self.screen, (180, 160, 120),
                              (col_l, ty), (panel.right - 36, ty))
                ty += 6
                ps = int(self._conquestScore.get('player', 0))
                es = int(self._conquestScore.get('enemy',  0))
                self.screen.blit(sf.render("Conquest pts", True, _MUTED),           (col_l, ty))
                self.screen.blit(sf.render(f"{ps} / {self._CONQUEST_WIN}",
                                           True, _PARCHMENT), (col_p, ty))
                self.screen.blit(sf.render(f"{es} / {self._CONQUEST_WIN}",
                                           True, _PARCHMENT), (col_e, ty))
                ty += 22

            # ── Animated star rating ──────────────────────────────────────────
            if won:
                ty += 8
                _pg.draw.line(self.screen, _GOLD,
                              (panel.x + 20, ty), (panel.right - 20, ty))
                ty += 10

                # Star requirements hint
                _pl = self._casualties.get('player', 0)
                _el = self._casualties.get('enemy',  0)
                _ps = max(1, self._startCounts.get('player', 1))
                _eff  = min(_el / max(_pl, 1), 4.0) / 4.0
                _surv = max(0.0, 1.0 - _pl / _ps)
                _score = _eff * 0.55 + _surv * 0.45
                req_f = _font(12)
                self.screen.blit(req_f.render(
                    f"Score: {_score:.2f}  (kill eff: {_eff:.2f}  survival: {_surv:.2f})",
                    True, _MUTED), (col_l, ty))
                self.screen.blit(req_f.render(
                    f"3★ needs {self._STAR3_SCORE}   2★ needs {self._STAR2_SCORE}",
                    True, (150, 140, 100)), (col_l, ty + 14))
                ty += 30

                star_cy  = ty + 30
                star_gap = 72
                star_xs  = [cx - star_gap, cx, cx + star_gap]

                for i in range(3):
                    sx  = star_xs[i]
                    f   = anim_frame - STAR_DELAYS[i]
                    lit = (i < stars)

                    if not lit:
                        # Unearned — static dim
                        _draw_star(self.screen, sx, star_cy, R_OUTER, R_INNER, COL_DIM)
                    elif f < 0:
                        # Earned but not yet revealed — dim placeholder
                        _draw_star(self.screen, sx, star_cy, R_OUTER, R_INNER, COL_DIM)
                    elif f >= ANIM_FRAMES:
                        # Settled
                        _draw_star(self.screen, sx, star_cy, R_OUTER, R_INNER, COL_LIT)
                    else:
                        # Bounce: 0→1.4→0.9→1.05→1.0
                        t = f / ANIM_FRAMES
                        if t < 0.28:
                            scale = t / 0.28 * 1.4
                        elif t < 0.55:
                            scale = 1.4 - (t - 0.28) / 0.27 * 0.5
                        elif t < 0.75:
                            scale = 0.9 + (t - 0.55) / 0.20 * 0.15
                        else:
                            scale = 1.05 - (t - 0.75) / 0.25 * 0.05
                        ro = max(2, int(R_OUTER * scale))
                        ri = max(1, int(R_INNER * scale))
                        # Glow burst while overshooting
                        if scale > 1.0:
                            glow_r = int(ro * 1.45)
                            gs = _pg.Surface((glow_r * 2 + 4, glow_r * 2 + 4), _pg.SRCALPHA)
                            alpha = int(200 * min(1.0, (scale - 1.0) / 0.4))
                            _pg.draw.circle(gs, (*COL_GLOW, alpha),
                                            (glow_r + 2, glow_r + 2), glow_r)
                            self.screen.blit(gs, (sx - glow_r - 2, star_cy - glow_r - 2))
                        _draw_star(self.screen, sx, star_cy, ro, ri,
                                   COL_GLOW if scale > 1.02 else COL_LIT)

                # Label fades in after all earned stars have settled
                if anim_frame >= LABEL_DELAY:
                    fade   = min(1.0, (anim_frame - LABEL_DELAY) / 20)
                    lbl_s  = _font(17, bold=True).render(
                        {3: "Perfect!", 2: "Good", 1: "Completed"}.get(stars, ""),
                        True, COL_LIT)
                    lbl_s.set_alpha(int(fade * 255))
                    self.screen.blit(lbl_s, (cx - lbl_s.get_width() // 2, star_cy + 40))

            # ── Continue button (visible after animation, or immediately on defeat) ──
            if anim_done or not won:
                hover   = btn_rect.collidepoint(mx, my)
                btn_col = (210, 195, 170) if hover else (185, 170, 148)
                _pg.draw.rect(self.screen, btn_col,  btn_rect, border_radius=6)
                _pg.draw.rect(self.screen, _GOLD_LIGHT if hover else _GOLD,
                              btn_rect, 2, border_radius=6)
                btn_txt = _font(20, bold=True).render("Continue  →", True, _GOLD_LIGHT)
                self.screen.blit(btn_txt, (
                    cx - btn_txt.get_width() // 2,
                    btn_rect.centery - btn_txt.get_height() // 2))

            _pg.display.flip()
            self.clock.tick(FPS)

    def _notifyAllyDeath(self, deadUnit):
        for u in self.units:
            if u.team == deadUnit.team and not u.routing:
                dist = math.hypot(u.x - deadUnit.x, u.y - deadUnit.y)
                if dist < 160:
                    u.loseMorale(12)

    def _moveSelected(self, pos):
        if not self.selectedUnits:
            return
        mx, my = pos
        self._prepForRedeploy(self.selectedUnits)
        cx = sum(u.x for u in self.selectedUnits) / len(self.selectedUnits)
        cy = sum(u.y for u in self.selectedUnits) / len(self.selectedUnits)
        for u in self.selectedUnits:
            u.patrolPath = []
            u.targetX = mx + (u.x - cx)
            u.targetY = my + (u.y - cy)
