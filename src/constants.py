# Module: constants
# All game-wide constants, colors, and unit statistics

SCREEN_WIDTH  = 1280
SCREEN_HEIGHT = 720
FPS           = 60
TITLE         = "Nerds ad War"

# Logical map size — larger than the screen; rendered scaled-to-fit
MAP_WIDTH  = 1920
MAP_HEIGHT = 1080

# Colors
BG_COLOR       = (74, 117, 44)
WHITE          = (255, 255, 255)
BLACK          = (0,   0,   0)
YELLOW         = (255, 255, 0)
SELECTION_FILL = (255, 255, 0, 40)

UNIT_COLORS = {
    'player': {
        'infantry':       (70,  130, 180),
        'heavy_infantry': (30,   80, 140),
        'cavalry':        (30,  144, 255),
        'artillery':      (0,    80, 200),
        'commander':      (40,   60, 120),
    },
    'enemy': {
        'infantry':       (220, 80,  80),
        'heavy_infantry': (160, 40,  40),
        'cavalry':        (200, 40,  40),
        'artillery':      (150, 0,   0),
        'commander':      (140, 30,  30),
    },
}

# Commander aura constants
COMMANDER_AURA_RADIUS  = 160   # px — radius of the morale/hp aura
COMMANDER_MORALE_BOOST = 0.12  # extra morale regen per frame for nearby allies
COMMANDER_HP_BOOST     = 0.012 # extra HP regen per frame for nearby allies (≈0.7 HP/s)

# Territory: how far from a friendly supply source a cell is considered "owned"
TERR_CLAIM_RADIUS = 220

# ── Multiplayer player colors ────────────────────────────────────────────────
# Each slot in MP picks a "paint" from this palette; the renderer shades the
# unit variants (heavy/cav/art) relative to the chosen base color.
# Quick-chat emote bubbles used in multiplayer scoreboard rows.
# Pressed via T-held + number key (1..len).
EMOTE_TEXTS = ["GG", "WP", "?!", "Help!", ":)", ">:("]


# Single source of truth for match-mode → slot count. Used by the lobby
# (server slot caps, UI layout, default-colour table) and by Game (slot ↔
# side mapping, spawn scaling, controller assignment).
MODE_SLOT_COUNT = {'1v1': 2, 'COOP': 2, '2v2': 4, '3v3': 6, '4v4': 8}

def slotCountForMode(mode):
    return MODE_SLOT_COUNT.get(mode, 2)

def teamOfSlot(slot, mode):
    """Return 'player' (first half of slots) or 'enemy' (second half).
    COOP pushes every human slot into the player team; AI drives enemy."""
    if mode == 'COOP':
        return 'player'
    n = slotCountForMode(mode)
    return 'player' if slot < n // 2 else 'enemy'


PLAYER_COLORS = [
    ('BLAUW',    (40,  100, 230)),   # deep saturated blue (was te zacht, leek op turkoois)
    ('ROOD',     (215,  45,  55)),   # zuiver rood (minder oranje-zweem)
    ('GROEN',    (50,  175,  70)),   # zuiver groen
    ('GEEL',     (245, 220,  50)),   # helder geel (verder van oranje af)
    ('PAARS',    (130,  55, 195)),   # diepere violet (verder van roze af)
    ('ORANJE',   (245, 125,  20)),   # vol oranje (verder van rood/geel af)
    ('TURKOOIS', (40,  205, 215)),   # cyaan-aqua (duidelijk losser van blauw)
    ('ROZE',     (240,  90, 180)),   # magenta-roze (verder van paars af)
]

def unitColorFromBase(base, unitType):
    """Return a shade of `base` (r,g,b) appropriate for a given unit type.
    Infantry uses the base, heavy gets darker, cavalry brighter, artillery
    the darkest — mirroring the feel of the default blue/red palette."""
    r, g, b = base
    if unitType == 'heavy_infantry':
        f = 0.60
        return (int(r * f), int(g * f), int(b * f))
    if unitType == 'commander':
        f = 0.45   # darkest shade — commands attention
        return (int(r * f), int(g * f), int(b * f))
    if unitType == 'cavalry':
        # Push toward pure saturation without blowing out
        f = 1.10
        return (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)))
    if unitType == 'artillery':
        f = 0.42
        return (int(r * f), int(g * f), int(b * f))
    return base  # infantry

# speed, attackRange, damage, hp, attackRate (frames), radius
UNIT_STATS = {
    'infantry':       (0.5,   100, 15, 100,  60,  8),
    'heavy_infantry': (0.38,   55, 28, 180,  72, 13),
    'cavalry':        (0.85,   26, 35,  80,  45, 10),
    'artillery':      (0.45,  260, 60,  60, 120, 12),
    'commander':      (0.38,   60, 22, 240,  68, 14),
    # Commander: heavy-infantry speed, slightly longer range than heavy,
    # less damage (support role), tankiest unit in the game (240 HP).
}
