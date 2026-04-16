# Module: game
# Game class — orchestrates the main loop, update logic and unit management

import math
import random

import pygame

from src.constants import (SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
                           TERR_CLAIM_RADIUS, MAP_WIDTH, MAP_HEIGHT,
                           PLAYER_COLORS, UNIT_COLORS, unitColorFromBase)
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


class Game(EventsMixin, FormationMixin, RendererMixin):
    def __init__(self, seed=42, screen=None, clock=None, biome=None, difficulty='NORMAAL',
                 gamemode='STANDAARD', netRole=None, session=None,
                 sessions=None, mode='1v1', mySlot=0, slotNames=None,
                 slotColors=None, customMap=None,
                 forces=None, aiPersonality=None, botSlots=None):
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
        self._POSTGAME_HOLD  = FPS * 6   # 6 seconds

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

        # AI: single-player always, MP host in COOP (AI plays the enemy team).
        # Client never runs AI — it only mirrors host snapshots.
        spawn_ai = self.netRole is None or \
                   (self.netRole == 'host' and self.matchMode == 'COOP')
        if spawn_ai:
            self.ai = EnemyAI(self, difficulty=difficulty)
            if self.aiPersonalityOverride:
                self.ai._personality = self.aiPersonalityOverride
        else:
            self.ai = None

        # Bot AIs for any enemy-side slots filled with a bot in 2v2/3v3/4v4.
        # The proxy restricts the AI to units owned by those slots so the
        # human teammates remain in command of their own units.
        self.botAIs = []
        if (self.netRole in (None, 'host') and self.botSlots
                and self.matchMode in ('2v2', '3v3', '4v4')):
            enemy_team_slots = set(self._teamSlots('enemy'))
            enemy_bots = {s for s in self.botSlots if s in enemy_team_slots}
            if enemy_bots:
                proxy   = _BotGameProxy(self, enemy_bots)
                bot_ai  = EnemyAI(proxy, difficulty=difficulty)
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
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 20, 10, 10, 4
        elif per_side == 3:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 18,  9,  9, 3
        elif per_side == 2:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 15,  8,  8, 4
        else:
            INF_ROWS, CAV_COUNT, HVY_COUNT, ART_COUNT = 10,  5,  5, 2
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
        side_slots = {
            'player': self._teamSlots('player'),
            'enemy':  self._teamSlots('enemy'),
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

        # Gradual escalation — starts small, grows each wave
        # Wave 1: 4 inf | Wave 3: 8+2cav | Wave 5: 12+4cav+2hvy | Wave 7+: adds art
        composition = {
            'infantry':       2 + n * 2,
            'cavalry':        max(0, n - 2),
            'heavy_infantry': max(0, n - 4),
            'artillery':      max(0, n - 6),
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

    def _teamCap(self, team: str) -> int:
        """Max units a team is allowed to field at once. Prevents outpost
        spawning from piling up indefinitely."""
        return 80 if self.matchMode in ('2v2', 'COOP') else 55

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

            # Respect team cap
            team_count = sum(1 for u in self.units if u.team == op.team)
            if team_count >= self._teamCap(op.team):
                continue

            utype = self._pickSpawnUnitType()
            offX  = random.uniform(-24, 24)
            offY  = random.uniform(-24, 24)
            u = Unit(op.x + offX, op.y + offY, op.team, utype)

            # Round-robin so every teammate gets an equal share of output.
            team_slots = self._teamSlots(op.team) or [0]
            op._spawnRot = (getattr(op, '_spawnRot', -1) + 1) % len(team_slots)
            u.controller = team_slots[op._spawnRot]

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
        from src.constants import slotCountForMode
        return slotCountForMode(self.matchMode)

    def _activeSlots(self):
        return list(range(self._modeSlotCount()))

    def _teamSlots(self, team):
        """Slot indices belonging to a given team for the current matchMode.
        COOP is a special case: both humans share the player team, the enemy
        side is AI-driven (no human slot)."""
        if self.matchMode == 'COOP':
            return [0, 1] if team == 'player' else []
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
        projs = [{'x': round(p.x, 1), 'y': round(p.y, 1), 'k': p.type}
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
        self.freezeTimer = data.get('fz', 0)
        self.winner      = data.get('w')

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
            p.type   = pd['k']
            style    = Projectile.STYLES.get(p.type, Projectile.STYLES['musket'])
            p.radius = style['radius']
            p.color  = style['color']
            p.done   = False
            new_projs.append(p)
        self.projectiles = new_projs

        # Effects — replace with the host's list. Local per-frame decay in
        # _clientTick keeps the animation smooth between snapshots.
        from src.entities.effect import Effect
        new_effs = []
        for ed in data.get('e', []):
            e = Effect(ed['x'], ed['y'], ed['k'])
            e.timer = ed['tm']
            new_effs.append(e)
        self.effects = new_effs

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
            self._notifyAllyDeath(d)
            if d.team == 'enemy':
                if hasattr(self.ai, 'recordCasualty'):
                    self.ai.recordCasualty(d.x, d.y)
                for _bai in self.botAIs:
                    _bai.recordCasualty(d.x, d.y)
        self.units         = [u for u in self.units         if u.hp > 0]
        self.selectedUnits = [u for u in self.selectedUnits if u.hp > 0]

        for u in self.units:
            u.update(self.units, self.projectiles, self.effects, self.terrain)
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
        self._computeSupply()
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

        # Player always loses if HQ falls or army wiped out
        if not any(u.team == 'player' for u in self.units) or (playerHq and playerHq.captured):
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

        # STANDAARD
        if not any(u.team == 'enemy' for u in self.units) or (enemyHq and enemyHq.captured):
            self.winner = 'player'

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
