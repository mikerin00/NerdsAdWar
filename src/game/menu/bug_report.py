# Module: menu.bug_report
# In-game bug report screen — sends to a Discord webhook.
# Set DISCORD_WEBHOOK_URL to your channel webhook.
# If left empty, reports are saved to bug_reports.txt instead.

import datetime
import json
import os
import platform
import threading
import urllib.error
import urllib.request

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src.game.menu._common import (
    _DARK_BG, _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER,
    _font,
)

try:
    from src.version import VERSION
except Exception:
    VERSION = '?'

DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1496212886824026376/fkwWYOiIA5WDf5-dnPAqvKYueEHZfWYEN27lYqYBSD4zmambwVM7TPYnu5Z5HL3pAV9H'

_LOCAL_FILE = os.path.join(os.getcwd(), 'bug_reports.txt')
_MAX_CHARS  = 800
_BOX_W      = 640
_BOX_H      = 420
_INPUT_H    = 200


def _send_report(description: str):
    ts   = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    sys_ = f"{platform.system()} {platform.release()}"
    full = (f"**Nerds at War {VERSION}** — {ts}\n"
            f"Platform: {sys_}\n\n"
            f"{description}")

    if DISCORD_WEBHOOK_URL:
        payload = json.dumps({'content': full[:2000]}).encode()
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            urllib.request.urlopen(req, timeout=8)
        except (urllib.error.URLError, OSError):
            _save_locally(full)
    else:
        _save_locally(full)


def _save_locally(text: str):
    try:
        with open(_LOCAL_FILE, 'a', encoding='utf-8') as f:
            f.write(text + '\n' + '-' * 60 + '\n')
    except OSError:
        pass


