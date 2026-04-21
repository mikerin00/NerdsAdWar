# Module: menu.campaign
# Linear campaign: world-map overview with nodes + connecting lines, mission
# briefings, and local progress persistence.
#
# CampaignMenu returns:
#   ('play', mission_dict)  — user picked a mission to launch
#   ('back', None)
#   ('quit', None)
# Parent routes the 'play' outcome into Game(...) with the mission's params.

import json
import math
import os

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _DIM, _WHITE, _MUTED,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _drawButton, _drawStars,
)


PROGRESS_FILE = os.path.join(os.getcwd(), 'campaign_progress.json')


# ── Mission manifest ────────────────────────────────────────────────────────
# Nodes placed along a rough diagonal from bottom-left to top-right, with the
# world map roughly 1100×480 px centred in the screen.

MISSIONS = [
    {
        'id':   'm1_ochtendgloren',
        'name': 'I · Dawn',
        'area': 'koen', 'area_level': 1,
        'dialog_before': 'koen_intro', 'dialog_after': None,
        'brief': ("A small enemy patrol has crossed the border.\n"
                  "Drive them off before they can regroup."),
        'biome':         'GRASSLAND',
        'gamemode':      'STANDAARD',
        'difficulty':    'MAKKELIJK',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 20, 'heavy_infantry': 2, 'cavalry': 4, 'artillery': 1},
            'enemy':  {'infantry': 16, 'heavy_infantry': 2, 'cavalry': 3, 'artillery': 1},
        },
        'node': (180, 580),
        'requires': [],
    },
    {
        'id':   'm2_bos',
        'name': 'II · The Dark Forest',
        'area': 'koen', 'area_level': 2,
        'dialog_before': 'koen_mid', 'dialog_after': None,
        'brief': ("Mist hangs heavy between the trees. Partisans are hiding —\n"
                  "you won't see them until they're already beside you."),
        'biome':         'FOREST',
        'gamemode':      'FOG',
        'difficulty':    'NORMAAL',
        'aiPersonality': 'OPPORTUNIST',
        'forces': {
            'player': {'infantry': 18, 'heavy_infantry': 4, 'cavalry': 4, 'artillery': 2},
            'enemy':  {'infantry': 20, 'heavy_infantry': 3, 'cavalry': 2, 'artillery': 1},
        },
        'node': (330, 470),
        'requires': ['m1_ochtendgloren'],
    },
    {
        'id':   'm3_brug',
        'name': 'III · The Bridge at the Meuse',
        'area': 'koen', 'area_level': 3,
        'dialog_before': None, 'dialog_after': 'koen_outro',
        'brief': ("The enemy occupies a vital bridge. Take the crossing —\n"
                  "every passage you don't take will be used against you."),
        'biome':         'RIVER_VALLEY',
        'gamemode':      'ASSAULT',
        'difficulty':    'NORMAAL',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 5, 'artillery': 2},
            # Enemy forces ignored in ASSAULT (scripted garrisons), but kept
            # for completeness.
        },
        'node': (500, 380),
        'requires': ['m2_bos'],
    },
    {
        'id':   'm4_hooglanden',
        'name': 'IV · The Highlands',
        'area': 'tim', 'area_level': 1,
        'dialog_before': 'tim_intro', 'dialog_after': None,
        'brief': ("The loyalists have dug in along the ridge.\n"
                  "Height is their advantage — use your cannons."),
        'biome':         'HIGHLANDS',
        'gamemode':      'STANDAARD',
        'difficulty':    'MOEILIJK',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 22, 'heavy_infantry': 5, 'cavalry': 4, 'artillery': 3},
            'enemy':  {'infantry': 24, 'heavy_infantry': 5, 'cavalry': 3, 'artillery': 3},
        },
        'node': (670, 310),
        'requires': ['m3_brug'],
    },
    {
        'id':   'm5_belegering',
        'name': 'V · The Siege',
        'area': 'tim', 'area_level': 2,
        'dialog_before': 'tim_mid', 'dialog_after': None,
        'brief': ("The capital is in rebel hands. All key outposts\n"
                  "must fall before the throne room is within reach."),
        'biome':         'MIXED',
        'gamemode':      'ASSAULT',
        'difficulty':    'MOEILIJK',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 28, 'heavy_infantry': 7, 'cavalry': 6, 'artillery': 3},
        },
        'node': (820, 240),
        'requires': ['m4_hooglanden'],
    },
    {
        'id':   'm6_laatste_slag',
        'name': 'VI · The Last Battle',
        'area': 'tim', 'area_level': 3,
        'dialog_before': None, 'dialog_after': 'tim_outro',
        'brief': ("The rebel leader personally commands his elite guard.\n"
                  "Defeat him — but this is only the beginning."),
        'biome':         'TWIN_RIVERS',
        'gamemode':      'STANDAARD',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 7, 'artillery': 4},
            'enemy':  {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 7, 'artillery': 4},
        },
        'node': (870, 180),
        'requires': ['m5_belegering'],
    },
    # ── Act II — post-war: new enemies from the north ────────────────────────
    {
        'id':   'm7_misty_plain',
        'name': 'VII · The Misty Plain',
        'area': 'mika', 'area_level': 1,
        'dialog_before': 'mika_intro', 'dialog_after': None,
        'brief': ("Reports from the north: a new army marches south.\n"
                  "Intercept them on the open plain before they reach the forests."),
        'biome':         'DRY_PLAINS',
        'gamemode':      'STANDAARD',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 26, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 3},
            'enemy':  {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 4},
        },
        'node': (970, 120),
        'requires': ['m6_laatste_slag'],
    },
    {
        'id':   'm8_moeras',
        'name': 'VIII · The Swamp',
        'area': 'mika', 'area_level': 2,
        'dialog_before': None, 'dialog_after': None,
        'brief': ("The enemy has retreated into the wetlands.\n"
                  "Move slowly, stay on dry ground, and encircle them."),
        'biome':         'WETLANDS',
        'gamemode':      'STANDAARD',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 24, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 3},
            'enemy':  {'infantry': 28, 'heavy_infantry': 6, 'cavalry': 3, 'artillery': 4},
        },
        'node': (1080, 230),
        'requires': ['m7_misty_plain'],
    },
    {
        'id':   'm9_tweeling_rivieren',
        'name': 'IX · Twin Rivers',
        'area': 'mika', 'area_level': 3,
        'dialog_before': 'mika_mid', 'dialog_after': None,
        'brief': ("Two rivers split the battlefield into three zones.\n"
                  "Whoever controls the bridges controls the battle."),
        'biome':         'TWIN_RIVERS',
        'gamemode':      'STANDAARD',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'OPPORTUNIST',
        'forces': {
            'player': {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 3},
            'enemy':  {'infantry': 26, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 3},
        },
        'node': (1170, 360),
        'requires': ['m8_moeras'],
    },
    {
        'id':   'm10_doorgang',
        'name': 'X · The Pass',
        'area': 'mika', 'area_level': 4,
        'dialog_before': None, 'dialog_after': 'mika_outro',
        'brief': ("A narrow pass between the lakes — the only route north.\n"
                  "The enemy has fortified it; break through the line."),
        'biome':         'LAKELANDS',
        'gamemode':      'ASSAULT',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 5, 'artillery': 4},
        },
        'node': (1120, 510),
        'requires': ['m9_tweeling_rivieren'],
    },
    {
        'id':   'm11_dageraad',
        'name': 'XI · Skirmish at Dawn',
        'area': 'luuk', 'area_level': 1,
        'dialog_before': 'luuk_intro', 'dialog_after': None,
        'brief': ("Before sunrise the enemy strikes — wave after wave.\n"
                  "Hold out until the morning light brings your reinforcements."),
        'biome':         'GRASSLAND',
        'gamemode':      'LAST_STAND',
        'difficulty':    'VETERAAN',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 20, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
        },
        'node': (970, 580),
        'requires': ['m10_doorgang'],
    },
    {
        'id':   'm12_bergpas',
        'name': 'XII · Mountain Pass Under Fire',
        'area': 'luuk', 'area_level': 2,
        'dialog_before': None, 'dialog_after': None,
        'brief': ("The loyalists have placed cannons on the heights.\n"
                  "Climb, avoid the gaps, and clear the batteries."),
        'biome':         'HIGHLANDS',
        'gamemode':      'ASSAULT',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 26, 'heavy_infantry': 7, 'cavalry': 4, 'artillery': 5},
        },
        'node': (820, 600),
        'requires': ['m11_dageraad'],
    },
    {
        'id':   'm13_spookbos',
        'name': 'XIII · Forest of Ghosts',
        'area': 'luuk', 'area_level': 3,
        'dialog_before': 'luuk_mid', 'dialog_after': None,
        'brief': ("Ghostly mist conceals everything within ten metres ahead.\n"
                  "Keep your lines tight — whoever gets lost, disappears."),
        'biome':         'FOREST',
        'gamemode':      'FOG',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'OPPORTUNIST',
        'forces': {
            'player': {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 3, 'artillery': 2},
            'enemy':  {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 3},
        },
        'node': (640, 620),
        'requires': ['m12_bergpas'],
    },
    {
        'id':   'm14_verraad',
        'name': 'XIV · The Betrayal',
        'area': 'luuk', 'area_level': 4,
        'dialog_before': None, 'dialog_after': 'luuk_outro',
        'brief': ("One of your own generals has switched sides. His elite cohort\n"
                  "leads him — defeat him or the entire line will waver."),
        'biome':         'MIXED',
        'gamemode':      'COMMANDER',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 22, 'heavy_infantry': 7, 'cavalry': 6, 'artillery': 3},
            'enemy':  {'infantry': 24, 'heavy_infantry': 7, 'cavalry': 7, 'artillery': 3},
        },
        'node': (470, 600),
        'requires': ['m13_spookbos'],
    },
    {
        'id':   'm15_lange_mars',
        'name': 'XV · The Long March',
        'area': 'matthijs', 'area_level': 1,
        'dialog_before': 'matthijs_intro', 'dialog_after': None,
        'brief': ("Exhausted from weeks of marching, you now face\n"
                  "a fresh, well-rested army on the open plains."),
        'biome':         'DRY_PLAINS',
        'gamemode':      'STANDAARD',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 20, 'heavy_infantry': 5, 'cavalry': 6, 'artillery': 2},
            'enemy':  {'infantry': 32, 'heavy_infantry': 9, 'cavalry': 8, 'artillery': 4},
        },
        'node': (310, 540),
        'requires': ['m14_verraad'],
    },
    {
        'id':   'm16_klooster',
        'name': 'XVI · Defence of the Monastery',
        'area': 'matthijs', 'area_level': 2,
        'dialog_before': None, 'dialog_after': None,
        'brief': ("Civilians and monks shelter within the walls.\n"
                  "Every wave must be broken — not one step back."),
        'biome':         'HIGHLANDS',
        'gamemode':      'LAST_STAND',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 24, 'heavy_infantry': 10, 'cavalry': 3, 'artillery': 5},
        },
        'node': (170, 400),
        'requires': ['m15_lange_mars'],
    },
    {
        'id':   'm17_citadel',
        'name': 'XVII · Assault on the Citadel',
        'area': 'matthijs', 'area_level': 3,
        'dialog_before': 'matthijs_mid', 'dialog_after': None,
        'brief': ("The enemy citadel is their last stronghold.\n"
                  "The decisive blow; only victory counts."),
        'biome':         'MIXED',
        'gamemode':      'ASSAULT',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 30, 'heavy_infantry': 10, 'cavalry': 6, 'artillery': 6},
        },
        'node': (140, 240),
        'requires': ['m16_klooster'],
    },
    {
        'id':   'm18_eindstrijd',
        'name': 'XVIII · The Final Battle',
        'area': 'matthijs', 'area_level': 4,
        'dialog_before': None, 'dialog_after': ['matthijs_outro', 'campaign_outro'],
        'brief': ("The enemy emperor marches out personally.\n"
                  "Win — or so you thought. A new front opens…"),
        'biome':         'TWIN_RIVERS',
        'gamemode':      'STANDAARD',
        'difficulty':    'NAPOLEON',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 28, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 5},
            'enemy':  {'infantry': 36, 'heavy_infantry': 12, 'cavalry': 10, 'artillery': 6},
        },
        'node': (300, 130),
        'requires': ['m17_citadel'],
    },
]


