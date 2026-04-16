# Module: ai_data
# Personality definitions and tactic weight tables for EnemyAI

# ── Difficulty settings ───────────────────────────────────────────────────────
# tick_interval  : frames between AI decision ticks  (lower = faster AI)
# mistake_rate   : chance [0-1] to pick a random target instead of optimal
# fallback_bonus : added to personality's fallback_ratio (positive = retreats easier)
# eval_interval  : frames between tactic re-evaluations
DIFFICULTY_SETTINGS = {
    'MAKKELIJK': {'tick_interval': 200, 'mistake_rate': 0.45, 'fallback_bonus':  0.20, 'eval_interval': 300},
    'NORMAAL':   {'tick_interval': 100, 'mistake_rate': 0.15, 'fallback_bonus':  0.00, 'eval_interval': 180},
    'MOEILIJK':  {'tick_interval':  65, 'mistake_rate': 0.05, 'fallback_bonus': -0.10, 'eval_interval': 120},
    'VETERAAN':  {'tick_interval':  35, 'mistake_rate': 0.00, 'fallback_bonus': -0.20, 'eval_interval':  80},
    'NAPOLEON':  {'tick_interval':  18, 'mistake_rate': 0.00, 'fallback_bonus': -0.35, 'eval_interval':  45},
}


# ── Personality traits ────────────────────────────────────────────────────────
# abandon_loss   : casualty-rate threshold to switch tactic
# abandon_stuck  : stuck-ticks before switching
# fallback_ratio : outnumbered ratio that triggers emergency fallback
# survival_style : 'BURST' | 'ANCHOR' | 'FADE' | 'MIXED'
PERSONALITY_TRAITS = {
    'AGGRESSIVE': {
        'abandon_loss':   0.25,
        'abandon_stuck':  3,
        'fallback_ratio': 0.50,
        'survival_style': 'BURST',
    },
    'DEFENSIVE': {
        'abandon_loss':   0.10,
        'abandon_stuck':  9,
        'fallback_ratio': 0.80,
        'survival_style': 'ANCHOR',
    },
    'OPPORTUNIST': {
        'abandon_loss':   0.14,
        'abandon_stuck':  4,
        'fallback_ratio': 0.65,
        'survival_style': 'FADE',
    },
    'BALANCED': {
        'abandon_loss':   0.18,
        'abandon_stuck':  6,
        'fallback_ratio': 0.72,
        'survival_style': 'MIXED',
    },
}


