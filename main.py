# Nerds ad War
# Entry point — loading screen → splash screen → main menu → lobby → game

import os
import subprocess
import sys

# ── Frozen-exe setup ─────────────────────────────────────────────────────────
# Nuitka (en PyInstaller) compileren naar een exe. We chdir naar de map van de
# exe zodat os.getcwd()-paden (audio, settings, maps) altijd schrijfbaar zijn.
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(_exe_dir)

# ── First-launch dependency bootstrap ───────────────────────────────────────
# Players who just double-click main.py shouldn't have to know about pip.
# If any required library is missing we install them from requirements.txt
# before the real imports run. Subsequent launches skip straight through.
def _ensureDeps():
    try:
        import pygame   # noqa: F401
        return
    except ImportError:
        pass
    req = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'requirements.txt')
    if not os.path.exists(req):
        print("[setup] requirements.txt ontbreekt — kan niet auto-installeren.")
        return
    print("[setup] Benodigde libraries worden geïnstalleerd…")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install',
                               '-r', req])
    except subprocess.CalledProcessError as e:
        print(f"[setup] FOUT: pip install faalde ({e}). Installeer handmatig:"
              f"\n    {sys.executable} -m pip install -r {req}")
        sys.exit(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)

_ensureDeps()

import random
import pygame

# ── Loading screen helpers ───────────────────────────────────────────────────
_load_surf   = None
_load_font_b = None
_load_font_s = None

def _init_loading():
    global _load_surf, _load_font_b, _load_font_s
    pygame.display.set_caption("Nerds ad War 2")
    _load_surf   = pygame.display.set_mode((480, 270))
    _load_font_b = pygame.font.SysFont(None, 52)
    _load_font_s = pygame.font.SysFont(None, 28)

