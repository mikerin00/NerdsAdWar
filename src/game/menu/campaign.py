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
    _drawButton,
)


PROGRESS_FILE = os.path.join(os.getcwd(), 'campaign_progress.json')


# ── Mission manifest ────────────────────────────────────────────────────────
# Nodes placed along a rough diagonal from bottom-left to top-right, with the
# world map roughly 1100×480 px centred in the screen.

MISSIONS = [
    {
        'id':   'm1_ochtendgloren',
        'name': 'I · Ochtendgloren',
        'brief': ("Een kleine patrouille van de vijand heeft de grens overschreden.\n"
                  "Verjaag ze voor ze zich kunnen hergroeperen."),
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
        'name': 'II · Het Donkere Bos',
        'brief': ("Mist hangt zwaar tussen de bomen. Partizanen verbergen zich —\n"
                  "je ziet ze pas als ze al naast je staan."),
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
        'name': 'III · De Brug over de Maas',
        'brief': ("De vijand bezet een cruciale brug. Verover de oversteek —\n"
                  "elke doorgang die je niet neemt wordt tegen je gebruikt."),
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
        'name': 'IV · De Hooglanden',
        'brief': ("De koningsgezinden hebben zich ingegraven op de heuvelrug.\n"
                  "Hoogte is hun voordeel — gebruik je kanonnen."),
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
        'name': 'V · De Belegering',
        'brief': ("De hoofdstad ligt in handen van de rebellen. Alle sleutelposten\n"
                  "moeten vallen voor de troonzaal bereikbaar is."),
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
        'name': 'VI · De Laatste Slag',
        'brief': ("De rebellenleider voert zijn elite-garde persoonlijk aan.\n"
                  "Verslaat hem — maar dit is pas het begin."),
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
    # ── Act II — naoorlog: nieuwe vijanden uit het noorden ──────────────────
    {
        'id':   'm7_misty_plain',
        'name': 'VII · De Mistige Vlakte',
        'brief': ("Berichten uit het noorden: een nieuw leger trekt zuidwaarts.\n"
                  "Onderschep ze op de open vlakte voor ze de bossen bereiken."),
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
        'name': 'VIII · Het Moeras',
        'brief': ("De vijand heeft zich teruggetrokken in het wetland.\n"
                  "Beweeg langzaam, blijf op droge grond, en omsingel ze."),
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
        'name': 'IX · Tweelingrivieren',
        'brief': ("Twee rivieren splitsen het slagveld in drieën.\n"
                  "Wie de bruggen beheerst, beheerst de slag."),
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
        'name': 'X · De Doorgang',
        'brief': ("Een smalle pas tussen de meren — de enige route noordwaarts.\n"
                  "De vijand heeft 'm versterkt; doorbreek de linie."),
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
        'name': 'XI · Schermutseling bij Dageraad',
        'brief': ("Voor zonsopgang slaat de vijand toe — golf na golf.\n"
                  "Houd stand tot het ochtendlicht je versterkingen brengt."),
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
        'name': 'XII · Bergpas Onder Vuur',
        'brief': ("De koningsgezinden hebben kanonnen op de hoogtes geplaatst.\n"
                  "Klim, vermijd de openingen, en ruim de batterijen op."),
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
        'name': 'XIII · Bos vol Spoken',
        'brief': ("Spookachtige mist verbergt alles tot tien meter voor je voeten.\n"
                  "Hou je linies dicht — wie verdwaalt, verdwijnt."),
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
        'name': 'XIV · Het Verraad',
        'brief': ("Een eigen generaal heeft de zijde gewisseld. Zijn elite-cohort\n"
                  "voert hem aan — sla hem uit het veld of de hele linie wankelt."),
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
        'name': 'XV · De Lange Mars',
        'brief': ("Uitgeput van weken marcheren neem je nu stelling tegen\n"
                  "een vers, uitgerust leger op de open vlaktes."),
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
        'name': 'XVI · Verdediging van het Klooster',
        'brief': ("Burgers en monniken schuilen binnen de muren.\n"
                  "Iedere golf moet gebroken worden — geen meter verlies."),
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
        'name': 'XVII · Stormloop op de Citadel',
        'brief': ("De vijandelijke citadel is hun laatste bolwerk.\n"
                  "Beslechtende klap; alleen overwinning telt."),
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
        'name': 'XVIII · De Eindstrijd',
        'brief': ("De vijandelijke keizer marcheert persoonlijk uit.\n"
                  "Win — of zo dacht je. Een nieuw front opent zich…"),
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


# ── Late game (m19–m50) — generated to keep the file readable. ─────────────
# Every late-game mission runs at NAPOLEON difficulty. Variety comes from
# biome / gamemode / personality / force loadout. Node coordinates pack
# the inner area of the map left empty by the m1–m18 outer loop.

def _addLateMissions(out):
    # (suffix, roman, dutch_name, brief, biome, gamemode, personality,
    #  player_forces_or_None, enemy_forces_or_None, (x, y))
    L = [
        # Act III — De Lange Campagne ─────────────────────────────────────────
        ('m19_grenswacht',   'XIX',   'De Grenswacht in de Mist',
         "Dichte ochtendmist boven de vlakte — je verkenners zien niets.\n"
         "Stuur cavalerie vooruit om de grens af te tasten.",
         'GRASSLAND',  'FOG',        'OPPORTUNIST',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         (430, 90)),
        ('m20_winter_passage','XX',  'Winter-Pas',
         "Sneeuw beperkt je manoeuvres. De vijand is met meer.",
         'HIGHLANDS',  'STANDAARD',  'DEFENSIVE',
         {'infantry': 20, 'heavy_infantry': 8, 'cavalry': 3, 'artillery': 4},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         (560, 90)),
        ('m21_brandend_dorp','XXI', 'Brandend Dorp',
         "Burgers vluchten — het dorp moet ontruimd worden onder vuur.",
         'MIXED',      'STANDAARD',  'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 2},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 8, 'artillery': 3},
         (690, 90)),
        ('m22_cavalerie_raid','XXII', 'Cavalerie-Raid',
         "Alleen cavalerie — slag-en-weg tegen een trage colonne.",
         'DRY_PLAINS', 'STANDAARD',  'OPPORTUNIST',
         {'infantry':  0, 'heavy_infantry': 0, 'cavalry': 14, 'artillery': 0},
         {'infantry': 26, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 3},
         (820, 90)),
        ('m23_bos_doorbraak','XXIII','Bos-Doorbraak',
         "Drijf de partizanen uit het woud. Hou je linies dicht.",
         'FOREST',     'STANDAARD',  'OPPORTUNIST',
         {'infantry': 24, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 2},
         (820, 160)),
        ('m24_meer_overgang','XXIV', 'Meer-Oversteek',
         "De brug is vernield. Vind een omweg of bouw een ponton.",
         'LAKELANDS',  'STANDAARD',  'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 5, 'artillery': 3},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         (690, 160)),
        ('m25_moeras_terugtocht','XXV','Moerasterugtocht',
         "Trek je leger terug door wetland — verlies geen artillerie.",
         'WETLANDS',   'STANDAARD',  'AGGRESSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 5},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 2},
         (560, 160)),
        ('m26_dubbele_rivier','XXVI','Dubbele Rivierslag',
         "Twee rivieren, twee fronten. Kies waar je doorbreekt.",
         'TWIN_RIVERS','STANDAARD',  'BALANCED',
         {'infantry': 24, 'heavy_infantry': 7, 'cavalry': 6, 'artillery': 3},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 7, 'artillery': 4},
         (430, 160)),

        # Act IV — Diplomatieke Oorlog ────────────────────────────────────────
        ('m27_belegering_tweede','XXVII','Tweede Belegering',
         "De vijand heeft hun citadel uitgebreid. Geen artillerie? Beklim 'm.",
         'HIGHLANDS',  'ASSAULT',    'DEFENSIVE',
         {'infantry': 30, 'heavy_infantry': 10, 'cavalry': 4, 'artillery': 0},
         None, (250, 230)),
        ('m28_omsingeling','XXVIII', 'Omsingeling',
         "Je bent omsingeld. Breek uit voor de vijand het ravijn dichtmaakt.",
         'MIXED',      'STANDAARD',  'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 4, 'cavalry': 4, 'artillery': 2},
         {'infantry': 36, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 3},
         (370, 230)),
        ('m29_bevoorrading','XXIX', 'Bevoorradingslijn',
         "Bescherm de wagons. Iedere kar die valt is een dag minder voedsel.",
         'GRASSLAND',  'STANDAARD',  'OPPORTUNIST',
         {'infantry': 20, 'heavy_infantry': 5, 'cavalry': 5, 'artillery': 2},
         {'infantry': 28, 'heavy_infantry': 7, 'cavalry': 8, 'artillery': 2},
         (490, 230)),
        ('m30_keizerlijke_garde','XXX','Keizerlijke Garde',
         "Hun garde is elite — zware infanterie en kanonnen, geen cavalerie.",
         'MIXED',      'STANDAARD',  'BALANCED',
         {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 3},
         {'infantry': 22, 'heavy_infantry': 14, 'cavalry': 0, 'artillery': 6},
         (610, 230)),
        ('m31_nachtelijke_aanval','XXXI','Nachtelijke Aanval',
         "Pikzwarte nacht in het bos — je ziet geen meter zonder licht.\n"
         "Geen artillerie nuttig in het donker; cavalerie en snelheid tellen.",
         'FOREST',     'FOG',        'AGGRESSIVE',
         {'infantry': 16, 'heavy_infantry': 4, 'cavalry': 12, 'artillery': 0},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 4},
         (730, 230)),
        ('m32_artillerie_duel','XXXII','Artillerie-Duel',
         "Beide kanten zwaar bewapend. Scheur eerst hun batterijen op.",
         'DRY_PLAINS', 'STANDAARD',  'DEFENSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 8},
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 8},
         (850, 230)),
        ('m33_versterkte_haven','XXXIII','Versterkte Haven',
         "Neem de haven in. De keizerlijke vloot kan niet meer aanmeren.",
         'WETLANDS',   'ASSAULT',    'DEFENSIVE',
         {'infantry': 26, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         None, (970, 230)),
        ('m34_commandant_jacht','XXXIV','Commandantenjacht',
         "Hun veldheer is gespot. Onthoofd het leger.",
         'HIGHLANDS',  'COMMANDER',  'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 6, 'cavalry': 6, 'artillery': 3},
         {'infantry': 26, 'heavy_infantry': 8, 'cavalry': 5, 'artillery': 3},
         (250, 290)),

        # Act V — Het Eindspel ────────────────────────────────────────────────
        ('m35_eerste_grote_golf','XXXV','Eerste Grote Golf',
         "Versterkingen zijn drie golven achterhaald. Houd stand.",
         'GRASSLAND',  'LAST_STAND', 'AGGRESSIVE',
         {'infantry': 22, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         None, (370, 290)),
        ('m36_strategische_terugtocht','XXXVI','Strategische Terugtocht',
         "Opoffer je achterhoede. De rest moet de pas bereiken.",
         'HIGHLANDS',  'STANDAARD',  'OPPORTUNIST',
         {'infantry': 16, 'heavy_infantry': 4, 'cavalry': 6, 'artillery': 2},
         {'infantry': 34, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 4},
         (490, 290)),
        ('m37_brandend_woud','XXXVII','Brandend Woud',
         "Het bos staat in brand. Rook verbergt vriend én vijand —\n"
         "vertrouw op je oren en val recht door de muur van vlammen.",
         'FOREST',     'FOG',        'AGGRESSIVE',
         {'infantry': 20, 'heavy_infantry': 6, 'cavalry': 4, 'artillery': 2},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         (610, 290)),
        ('m38_winterpaleis','XXXVIII','Winterpaleis',
         "Bestorm het winterpaleis. Versterkte muren, geen genade.",
         'MIXED',      'ASSAULT',    'DEFENSIVE',
         {'infantry': 28, 'heavy_infantry': 12, 'cavalry': 4, 'artillery': 5},
         None, (730, 290)),
        ('m39_dubbele_omsingeling','XXXIX','Dubbele Omsingeling',
         "Vijanden links én rechts. Centreer je linie of sterf.",
         'DRY_PLAINS', 'STANDAARD',  'AGGRESSIVE',
         {'infantry': 24, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         {'infantry': 36, 'heavy_infantry': 10, 'cavalry': 10, 'artillery': 4},
         (850, 290)),
        ('m40_doorbraak_zuid','XL',  'Doorbraak Zuid',
         "Een laatste kans op vrije passage. De vijand staat 3 op 1.",
         'TWIN_RIVERS','ASSAULT',    'DEFENSIVE',
         {'infantry': 22, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 3},
         None, (970, 290)),
        ('m41_keizers_voorhoede','XLI','Voorhoede van de Keizer',
         "De keizer rijdt voorop. Bereik en versla zijn elite-cohort.",
         'MIXED',      'COMMANDER',  'AGGRESSIVE',
         {'infantry': 24, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 3},
         {'infantry': 28, 'heavy_infantry': 10, 'cavalry': 6, 'artillery': 3},
         (250, 350)),
        ('m42_laatste_brigade','XLII','Laatste Brigade',
         "Slechts één brigade over. Maak ze elke kogel waard.",
         'GRASSLAND',  'STANDAARD',  'BALANCED',
         {'infantry': 14, 'heavy_infantry': 4, 'cavalry': 4, 'artillery': 1},
         {'infantry': 36, 'heavy_infantry': 12, 'cavalry': 8, 'artillery': 4},
         (370, 350)),

        # Act VI — Legende ───────────────────────────────────────────────────
        ('m43_kanonniers_droom','XLIII','Kanonniers-Droom',
         "Alleen artillerie en zware infanterie. Geen mobiliteit, alle kracht.",
         'DRY_PLAINS', 'STANDAARD',  'BALANCED',
         {'infantry':  0, 'heavy_infantry': 16, 'cavalry': 0, 'artillery': 10},
         {'infantry': 32, 'heavy_infantry': 8, 'cavalry': 10, 'artillery': 4},
         (490, 350)),
        ('m44_infanterie_alleen','XLIV','Te Voet',
         "Geen paarden, geen kanonnen. Alleen kogel en bajonet.",
         'FOREST',     'STANDAARD',  'OPPORTUNIST',
         {'infantry': 36, 'heavy_infantry': 8, 'cavalry': 0, 'artillery': 0},
         {'infantry': 28, 'heavy_infantry': 8, 'cavalry': 6, 'artillery': 4},
         (610, 350)),
        ('m45_cavalerie_zonder_steun','XLV','Cavalerie Zonder Steun',
         "12 ruiters tegen een leger. Hit-and-run is alles.",
         'GRASSLAND',  'STANDAARD',  'AGGRESSIVE',
         {'infantry':  0, 'heavy_infantry': 0, 'cavalry': 12, 'artillery': 0},
         {'infantry': 30, 'heavy_infantry': 8, 'cavalry': 4, 'artillery': 4},
         (730, 350)),
        ('m46_keizerlijke_belegering','XLVI','Keizerlijke Belegering',
         "Hun hoofdstad. Drie HQ's te bestormen, geen aanvulling.",
         'MIXED',      'ASSAULT',    'DEFENSIVE',
         {'infantry': 32, 'heavy_infantry': 12, 'cavalry': 6, 'artillery': 6},
         None, (850, 350)),
        ('m47_zware_belegering','XLVII','De Tweede Citadel',
         "De binnenste citadel — geen aanvulling, geen verzwakking, alles in.",
         'HIGHLANDS',  'ASSAULT',    'DEFENSIVE',
         {'infantry': 30, 'heavy_infantry': 14, 'cavalry': 4, 'artillery': 6},
         None, (970, 350)),
        ('m48_keizers_arena','XLVIII','Keizers Arena',
         "Eén op één met de keizer en zijn lijfwacht. Geen artillerie.",
         'MIXED',      'COMMANDER',  'AGGRESSIVE',
         {'infantry': 18, 'heavy_infantry': 6, 'cavalry': 8, 'artillery': 0},
         {'infantry': 22, 'heavy_infantry': 10, 'cavalry': 6, 'artillery': 0},
         (430, 410)),
        ('m49_ragnarok',     'XLIX', 'Ragnarok',
         "Eindeloze golven. Hou stand zo lang als je kunt.",
         'TWIN_RIVERS','LAST_STAND', 'AGGRESSIVE',
         {'infantry': 26, 'heavy_infantry': 12, 'cavalry': 6, 'artillery': 6},
         None, (610, 410)),
        ('m50_de_ondergang', 'L',    'De Ondergang',
         "De keizer zelf. Geen versterking. Geen omweg. Geen genade.",
         'TWIN_RIVERS','COMMANDER',  'AGGRESSIVE',
         {'infantry': 26, 'heavy_infantry': 10, 'cavalry': 8, 'artillery': 4},
         {'infantry': 40, 'heavy_infantry': 14, 'cavalry': 12, 'artillery': 6},
         (820, 410)),
    ]
    prev = 'm18_eindstrijd'
    for suffix, roman, dutch, brief, biome, gm, pers, pf, ef, node in L:
        m = {
            'id': suffix,
            'name': f'{roman} · {dutch}',
            'brief': brief,
            'biome': biome,
            'gamemode': gm,
            'difficulty': 'NAPOLEON',
            'aiPersonality': pers,
            'forces': {'player': pf} if ef is None else {'player': pf, 'enemy': ef},
            'node': node,
            'requires': [prev],
        }
        out.append(m)
        prev = suffix


_addLateMissions(MISSIONS)


# Adaptive snake-grid for mission nodes. Overrides any per-mission `node`
# so 50 points stay evenly spread regardless of screen resolution, and
# avoids the briefing-panel strip on the right.
def _layoutCampaignNodes(missions):
    n = len(missions)
    cols = 10
    rows = (n + cols - 1) // cols
    avail_left   = 50
    avail_right  = SCREEN_WIDTH - 380   # briefing panel goes right of this
    avail_top    = 150                  # below title
    avail_bottom = SCREEN_HEIGHT - 90   # above bottom buttons
    avail_w = max(400, avail_right - avail_left)
    avail_h = max(300, avail_bottom - avail_top)
    x_step = avail_w / cols
    y_step = avail_h / rows
    for i, m in enumerate(missions):
        row = i // cols
        col = i % cols
        # Snake: even rows L→R, odd rows R→L so the connecting line stays
        # neighbour-to-neighbour without crisscrossing the whole map.
        if row % 2 == 1:
            col = cols - 1 - col
        x = int(avail_left + (col + 0.5) * x_step)
        y = int(avail_top  + (row + 0.5) * y_step)
        m['node'] = (x, y)

_layoutCampaignNodes(MISSIONS)

MISSIONS_BY_ID = {m['id']: m for m in MISSIONS}


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

def markMissionComplete(mission_id: str):
    """Called by main.py after a successful mission play."""
    data = _loadProgress()
    if mission_id not in data['completed']:
        data['completed'].append(mission_id)
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
# CampaignMenu — world map
# ════════════════════════════════════════════════════════════════════════════

class CampaignMenu:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.selected = None    # selected mission dict (for briefing panel)

    def run(self):
        while True:
            data      = _loadProgress()
            completed = set(data.get('completed', []))
            result    = self._loop(completed)
            if result is None:
                continue
            action, payload = result
            if action == 'play':
                return 'play', payload
            if action == 'reset':
                _saveProgress({'completed': []})
                self.selected = None
                continue
            if action == 'back':
                return 'back', None
            if action == 'quit':
                return 'quit', None

    def _loop(self, completed):
        cx = SCREEN_WIDTH // 2

        back_rect  = pygame.Rect(30, SCREEN_HEIGHT - 56, 140, 38)
        reset_rect = pygame.Rect(SCREEN_WIDTH - 180, SCREEN_HEIGHT - 56, 150, 38)

        # Briefing panel on the right if a mission is selected
        panel_rect = pygame.Rect(SCREEN_WIDTH - 360, 150, 320, 420)

        while True:
            mx, my = pygame.mouse.get_pos()
            click  = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return ('quit', None)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.selected is not None:
                        self.selected = None
                    else:
                        return ('back', None)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            # Title
            tf = _font(44, bold=True)
            _renderShadow(self.screen, "CAMPAGNE", tf, _GOLD_LIGHT,
                          cx - tf.size("CAMPAGNE")[0] // 2, 40, offset=3)
            _drawDivider(self.screen, 100)

            # Progress line
            done = len(completed)
            total = len(MISSIONS)
            sub = f"Vooruitgang:  {done} / {total}  missies"
            ss = _font(16).render(sub, True, _PARCHMENT)
            self.screen.blit(ss, (cx - ss.get_width() // 2, 115))

            # Draw connecting lines between nodes (based on `requires`)
            for mission in MISSIONS:
                me  = mission['node']
                stat = _status(mission, completed)
                for dep_id in mission.get('requires', []):
                    dep = MISSIONS_BY_ID.get(dep_id)
                    if not dep: continue
                    dep_stat = _status(dep, completed)
                    # Line colour: gold if this edge leads to a cleared
                    # mission, dim if downstream still locked.
                    if stat == 'done':
                        col = _GOLD_LIGHT
                    elif stat == 'available':
                        col = _GOLD
                    else:
                        col = (70, 55, 40)
                    self._drawPath(dep['node'], me, col,
                                   width=4 if stat != 'locked' else 2)

            # Draw nodes + pick up hovered/clicked
            hovered = None
            for mission in MISSIONS:
                stat   = _status(mission, completed)
                cxn, cyn = mission['node']
                # Pulse gold for the current available mission
                if stat == 'done':
                    fill = (90, 190, 110)
                    ring = (160, 240, 160)
                    radius = 18
                elif stat == 'available':
                    pulse = 4 * math.sin(self.tick * 0.1)
                    fill = (240, 210, 90)
                    ring = (255, 240, 150)
                    radius = int(19 + pulse)
                else:
                    fill = (200, 188, 162)     # faded parchment
                    ring = (150, 130,  95)
                    radius = 15

                pygame.draw.circle(self.screen, fill, (cxn, cyn), radius)
                pygame.draw.circle(self.screen, ring, (cxn, cyn), radius, 2)
                # Label under the node — only the roman numeral so 50 nodes
                # don't have overlapping full-name labels. Full name shows
                # in the briefing panel on selection / hover.
                short = mission['name'].split(' · ')[0]
                lbl = _font(13, bold=(stat == 'available')).render(
                    short, True,
                    _WHITE if stat != 'locked' else _MUTED)
                self.screen.blit(lbl, (cxn - lbl.get_width() // 2, cyn + radius + 2))

                # Hit-test (don't let briefing panel eat clicks on its own nodes)
                if (cxn - mx) ** 2 + (cyn - my) ** 2 <= (radius + 4) ** 2:
                    hovered = mission

            # Briefing panel (only when a mission is selected)
            play_hover = False
            if self.selected is not None:
                stat = _status(self.selected, completed)
                pygame.draw.rect(self.screen, (244, 236, 219), panel_rect,
                                 border_radius=6)
                pygame.draw.rect(self.screen, _GOLD, panel_rect, 2,
                                 border_radius=6)
                tx = panel_rect.x + 16
                ty = panel_rect.y + 14
                nm = _font(22, bold=True).render(self.selected['name'], True,
                                                 _GOLD_LIGHT)
                self.screen.blit(nm, (tx, ty))
                ty += 32
                # Brief text (multi-line)
                for line in self.selected['brief'].split('\n'):
                    ls = _font(14).render(line, True, _PARCHMENT)
                    self.screen.blit(ls, (tx, ty)); ty += 20
                ty += 10
                # Stats block
                stats = [
                    f"Biome:      {self.selected['biome']}",
                    f"Modus:      {self.selected['gamemode']}",
                    f"Moeilijk:   {self.selected['difficulty']}",
                ]
                ai = self.selected.get('aiPersonality')
                if ai: stats.append(f"AI stijl:   {ai}")
                fp = self.selected.get('forces', {}).get('player')
                if fp:
                    stats.append(
                        f"Leger:      {fp.get('infantry', 0)} inf · "
                        f"{fp.get('heavy_infantry', 0)} heavy · "
                        f"{fp.get('cavalry', 0)} cav · "
                        f"{fp.get('artillery', 0)} art")
                for s in stats:
                    ss = _font(13).render(s, True, _MUTED)
                    self.screen.blit(ss, (tx, ty)); ty += 18

                # Status banner
                ty = panel_rect.bottom - 96
                status_txt = {'done': "✓ AFGEROND — speel opnieuw?",
                              'available': "Beschikbaar",
                              'locked': "✗ Vergrendeld"}[stat]
                status_col = {'done': (120, 220, 120),
                              'available': _GOLD_LIGHT,
                              'locked': (200, 120, 120)}[stat]
                sts = _font(14, bold=True).render(status_txt, True, status_col)
                self.screen.blit(sts, (tx, ty))

                play_rect = pygame.Rect(panel_rect.x + 16,
                                        panel_rect.bottom - 58,
                                        panel_rect.width - 32, 44)
                play_enabled = (stat in ('available', 'done'))
                play_label   = "Speel ▶" if stat == 'available' else "Opnieuw ▶"
                play_hover   = _button(self.screen, play_rect, play_label,
                                       mx, my, enabled=play_enabled)

            # Hover tooltip — full mission name above the cursor so players
            # don't have to click each node to know what it is.
            if hovered is not None and self.selected is None:
                tip_surf = _font(15, bold=True).render(
                    hovered['name'], True, _GOLD_LIGHT)
                pad = 6
                tw, th = tip_surf.get_width() + pad * 2, tip_surf.get_height() + pad * 2
                tx = max(8, min(SCREEN_WIDTH - tw - 8, mx - tw // 2))
                ty = max(8, my - th - 14)
                bg = pygame.Surface((tw, th), pygame.SRCALPHA)
                bg.fill((20, 20, 30, 220))
                self.screen.blit(bg, (tx, ty))
                pygame.draw.rect(self.screen, _GOLD, (tx, ty, tw, th), 1)
                self.screen.blit(tip_surf, (tx + pad, ty + pad))

            # Bottom buttons
            back_hover  = _button(self.screen, back_rect,  "Terug",
                                  mx, my)
            reset_hover = _button(self.screen, reset_rect, "Reset vooruitgang",
                                  mx, my)

            if click:
                if play_hover and self.selected:
                    if _status(self.selected, completed) in ('available', 'done'):
                        return ('play', self.selected)
                elif hovered is not None \
                        and _status(hovered, completed) != 'locked':
                    self.selected = hovered
                elif back_hover:
                    return ('back', None)
                elif reset_hover:
                    return ('reset', None)
                else:
                    # Clicked empty space — deselect the briefing
                    if self.selected and not panel_rect.collidepoint(mx, my):
                        self.selected = None

            pygame.display.flip()
            self.clock.tick(60)

    def _drawPath(self, a, b, color, width=3):
        """Draw a softly-curved line between two map nodes."""
        ax, ay = a; bx, by = b
        # Quadratic bezier control pt biased toward average-y with a bit of arc
        mx = (ax + bx) / 2
        my = (ay + by) / 2 - 40
        steps = 24
        prev = a
        for i in range(1, steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * mx + t * t * bx
            y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * my + t * t * by
            pygame.draw.line(self.screen, color, prev, (int(x), int(y)), width)
            prev = (int(x), int(y))