# ── Tactic weights per personality ───────────────────────────────────────────
PERSONALITIES = {
    'AGGRESSIVE': {
        'BLITZKRIEG':          10, 'PINCER':              8, 'CENTER_PUSH':          8,
        'CAVALRY_RAID':         7, 'ENCIRCLEMENT':        7, 'DOUBLE_ENVELOP':        7,
        'HAMMER_AND_ANVIL':     7, 'ECHELON':             6, 'STEAMROLLER':           5,
        'FEINT_STRIKE':         5, 'GRAND_BATTERY':       5, 'DOUBLE_OP_PRESSURE':    5,
        'REFUSE_FLANK':         4, 'SKIRMISH_SCREEN':     4, 'GUERRILLA':             3,
        'HILL_CONTROL':         3, 'OP_ISOLATION':        3, 'COUNTERATTACK':         2,
        'ARTILLERY_DOM':        2, 'BRIDGE_CONTROL':      2, 'ATTRITION':             2,
        'SUPPLY_EDGE_PRESSURE': 2, 'SIEGELINE':           1,
        'COMBINED_ARMS':        8, 'CAVALRY_EXPLOIT':     7, 'FEIGNED_RETREAT':       5,
        'COUNTER_BATTERY':      3, 'DEFENSE_IN_DEPTH':    2, 'FOREST_DELAY':          2,
        'DELAYING_ACTION':      1, 'CONTACT_AND_FADE':    1, 'MOBILE_SUPPLY_BUBBLE':  1,
    },
    'DEFENSIVE': {
        'SIEGELINE':            10, 'COUNTERATTACK':       9, 'BRIDGE_CONTROL':        8,
        'REFUSE_FLANK':          8, 'ARTILLERY_DOM':       7, 'ATTRITION':             7,
        'HILL_CONTROL':          6, 'MOBILE_SUPPLY_BUBBLE':6, 'SKIRMISH_SCREEN':       5,
        'STEAMROLLER':           4, 'FEINT_STRIKE':        4, 'GUERRILLA':             4,
        'GRAND_BATTERY':         4, 'OP_ISOLATION':        4, 'ECHELON':               3,
        'DOUBLE_ENVELOP':        3, 'PINCER':              3, 'ENCIRCLEMENT':          2,
        'CENTER_PUSH':           2, 'CAVALRY_RAID':        2, 'BLITZKRIEG':            1,
        'SUPPLY_EDGE_PRESSURE':  3, 'DOUBLE_OP_PRESSURE':  2, 'HAMMER_AND_ANVIL':      2,
        'DEFENSE_IN_DEPTH':      9, 'COUNTER_BATTERY':     7, 'FOREST_DELAY':          6,
        'FEIGNED_RETREAT':       4, 'COMBINED_ARMS':       3, 'CAVALRY_EXPLOIT':       2,
        'DELAYING_ACTION':       5, 'CONTACT_AND_FADE':    3,
    },
    'OPPORTUNIST': {
        'FEINT_STRIKE':         10, 'GUERRILLA':           9, 'HILL_CONTROL':          8,
        'ARTILLERY_DOM':         8, 'SKIRMISH_SCREEN':     7, 'CAVALRY_RAID':          7,
        'CONTACT_AND_FADE':      7, 'BRIDGE_CONTROL':      6, 'PINCER':                6,
        'ECHELON':               6, 'REFUSE_FLANK':        5, 'COUNTERATTACK':         5,
        'DOUBLE_ENVELOP':        5, 'CENTER_PUSH':         4, 'ENCIRCLEMENT':          4,
        'STEAMROLLER':           3, 'BLITZKRIEG':          3, 'SIEGELINE':             2,
        'ATTRITION':             3, 'OP_ISOLATION':        6, 'SUPPLY_EDGE_PRESSURE':  6,
        'DOUBLE_OP_PRESSURE':    6, 'GRAND_BATTERY':       4, 'HAMMER_AND_ANVIL':      4,
        'FEIGNED_RETREAT':       8, 'CAVALRY_EXPLOIT':     7, 'FOREST_DELAY':          6,
        'COUNTER_BATTERY':       5, 'COMBINED_ARMS':       4, 'DEFENSE_IN_DEPTH':      3,
        'DELAYING_ACTION':       4, 'MOBILE_SUPPLY_BUBBLE':3,
    },
    'BALANCED': {t: 5 for t in [
        'BLITZKRIEG', 'SIEGELINE', 'PINCER', 'FEINT_STRIKE', 'ARTILLERY_DOM',
        'GUERRILLA', 'REFUSE_FLANK', 'STEAMROLLER', 'CAVALRY_RAID', 'HILL_CONTROL',
        'CENTER_PUSH', 'COUNTERATTACK', 'ENCIRCLEMENT', 'BRIDGE_CONTROL',
        'SKIRMISH_SCREEN', 'ECHELON', 'DOUBLE_ENVELOP', 'ATTRITION',
        'GRAND_BATTERY', 'SUPPLY_EDGE_PRESSURE', 'OP_ISOLATION', 'DOUBLE_OP_PRESSURE',
        'HAMMER_AND_ANVIL', 'COUNTER_BATTERY', 'FEIGNED_RETREAT', 'DEFENSE_IN_DEPTH',
        'CAVALRY_EXPLOIT', 'FOREST_DELAY', 'COMBINED_ARMS',
        'DELAYING_ACTION', 'CONTACT_AND_FADE', 'MOBILE_SUPPLY_BUBBLE',
    ]},
}

ALL_TACTICS = list(PERSONALITIES['BALANCED'].keys())


# ── Counter map ───────────────────────────────────────────────────────────────
# Maps detected player behaviour → list of (tactic, weight_bonus) tuples.
# These bonuses are added on top of personality weights during tactic selection
# when a counter-switch is triggered.  They do NOT force a switch — the normal
# casualty / stuck evaluation still decides when to switch.
#
# Mapping rationale (from tactics_counters.txt):
#   CAVALRY_FORWARD     → form defensive line / squares to absorb charge
#   WIDE_LINE           → punch through the thin centre or mass artillery
#   ARTILLERY_FORWARD   → cavalry raid / blitz before they set up
#   PLAYER_ADVANCING    → counterattack when they cross the trigger line
#   PLAYER_HOLDING      → outpost pressure / supply edge to force movement
#   PLAYER_FLANKING     → refuse that flank, envelop the other side
#   PLAYER_IN_SQUARE    → grand battery / attrition (squares eat artillery)
#   SUPPLY_DEPENDENT    → cut them off from their supply bubble
#   OP_RAIDING          → defend OPs, ride to intercept