# ── Late game (m19–m50) — 6-7 extra missions per world to reach 10 each ─────

def _addLateMissions(out):
    # Each tuple: (id, roman, name, brief, biome, gamemode, personality,
    #              player_forces, enemy_forces_or_None, area, area_level)
    # requires is chained automatically within each area.
    AREA_LAST = {          # last story-mission id per area (chain anchor)
        'koen':     'm3_brug',
        'tim':      'm6_laatste_slag',
        'mika':     'm10_doorgang',
        'luuk':     'm14_verraad',
        'matthijs': 'm18_eindstrijd',
    }
    prev = dict(AREA_LAST)

    L = [
        # ── World 1 – Koen  (levels 4-10) ────────────────────────────────────
        ('m19_grenswacht',   'XIX',   'Border Watch in the Mist',
         "Dense morning mist over the plain — your scouts see nothing.\n"
         "Send cavalry forward to probe the border.",
         'GRASSLAND', 'FOG', 'OPPORTUNIST',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         'koen', 4),
        ('m20_winter_passage', 'XX', 'Winter Pass',
         "Snow limits your manoeuvres. The enemy outnumbers you.",
         'HIGHLANDS', 'STANDAARD', 'DEFENSIVE',
         {'infantry': 20, 'heavy_infantry': 8, 'cavalry': 3, 'artillery': 4},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         'koen', 5),
        ('m21_brandend_dorp', 'XXI', 'Burning Village',
         "Civilians are fleeing — the village must be cleared under fire.",
         'MIXED', 'STANDAARD', 'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 2},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 8, 'artillery': 3},
         'koen', 6),
        ('m22_cavalerie_raid', 'XXII', 'Cavalry Raid',
         "Cavalry only — hit-and-run against a slow column.",
         'DRY_PLAINS', 'STANDAARD', 'OPPORTUNIST',
         {'infantry': 0, 'heavy_infantry': 0, 'cavalry': 14, 'artillery': 0},
         {'infantry': 26, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 3},
         'koen', 7),
        ('m23_bos_doorbraak', 'XXIII', 'Forest Breakthrough',
         "Drive the partisans from the forest. Keep your lines tight.",
         'FOREST', 'STANDAARD', 'OPPORTUNIST',
         {'infantry': 24, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 2},
         'koen', 8),
        ('m24_meer_overgang', 'XXIV', 'Lake Crossing',
         "The bridge is destroyed. Find a detour or build a pontoon.",
         'LAKELANDS', 'STANDAARD', 'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 5, 'artillery': 3},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         'koen', 9),
        ('m25_moeras_terugtocht', 'XXV', 'Swamp Retreat',
         "Withdraw your army through wetlands — don't lose the artillery.",
         'WETLANDS', 'STANDAARD', 'AGGRESSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 5},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 2},
         'koen', 10),

        # ── World 2 – Tim  (levels 4-10) ─────────────────────────────────────
        ('m26_dubbele_rivier', 'XXVI', 'Twin River Battle',
         "Two rivers, two fronts. Choose where you break through.",
         'TWIN_RIVERS', 'STANDAARD', 'BALANCED',
         {'infantry': 24, 'heavy_infantry': 7, 'cavalry': 6, 'artillery': 3},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 7, 'artillery': 4},
         'tim', 4),
        ('m27_belegering_tweede', 'XXVII', 'Second Siege',
         "The enemy has expanded their citadel. No artillery? Climb it.",
         'HIGHLANDS', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 30, 'heavy_infantry': 10, 'cavalry': 4, 'artillery': 0},
         None, 'tim', 5),
        ('m28_omsingeling', 'XXVIII', 'Encirclement',
         "You are surrounded. Break out before the enemy closes the ravine.",
         'MIXED', 'STANDAARD', 'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 4, 'cavalry': 4, 'artillery': 2},
         {'infantry': 36, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 3},
         'tim', 6),
        ('m29_bevoorrading', 'XXIX', 'Supply Line',
         "Protect the wagons. Every cart that falls is one day less of food.",
         'GRASSLAND', 'STANDAARD', 'OPPORTUNIST',
         {'infantry': 20, 'heavy_infantry': 5, 'cavalry': 5, 'artillery': 2},
         {'infantry': 28, 'heavy_infantry': 7, 'cavalry': 8, 'artillery': 2},
         'tim', 7),
        ('m30_keizerlijke_garde', 'XXX', 'Imperial Guard',
         "Their guard is elite — heavy infantry and cannons, no cavalry.",
         'MIXED', 'STANDAARD', 'BALANCED',
         {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 3},
         {'infantry': 22, 'heavy_infantry': 14, 'cavalry': 0, 'artillery': 6},
         'tim', 8),
        ('m31_nachtelijke_aanval', 'XXXI', 'Night Attack',
         "Pitch-black night in the forest — you can't see a metre without light.\n"
         "Artillery is useless in the dark; cavalry and speed are everything.",
         'FOREST', 'FOG', 'AGGRESSIVE',
         {'infantry': 16, 'heavy_infantry': 4, 'cavalry': 12, 'artillery': 0},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 4},
         'tim', 9),
        ('m32_artillerie_duel', 'XXXII', 'Artillery Duel',
         "Both sides heavily armed. Shred their batteries first.",
         'DRY_PLAINS', 'STANDAARD', 'DEFENSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 8},
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 8},
         'tim', 10),

        # ── World 3 – Mika  (levels 5-10) ────────────────────────────────────
        ('m33_versterkte_haven', 'XXXIII', 'Fortified Harbour',
         "Take the harbour. The imperial fleet will no longer be able to dock.",
         'WETLANDS', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 26, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         None, 'mika', 5),
        ('m34_commandant_jacht', 'XXXIV', 'Commander Hunt',
         "Their field marshal has been spotted. Behead the army.",
         'HIGHLANDS', 'COMMANDER', 'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 3},
         {'infantry': 26, 'heavy_infantry': 8, 'cavalry': 5, 'artillery': 3},
         'mika', 6),
        ('m35_eerste_grote_golf', 'XXXV', 'First Great Wave',
         "Reinforcements are three waves away. Hold out.",
         'GRASSLAND', 'LAST_STAND', 'AGGRESSIVE',
         {'infantry': 22, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         None, 'mika', 7),
        ('m36_strategische_terugtocht', 'XXXVI', 'Strategic Retreat',
         "Sacrifice your rearguard. The rest must reach the pass.",
         'HIGHLANDS', 'STANDAARD', 'OPPORTUNIST',
         {'infantry': 16, 'heavy_infantry': 4, 'cavalry': 6, 'artillery': 2},
         {'infantry': 34, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 4},
         'mika', 8),
        ('m37_brandend_woud', 'XXXVII', 'Burning Forest',
         "The forest is on fire. Smoke hides friend and foe alike —\n"
         "trust your instincts and charge straight through.",
         'FOREST', 'FOG', 'AGGRESSIVE',
         {'infantry': 20, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         'mika', 9),
        ('m38_winterpaleis', 'XXXVIII', 'Winter Palace',
         "Storm the winter palace. Fortified walls, no mercy.",
         'MIXED', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 28, 'heavy_infantry': 12, 'cavalry': 4, 'artillery': 5},
         None, 'mika', 10),

        # ── World 4 – Luuk  (levels 5-10) ────────────────────────────────────
        ('m39_dubbele_omsingeling', 'XXXIX', 'Double Encirclement',
         "Enemies left and right. Centre your line or die.",
         'DRY_PLAINS', 'STANDAARD', 'AGGRESSIVE',
         {'infantry': 24, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         {'infantry': 36, 'heavy_infantry': 10, 'cavalry': 10, 'artillery': 4},
         'luuk', 5),
        ('m40_doorbraak_zuid', 'XL', 'Southern Breakthrough',
         "One last chance at free passage. The enemy outnumbers you 3 to 1.",
         'TWIN_RIVERS', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         None, 'luuk', 6),
        ('m41_keizers_voorhoede', 'XLI', "Emperor's Vanguard",
         "The emperor rides at the front. Reach and defeat his elite cohort.",
         'MIXED', 'COMMANDER', 'AGGRESSIVE',
         {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 3},
         {'infantry': 28, 'heavy_infantry': 10, 'cavalry': 6, 'artillery': 3},
         'luuk', 7),
        ('m42_laatste_brigade', 'XLII', 'Last Brigade',
         "Only one brigade left. Make every bullet count.",
         'GRASSLAND', 'STANDAARD', 'BALANCED',
         {'infantry': 14, 'heavy_infantry': 4, 'cavalry': 4, 'artillery': 1},
         {'infantry': 36, 'heavy_infantry': 12, 'cavalry': 8, 'artillery': 4},
         'luuk', 8),
        ('m43_kanonniers_droom', 'XLIII', "Artillerist's Dream",
         "Artillery and heavy infantry only. No mobility, all firepower.",
         'DRY_PLAINS', 'STANDAARD', 'BALANCED',
         {'infantry': 0, 'heavy_infantry': 16, 'cavalry': 0, 'artillery': 10},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 10, 'artillery': 4},
         'luuk', 9),
        ('m44_infanterie_alleen', 'XLIV', 'On Foot',
         "No horses, no cannons. Only musket and bayonet.",
         'FOREST', 'STANDAARD', 'OPPORTUNIST',
         {'infantry': 36, 'heavy_infantry': 8, 'cavalry': 0, 'artillery': 0},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 4},
         'luuk', 10),

        # ── World 5 – Matthijs  (levels 5-10) ────────────────────────────────
        ('m45_cavalerie_zonder_steun', 'XLV', 'Cavalry Without Support',
         "12 riders against an army. Hit-and-run is everything.",
         'GRASSLAND', 'STANDAARD', 'AGGRESSIVE',
         {'infantry': 0, 'heavy_infantry': 0, 'cavalry': 12, 'artillery': 0},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         'matthijs', 5),
        ('m46_keizerlijke_belegering', 'XLVI', 'Imperial Siege',
         "Their capital. Three HQs to storm, no reinforcements.",
         'MIXED', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 32, 'heavy_infantry': 12, 'cavalry': 6, 'artillery': 6},
         None, 'matthijs', 6),
        ('m47_zware_belegering', 'XLVII', 'The Second Citadel',
         "The inner citadel — no reinforcements, no weakening, all in.",
         'HIGHLANDS', 'ASSAULT', 'DEFENSIVE',
         {'infantry': 30, 'heavy_infantry': 14, 'cavalry': 4, 'artillery': 6},
         None, 'matthijs', 7),
        ('m48_keizers_arena', 'XLVIII', "Emperor's Arena",
         "One on one with the emperor and his bodyguard. No artillery.",
         'MIXED', 'COMMANDER', 'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 0},
         {'infantry': 22, 'heavy_infantry': 10, 'cavalry': 6, 'artillery': 0},
         'matthijs', 8),
        ('m49_ragnarok', 'XLIX', 'Ragnarok',
         "Endless waves. Hold out as long as you can.",
         'TWIN_RIVERS', 'LAST_STAND', 'AGGRESSIVE',
         {'infantry': 26, 'heavy_infantry': 12, 'cavalry': 6, 'artillery': 6},
         None, 'matthijs', 9),
        ('m50_de_ondergang', 'L', 'The Downfall',
         "The emperor himself. No reinforcements. No detour. No mercy.",
         'TWIN_RIVERS', 'COMMANDER', 'AGGRESSIVE',
         {'infantry': 26, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 4},
         {'infantry': 40, 'heavy_infantry': 14, 'cavalry': 12, 'artillery': 6},
         'matthijs', 10),
    ]
    for row in L:
        suffix, roman, name, brief, biome, gm, pers, pf, ef, area, al = row
        m = {
            'id':            suffix,
            'name':          f'{roman} · {name}',
            'brief':         brief,
            'biome':         biome,
            'gamemode':      gm,
            'difficulty':    'NAPOLEON',
            'aiPersonality': pers,
            'forces':        {'player': pf} if ef is None else {'player': pf, 'enemy': ef},
            'node':          (0, 0),
            'requires':      [prev[area]],
            'area':          area,
            'area_level':    al,
            'dialog_before': None,
            'dialog_after':  None,
        }
        out.append(m)
        prev[area] = suffix


