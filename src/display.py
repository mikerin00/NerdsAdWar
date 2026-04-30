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


def loadMode():
    try:
        with open(_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return FULLSCREEN
    mode = data.get('mode')
    return mode if mode in _VALID else FULLSCREEN


def saveMode(mode):
    if mode not in _VALID:
        return
    try:
        with open(_FILE, 'w', encoding='utf-8') as f:
            json.dump({'mode': mode}, f, indent=2)
    except OSError:
        pass


def applyMode(mode, logicalW, logicalH):
    """Re-create the display surface in the requested mode. Returns the new
    surface so callers can replace their cached `screen` reference.

    SCALED keeps the logical resolution fixed at logicalW×logicalH regardless
    of window size, so menus and game UI never need to reflow. Fall back to
    plain flags when the hardware renderer is unavailable."""
    scaled = getattr(pygame, 'SCALED', 0)

    if mode == FULLSCREEN:
        if scaled:
            try:
                # (0, 0) → pygame uses the native desktop resolution for the
                # window and scales the logical surface to fit automatically.
                return pygame.display.set_mode((0, 0), scaled | pygame.FULLSCREEN)
            except pygame.error:
                pass
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

    else:  # WINDOWED
        # Fit the initial window within 90 % of the desktop so it never
        # overflows on laptops or monitors smaller than logicalW×logicalH.
        try:
            sw, sh = pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError):
            info   = pygame.display.Info()
            sw, sh = info.current_w, info.current_h
        scale = min(sw * 0.90 / logicalW, sh * 0.90 / logicalH, 1.0)
        win_w = max(int(logicalW * scale), 320)
        win_h = max(int(logicalH * scale), 180)
        if scaled:
            try:
                return pygame.display.set_mode((win_w, win_h),
                                               scaled | pygame.RESIZABLE)
            except pygame.error:
                pass
        return pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
