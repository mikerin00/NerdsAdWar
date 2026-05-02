# Display mode handling — fullscreen vs windowed, persistent + hot-togglable.
# Logical screen size (SCREEN_WIDTH × SCREEN_HEIGHT) never changes; pygame's
# SCALED flag letterboxes/scales the logical surface to whatever the actual
# OS window is. That's why all menus keep working after a toggle without
# any layout recompute.

import json
import os

import pygame


_FILE = os.path.join(os.getcwd(), 'display.json')

FULLSCREEN = 'fullscreen'
WINDOWED   = 'windowed'

_VALID = (FULLSCREEN, WINDOWED)


def _readConfig() -> dict:
    try:
        with open(_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _writeConfig(data: dict):
    try:
        with open(_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def loadMode() -> str:
    mode = _readConfig().get('mode')
    return mode if mode in _VALID else FULLSCREEN


def saveMode(mode: str):
    if mode not in _VALID:
        return
    cfg = _readConfig()
    cfg['mode'] = mode
    _writeConfig(cfg)


def loadMonitor() -> int:
    try:
        return int(_readConfig().get('monitor', 0))
    except (TypeError, ValueError):
        return 0


def saveMonitor(index: int):
    cfg = _readConfig()
    cfg['monitor'] = index
    _writeConfig(cfg)


def getMonitorCount() -> int:
    try:
        return max(1, len(pygame.display.get_desktop_sizes()))
    except Exception:
        return 1


def _getNativeRes(monitor: int) -> tuple:
    """Return (width, height) of the given monitor index.

    On multi-monitor setups (0,0) passed to set_mode can resolve to the
    combined virtual-desktop size instead of a single screen, causing wrong
    scaling with pygame.SCALED.  Reading per-display sizes explicitly avoids
    that problem.
    """
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            idx = max(0, min(monitor, len(sizes) - 1))
            return sizes[idx]
    except Exception:
        pass
    try:
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            return info.current_w, info.current_h
    except Exception:
        pass
    return 1920, 1080


def applyMode(mode, logicalW, logicalH):
    """Re-create the display surface in the requested mode. Returns the new
    surface so callers can replace their cached `screen` reference.

    SCALED keeps the logical resolution fixed at logicalW×logicalH regardless
    of window size, so menus and game UI never need to reflow.

    The monitor index from display.json controls which physical screen is used,
    which fixes the common dual-monitor sizing issue where the game ends up on
    the wrong screen or at the wrong resolution.
    """
    monitor = loadMonitor()
    scaled  = getattr(pygame, 'SCALED', 0)

    # Clamp to actual display count (handles monitor being unplugged etc.)
    n = getMonitorCount()
    monitor = max(0, min(monitor, n - 1))

    native_w, native_h = _getNativeRes(monitor)

    if mode == FULLSCREEN:
        if scaled:
            try:
                return pygame.display.set_mode(
                    (native_w, native_h), scaled | pygame.FULLSCREEN,
                    display=monitor)
            except (pygame.error, TypeError):
                # Older pygame without display= kwarg
                try:
                    return pygame.display.set_mode(
                        (native_w, native_h), scaled | pygame.FULLSCREEN)
                except pygame.error:
                    pass
        return pygame.display.set_mode((native_w, native_h), pygame.FULLSCREEN)

    else:  # WINDOWED
        # Fit within 90 % of the chosen monitor so the window never overflows.
        scale = min(native_w * 0.90 / logicalW, native_h * 0.90 / logicalH, 1.0)
        win_w = max(int(logicalW * scale), 320)
        win_h = max(int(logicalH * scale), 180)
        if scaled:
            try:
                return pygame.display.set_mode(
                    (win_w, win_h), scaled | pygame.RESIZABLE,
                    display=monitor)
            except (pygame.error, TypeError):
                try:
                    return pygame.display.set_mode(
                        (win_w, win_h), scaled | pygame.RESIZABLE)
                except pygame.error:
                    pass
        return pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
