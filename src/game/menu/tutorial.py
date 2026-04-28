# Module: menu.tutorial
# Three scripted tutorial missions with verbose briefings. Uses the same
# force-override/AI plumbing as Campaign, but kept separate so the campaign
# manifest stays thematic.

import os
import json

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game.menu._common import (
    _PARCHMENT, _GOLD, _GOLD_LIGHT, _DIM, _WHITE, _MUTED,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider,
    _drawButton,
)
from src import audio


TUTORIAL_PROGRESS = os.path.join(os.getcwd(), 'tutorial_progress.json')

def _progressFile() -> str:
    from src import accounts
    return accounts.tutorialProgressFile()

TUTORIALS = [
    {
        'id':   'tut1_basis',
        'name': 'Lesson 1 · The Basics',
        'brief': (
            "Welcome to Nerds at War. This is your first battle.\n"
            "\n"
            "CONTROLS:\n"
            "  Left click drag  -  select a group of units\n"
            "  Left click       -  select a single unit\n"
            "  Right click      -  move or attack\n"
            "  SPACE            -  start battle immediately\n"
            "\n"
            "FLANKING & MORALE:\n"
            "  Attacking from behind: +80% damage.\n"
            "  Attacking from the side: +35% damage.\n"
            "  Units at 0 morale flee — rally them\n"
            "  behind your lines to restore their morale.\n"
            "\n"
            "GOAL:  Defeat the small enemy group on the right.\n"
            "Focus your fire on one target at a time."
        ),
        'biome':         'GRASSLAND',
        'gamemode':      'STANDAARD',
        'difficulty':    'MAKKELIJK',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 12, 'heavy_infantry': 0, 'cavalry': 2, 'artillery': 0},
            'enemy':  {'infantry': 8,  'heavy_infantry': 0, 'cavalry': 0, 'artillery': 0},
        },
    },
    {
        'id':   'tut2_formaties',
        'name': 'Lesson 2 · Formations',
        'brief': (
            "Formations determine how your troops are positioned.\n"
            "\n"
            "SQUARE (F key):\n"
            "  Infantry forms a square: −70% damage from cavalry.\n"
            "  But: +50% damage from artillery.\n"
            "\n"
            "LINE (Shift + right click drag):\n"
            "  Draw a path — troops align themselves toward the enemy.\n"
            "  Wide firing range, but vulnerable to flanking attacks.\n"
            "\n"
            "SHIELD WALL (automatic):\n"
            "  Two heavy infantry side by side activate a shield wall:\n"
            "  −45% damage. Keep them grouped for maximum protection.\n"
            "\n"
            "GOAL:  The enemy sends cavalry. Form a square in time\n"
            "and use your artillery to stop them."
        ),
        'biome':         'GRASSLAND',
        'gamemode':      'STANDAARD',
        'difficulty':    'MAKKELIJK',
        'aiPersonality': 'AGGRESSIVE',
        'forces': {
            'player': {'infantry': 16, 'heavy_infantry': 4, 'cavalry': 0, 'artillery': 1},
            'enemy':  {'infantry': 8,  'heavy_infantry': 0, 'cavalry': 6, 'artillery': 0},
        },
    },
    {
        'id':   'tut3_terrein',
        'name': 'Lesson 3 · Terrain',
        'brief': (
            "Terrain affects speed, damage, and cover.\n"
            "\n"
            "FOREST:  Defender takes 25% less damage.\n"
            "  Speed: −40%. Ideal position for infantry.\n"
            "\n"
            "HIGH GROUND:  +25% damage when attacking downhill.\n"
            "  −20% damage when attacking uphill.\n"
            "  Artillery on a hill dominates the entire battlefield.\n"
            "\n"
            "RIVER:  −85% speed in water, −60% damage.\n"
            "  Use bridges to cross quickly.\n"
            "\n"
            "ROCKS & LAKES:  completely impassable.\n"
            "  Use them as cover or route enemies around them.\n"
            "\n"
            "GOAL:  Occupy the high ground before the enemy.\n"
            "Send cavalry via the bridge to flank."
        ),
        'biome':         'RIVER_VALLEY',
        'gamemode':      'STANDAARD',
        'difficulty':    'NORMAAL',
        'aiPersonality': 'DEFENSIVE',
        'forces': {
            'player': {'infantry': 14, 'heavy_infantry': 2, 'cavalry': 3, 'artillery': 2},
            'enemy':  {'infantry': 12, 'heavy_infantry': 3, 'cavalry': 2, 'artillery': 1},
        },
    },
    {
        'id':   'tut4_troepen',
        'name': 'Lesson 4 · Units & Matchups',
        'brief': (
            "Every unit has strengths and weaknesses.\n"
            "\n"
            "INFANTRY (range 100):  musket fire at distance.\n"
            "HEAVY INFANTRY (180 HP):  melee, slower.\n"
            "  −35% damage from infantry; +35% from cavalry.\n"
            "  Shield wall next to a neighbour: −45% extra protection.\n"
            "\n"
            "CAVALRY (HP 80, fastest):  charge = 2× damage.\n"
            "  Counter with square formation or artillery.\n"
            "\n"
            "ARTILLERY (range 260):  deploy required (1.5s).\n"
            "  Devastating vs dense groups. Protect them well.\n"
            "\n"
            "COMMANDER (240 HP):  aura around grants\n"
            "  +morale recovery & +HP recovery to allies.\n"
            "\n"
            "GOAL:  Deploy each unit at the right moment.\n"
            "Defeat the enemy by smart matchups."
        ),
        'biome':         'GRASSLAND',
        'gamemode':      'STANDAARD',
        'difficulty':    'NORMAAL',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 8, 'heavy_infantry': 4, 'cavalry': 3, 'artillery': 2},
            'enemy':  {'infantry': 10, 'heavy_infantry': 3, 'cavalry': 4, 'artillery': 1},
        },
    },
    {
        'id':   'tut5_supply',
        'name': 'Lesson 5 · Supply & Outposts',
        'brief': (
            "Units far from your HQ become exhausted. Outposts (the\n"
            "circles on the map) are neutral — capture them and they\n"
            "supply your army: better morale, faster recovery.\n"
            "\n"
            "SUPPLY EFFECT:\n"
            "  No supply: morale max = 60, slow recovery.\n"
            "  Full supply: morale max = 100, fast recovery + HP regen.\n"
            "  HP recovery only works outside combat range.\n"
            "\n"
            "TIPS:\n"
            "  Cavalry is perfect for quickly claiming an outpost.\n"
            "  Artillery near an outpost controls the terrain without\n"
            "  moving — ideal static defence.\n"
            "\n"
            "GOAL:  Defeat the enemy. Capture at least one outpost\n"
            "before attacking — you'll notice the difference in morale."
        ),
        'biome':         'MIXED',
        'gamemode':      'STANDAARD',
        'difficulty':    'NORMAAL',
        'aiPersonality': 'BALANCED',
        'forces': {
            'player': {'infantry': 18, 'heavy_infantry': 3, 'cavalry': 4, 'artillery': 2},
            'enemy':  {'infantry': 18, 'heavy_infantry': 3, 'cavalry': 4, 'artillery': 2},
        },
    },
]