def _draw_loading(progress: float, status: str):
    """Draw a loading screen. progress 0.0–1.0."""
    W, H = 480, 270
    _load_surf.fill((22, 36, 14))

    # Title
    title = _load_font_b.render("Nerds ad War 2", True, (240, 210, 70))
    _load_surf.blit(title, title.get_rect(center=(W // 2, 85)))

    # Status
    stxt = _load_font_s.render(status, True, (160, 190, 130))
    _load_surf.blit(stxt, stxt.get_rect(center=(W // 2, 148)))

    # Progress bar
    bw, bh = 320, 14
    bx, by = (W - bw) // 2, 175
    pygame.draw.rect(_load_surf, (45, 65, 30), (bx, by, bw, bh), border_radius=7)
    fill_w = max(0, min(bw, int(bw * progress)))
    if fill_w > 0:
        pygame.draw.rect(_load_surf, (100, 185, 70),
                         (bx, by, fill_w, bh), border_radius=7)

    # Tip onderaan
    tip = _load_font_s.render("Even geduld…", True, (80, 110, 60))
    _load_surf.blit(tip, tip.get_rect(center=(W // 2, 240)))

    pygame.display.flip()

    # Drain event queue so Windows niet denkt dat het programma hangt
    for _e in pygame.event.get():
        if _e.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit


if __name__ == '__main__':

    # Haal desktop-resolutie op VOOR we een venster aanmaken, anders geeft
    # Info() de loading-window resolutie terug op sommige systemen.
    pygame.init()
    _desktop_info = pygame.display.Info()
    _DESK_W = _desktop_info.current_w
    _DESK_H = _desktop_info.current_h

    # Zet constanten NU, vóór alle imports — anders laden de UI-modules met
    # de standaard 1280×720 en schaalt de hele UI niet mee.
    import src.constants as C
    C.SCREEN_WIDTH  = _DESK_W
    C.SCREEN_HEIGHT = _DESK_H

    # Show loading window as early as possible
    _init_loading()
    _draw_loading(0.05, "Opstarten…")

    # ── Update check (alleen in gebouwde exe, stil bij offline) ──────────────
    _draw_loading(0.10, "Controleer op updates…")
    from src import updater
    from src.version import VERSION
    if updater.runUpdateFlow(VERSION):
        pygame.quit()
        raise SystemExit

    # ── Heavy imports (these are the slow part on first run) ─────────────────
    _draw_loading(0.20, "Audio laden…")
    from src import audio

    _draw_loading(0.45, "Audio genereren…")
    audio.init()   # synthesises WAV files on first run — takes a moment

    _draw_loading(0.65, "Menu laden…")
    from src.game.menu import (SplashScreen, MainMenu, LobbyScreen,
                                MultiplayerMenu, SandboxMenu, CampaignMenu,
                                markMissionComplete, TutorialMenu,
                                markTutorialComplete, SettingsMenu)

    _draw_loading(0.85, "Game laden…")
    from src.game.game import Game

    _draw_loading(1.00, "Klaar!")
    pygame.time.wait(120)   # kort even zichtbaar houden voordat we switchen

    # ── Switch naar de gekozen display-mode ──────────────────────────────────
    # SCALED houdt de logische resolutie gelijk aan SCREEN_WIDTH/HEIGHT — de
    # toggle in het settings-menu kan dus tussen fullscreen en windowed
    # wisselen zonder dat menu-layouts herberekend hoeven te worden.
    from src import display as displaymode
    screen = displaymode.applyMode(
        displaymode.loadMode(), C.SCREEN_WIDTH, C.SCREEN_HEIGHT)
    pygame.display.set_caption(C.TITLE)
    clock = pygame.time.Clock()

    # ── Splash ───────────────────────────────────────────────────────────────
    result = SplashScreen(screen, clock).run()
    if result == 'quit':
        pygame.quit()
        raise SystemExit

    # ── Main loop (menu → lobby → game → menu → …) ───────────────────────────
    while True:
        mode = MainMenu(screen, clock).run()
        if mode == 'quit':
            break

        if mode == 'singleplayer':
            config = LobbyScreen(screen, clock).run()
            if config == 'quit':
                break
            if config == 'back':
                continue

            audio.stop_music()
            outcome = Game(
                seed       = random.randint(0, 9999),
                screen     = screen,
                clock      = clock,
                biome      = config['biome'],
                difficulty = config['difficulty'],
                gamemode   = config['gamemode'],
                customMap  = config.get('customMap'),
            ).run()

            if outcome == 'quit':
                break
            continue

        if mode == 'multiplayer':
            outcome, config, sessions = MultiplayerMenu(screen, clock).run()
            if outcome == 'quit':
                break
            if outcome == 'back' or outcome != 'start':
                continue

            audio.stop_music()
            try:
                game_outcome = Game(
                    seed       = config['seed'],
                    screen     = screen,
                    clock      = clock,
                    biome      = config['biome'],
                    difficulty = config['difficulty'],
                    gamemode   = config['gamemode'],
                    netRole    = config['role'],
                    sessions   = sessions,
                    mode       = config.get('mode', '1v1'),
                    mySlot     = config.get('mySlot', 0),
                    slotNames  = config.get('slotNames', []),
                    slotColors = config.get('slotColors', []),
                    customMap  = config.get('customMap'),
                    botSlots   = config.get('botSlots', []),
                ).run()
            finally:
                for s in sessions or []:
                    s.close()

            if game_outcome == 'quit':
                break
            continue

        if mode == 'settings':
            SettingsMenu(screen, clock).run()
            # Settings can switch fullscreen ↔ windowed which invalidates
            # the previous screen surface. Pick up the live one.
            screen = pygame.display.get_surface()
            continue

        if mode == 'tutorial':
            outcome, mission = TutorialMenu(screen, clock).run()
            if outcome == 'quit':
                break
            if outcome != 'play' or not mission:
                continue
            audio.stop_music()
            game = Game(
                seed          = random.randint(0, 9999),
                screen        = screen,
                clock         = clock,
                biome         = mission['biome'],
                difficulty    = mission['difficulty'],
                gamemode      = mission['gamemode'],
                forces        = mission.get('forces'),
                aiPersonality = mission.get('aiPersonality'),
            )
            game_outcome = game.run()
            if game.winner == 'player':
                markTutorialComplete(mission['id'])
            if game_outcome == 'quit':
                break
            continue

        if mode == 'campaign':
            outcome, mission = CampaignMenu(screen, clock).run()
            if outcome == 'quit':
                break
            if outcome != 'play' or not mission:
                continue
            audio.stop_music()
            game = Game(
                seed          = random.randint(0, 9999),
                screen        = screen,
                clock         = clock,
                biome         = mission['biome'],
                difficulty    = mission['difficulty'],
                gamemode      = mission['gamemode'],
                forces        = mission.get('forces'),
                aiPersonality = mission.get('aiPersonality'),
            )
            game_outcome = game.run()
            if game.winner == 'player':
                markMissionComplete(mission['id'])
            if game_outcome == 'quit':
                break
            continue

        if mode == 'sandbox':
            outcome, data = SandboxMenu(screen, clock).run()
            if outcome == 'quit':
                break
            if outcome != 'play' or not data:
                continue
            audio.stop_music()
            game_outcome = Game(
                seed      = random.randint(0, 9999),
                screen    = screen,
                clock     = clock,
                biome     = 'GRASSLAND',
                difficulty= 'NORMAAL',
                gamemode  = 'STANDAARD',
                customMap = data,
            ).run()
            if game_outcome == 'quit':
                break
            continue

        continue

    pygame.quit()
    raise SystemExit