_addLateMissions(MISSIONS)

MISSIONS_BY_ID = {m['id']: m for m in MISSIONS}


# ── World definitions ────────────────────────────────────────────────────────

WORLDS = [
    {
        'id':      'home',
        'type':    'story',
        'title':   'Het Paleis',
        'villain': 'Hoe het begon…',
        'portrait': 'bronisz',
        'desc':    "Een feest. Een ontvoering. Een briefje.\n"
                   "En één man die niets heeft meegekregen.",
        'dialog_keys': ['prologue'],
        'missions': [],
    },
    {
        'id':      'koen',
        'title':   'The Borderlands',
        'villain': 'Koen de Stuiterbal',
        'portrait': 'koen',
        'desc':    "The border region — open fields, scattered forests,\n"
                   "and one very distracted defender.",
        'missions': [],
    },
    {
        'id':      'tim',
        'title':   'The River Valley',
        'villain': 'Tim de Onzekere',
        'portrait': 'tim',
        'desc':    "A valley crossed by rivers and bridges.\n"
                   "Tim is fairly sure he's on the right one.",
        'missions': [],
    },
    {
        'id':      'mika',
        'title':   'The Dry Plains',
        'villain': 'Mika de Mespunt',
        'portrait': 'mika',
        'desc':    "Open, harsh, unforgiving terrain.\n"
                   "Mika chose it on purpose.",
        'missions': [],
    },
    {
        'id':      'luuk',
        'title':   'The Highlands',
        'villain': 'Luuk de Toren',
        'portrait': 'luuk',
        'desc':    "The highland gateway to Matthijs' fort.\n"
                   "Luuk is here. He figured you'd come.",
        'missions': [],
    },
    {
        'id':      'matthijs',
        'title':   "Matthijs' Fort",
        'villain': 'Generaal Matthijs',
        'portrait': 'matthijs',
        'desc':    "The final stronghold. Matthijs awaits.\n"
                   "Bronisz is already on his third course.",
        'missions': [],
    },
]