# ── progress persistence ───────────────────────────────────────────────────

def _loadProgress():
    try:
        with open(_progressFile(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'completed' in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {'completed': []}

def _saveProgress(data):
    try:
        with open(_progressFile(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

def markTutorialComplete(mission_id: str):
    data = _loadProgress()
    if mission_id not in data['completed']:
        data['completed'].append(mission_id)
        _saveProgress(data)


# ── UI helpers ─────────────────────────────────────────────────────────────

def _button(surf, rect, label, mx, my, enabled=True):
    return _drawButton(surf, rect, label, mx, my, enabled=enabled, font_size=20)


# ════════════════════════════════════════════════════════════════════════════
# TutorialMenu — simple list, click opens briefing, briefing has Start button.
# ════════════════════════════════════════════════════════════════════════════

class TutorialMenu:
    """Returns:
        ('play', tutorial_dict)
        ('back', None)
        ('quit', None)
    """

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)
        self.selected = None

    def run(self):
        while True:
            data = _loadProgress()
            completed = set(data.get('completed', []))

            if self.selected is None:
                result = self._listScreen(completed)
            else:
                result = self._briefingScreen(self.selected, completed)
            if result is None:
                continue
            action, payload = result
            if action == 'play':
                return 'play', payload
            if action == 'select':
                self.selected = payload
            if action == 'deselect':
                self.selected = None
            if action == 'back':
                return 'back', None
            if action == 'quit':
                return 'quit', None

    def _listScreen(self, completed):
        cx = SCREEN_WIDTH // 2

        back_rect = pygame.Rect(30, SCREEN_HEIGHT - 60, 160, 40)
        row_h     = 80
        top_y     = 200
        row_rects = []
        for i, tut in enumerate(TUTORIALS):
            r = pygame.Rect(cx - 360, top_y + i * (row_h + 14), 720, row_h)
            row_rects.append(r)

        while True:
            mx, my = pygame.mouse.get_pos()
            click = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return ('quit', None)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return ('back', None)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(44, bold=True)
            _renderShadow(self.screen, "TUTORIAL", tf, _GOLD_LIGHT,
                          cx - tf.size("TUTORIAL")[0] // 2, 70, offset=3)
            _drawDivider(self.screen, 135)

            sub = _font(16).render("Learn all mechanics in five missions",
                                   True, _PARCHMENT)
            self.screen.blit(sub, (cx - sub.get_width() // 2, 160))

            # Rows
            for tut, r in zip(TUTORIALS, row_rects):
                done  = tut['id'] in completed
                hover = r.collidepoint(mx, my)
                bg    = (248, 232, 204) if hover else (232, 220, 196)
                pygame.draw.rect(self.screen, bg, r, border_radius=6)
                brd = _GOLD_LIGHT if hover else _GOLD
                pygame.draw.rect(self.screen, brd, r, 2, border_radius=6)
                # Check if complete
                if done:
                    pygame.draw.circle(self.screen, (120, 220, 120),
                                       (r.x + 30, r.centery), 12)
                    ch = _font(16, bold=True).render("V", True, (20, 40, 20))
                    self.screen.blit(ch, (r.x + 30 - ch.get_width() // 2,
                                          r.centery - ch.get_height() // 2))
                else:
                    pygame.draw.circle(self.screen, (80, 70, 60),
                                       (r.x + 30, r.centery), 12, 2)
                # Title + first brief line
                title = _font(22, bold=True).render(tut['name'], True,
                                                    _GOLD_LIGHT)
                self.screen.blit(title, (r.x + 60, r.y + 14))
                first_line = tut['brief'].split('\n')[0]
                fl = _font(14).render(first_line, True, _MUTED)
                self.screen.blit(fl, (r.x + 60, r.y + 46))

                if click and hover:
                    audio.play_sfx('click')
                    return ('select', tut)

            back_hover = _button(self.screen, back_rect, "Back", mx, my)
            if click and back_hover:
                audio.play_sfx('click')
                return ('back', None)

            pygame.display.flip()
            self.clock.tick(60)

    def _briefingScreen(self, tutorial, completed):
        cx = SCREEN_WIDTH // 2
        panel_rect = pygame.Rect(cx - 400, 140, 800, 460)
        start_rect = pygame.Rect(cx - 120, SCREEN_HEIGHT - 120, 240, 52)
        back_rect  = pygame.Rect(30, SCREEN_HEIGHT - 60, 160, 40)

        while True:
            mx, my = pygame.mouse.get_pos()
            click  = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return ('quit', None)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return ('deselect', None)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    click = True

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            _drawBackground(self.screen, self.tick)
            _drawParticles(self.screen, self.particles)

            tf = _font(38, bold=True)
            _renderShadow(self.screen, tutorial['name'], tf, _GOLD_LIGHT,
                          cx - tf.size(tutorial['name'])[0] // 2, 80, offset=3)
            _drawDivider(self.screen, 140)

            pygame.draw.rect(self.screen, (244, 236, 219), panel_rect,
                             border_radius=8)
            pygame.draw.rect(self.screen, _GOLD, panel_rect, 2,
                             border_radius=8)
            # Brief text (multi-line)
            y = panel_rect.y + 22
            for line in tutorial['brief'].split('\n'):
                col = _PARCHMENT
                bold = False
                if line.strip().endswith(':') or line.upper() == line and line.strip():
                    col  = _GOLD_LIGHT
                    bold = True
                elif line.startswith('GOAL'):
                    col  = (140, 220, 140)
                    bold = True
                ls = _font(16, bold=bold).render(line, True, col)
                self.screen.blit(ls, (panel_rect.x + 22, y))
                y += 24

            start_hover = _button(self.screen, start_rect, "Start Mission ▶",
                                  mx, my)
            back_hover  = _button(self.screen, back_rect, "Back", mx, my)

            if click:
                if start_hover:
                    audio.play_sfx('click')
                    return ('play', tutorial)
                elif back_hover:
                    audio.play_sfx('click')
                    return ('deselect', None)

            pygame.display.flip()
            self.clock.tick(60)
