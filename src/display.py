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

    We prefer the SCALED flag so the logical resolution stays constant
    across toggle (and menu layouts don't need to reflow), but some setups
    can't create the hardware renderer SCALED needs — fall back to plain
    flags on failure."""
    scaled = getattr(pygame, 'SCALED', 0)
    base   = pygame.RESIZABLE if mode == WINDOWED else pygame.FULLSCREEN
    if scaled:
        try:
            return pygame.display.set_mode((logicalW, logicalH),
                                           scaled | base)
        except pygame.error:
            pass   # hardware renderer unavailable — fall through to plain
    return pygame.display.set_mode((logicalW, logicalH), base)