COUNTER_MAP = {
    'CAVALRY_FORWARD': [
        ('SIEGELINE',            5),
        ('HILL_CONTROL',         4),
        ('REFUSE_FLANK',         3),
        ('SKIRMISH_SCREEN',      3),
        ('BRIDGE_CONTROL',       2),
    ],
    'WIDE_LINE': [
        ('CENTER_PUSH',          5),
        ('GRAND_BATTERY',        4),
        ('HAMMER_AND_ANVIL',     4),
        ('FEINT_STRIKE',         3),
    ],
    'ARTILLERY_FORWARD': [
        ('ENCIRCLEMENT',         4),
        ('FEINT_STRIKE',         4),
        ('GRAND_BATTERY',        3),   # counter-battery from safe distance
        ('CONTACT_AND_FADE',     3),
    ],
    'PLAYER_ADVANCING': [
        ('COUNTERATTACK',        6),
        ('BRIDGE_CONTROL',       4),
        ('REFUSE_FLANK',         3),
        ('ATTRITION',            3),
    ],
    'PLAYER_HOLDING': [
        ('SUPPLY_EDGE_PRESSURE', 5),
        ('DOUBLE_OP_PRESSURE',   5),
        ('ARTILLERY_DOM',        4),
        ('OP_ISOLATION',         3),
    ],
    'PLAYER_FLANKING': [
        ('REFUSE_FLANK',         5),
        ('PINCER',               4),
        ('DOUBLE_ENVELOP',       4),
        ('CENTER_PUSH',          3),
    ],
    'PLAYER_IN_SQUARE': [
        ('GRAND_BATTERY',        7),
        ('ATTRITION',            5),
        ('ARTILLERY_DOM',        4),
        ('SKIRMISH_SCREEN',      3),
    ],
    'SUPPLY_DEPENDENT': [
        ('OP_ISOLATION',         6),
        ('DOUBLE_OP_PRESSURE',   5),
        ('CAVALRY_RAID',         4),
        ('SUPPLY_EDGE_PRESSURE', 4),
    ],
    'OP_RAIDING': [
        ('SIEGELINE',            4),
        ('COUNTERATTACK',        4),
        ('CAVALRY_RAID',         4),   # race them to objectives
        ('SKIRMISH_SCREEN',      3),
    ],
    'RIVER_DEFENSE': [
        ('BRIDGE_CONTROL',       8),   # seize the bridges — don't wade into the water
        ('ARTILLERY_DOM',        6),   # bombard safely from our bank
        ('FEINT_STRIKE',         5),   # fake one bridge, real crossing at other
        ('GRAND_BATTERY',        5),   # soften the defenders before any crossing
        ('ATTRITION',            4),   # grind them at range, no frontal river assault
    ],
    'PLAYER_HOLDS_CHOKE': [
        ('GRAND_BATTERY',        7),   # bombard the funnel from safe range
        ('COUNTER_BATTERY',      5),   # if they brought guns, kill them first
        ('ARTILLERY_DOM',        6),   # sustained shelling on the chokepoint
        ('ENCIRCLEMENT',         5),   # go around — don't push through
        ('DOUBLE_ENVELOP',       5),
        ('PINCER',               4),
        ('FEINT_STRIKE',         4),   # fake the chokepoint, hit elsewhere
        ('CAVALRY_EXPLOIT',      3),   # cavalry around the flank
        ('REFUSE_FLANK',         3),   # screen the choke, fight on the other side
    ],
    'FORTIFIED_RIVER': [
        ('COUNTER_BATTERY',     10),   # destroy their artillery first
        ('GRAND_BATTERY',        9),   # artillery duel — clear bridge defenders
        ('BRIDGE_CONTROL',       8),   # then cross at the bridge with infantry
        ('ARTILLERY_DOM',        7),   # sustained bombardment from safe side
        ('COMBINED_ARMS',        5),   # phased assault after softening
        ('FEINT_STRIKE',         4),   # feint one bridge, cross the other
    ],
}


# ── Biome tactic modifiers ────────────────────────────────────────────────────
# Weight bonuses/penalties applied based on the biome the game is played in.
# Positive = favoured, negative = suppressed (clamped so weight never goes < 1).