_world_by_id = {w['id']: w for w in WORLDS}
for _m in MISSIONS:
    _area = _m.get('area')
    if _area and _area in _world_by_id:
        _world_by_id[_area]['missions'].append(_m)


# ── Per-world node layout ────────────────────────────────────────────────────

def _layoutWorldNodes(missions):
    """Snake-path layout for up to 10 nodes in a world map."""
    n = len(missions)
    if n == 0:
        return
    avail_l = 55
    avail_r = SCREEN_WIDTH - 370
    avail_t = 165
    avail_b = SCREEN_HEIGHT - 85
    cols    = min(n, 5)
    rows    = (n + cols - 1) // cols
    xs      = (avail_r - avail_l) / cols
    ys      = (avail_b - avail_t) / max(rows, 1)
    for i, m in enumerate(missions):
        row = i // cols
        col = i % cols
        if row % 2 == 1:
            col = cols - 1 - col
        m['node'] = (int(avail_l + (col + 0.5) * xs),
                     int(avail_t + (row + 0.5) * ys))

for _w in WORLDS:
    _layoutWorldNodes(_w['missions'])


# ── Progress persistence ────────────────────────────────────────────────────

def _loadProgress():
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {'completed': []}
    if not isinstance(data, dict) or 'completed' not in data:
        return {'completed': []}
    return data

