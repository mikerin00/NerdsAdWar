# Nerds at War
# Entry point — loading screen → splash screen → main menu → lobby → game

import os
import subprocess
import sys

# ── Frozen-exe setup ─────────────────────────────────────────────────────────
# Nuitka / PyInstaller compile to an exe. chdir to the exe's directory so that
# os.getcwd() paths (audio, settings, maps) are always writable.
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(_exe_dir)
    # Copy bundled custom music to the asset folder on first run
    _dst_music = os.path.join(_exe_dir, 'assets', 'audio', 'music_menu_custom.mpeg')
    if not os.path.isfile(_dst_music):
        import glob as _glob, shutil as _shutil
        _pattern = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                'NerdsAdWar', '**', 'music_menu_custom.mpeg')
        _found = _glob.glob(_pattern, recursive=True)
        if _found:
            os.makedirs(os.path.dirname(_dst_music), exist_ok=True)
            _shutil.copy2(_found[0], _dst_music)

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
        print("[setup] requirements.txt missing — cannot auto-install.")
        return
    print("[setup] Installing required libraries…")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install',
                               '-r', req])
    except subprocess.CalledProcessError as e:
        print(f"[setup] ERROR: pip install failed ({e}). Install manually:"
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
    pygame.display.set_caption("Nerds at War")
    _logo_path = os.path.join(os.getcwd(), 'assets', 'logo.png')
    if os.path.isfile(_logo_path):
        icon = pygame.image.load(_logo_path)
        pygame.display.set_icon(icon)
    _load_surf   = pygame.display.set_mode((480, 270))
    _load_font_b = pygame.font.SysFont(None, 52)
    _load_font_s = pygame.font.SysFont(None, 28)

def _draw_loading(progress: float, status: str):
    """Draw a loading screen. progress 0.0–1.0."""
    W, H = 480, 270
    _load_surf.fill((22, 36, 14))

    # Title
    title = _load_font_b.render("Nerds at War", True, (240, 210, 70))
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
    tip = _load_font_s.render("Please wait…", True, (80, 110, 60))
    _load_surf.blit(tip, tip.get_rect(center=(W // 2, 240)))

    pygame.display.flip()

    # Drain event queue so Windows niet denkt dat het programma hangt
    for _e in pygame.event.get():
        if _e.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit


if __name__ == '__main__':
    import traceback, ctypes as _ctypes

    def _crash(msg):
        _log = os.path.join(
            os.path.dirname(os.path.abspath(sys.executable)), 'crash.log')
        try:
            open(_log, 'w').write(msg)
        except Exception:
            pass
        _ctypes.windll.user32.MessageBoxW(None, msg[:500], "Crash", 0x10)

    try:
        # Read desktop resolution BEFORE creating any window — otherwise Info()
        # returns the loading-window resolution on some systems.
        pygame.init()
        _desktop_info = pygame.display.Info()
        _DESK_W = _desktop_info.current_w
        _DESK_H = _desktop_info.current_h

        # Patch constants NOW, before all imports — otherwise UI modules load
        # with the default 1280×720 and the entire layout won't scale.
        import src.constants as C
        C.SCREEN_WIDTH  = _DESK_W
        C.SCREEN_HEIGHT = _DESK_H

        # Show loading window as early as possible
        _init_loading()
        _draw_loading(0.05, "Starting…")

        # ── Update check (only in built exe, silent when offline) ────────────────
        _draw_loading(0.10, "Checking for updates…")
        from src import updater
        from src.version import VERSION
        updater.downloadPortraits()   # background thread — downloads missing PNGs
        if updater.runUpdateFlow(VERSION):
            pygame.quit()
            raise SystemExit

        # ── Heavy imports (these are the slow part on first run) ─────────────────
        _draw_loading(0.20, "Loading audio…")
        from src import audio

        _draw_loading(0.45, "Generating audio…")
        audio.init()   # synthesises WAV files on first run — takes a moment

        _draw_loading(0.65, "Loading menu…")
        from src.game.menu import (SplashScreen, MainMenu, LobbyScreen,
                                    MultiplayerMenu, SandboxMenu, CampaignMenu,
                                    markMissionComplete, TutorialMenu,
                                    markTutorialComplete, SettingsMenu,
                                    WhatsNewScreen, shouldShowWhatsNew,
                                    markWhatsNewSeen, StoryDialogScreen)

        _draw_loading(0.85, "Loading game…")
        from src.game.game import Game

        _draw_loading(1.00, "Ready!")
        pygame.time.wait(120)   # brief pause so the "Ready!" message is visible

        # ── Apply the chosen display mode ─────────────────────────────────────────
        # SCALED keeps the logical resolution equal to SCREEN_WIDTH/HEIGHT so the
        # fullscreen ↔ windowed toggle in Settings never requires a layout rebuild.
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

        # ── What's New (eenmalig per versie) ─────────────────────────────────────
        if shouldShowWhatsNew(VERSION):
            result = WhatsNewScreen(screen, clock, VERSION).run()
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
                        seed         = config['seed'],
                        screen       = screen,
                        clock        = clock,
                        biome        = config['biome'],
                        difficulty   = config['difficulty'],
                        gamemode     = config['gamemode'],
                        netRole      = config['role'],
                        sessions     = sessions,
                        mode         = config.get('mode', '1v1'),
                        mySlot       = config.get('mySlot', 0),
                        slotNames    = config.get('slotNames', []),
                        slotColors   = config.get('slotColors', []),
                        customMap    = config.get('customMap'),
                        botSlots     = config.get('botSlots', []),
                        coopPlayers  = config.get('coopPlayers'),
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

            if mode == 'whats_new':
                result = WhatsNewScreen(screen, clock, VERSION).run()
                markWhatsNewSeen(VERSION)
                if result == 'quit':
                    break
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

                def _play_dialogs(keys):
                    if not keys:
                        return
                    for k in ([keys] if isinstance(keys, str) else keys):
                        StoryDialogScreen(screen, clock, k).run()

                _play_dialogs(mission.get('dialog_before'))

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
                    markMissionComplete(mission['id'], game.calcStars())
                    _play_dialogs(mission.get('dialog_after'))

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

    except SystemExit:
        raise
    except Exception:
        try:
            pygame.quit()
        except Exception:
            pass
        _crash(traceback.format_exc())