BIOME_MODIFIERS = {
    'GRASSLAND': {
        # Open terrain: formation tactics, cavalry charges, steamroller lines
        'STEAMROLLER': 5, 'ECHELON': 4, 'DOUBLE_ENVELOP': 4, 'PINCER': 3,
        'BLITZKRIEG': 3, 'HAMMER_AND_ANVIL': 3, 'CAVALRY_EXPLOIT': 3,
        # No natural cover — avoid guerrilla / forest tactics
        'GUERRILLA': -5, 'FOREST_DELAY': -8, 'BRIDGE_CONTROL': -8,
    },
    'RIVER_VALLEY': {
        # Bridge control is king; crossing tactics vital
        'BRIDGE_CONTROL': 8, 'COMBINED_ARMS': 5, 'ARTILLERY_DOM': 4,
        'COUNTER_BATTERY': 3, 'GRAND_BATTERY': 3, 'FEINT_STRIKE': 3,
        # Don't blindly rush across — penalise open charges
        'BLITZKRIEG': -4, 'CAVALRY_RAID': -3, 'STEAMROLLER': -3,
    },
    'LAKELANDS': {
        # Lakes create natural chokepoints — control them
        'SIEGELINE': 5, 'COUNTERATTACK': 5, 'ATTRITION': 4,
        'REFUSE_FLANK': 4, 'ARTILLERY_DOM': 3, 'DEFENSE_IN_DEPTH': 3,
        # Wide sweeping manoeuvres fail around lakes
        'ENCIRCLEMENT': -4, 'DOUBLE_ENVELOP': -3, 'PINCER': -3,
    },
    'HIGHLANDS': {
        # Hills everywhere — dominate high ground
        'HILL_CONTROL': 8, 'ARTILLERY_DOM': 6, 'SIEGELINE': 4,
        'GRAND_BATTERY': 4, 'ATTRITION': 3, 'DEFENSE_IN_DEPTH': 3,
        # Cavalry charges uphill are risky
        'BLITZKRIEG': -3, 'CAVALRY_RAID': -2,
    },
    'FOREST': {
        # Dense forest — ambushes, guerrilla, concealment
        'GUERRILLA': 8, 'FOREST_DELAY': 6, 'SKIRMISH_SCREEN': 5,
        'CONTACT_AND_FADE': 4, 'FEINT_STRIKE': 4, 'DEFENSE_IN_DEPTH': 3,
        # Artillery has poor LOS; wide formations get lost in trees
        'ARTILLERY_DOM': -4, 'GRAND_BATTERY': -3, 'STEAMROLLER': -3,
        'DOUBLE_ENVELOP': -2,
    },
    'MIXED': {
        # Balanced — slight combined-arms bonus
        'COMBINED_ARMS': 4, 'REFUSE_FLANK': 2, 'FEINT_STRIKE': 2,
    },
    'DRY_PLAINS': {
        # Rocky open terrain — formation warfare, use rocks as cover
        'STEAMROLLER': 4, 'ECHELON': 4, 'SIEGELINE': 3,
        'COUNTERATTACK': 3, 'HILL_CONTROL': 3, 'HAMMER_AND_ANVIL': 3,
        # No water, no forest — those tactics useless
        'BRIDGE_CONTROL': -8, 'GUERRILLA': -4, 'FOREST_DELAY': -8,
    },
    'TWIN_RIVERS': {
        # Two river crossings — bridge control on both, combined arms push
        'BRIDGE_CONTROL': 8, 'COMBINED_ARMS': 5, 'SIEGELINE': 4,
        'ARTILLERY_DOM': 4, 'FEINT_STRIKE': 4, 'DEFENSE_IN_DEPTH': 3,
        # Wide flanks are hard with two rivers in the way
        'ENCIRCLEMENT': -4, 'DOUBLE_ENVELOP': -3, 'BLITZKRIEG': -3,
        'CAVALRY_RAID': -3,
    },
}

# ── Terrain trait bonuses ────────────────────────────────────────────────────
# Applied dynamically based on analyzed terrain traits (openness, chokepoints, etc.)
# Format: list of (condition_fn, tactic_bonuses_dict)
# condition_fn receives the terrain traits dict from analyzeTerrain()

