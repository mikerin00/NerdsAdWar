# Module: menu.account_menu
# AccountLoginScreen  — shown at startup when no session is active.
# AccountProfileScreen — profile, stats, avatar, sign-out.

import os
import threading

import pygame

from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from src import audio, accounts
from src.game.menu._common import (
    _DARK_BG, _PARCHMENT, _GOLD, _GOLD_LIGHT, _MUTED, _DIM, _WHITE,
    _BTN_BG, _BTN_BG_HOVER, _BTN_BG_DISABLED, _MUTED_RED,
    _makeParticles, _updateParticles, _drawParticles,
    _drawBackground, _font, _renderShadow, _drawDivider, _drawButton,
)


# ── Avatar helpers ────────────────────────────────────────────────────────────

def _loadAvatarCircle(path: str, size: int) -> pygame.Surface | None:
    """Load an image from path, scale to size×size, clip to a circle."""
    if not path or not os.path.isfile(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.smoothscale(img, (size, size))
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return img
    except Exception:
        return None


def _drawDefaultAvatar(surf: pygame.Surface, cx: int, cy: int, r: int,
                       color=None) -> None:
    """Draw a simple person silhouette as placeholder avatar."""
    if color is None:
        color = _GOLD
    pygame.draw.circle(surf, color, (cx, cy), r, 2)
    # Head
    pygame.draw.circle(surf, color, (cx, cy - r // 3), r // 4)
    # Body trapezoid
    bw = r // 2
    pts = [(cx - bw, cy + r - 4), (cx + bw, cy + r - 4),
           (cx + bw // 2, cy + 2), (cx - bw // 2, cy + 2)]
    pygame.draw.polygon(surf, color, pts, 2)


# ── Shared text-field draw ────────────────────────────────────────────────────

def _drawField(surf, rect, label, value, active, mask=False, tick=0, error=False):
    """Draw a labelled input field. mask=True shows bullets for passwords."""
    f_lbl = _font(15)
    lbl   = f_lbl.render(label, True, _MUTED if not error else (180, 60, 60))
    surf.blit(lbl, (rect.x, rect.y - 20))

    brd = _GOLD_LIGHT if active else (_GOLD if not error else (180, 60, 60))
    bg  = _BTN_BG_HOVER if active else _BTN_BG
    pygame.draw.rect(surf, bg,  rect, border_radius=4)
    pygame.draw.rect(surf, brd, rect, 2 if active else 1, border_radius=4)

    display = ('•' * len(value)) if mask else value
    f_txt   = _font(20)
    txt     = f_txt.render(display, True, _WHITE)
    # Clip to field width
    clip_w  = rect.width - 16
    if txt.get_width() > clip_w:
        # Show the tail end of the text
        txt_x = rect.x + 8
        clip  = pygame.Rect(txt.get_width() - clip_w, 0, clip_w, txt.get_height())
        surf.blit(txt, (txt_x, rect.centery - txt.get_height() // 2), clip)
    else:
        surf.blit(txt, (rect.x + 8, rect.centery - txt.get_height() // 2))

    # Blinking cursor when active
    if active and (tick // 30) % 2 == 0:
        cx = rect.x + 8 + min(txt.get_width(), clip_w) + 2
        cy1 = rect.centery - 10
        cy2 = rect.centery + 10
        pygame.draw.line(surf, _PARCHMENT, (cx, cy1), (cx, cy2), 1)


# ══════════════════════════════════════════════════════════════════════════════
# AccountLoginScreen
# ══════════════════════════════════════════════════════════════════════════════

class AccountLoginScreen:
    """Login / register screen shown when no session is active.
    Returns 'logged_in' or 'quit'."""

    _FW = 360
    _FH = 44

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(50)

        self._mode       = 'login'   # 'login' | 'register'
        self._username   = ''
        self._password   = ''
        self._password2  = ''        # confirm (register only)
        self._activeField = 'user'  # 'user' | 'pass' | 'pass2'
        self._error      = ''
        self._pending    = False     # True while server call is in flight

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        fw, fh = self._FW, self._FH
        self._rect_user  = pygame.Rect(cx - fw // 2, cy - 60, fw, fh)
        self._rect_pass  = pygame.Rect(cx - fw // 2, cy + 10, fw, fh)
        self._rect_pass2 = pygame.Rect(cx - fw // 2, cy + 80, fw, fh)

        bw, bh = 160, 44
        self._btn_action = pygame.Rect(cx - bw // 2, cy + 170, bw, bh)
        self._btn_toggle = pygame.Rect(cx - bw // 2, cy + 228, bw, bh)

    # ── event helpers ────────────────────────────────────────────────────────

    def _handleKey(self, event):
        if event.key == pygame.K_TAB:
            order = ['user', 'pass', 'pass2'] if self._mode == 'register' else ['user', 'pass']
            idx   = order.index(self._activeField) if self._activeField in order else 0
            self._activeField = order[(idx + 1) % len(order)]
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._doAction()
            return

        target = self._activeField
        if target == 'user':
            buf = self._username
        elif target == 'pass':
            buf = self._password
        else:
            buf = self._password2

        if event.key == pygame.K_BACKSPACE:
            buf = buf[:-1]
        elif event.unicode and event.unicode.isprintable() and len(buf) < 32:
            buf += event.unicode

        if target == 'user':
            self._username  = buf
        elif target == 'pass':
            self._password  = buf
        else:
            self._password2 = buf

    def _doAction(self):
        if self._pending:
            return
        self._error = ''
        if self._mode == 'register' and self._password != self._password2:
            self._error = 'Wachtwoorden komen niet overeen.'
            return

        self._pending = True
        username, password, mode = self._username, self._password, self._mode

        def _work():
            if mode == 'login':
                ok, result = accounts.login(username, password)
            else:
                ok, result = accounts.register(username, password)
            if ok:
                audio.play_sfx('click')
                self._result = 'logged_in'
            else:
                self._error = result
            self._pending = False

        threading.Thread(target=_work, daemon=True).start()

    def _toggleMode(self):
        self._mode      = 'register' if self._mode == 'login' else 'login'
        self._error     = ''
        self._password  = ''
        self._password2 = ''
        self._activeField = 'user'

    # ── run ──────────────────────────────────────────────────────────────────

    def run(self):
        self._result = None
        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'quit'
                    self._handleKey(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not self._pending:
                        if self._rect_user.collidepoint(mx, my):
                            self._activeField = 'user'
                        elif self._rect_pass.collidepoint(mx, my):
                            self._activeField = 'pass'
                        elif self._mode == 'register' and self._rect_pass2.collidepoint(mx, my):
                            self._activeField = 'pass2'
                        elif self._btn_action.collidepoint(mx, my):
                            audio.play_sfx('click')
                            self._doAction()
                        elif self._btn_toggle.collidepoint(mx, my):
                            audio.play_sfx('click')
                            self._toggleMode()

            if self._result:
                return self._result

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(mx, my)
            self.clock.tick(60)

    # ── draw ─────────────────────────────────────────────────────────────────

    def _draw(self, mx, my):
        surf = self.screen
        cx   = SCREEN_WIDTH  // 2
        cy   = SCREEN_HEIGHT // 2

        _drawBackground(surf, self.tick)
        _drawParticles(surf, self.particles)

        # Title
        tf    = _font(52, bold=True)
        title = "NERDS AT WAR"
        tw    = tf.size(title)[0]
        _renderShadow(surf, title, tf, _GOLD_LIGHT, cx - tw // 2, 52, offset=3)
        _drawDivider(surf, 120)

        # Subtitle
        mode_lbl = "Account aanmaken" if self._mode == 'register' else "Inloggen"
        sf = _font(22, bold=True)
        sw = sf.size(mode_lbl)[0]
        _renderShadow(surf, mode_lbl, sf, _PARCHMENT, cx - sw // 2, 148)

        # Avatar placeholder
        _drawDefaultAvatar(surf, cx, 215, 36)

        # Fields
        _drawField(surf, self._rect_user,  "Gebruikersnaam",
                   self._username,  self._activeField == 'user',
                   mask=False, tick=self.tick)
        _drawField(surf, self._rect_pass,  "Wachtwoord",
                   self._password,  self._activeField == 'pass',
                   mask=True, tick=self.tick)
        if self._mode == 'register':
            _drawField(surf, self._rect_pass2, "Herhaal wachtwoord",
                       self._password2, self._activeField == 'pass2',
                       mask=True, tick=self.tick,
                       error=(bool(self._error) and 'overeen' in self._error))

        # Error
        if self._error:
            ef  = _font(16)
            et  = ef.render(self._error, True, (175, 50, 50))
            surf.blit(et, (cx - et.get_width() // 2,
                           self._btn_action.y - 26))

        # Action button (or "Verbinden..." spinner when pending)
        btn_y_base = cy + (150 if self._mode == 'register' else 130)
        btn_rect = pygame.Rect(cx - 80, btn_y_base, 160, 44)
        if self._pending:
            dots = '.' * ((self.tick // 20) % 4)
            pf  = _font(18)
            pt  = pf.render(f'Verbinden{dots}', True, _GOLD)
            surf.blit(pt, (cx - pt.get_width() // 2,
                           btn_rect.centery - pt.get_height() // 2))
        else:
            _drawButton(surf, btn_rect,
                        'Inloggen' if self._mode == 'login' else 'Registreer',
                        mx, my, font_size=20)

        # Actually use the pre-computed rects for clicks but draw at correct pos
        self._btn_action = btn_rect
        tog_rect = pygame.Rect(cx - 130, btn_y_base + 60, 260, 36)
        self._btn_toggle = tog_rect
        tog_lbl = "Nog geen account? Registreer" if self._mode == 'login' \
                  else "Al een account? Inloggen"
        tf2  = _font(15)
        tt   = tf2.render(tog_lbl, True,
                          _GOLD_LIGHT if tog_rect.collidepoint(mx, my) else _GOLD)
        surf.blit(tt, (cx - tt.get_width() // 2,
                       tog_rect.centery - tt.get_height() // 2))

        pygame.display.flip()


# ══════════════════════════════════════════════════════════════════════════════
# AccountProfileScreen
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# FriendsScreen
# ══════════════════════════════════════════════════════════════════════════════

class FriendsScreen:
    """Vriendenlijst — online status + stats per vriend, vriend toevoegen/verwijderen."""

    _FW = 380   # breedte invoerveld

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(40)

        self._friends      = None   # None = laden, [] = leeg/fout, list = geladen
        self._add_input    = ''
        self._add_error    = ''
        self._add_ok       = ''
        self._add_pending  = False
        self._field_active = False
        self._remove_pending = set()   # usernames waarvoor remove loopt

        threading.Thread(target=self._loadFriends, daemon=True).start()

    def _loadFriends(self):
        self._friends = accounts.getFriends()

    def _reload(self):
        self._friends = None
        threading.Thread(target=self._loadFriends, daemon=True).start()

    def _doAdd(self):
        if self._add_pending or not self._add_input.strip():
            return
        self._add_error = ''
        self._add_ok    = ''
        self._add_pending = True
        name = self._add_input.strip()

        def _work():
            ok, msg = accounts.addFriend(name)
            if ok:
                self._add_ok    = f'{name} toegevoegd!'
                self._add_input = ''
                self._reload()
            else:
                self._add_error = msg
            self._add_pending = False

        threading.Thread(target=_work, daemon=True).start()

    def _doRemove(self, friend_username: str):
        if friend_username in self._remove_pending:
            return
        self._remove_pending.add(friend_username)

        def _work():
            accounts.removeFriend(friend_username)
            self._remove_pending.discard(friend_username)
            self._reload()

        threading.Thread(target=_work, daemon=True).start()

    def run(self):
        cx  = SCREEN_WIDTH  // 2
        bw, bh = 200, 44
        btn_back = pygame.Rect(cx - bw // 2, SCREEN_HEIGHT - 80, bw, bh)
        fw = self._FW
        field_rect = pygame.Rect(cx - fw // 2, 200, fw, 44)
        btn_add    = pygame.Rect(cx + fw // 2 + 12, 200, 140, 44)

        while True:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return 'back'
                    if self._field_active:
                        if event.key == pygame.K_BACKSPACE:
                            self._add_input = self._add_input[:-1]
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self._doAdd()
                        elif event.unicode and event.unicode.isprintable() and len(self._add_input) < 24:
                            self._add_input += event.unicode
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_back.collidepoint(mx, my):
                        audio.play_sfx('click')
                        return 'back'
                    if btn_add.collidepoint(mx, my) and not self._add_pending:
                        audio.play_sfx('click')
                        self._doAdd()
                    self._field_active = field_rect.collidepoint(mx, my)
                    # Remove buttons — handled in _draw via hit-test list
                    if isinstance(self._friends, list):
                        for i, f in enumerate(self._friends):
                            rbtn = self._removeRect(i)
                            if rbtn.collidepoint(mx, my) and f['username'].lower() not in self._remove_pending:
                                audio.play_sfx('click')
                                self._doRemove(f['username'].lower())

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(mx, my, btn_back, field_rect, btn_add)
            self.clock.tick(60)

    def _removeRect(self, row_index: int) -> pygame.Rect:
        """Hitbox voor de verwijder-knop van een vriendrij."""
        list_y = 310
        row_h  = 52
        return pygame.Rect(SCREEN_WIDTH // 2 + 420, list_y + row_index * row_h + 10, 100, 32)

    def _draw(self, mx, my, btn_back, field_rect, btn_add):
        surf = self.screen
        cx   = SCREEN_WIDTH // 2

        _drawBackground(surf, self.tick)
        _drawParticles(surf, self.particles)

        # Titel
        tf    = _font(42, bold=True)
        title = 'Vrienden'
        tw    = tf.size(title)[0]
        _renderShadow(surf, title, tf, _GOLD_LIGHT, cx - tw // 2, 38, offset=3)
        _drawDivider(surf, 98)

        # ── Vriend toevoegen ─────────────────────────────────────────────────
        lf = _font(16)
        lt = lf.render('Vriend toevoegen via gebruikersnaam:', True, _MUTED)
        surf.blit(lt, (cx - lt.get_width() // 2, 160))

        _drawField(surf, field_rect, '', self._add_input,
                   self._field_active, mask=False, tick=self.tick)

        if self._add_pending:
            af = _font(16)
            at = af.render('Toevoegen...', True, _GOLD)
            surf.blit(at, (btn_add.x + btn_add.width // 2 - at.get_width() // 2,
                           btn_add.centery - at.get_height() // 2))
        else:
            _drawButton(surf, btn_add, 'Toevoegen', mx, my, font_size=16)

        if self._add_error:
            ef = _font(15)
            et = ef.render(self._add_error, True, (180, 60, 60))
            surf.blit(et, (cx - et.get_width() // 2, 256))
        elif self._add_ok:
            of = _font(15)
            ot = of.render(self._add_ok, True, (80, 200, 80))
            surf.blit(ot, (cx - ot.get_width() // 2, 256))

        _drawDivider(surf, 280)

        # ── Vriendenlijst ────────────────────────────────────────────────────
        list_y = 310
        row_h  = 52

        if self._friends is None:
            wf = _font(20)
            wt = wf.render('Laden...', True, _MUTED)
            surf.blit(wt, (cx - wt.get_width() // 2, list_y + 20))
        elif not self._friends:
            wf = _font(20)
            wt = wf.render('Nog geen vrienden — voeg iemand toe hierboven.', True, _MUTED)
            surf.blit(wt, (cx - wt.get_width() // 2, list_y + 20))
        else:
            nf  = _font(20, bold=True)
            sf  = _font(16)
            for i, f in enumerate(self._friends):
                ry   = list_y + i * row_h
                name = f['username']
                online = f.get('online', False)
                stats  = f.get('stats', {})
                wins   = stats.get('total_wins', 0)
                losses = stats.get('total_losses', 0)
                played = stats.get('games_played', 0)
                rate   = int(wins / played * 100) if played > 0 else 0

                # Rij achtergrond
                if i % 2 == 0:
                    row_bg = pygame.Surface((860, row_h - 4), pygame.SRCALPHA)
                    row_bg.fill((168, 110, 50, 14))
                    surf.blit(row_bg, (cx - 430, ry))

                # Online/offline stip
                dot_color = (80, 210, 80) if online else (110, 110, 110)
                pygame.draw.circle(surf, dot_color, (cx - 410, ry + row_h // 2), 7)
                pygame.draw.circle(surf, (20, 20, 20), (cx - 410, ry + row_h // 2), 7, 1)

                # Naam
                name_surf = nf.render(name, True, _WHITE if online else _MUTED)
                surf.blit(name_surf, (cx - 390, ry + 8))

                # Status label
                status_txt = 'Online' if online else 'Offline'
                st_color   = (80, 210, 80) if online else (100, 100, 100)
                st_surf    = sf.render(status_txt, True, st_color)
                surf.blit(st_surf, (cx - 390, ry + 30))

                # Stats
                stats_txt = f'W: {wins}  V: {losses}  Potjes: {played}  ({rate}% winrate)'
                ss = sf.render(stats_txt, True, _PARCHMENT)
                surf.blit(ss, (cx - 100, ry + row_h // 2 - ss.get_height() // 2))

                # Verwijder knop
                rbtn = self._removeRect(i)
                if f['username'].lower() in self._remove_pending:
                    rt = sf.render('...', True, _MUTED)
                    surf.blit(rt, (rbtn.x + rbtn.width // 2 - rt.get_width() // 2,
                                   rbtn.centery - rt.get_height() // 2))
                else:
                    col = (200, 60, 60) if rbtn.collidepoint(mx, my) else (140, 50, 50)
                    pygame.draw.rect(surf, col, rbtn, border_radius=4)
                    pygame.draw.rect(surf, (200, 100, 100), rbtn, 1, border_radius=4)
                    rt = sf.render('Verwijder', True, _WHITE)
                    surf.blit(rt, (rbtn.x + rbtn.width // 2 - rt.get_width() // 2,
                                   rbtn.centery - rt.get_height() // 2))

        # Terug knop
        _drawButton(surf, btn_back, '< Terug', mx, my)
        pygame.display.flip()


_STAT_LABELS = [
    ('games_played',    'Potjes gespeeld'),
    ('total_wins',      'Gewonnen'),
    ('total_losses',    'Verloren'),
    ('campaign_wins',   'Campagne missies gewonnen'),
    ('fog_wins',        'Fog of War gewonnen'),
    ('record_wave',     'Record golf (Last Stand)'),
]


class AccountProfileScreen:
    """Full-page profile / stats screen.
    Returns 'back', 'logout', or 'quit'."""

    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock
        self.tick   = 0
        self.particles, self.prng = _makeParticles(40)
        self._avatarCache: tuple | None = None  # (path, surface)

    def _getAvatarSurf(self, path, size=96):
        if self._avatarCache and self._avatarCache[0] == path:
            return self._avatarCache[1]
        surf = _loadAvatarCircle(path, size)
        self._avatarCache = (path, surf)
        return surf

    def _pickAvatar(self, username):
        """Open the native Windows file-picker dialog to choose a profile photo.
        Uses Win32 GetOpenFileNameW directly to avoid tkinter ↔ pygame crashes."""
        import ctypes
        import ctypes.wintypes as wt

        class _OFN(ctypes.Structure):
            _fields_ = [
                ('lStructSize',       wt.DWORD),
                ('hwndOwner',         wt.HWND),
                ('hInstance',         wt.HINSTANCE),
                ('lpstrFilter',       wt.LPCWSTR),
                ('lpstrCustomFilter', wt.LPWSTR),
                ('nMaxCustFilter',    wt.DWORD),
                ('nFilterIndex',      wt.DWORD),
                ('lpstrFile',         wt.LPWSTR),
                ('nMaxFile',          wt.DWORD),
                ('lpstrFileTitle',    wt.LPWSTR),
                ('nMaxFileTitle',     wt.DWORD),
                ('lpstrInitialDir',   wt.LPCWSTR),
                ('lpstrTitle',        wt.LPCWSTR),
                ('Flags',             wt.DWORD),
                ('nFileOffset',       wt.WORD),
                ('nFileExtension',    wt.WORD),
                ('lpstrDefExt',       wt.LPCWSTR),
                ('lCustData',         ctypes.c_long),
                ('lpfnHook',          ctypes.c_void_p),
                ('lpTemplateName',    wt.LPCWSTR),
                ('pvReserved',        ctypes.c_void_p),
                ('dwReserved',        wt.DWORD),
                ('FlagsEx',           wt.DWORD),
            ]

        try:
            buf = ctypes.create_unicode_buffer(32768)
            ofn = _OFN()
            ofn.lStructSize = ctypes.sizeof(_OFN)
            ofn.lpstrFilter = "Afbeeldingen\0*.png;*.jpg;*.jpeg;*.bmp;*.gif\0Alle bestanden\0*.*\0"
            ofn.lpstrFile   = buf
            ofn.nMaxFile    = len(buf)
            ofn.lpstrTitle  = "Kies een profielfoto"
            ofn.Flags       = 0x00001000 | 0x00000800  # OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST
            if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                path = buf.value
                if path and os.path.isfile(path):
                    accounts.setAvatar(username, path)
                    self._avatarCache = None
        except Exception:
            pass

    def run(self):
        cx = SCREEN_WIDTH  // 2
        bw, bh = 200, 44

        btn_back    = pygame.Rect(cx - bw // 2, SCREEN_HEIGHT - 80, bw, bh)
        btn_logout  = pygame.Rect(cx - bw // 2 + 220, SCREEN_HEIGHT - 80, bw, bh)
        btn_friends = pygame.Rect(cx - bw // 2 - 220, SCREEN_HEIGHT - 80, bw, bh)
        btn_avatar  = pygame.Rect(cx + 58, 160, 140, 34)

        while True:
            user = accounts.getActiveUser()
            if user is None:
                return 'logout'

            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 'back'
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_back.collidepoint(mx, my):
                        audio.play_sfx('click')
                        return 'back'
                    if btn_logout.collidepoint(mx, my):
                        audio.play_sfx('click')
                        accounts.logout()
                        return 'logout'
                    if btn_friends.collidepoint(mx, my):
                        audio.play_sfx('click')
                        result = FriendsScreen(self.screen, self.clock).run()
                        if result == 'quit':
                            return 'quit'
                    if btn_avatar.collidepoint(mx, my):
                        audio.play_sfx('click')
                        self._pickAvatar(user['username'])

            self.tick += 1
            _updateParticles(self.particles, self.prng)
            self._draw(mx, my, user, btn_back, btn_logout, btn_friends, btn_avatar)
            self.clock.tick(60)

    def _draw(self, mx, my, user, btn_back, btn_logout, btn_friends, btn_avatar):
        surf = self.screen
        cx   = SCREEN_WIDTH  // 2

        _drawBackground(surf, self.tick)
        _drawParticles(surf, self.particles)

        # Title
        tf    = _font(42, bold=True)
        title = "Mijn Account"
        tw    = tf.size(title)[0]
        _renderShadow(surf, title, tf, _GOLD_LIGHT, cx - tw // 2, 38, offset=3)
        _drawDivider(surf, 98)

        # ── Avatar area ────────────────────────────────────────────────────
        av_size = 96
        av_x    = cx - 180
        av_y    = 120
        av_cx   = av_x + av_size // 2
        av_cy   = av_y + av_size // 2
        av_surf = self._getAvatarSurf(user.get('avatar'), av_size)
        if av_surf:
            surf.blit(av_surf, (av_x, av_y))
        else:
            _drawDefaultAvatar(surf, av_cx, av_cy, av_size // 2)
        # Border ring
        pygame.draw.circle(surf, _GOLD, (av_cx, av_cy), av_size // 2 + 2, 2)

        # ── Username + joined ─────────────────────────────────────────────
        nf  = _font(30, bold=True)
        nt  = nf.render(user['username'], True, _WHITE)
        surf.blit(nt, (av_x + av_size + 20, av_y + 10))

        df  = _font(16)
        dt  = df.render(f"Lid sinds {user.get('created', '?')}", True, _MUTED)
        surf.blit(dt, (av_x + av_size + 20, av_y + 52))

        # Change avatar button
        _drawButton(surf, btn_avatar, "Foto wijzigen", mx, my, font_size=16)

        # ── Stats table ────────────────────────────────────────────────────
        _drawDivider(surf, av_y + av_size + 28)

        stats   = user.get('stats', {})
        table_y = av_y + av_size + 50
        lf      = _font(18)
        vf      = _font(18, bold=True)
        row_h   = 34
        col_lbl = cx - 260
        col_val = cx + 180

        for i, (key, label) in enumerate(_STAT_LABELS):
            y   = table_y + i * row_h
            val = stats.get(key, 0)

            # Alternate row tint
            if i % 2 == 0:
                row_surf = pygame.Surface((col_val - col_lbl + 60, row_h - 4),
                                          pygame.SRCALPHA)
                row_surf.fill((168, 110, 50, 18))
                surf.blit(row_surf, (col_lbl - 8, y))

            lt = lf.render(label, True, _PARCHMENT)
            surf.blit(lt, (col_lbl, y + 6))
            vt = vf.render(str(val), True, _GOLD)
            surf.blit(vt, (col_val - vt.get_width(), y + 6))

        # ── Buttons ────────────────────────────────────────────────────────
        _drawButton(surf, btn_friends, "Vrienden",   mx, my, font_size=20)
        _drawButton(surf, btn_back,    "< Terug",    mx, my)
        _drawButton(surf, btn_logout,  "Uitloggen",  mx, my, font_size=20)

        pygame.display.flip()