class BugReportScreen:
    """Modal bug-report overlay.
    Usage:  BugReportScreen(screen, clock, bg).run()
    bg — frozen background surface (game frame or menu).
    Returns when dismissed."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 bg: pygame.Surface):
        self._screen = screen
        self._clock  = clock
        self._bg     = bg
        self._text   = ''
        self._status = None   # None | 'sending' | 'sent' | 'saved'
        self._cursor_tick = 0

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2
        self._box = pygame.Rect(cx - _BOX_W // 2, cy - _BOX_H // 2, _BOX_W, _BOX_H)

        bw, bh = 140, 44
        gap = 20
        total = bw * 2 + gap
        bx = cx - total // 2
        by = self._box.bottom - bh - 20
        self._send_rect   = pygame.Rect(bx,          by, bw, bh)
        self._cancel_rect = pygame.Rect(bx + bw + gap, by, bw, bh)

        # Input area rect
        self._input_rect = pygame.Rect(
            self._box.x + 20,
            self._box.y + 120,
            _BOX_W - 40,
            _INPUT_H,
        )

    def run(self):
        pygame.key.set_repeat(400, 40)
        try:
            while True:
                mx, my = pygame.mouse.get_pos()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    if event.type == pygame.KEYDOWN:
                        if self._status in ('sent', 'saved'):
                            return
                        if event.key == pygame.K_ESCAPE:
                            return
                        elif event.key == pygame.K_BACKSPACE:
                            self._text = self._text[:-1]
                        elif event.key == pygame.K_RETURN:
                            if len(self._text) < _MAX_CHARS:
                                self._text += '\n'
                        elif event.unicode and len(self._text) < _MAX_CHARS:
                            ch = event.unicode
                            if ch.isprintable() or ch == '\t':
                                self._text += ch
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._status in ('sent', 'saved'):
                            return
                        if self._send_rect.collidepoint(mx, my):
                            self._submit()
                        elif self._cancel_rect.collidepoint(mx, my):
                            return

                self._cursor_tick += 1
                self._draw(mx, my)
                self._clock.tick(60)
        finally:
            pygame.key.set_repeat(0, 0)

    def _submit(self):
        if self._status == 'sending' or not self._text.strip():
            return
        self._status = 'sending'
        desc = self._text.strip()

        def _worker():
            _send_report(desc)
            self._status = 'saved' if not DISCORD_WEBHOOK_URL else 'sent'

        threading.Thread(target=_worker, daemon=True).start()

    def _draw(self, mx, my):
        surf = self._screen
        surf.blit(self._bg, (0, 0))

        # Dim overlay
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((10, 8, 5, 160))
        surf.blit(dim, (0, 0))

        box = self._box
        pygame.draw.rect(surf, _DARK_BG, box, border_radius=8)
        pygame.draw.rect(surf, _GOLD,    box, 2, border_radius=8)

        cx = box.centerx

        # Title
        tf = _font(28, bold=True)
        tt = tf.render("Report a Bug", True, _PARCHMENT)
        surf.blit(tt, (cx - tt.get_width() // 2, box.top + 16))

        # Subtitle
        sf = _font(16)
        st = sf.render("Describe what went wrong (then press Send).", True, _MUTED)
        surf.blit(st, (cx - st.get_width() // 2, box.top + 58))

        pygame.draw.line(surf, _GOLD,
                         (box.x + 20, box.top + 88), (box.right - 20, box.top + 88), 1)

        # Text input area
        ir = self._input_rect
        pygame.draw.rect(surf, (30, 26, 20), ir, border_radius=4)
        pygame.draw.rect(surf, _GOLD, ir, 1, border_radius=4)

        if self._status in ('sent', 'saved'):
            msg   = "Sent! Thank you." if self._status == 'sent' else "Saved to bug_reports.txt."
            mf    = _font(22, bold=True)
            ms    = mf.render(msg, True, (120, 220, 120))
            surf.blit(ms, (cx - ms.get_width() // 2,
                           ir.centery - ms.get_height() // 2))
            cf = _font(15)
            cs = cf.render("Press any key or click to close.", True, _MUTED)
            surf.blit(cs, (cx - cs.get_width() // 2, ir.centery + 30))
        elif self._status == 'sending':
            sf2  = _font(18)
            ss   = sf2.render("Sending…", True, _MUTED)
            surf.blit(ss, (cx - ss.get_width() // 2,
                           ir.centery - ss.get_height() // 2))
        else:
            # Render typed text with word-wrap
            tf2   = _font(17)
            lh    = tf2.get_linesize()
            pad   = 10
            y     = ir.y + pad
            max_w = ir.width - pad * 2

            display = self._text
            blink   = (self._cursor_tick // 30) % 2 == 0
            if blink:
                display += '|'

            for raw_line in display.split('\n'):
                words = raw_line.split(' ') if raw_line else ['']
                line  = ''
                for w in words:
                    test = (line + ' ' + w).strip()
                    if tf2.size(test)[0] <= max_w:
                        line = test
                    else:
                        if line:
                            surf.blit(tf2.render(line, True, _WHITE), (ir.x + pad, y))
                            y += lh
                        line = w
                if line:
                    surf.blit(tf2.render(line, True, _WHITE), (ir.x + pad, y))
                    y += lh

            # Char counter
            cf3 = _font(13)
            cc  = cf3.render(f"{len(self._text)}/{_MAX_CHARS}", True, _DIM)
            surf.blit(cc, (ir.right - cc.get_width() - 6, ir.bottom + 4))

        # Buttons
        for rect, label, active in (
            (self._send_rect,   'Send',   self._status is None and bool(self._text.strip())),
            (self._cancel_rect, 'Cancel', True),
        ):
            hover = rect.collidepoint(mx, my) and active
            bg    = _BTN_BG_HOVER if hover else _BTN_BG
            brd   = _GOLD_LIGHT if hover else (_GOLD if active else _DIM)
            col   = _WHITE if hover else (_PARCHMENT if active else _DIM)
            pygame.draw.rect(surf, bg,  rect, border_radius=5)
            pygame.draw.rect(surf, brd, rect, 2 if hover else 1, border_radius=5)
            lf = _font(22, bold=hover)
            ls = lf.render(label, True, col)
            surf.blit(ls, (rect.centerx - ls.get_width() // 2,
                           rect.centery - ls.get_height() // 2))

        pygame.display.flip()