TERRAIN_TRAIT_BONUSES = [
    # Any chokepoint at all → start leaning toward chokepoint-exploitation tactics
    (lambda t: t['n_chokepoints'] >= 1, {
        'SIEGELINE': 3, 'COUNTERATTACK': 2, 'ARTILLERY_DOM': 2,
        'GRAND_BATTERY': 2,
        'ENCIRCLEMENT': -2, 'DOUBLE_ENVELOP': -2,
    }),
    # Many chokepoints → strongly favour defensive chokepoint tactics
    (lambda t: t['n_chokepoints'] >= 2, {
        'SIEGELINE': 4, 'COUNTERATTACK': 4, 'DEFENSE_IN_DEPTH': 4,
        'ATTRITION': 3, 'ARTILLERY_DOM': 2,
        'ENCIRCLEMENT': -2, 'DOUBLE_ENVELOP': -2,
    }),
    # A chokepoint on our own half → must hold it (defensive deep-line bonus)
    (lambda t: len(t.get('chokes_own', [])) >= 1, {
        'SIEGELINE': 3, 'DEFENSE_IN_DEPTH': 3, 'COUNTERATTACK': 2,
        'BRIDGE_CONTROL': 2,
    }),
    # A chokepoint in the contested middle → race to seize it offensively
    (lambda t: len(t.get('chokes_mid', [])) >= 1, {
        'CENTER_PUSH': 4, 'HAMMER_AND_ANVIL': 3, 'ARTILLERY_DOM': 3,
        'GRAND_BATTERY': 2, 'ECHELON': 2,
        'ENCIRCLEMENT': -3, 'DOUBLE_ENVELOP': -3,
    }),
    # Very open terrain (>50% open) → favour mass movement and cavalry
    (lambda t: t['openness'] > 0.50, {
        'STEAMROLLER': 4, 'BLITZKRIEG': 3, 'ECHELON': 3,
        'HAMMER_AND_ANVIL': 3, 'PINCER': 2, 'CAVALRY_EXPLOIT': 3,
    }),
    # Heavy forest (>20%) → guerrilla, ambush
    (lambda t: t['forest_cover'] > 0.20, {
        'GUERRILLA': 4, 'FOREST_DELAY': 3, 'SKIRMISH_SCREEN': 3,
        'CONTACT_AND_FADE': 2,
    }),
    # Heavy hills (>25%) → high ground control
    (lambda t: t['hill_cover'] > 0.25, {
        'HILL_CONTROL': 5, 'ARTILLERY_DOM': 3, 'GRAND_BATTERY': 2,
    }),
    # Lots of water (>10%) → careful, defensive
    (lambda t: t['water_cover'] > 0.10, {
        'ATTRITION': 3, 'SIEGELINE': 3, 'DEFENSE_IN_DEPTH': 2,
        'BLITZKRIEG': -3, 'CAVALRY_RAID': -2,
    }),
]


# ── Tactic avoidance map ──────────────────────────────────────────────────────
# When a behaviour is active, these tactics get their weight clamped to 1 (near-zero).
# Used to prevent the AI from charging blindly into situations it should recognise as traps.
TACTIC_AVOIDANCE = {
    'RIVER_DEFENSE': [
        'STEAMROLLER',      # would march straight into the water
        'BLITZKRIEG',       # cavalry charge into a river = disaster
        'HAMMER_AND_ANVIL', # frontal hammer into a defended river bank
        'CENTER_PUSH',      # hard push through the middle = straight into the trap
        'PINCER',           # both wings crossing open river = double disaster
    ],
    'PLAYER_HOLDS_CHOKE': [
        'STEAMROLLER',      # marching a wide line into a held funnel = mass casualties
        'CENTER_PUSH',      # the centre IS the choke — straight into the kill zone
        'HAMMER_AND_ANVIL', # hammer head dies in the funnel before anvil engages
        'BLITZKRIEG',       # cavalry compressed in a choke get shot apart
        'CAVALRY_RAID',     # same — mounted units in a narrow lane
    ],
    'FORTIFIED_RIVER': [
        'CAVALRY_RAID',     # cavalry into artillery behind river = suicide
        'BLITZKRIEG',       # rushing a fortified river = massacre
        'STEAMROLLER',      # frontal push into cannons
        'CENTER_PUSH',      # center into artillery kill zone
        'HAMMER_AND_ANVIL', # hammer charge into defended bank
        'PINCER',           # two wings exposed to artillery
        'ENCIRCLEMENT',     # can't surround across a river
        'DOUBLE_ENVELOP',   # same problem
        'CONTACT_AND_FADE', # fading solves nothing — must commit to a bridge assault
        'DELAYING_ACTION',  # retreating cedes the river permanently
    ],
}