def _saveProgress(data):
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

def markMissionComplete(mission_id: str, stars: int = 1):
    """Called by main.py after a successful mission play."""
    data = _loadProgress()
    if mission_id not in data['completed']:
        data['completed'].append(mission_id)
    # Always update stars if the new score is better
    if 'stars' not in data:
        data['stars'] = {}
    if stars > data['stars'].get(mission_id, 0):
        data['stars'][mission_id] = stars
    _saveProgress(data)


def _status(mission, completed):
    """Returns 'done' | 'available' | 'locked'."""
    if mission['id'] in completed:
        return 'done'
    if all(dep in completed for dep in mission.get('requires', [])):
        return 'available'
    return 'locked'


# ── Drawing helpers ─────────────────────────────────────────────────────────

def _button(surf, rect, label, mx, my, enabled=True):
    return _drawButton(surf, rect, label, mx, my, enabled=enabled, font_size=20)


# ════════════════════════════════════════════════════════════════════════════
# CampaignMenu — world select → world mission map
# ════════════════════════════════════════════════════════════════════════════

class CampaignMenu:
    def __init__(self, screen, clock):
        self.screen    = screen
        self.clock     = clock
        self.tick      = 0
        self.particles, self.prng = _makeParticles(50)
        self.selected  = None
        self._world_idx = 0
        self._portraits = {}
        self._bg_cache  = {}   # world_id → gradient Surface

    # ── Public entry point ───────────────────────────────────────────────────

    def run(self):
        while True:
            result = self._worldSelectLoop()
            if result in ('back', 'quit'):
                return result, None
            self._world_idx = result
            world = WORLDS[result]

            # Story world: play dialogs and return to world select
            if world.get('type') == 'story':
                from src.game.menu.story_dialogs import StoryDialogScreen
                for key in world.get('dialog_keys', []):
                    StoryDialogScreen(self.screen, self.clock, key).run()
                continue

            self.selected = None
            while True:
                data      = _loadProgress()
                completed = set(data.get('completed', []))
                r2 = self._worldMapLoop(world, completed, data)
                if r2 is None:
                    continue
                action, payload = r2
                if action == 'play':
                    return 'play', payload
                if action == 'reset':
                    _saveProgress({'completed': []})
                    self.selected = None
                    continue
                if action == 'back':
                    break
                if action == 'quit':
                    return 'quit', None

    # ── World selection screen ───────────────────────────────────────────────

    def _worldSelectLoop(self):
        """Show world cards with ◄ ► navigation. Returns world index or 'back'/'quit'."""
        W, H   = SCREEN_WIDTH, SCREEN_HEIGHT
        idx    = self._world_idx
        arr_w, arr_h = 58, 80
        left_r  = pygame.Rect(16,  H // 2 - arr_h // 2, arr_w, arr_h)
        right_r = pygame.Rect(W - 16 - arr_w, H // 2 - arr_h // 2, arr_w, arr_h)
        back_r  = pygame.Rect(30,  H - 62, 120, 40)
        enter_r = pygame.Rect(W // 2 - 130, H - 82, 260, 54)

        while True:
            data      = _loadProgress()
            completed = set(data.get('completed', []))
            world     = WORLDS[idx]
            is_story  = world.get('type') == 'story'
            wstat     = 'available' if is_story else self._worldStatus(world, completed)
            locked    = (wstat == 'locked')

            mx, my = pygame.mouse.get_pos()
            click  = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return 'quit'
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return 'back'
                    if ev.key in (pygame.K_LEFT, pygame.K_a):
                        idx = (idx - 1) % len(WORLDS)
                    if ev.key in (pygame.K_RIGHT, pygame.K_d):
                        idx = (idx + 1) % len(WORLDS)
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE) and not locked:
                        self._world_idx = idx
                        return idx
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)

            # Gradient background (cached per world)
            self.screen.blit(self._bgSurf(world), (0, 0))
            _drawParticles(self.screen, self.particles)

            # Villain portrait — right half
            portrait = self._loadPortrait(world['portrait'])
            if portrait:
                ph     = int(H * 0.68)
                pw     = int(portrait.get_width() * ph / portrait.get_height())
                px     = W - pw - 50
                py     = (H - ph) // 2 + 10
                scaled = pygame.transform.smoothscale(portrait, (pw, ph))
                if locked:
                    scaled.set_alpha(70)
                self.screen.blit(scaled, (px, py))

            # Left content area
            cxL = (W - 360) // 2   # horizontal centre of left area
            col_title = _MUTED if locked else _GOLD_LIGHT
            col_sub   = (110, 100, 80) if locked else _PARCHMENT
            col_dim   = (90,  82,  65) if locked else (165, 155, 130)

            tf = _font(52, bold=True)
            _renderShadow(self.screen, world['title'], tf, col_title,
                          cxL - tf.size(world['title'])[0] // 2,
                          H // 2 - 145, offset=3)

            vf  = _font(22)
            vs  = vf.render(world['villain'], True, col_sub)
            self.screen.blit(vs, (cxL - vs.get_width() // 2, H // 2 - 80))

            for i, line in enumerate(world['desc'].split('\n')):
                ds = _font(16).render(line, True, col_dim)
                self.screen.blit(ds, (cxL - ds.get_width() // 2,
                                      H // 2 - 30 + i * 22))

            # Progress (skip for story worlds)
            if not is_story:
                done_c  = sum(1 for m in world['missions'] if m['id'] in completed)
                total_c = len(world['missions'])
                pf_s    = _font(18, bold=True).render(
                    f"{done_c} / {total_c}  missions", True, col_title)
                self.screen.blit(pf_s, (cxL - pf_s.get_width() // 2, H // 2 + 25))

                if done_c > 0:
                    total_stars = sum(data.get('stars', {}).get(m['id'], 0)
                                      for m in world['missions']
                                      if m['id'] in completed)
                    _drawStars(self.screen, cxL, H // 2 + 62,
                               min(total_c * 3, 10), min(total_stars, 10),
                               r_outer=7, r_inner=3)

            if locked:
                lk = _font(22, bold=True).render("LOCKED", True, (210, 70, 70))
                self.screen.blit(lk, (cxL - lk.get_width() // 2, H // 2 + 80))

            # Navigation dots
            for di in range(len(WORLDS)):
                pygame.draw.circle(
                    self.screen,
                    _GOLD if di == idx else (75, 65, 48),
                    (W // 2 - (len(WORLDS) - 1) * 15 + di * 30, H - 108), 8)

            # Arrow buttons
            for rect, lbl in ((left_r, '◄'), (right_r, '►')):
                hov = rect.collidepoint(mx, my)
                pygame.draw.rect(self.screen,
                                 (65, 52, 38) if hov else (42, 34, 26),
                                 rect, border_radius=8)
                pygame.draw.rect(self.screen,
                                 _GOLD_LIGHT if hov else _GOLD,
                                 rect, 2, border_radius=8)
                as_ = _font(26, bold=True).render(lbl, True,
                                                   _GOLD_LIGHT if hov else _GOLD)
                self.screen.blit(as_, (rect.centerx - as_.get_width() // 2,
                                       rect.centery - as_.get_height() // 2))

            _button(self.screen, back_r,  "Back", mx, my)
            enter_label = ("Bekijk Verhaal  ►" if is_story
                           else "Enter World  ►" if not locked else "Locked")
            _button(self.screen, enter_r, enter_label,
                    mx, my, enabled=not locked)

            if click:
                if left_r.collidepoint(mx, my):
                    idx = (idx - 1) % len(WORLDS)
                elif right_r.collidepoint(mx, my):
                    idx = (idx + 1) % len(WORLDS)
                elif back_r.collidepoint(mx, my):
                    return 'back'
                elif enter_r.collidepoint(mx, my) and not locked:
                    self._world_idx = idx
                    return idx

            pygame.display.flip()
            self.clock.tick(60)

    # ── Per-world mission map ────────────────────────────────────────────────

    def _worldMapLoop(self, world, completed, data):
        """Mission map for one world. Returns (action, payload) or None."""
        W, H       = SCREEN_WIDTH, SCREEN_HEIGHT
        cx         = W // 2
        missions   = world['missions']
        back_rect  = pygame.Rect(30, H - 56, 140, 38)
        reset_rect = pygame.Rect(W - 180, H - 56, 150, 38)
        panel_rect = pygame.Rect(W - 360, 150, 320, 430)

        while True:
            mx, my = pygame.mouse.get_pos()
            click  = False
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return ('quit', None)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if self.selected is not None:
                        self.selected = None
                    else:
                        return ('back', None)
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)

            # Themed background
            self.screen.blit(self._bgSurf(world), (0, 0))
            _drawParticles(self.screen, self.particles)

            # Title
            tf = _font(36, bold=True)
            _renderShadow(self.screen, world['title'], tf, _GOLD_LIGHT,
                          cx - tf.size(world['title'])[0] // 2, 22, offset=3)
            vs = _font(18).render(world['villain'], True, _MUTED)
            self.screen.blit(vs, (cx - vs.get_width() // 2, 68))
            _drawDivider(self.screen, 98)

            done  = sum(1 for m in missions if m['id'] in completed)
            total = len(missions)
            ss    = _font(15).render(f"Progress:  {done} / {total}",
                                     True, _PARCHMENT)
            self.screen.blit(ss, (cx - ss.get_width() // 2, 108))

            # Connecting paths (within this world only)
            for m in missions:
                stat = _status(m, completed)
                for dep_id in m.get('requires', []):
                    dep = MISSIONS_BY_ID.get(dep_id)
                    if not dep or dep.get('area') != world['id']:
                        continue
                    col = (_GOLD_LIGHT if stat == 'done'
                           else _GOLD if stat == 'available'
                           else (70, 55, 40))
                    self._drawPath(dep['node'], m['node'], col,
                                   width=4 if stat != 'locked' else 2)

            # Nodes
            hovered = None
            for m in missions:
                stat       = _status(m, completed)
                cxn, cyn   = m['node']
                if stat == 'done':
                    fill, ring, radius = (90, 190, 110), (160, 240, 160), 18
                elif stat == 'available':
                    pulse  = 4 * math.sin(self.tick * 0.1)
                    fill, ring = (240, 210, 90), (255, 240, 150)
                    radius = int(19 + pulse)
                else:
                    fill, ring, radius = (200, 188, 162), (150, 130, 95), 15

                pygame.draw.circle(self.screen, fill,   (cxn, cyn), radius)
                pygame.draw.circle(self.screen, ring,   (cxn, cyn), radius, 2)
                short = m['name'].split(' · ')[0]
                lbl   = _font(13, bold=(stat == 'available')).render(
                    short, True, _WHITE if stat != 'locked' else _MUTED)
                self.screen.blit(lbl, (cxn - lbl.get_width() // 2, cyn + radius + 2))
                if stat == 'done':
                    _drawStars(self.screen, cxn, cyn + radius + 22, 3,
                               data.get('stars', {}).get(m['id'], 1),
                               r_outer=6, r_inner=3)
                if (cxn - mx) ** 2 + (cyn - my) ** 2 <= (radius + 4) ** 2:
                    hovered = m

            # Briefing panel
            play_hover = False
            if self.selected is not None:
                stat = _status(self.selected, completed)
                pygame.draw.rect(self.screen, (244, 236, 219), panel_rect,
                                 border_radius=6)
                pygame.draw.rect(self.screen, _GOLD, panel_rect, 2,
                                 border_radius=6)
                tx = panel_rect.x + 16
                ty = panel_rect.y + 14
                nm = _font(22, bold=True).render(
                    self.selected['name'], True, _GOLD_LIGHT)
                self.screen.blit(nm, (tx, ty)); ty += 32
                for line in self.selected['brief'].split('\n'):
                    ls = _font(14).render(line, True, _PARCHMENT)
                    self.screen.blit(ls, (tx, ty)); ty += 20
                ty += 10
                stats_lines = [
                    f"Biome:      {self.selected['biome']}",
                    f"Mode:       {self.selected['gamemode']}",
                    f"Difficulty: {self.selected['difficulty']}",
                ]
                if self.selected.get('aiPersonality'):
                    stats_lines.append(f"AI style:   {self.selected['aiPersonality']}")
                fp = self.selected.get('forces', {}).get('player')
                if fp:
                    stats_lines.append(
                        f"Forces:  {fp.get('infantry',0)} inf · "
                        f"{fp.get('heavy_infantry',0)} hvy · "
                        f"{fp.get('cavalry',0)} cav · "
                        f"{fp.get('artillery',0)} art")
                for s in stats_lines:
                    self.screen.blit(_font(13).render(s, True, _MUTED), (tx, ty))
                    ty += 18

                ty = panel_rect.bottom - 96
                status_txt = {'done': "✓ COMPLETED — play again?",
                              'available': "Available",
                              'locked': "✗ Locked"}[stat]
                status_col = {'done': (120, 220, 120),
                              'available': _GOLD_LIGHT,
                              'locked': (200, 120, 120)}[stat]
                self.screen.blit(
                    _font(14, bold=True).render(status_txt, True, status_col),
                    (tx, ty))
                if stat == 'done':
                    _drawStars(self.screen, panel_rect.right - 52, ty + 8,
                               3, data.get('stars', {}).get(self.selected['id'], 1),
                               r_outer=10, r_inner=4)
                play_rect    = pygame.Rect(panel_rect.x + 16,
                                           panel_rect.bottom - 58,
                                           panel_rect.width - 32, 44)
                play_enabled = stat in ('available', 'done')
                play_hover   = _button(
                    self.screen, play_rect,
                    "Play ▶" if stat == 'available' else "Play again ▶",
                    mx, my, enabled=play_enabled)

            # Hover tooltip
            if hovered is not None and self.selected is None:
                tip  = _font(15, bold=True).render(hovered['name'], True, _GOLD_LIGHT)
                pad  = 6
                tw, th = tip.get_width() + pad * 2, tip.get_height() + pad * 2
                ttx  = max(8, min(W - tw - 8, mx - tw // 2))
                tty  = max(8, my - th - 14)
                bg   = pygame.Surface((tw, th), pygame.SRCALPHA)
                bg.fill((20, 20, 30, 220))
                self.screen.blit(bg,  (ttx, tty))
                pygame.draw.rect(self.screen, _GOLD, (ttx, tty, tw, th), 1)
                self.screen.blit(tip, (ttx + pad, tty + pad))

            back_hov  = _button(self.screen, back_rect,  "Back",           mx, my)
            reset_hov = _button(self.screen, reset_rect, "Reset progress", mx, my)

            if click:
                if play_hover and self.selected:
                    if _status(self.selected, completed) in ('available', 'done'):
                        return ('play', self.selected)
                elif hovered is not None \
                        and _status(hovered, completed) != 'locked':
                    self.selected = hovered
                elif back_hov:
                    return ('back', None)
                elif reset_hov:
                    return ('reset', None)
                elif self.selected and not panel_rect.collidepoint(mx, my):
                    self.selected = None

            pygame.display.flip()
            self.clock.tick(60)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _worldStatus(self, world, completed):
        if not world['missions']:
            return 'locked'
        first = world['missions'][0]
        if all(m['id'] in completed for m in world['missions']):
            return 'done'
        if all(dep in completed for dep in first.get('requires', [])):
            return 'available'
        return 'locked'

    def _bgSurf(self, world):
        wid = world['id']
        if wid not in self._bg_cache:
            self._bg_cache[wid] = self._buildWorldBg(wid)
        return self._bg_cache[wid]

    @staticmethod
    def _lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * max(0.0, min(1.0, t)))
                     for i in range(3))

    def _buildWorldBg(self, wid):
        W, H = SCREEN_WIDTH, SCREEN_HEIGHT
        surf = pygame.Surface((W, H))

        def grad(y1, y2, c1, c2):
            span = max(1, y2 - y1)
            for y in range(max(0, y1), min(H, y2)):
                col = self._lerp(c1, c2, (y - y1) / span)
                pygame.draw.line(surf, col, (0, y), (W, y))

        if wid == 'home':
            # Warm candlelit palace interior
            grad(0,      int(H*0.45), (75, 15, 28),  (120, 45, 22))
            grad(int(H*0.45), H,      (155, 90, 22), (195, 135, 30))
            # Arch outlines — golden frame
            for ax in (int(W*0.18), int(W*0.5), int(W*0.82)):
                pygame.draw.arc(surf, (195, 145, 35),
                                pygame.Rect(ax - 110, -55, 220, 260),
                                0, math.pi, 5)
            # Candlelight glow blobs at bottom
            for cx_ in (int(W*0.25), int(W*0.5), int(W*0.75)):
                s = pygame.Surface((160, 100), pygame.SRCALPHA)
                pygame.draw.ellipse(s, (220, 160, 40, 55), (0, 0, 160, 100))
                surf.blit(s, (cx_ - 80, H - 80))

        elif wid == 'koen':
            # Open fields under bright sky
            HZ = int(H * 0.60)
            grad(0,   HZ, (110, 185, 245), (178, 222, 255))
            grad(HZ,  H,  (62, 148, 42),   (45,  112, 30))
            # Rolling hill silhouette
            hill_pts = [
                (0, H), (0, HZ + int(H*0.06)),
                (int(W*0.12), HZ - int(H*0.04)),
                (int(W*0.28), HZ + int(H*0.02)),
                (int(W*0.44), HZ - int(H*0.06)),
                (int(W*0.58), HZ + int(H*0.01)),
                (int(W*0.72), HZ - int(H*0.05)),
                (int(W*0.88), HZ + int(H*0.03)),
                (W, HZ - int(H*0.02)), (W, H),
            ]
            pygame.draw.polygon(surf, (52, 135, 35), hill_pts)
            # Tree clusters on hills
            for tx, ty_ in ((int(W*0.12), HZ - int(H*0.04)),
                            (int(W*0.44), HZ - int(H*0.06)),
                            (int(W*0.72), HZ - int(H*0.05))):
                for dx in range(-22, 24, 11):
                    pygame.draw.circle(surf, (28, 95, 18),
                                       (tx + dx, ty_ - 14), 12)

        elif wid == 'tim':
            # Misty river valley
            HZ = int(H * 0.58)
            grad(0,   HZ, (95, 140, 200),  (155, 185, 225))
            grad(HZ,  H,  (42,  98,  52),  (30,   72,  38))
            # Mist at horizon
            mist = pygame.Surface((W, int(H*0.12)), pygame.SRCALPHA)
            for my_ in range(mist.get_height()):
                a = int(90 * (1 - my_ / mist.get_height()))
                pygame.draw.line(mist, (195, 215, 235, a), (0, my_), (W, my_))
            surf.blit(mist, (0, HZ - int(H*0.06)))
            # River band
            RY = int(H * 0.70)
            RH = int(H * 0.09)
            grad(RY, RY + RH, (42, 100, 155), (55, 125, 180))
            pygame.draw.line(surf, (110, 168, 210), (0, RY + int(RH*0.25)),
                             (W, RY + int(RH*0.25)), 2)
            # Far bank tree line
            for tx in range(0, W, 18):
                pygame.draw.circle(surf, (28, 78, 32),
                                   (tx, HZ + int(H*0.04)), 9)

        elif wid == 'mika':
            # Baking dry plains
            HZ = int(H * 0.62)
            grad(0,   HZ, (225, 168, 68),  (240, 200, 128))
            grad(HZ,  H,  (168, 132, 52),  (145, 108, 38))
            # Heat shimmer at horizon
            for i in range(4):
                s = pygame.Surface((W, 3), pygame.SRCALPHA)
                s.fill((240, 200, 100, 30))
                surf.blit(s, (0, HZ - 10 + i * 5))
            # Rock formations
            for rx, rh_frac in ((int(W*0.12), 0.16), (int(W*0.38), 0.13),
                                (int(W*0.62), 0.19), (int(W*0.82), 0.12)):
                rh = int(H * rh_frac)
                rock = [
                    (rx - int(W*0.04), HZ),
                    (rx - int(W*0.025), HZ - rh),
                    (rx,               HZ - int(rh*1.18)),
                    (rx + int(W*0.025),HZ - int(rh*0.75)),
                    (rx + int(W*0.04), HZ),
                ]
                pygame.draw.polygon(surf, (125, 95, 35), rock)
                pygame.draw.polygon(surf, (105, 78, 28), rock, 2)

        elif wid == 'luuk':
            # Rocky mountain highlands
            HZ = int(H * 0.55)
            grad(0,   HZ, (58,  82, 138),  (108, 132, 188))
            grad(HZ,  H,  (60,  55,  70),  (42,  38,  50))
            # Snow on distant ridge
            grad(int(H*0.38), int(H*0.50),
                 (185, 190, 210), (95, 88, 105))
            # Mountain silhouette
            mtn = [
                (0, H), (0, int(H*0.58)),
                (int(W*0.08), int(H*0.45)),
                (int(W*0.18), int(H*0.55)),
                (int(W*0.28), int(H*0.32)),   # peak
                (int(W*0.36), int(H*0.50)),
                (int(W*0.48), int(H*0.22)),   # highest peak
                (int(W*0.58), int(H*0.45)),
                (int(W*0.68), int(H*0.35)),
                (int(W*0.78), int(H*0.52)),
                (int(W*0.88), int(H*0.40)),
                (W,           int(H*0.55)),
                (W, H),
            ]
            pygame.draw.polygon(surf, (52, 48, 62), mtn)
            # Snow caps
            for px_, py_ in ((int(W*0.28), int(H*0.32)),
                             (int(W*0.48), int(H*0.22)),
                             (int(W*0.68), int(H*0.35))):
                cap = [(px_, py_),
                       (px_ - int(W*0.04), py_ + int(H*0.08)),
                       (px_ + int(W*0.04), py_ + int(H*0.08))]
                pygame.draw.polygon(surf, (228, 232, 240), cap)

        elif wid == 'matthijs':
            # Night siege — glowing fort
            grad(0,         int(H*0.55), (8,   6,  14),  (30,  15,  12))
            grad(int(H*0.55), H,         (72,  28,  14),  (40,  16,   8))
            # Star field
            rng_ = __import__('random').Random(77)
            for _ in range(80):
                sx_, sy_ = rng_.randint(0, W), rng_.randint(0, int(H*0.48))
                r_ = rng_.choice((1, 1, 1, 2))
                pygame.draw.circle(surf, (200, 195, 180), (sx_, sy_), r_)
            # Fortress wall
            WY = int(H * 0.50)
            grad(WY, H, (42, 32, 22), (28, 18, 12))
            # Battlements
            MW, GW = 40, 24
            x_ = 0
            while x_ < W:
                pygame.draw.rect(surf, (35, 26, 18),
                                 (x_, WY - 38, MW, 40))
                x_ += MW + GW
            # Arrow-slit fire glow
            for fx in range(80, W - 80, 160):
                glow = pygame.Surface((48, 60), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (200, 110, 20, 80), (0, 0, 48, 60))
                surf.blit(glow, (fx - 24, WY + 30))
                pygame.draw.rect(surf, (230, 140, 30), (fx, WY + 38, 12, 28))

        else:
            # Fallback gradient
            grad(0, H, (40, 60, 30), (70, 100, 50))

        return surf

    def _loadPortrait(self, key):
        if key not in self._portraits:
            try:
                from src.game.menu.story_dialogs import PORTRAIT_FILES
                self._portraits[key] = pygame.image.load(
                    PORTRAIT_FILES[key]).convert_alpha()
            except Exception:
                self._portraits[key] = None
        return self._portraits[key]

    def _drawPath(self, a, b, color, width=3):
        ax, ay = a; bx, by = b
        cpx = (ax + bx) / 2
        cpy = (ay + by) / 2 - 40
        steps = 24
        prev  = a
        for i in range(1, steps + 1):
            t = i / steps
            x = (1-t)**2 * ax + 2*(1-t)*t * cpx + t*t * bx
            y = (1-t)**2 * ay + 2*(1-t)*t * cpy + t*t * by
            pygame.draw.line(self.screen, color, prev, (int(x), int(y)), width)
            prev = (int(x), int(y))
