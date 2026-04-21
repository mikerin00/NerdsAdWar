# Campaign story dialogs — based on the Nerds at War Story Bible v1.0
#
# Format per dialog:  list of exchanges
#   speaker  : display name
#   portrait : key matching PORTRAIT_FILES below
#   side     : 'left' | 'right'
#   text     : the line (keep under ~80 chars per line for the text box)

import math
import os

import pygame

# Portrait image paths (relative to cwd, same folder as character PNGs)
_PORTRAIT_DIR = os.path.join('story', 'characters_PNG')

PORTRAIT_FILES = {
    'hero':     os.path.join(_PORTRAIT_DIR, 'hero.png'),
    'koen':     os.path.join(_PORTRAIT_DIR, 'koen.png'),
    'tim':      os.path.join(_PORTRAIT_DIR, 'tim.png'),
    'mika':     os.path.join(_PORTRAIT_DIR, 'mika.png'),
    'luuk':     os.path.join(_PORTRAIT_DIR, 'luuk.png'),
    'matthijs': os.path.join(_PORTRAIT_DIR, 'matthijs.png'),
    'bronisz':  os.path.join(_PORTRAIT_DIR, 'bronisz.png'),
    'soldier':  os.path.join(_PORTRAIT_DIR, 'soldaat.png'),
}

# ── Area 1 — Koen de Stuiterbal ─────────────────────────────────────────────

DIALOGS = {

# ── Campaign intro & outro ───────────────────────────────────────────────────

'prologue': [
    # ── Scene 1: Het Feest ───────────────────────────────────────────────────
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Koen. Stop met praten."},
    {'speaker': 'Koen',      'portrait': 'koen',     'side': 'right',
     'text': "Maar hij BEWOOG ik zweer het die steen—"},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "KOEN."},
    {'speaker': 'Koen',      'portrait': 'koen',     'side': 'right',
     'text': "Ja baas."},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Kijk daar. Achter de bar."},
    {'speaker': 'Koen',      'portrait': 'koen',     'side': 'right',
     'text': "Ohhhh. Is dat... een prinses?"},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Ze is prachtig. Elegant. Gevangen in dit saaie feest,\n"
             "omringd door mensen die haar niet begrijpen.\n"
             "Ik moet haar bevrijden."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "..."},
    {'speaker': 'Koen',      'portrait': 'koen',     'side': 'right',
     'text': "WE GAAN OP MISSIE!!!"},
    # ── Scene 2: Het Plan ────────────────────────────────────────────────────
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Tim. Mika. Luuk. Bereid je voor.\n"
             "We verlaten het paleis. Vanavond. Met haar."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "..."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "Het feest is toch al saai."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "Ik doe mee."},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "...Ze wil mee."},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Dit is het mooiste moment van mijn leven."},
    {'speaker': 'Koen',      'portrait': 'koen',     'side': 'right',
     'text': "WAT GAAN WE ETE— ik bedoel. Wij zijn er klaar voor, baas."},
    # ── Scene 3: De Ochtend ──────────────────────────────────────────────────
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "Waar is iedereen."},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Wees niet jaloers.\nIk heb gevonden wat ik zocht.\nZij is weg. Wij zijn weg.  — Matthijs"},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "Ik ga ze halen."},
],

'campaign_intro': [
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'Matthijs',  'portrait': 'matthijs', 'side': 'right',
     'text': "Wees niet jaloers.\n— Generaal Matthijs"},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "Oké."},
],

'campaign_outro': [
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "Dat was aangenamer dan verwacht."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "Jij bent de prinses."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "Dat was de naam van mijn boot."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
    {'speaker': 'Bronisz',   'portrait': 'bronisz',  'side': 'right',
     'text': "Ik heb de desserts meegenomen.\nPrettige reis."},
    {'speaker': 'De Hero',   'portrait': 'hero',     'side': 'left',
     'text': "..."},
],

# ── Area 1 — Koen de Stuiterbal ─────────────────────────────────────────────

'koen_intro': [
    {'speaker': 'Soldier',  'portrait': 'soldier', 'side': 'right',
     'text': "He's... somewhere around here, sir."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "HERE I AM! I found the most incredible rock, it has\n"
             "this stripe on it and it's sort of— wait, who are you?"},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "I'm here to cross the border."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "The border! Right! I'm supposed to stop that! Okay so\n"
             "here's the plan: we go left, but also sort of right, and\n"
             "then we kind of— is that a cloud shaped like a horse?"},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "Okay! CHARGE! Or— wait. Which way is the border again?"},
],

'koen_mid': [
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "Hold on, hold on. Before we continue— look at this."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "It's a bird. I found him in the forest. His name is Gerald.\n"
             "He blinked at me twice, which I think means he's on our side."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "Right. Okay. Back to the war. Gerald, stay here."},
],

'koen_outro': [
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "Okay, fair enough! You're really fast, did you know that?\n"
             "Very fast. You should be proud of that."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "No hard feelings! I learned a lot today. Mostly about rocks,\n"
             "but also a bit about tactics. Anyway— oh."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Koen',     'portrait': 'koen',  'side': 'right',
     'text': "OH. What is THAT in the grass. I have to go."},
],

# ── Area 2 — Tim de Onzekere ─────────────────────────────────────────────────

'tim_intro': [
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "Ah. You made it. I wasn't entirely sure this was the\n"
             "right meeting point, but here we are."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "I'm here to get through."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "Right. So, I've set up a defensive line. I should mention\n"
             "I'm not fully confident it's the right position."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "The orders said 'hold the ridge.' There are three ridges.\n"
             "I picked the middle one, which felt logical."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "That's usually right."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "That's what made me nervous."},
],

'tim_mid': [
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "I've been rethinking the plan. I think it's actually\n"
             "quite good. You can say something."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "I'm interpreting that as agreement."},
],

'tim_outro': [
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "I had a feeling this was going to happen. Around the\n"
             "second battle. Something felt off."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "You were right."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "I usually am. I just never know when to trust it."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Tim',      'portrait': 'tim',   'side': 'right',
     'text': "Do you have any feedback? For next time?\n"
             "I have a notebook."},
],

# ── Area 3 — Mika de Mespunt ─────────────────────────────────────────────────

'mika_intro': [
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "Finally. I was beginning to think you got lost."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "No."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "I've prepared a comprehensive tactical analysis of all\n"
             "possible approaches to this plain. Would you like to hear it?"},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "No."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "Then you'll be walking into a precisely engineered defeat.\n"
             "Every variable accounted for. Every outcome calculated."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "Why did the soldier cross the plains?"},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "To get to the other side. Where he loses. That was a joke."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
],

'mika_mid': [
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "I need to say something. It is not a compliment."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "You are better than projected. This validates my projection,\n"
             "because I projected you might be better than projected."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "Don't read into it."},
],

'mika_outro': [
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "The plan was perfect. Execution: flawless. Outcome:\n"
             "theoretically impossible."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "External variables. Specifically, you."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "You lost."},
    {'speaker': 'Mika',     'portrait': 'mika',  'side': 'right',
     'text': "I prefer 'unexpected outcome.'\n"
             "...That's the closest thing to a conversation we've had."},
],

# ── Area 4 — Luuk de Toren ───────────────────────────────────────────────────

'luuk_intro': [
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "You made it."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "Yes."},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "Took a while."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "There were four others."},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "I heard."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "You can start whenever."},
],

'luuk_mid': [
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "Hm."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "Faster than I thought."},
],

'luuk_outro': [
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "Saw that coming. Around level two, roughly."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "Why did you keep going?"},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "Seemed polite."},
    {'speaker': 'The Hero', 'portrait': 'hero',  'side': 'left',
     'text': "..."},
    {'speaker': 'Luuk',     'portrait': 'luuk',  'side': 'right',
     'text': "There's a coffee place inside. Before you fight Matthijs.\n"
             "Just saying."},
],

# ── Area 5 — Generaal Matthijs ───────────────────────────────────────────────

'matthijs_intro': [
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "YOU! You dare breach the walls of my magnificent fortress?\n"
             "On THIS night?!"},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "He's been rehearsing."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "SILENCE! This is a moment of DESTINY! I have faced four\n"
             "of history's greatest— well, four of MY greatest—"},
    {'speaker': 'The Hero', 'portrait': 'hero',     'side': 'left',
     'text': "Where is Princess Bronisz."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "HERE! Safe! Beloved! Dining on the finest cuisine\n"
             "this region has to offer!"},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "The soup was adequate."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "EXTRAORDINARY, she means! Now— to battle! For love!\n"
             "For honour! For— for—"},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "For the record, I came willingly. The party was boring."},
],

'matthijs_mid': [
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "My troops remain undaunted! Their spirit burns like— like—"},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "A candle."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "A CANDLE! Undying! Eternal! ...That's good, right?"},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "Candles go out, Matthijs."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "...NOT THESE ONES."},
],

'matthijs_outro': [
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "..."},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "I assumed you knew."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "..."},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "We've had twelve meals together, Matthijs."},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "..."},
    {'speaker': 'Bronisz',  'portrait': 'bronisz',  'side': 'right',
     'text': "May I have the dessert?"},
    {'speaker': 'Matthijs', 'portrait': 'matthijs', 'side': 'right',
     'text': "..."},
],

}


# ── StoryDialogScreen ────────────────────────────────────────────────────────
# Fire Emblem / Pokémon-style dialog renderer.
# Usage:
#   StoryDialogScreen(screen, clock, 'koen_intro').run()
# Returns when the player advances past the last exchange.

_BOX_H_FRAC = 0.30    # dialog box occupies bottom 30% of screen
_PORTRAIT_W = 220
_PORTRAIT_H = 320
_TYPE_SPEED = 2        # characters revealed per frame (0 = instant)


class StoryDialogScreen:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 dialog_key: str):
        self._screen = screen
        self._clock  = clock
        self._lines  = DIALOGS.get(dialog_key, [])
        self._portraits: dict = {}
        W, H = screen.get_size()
        self._W, self._H = W, H
        self._box_y  = int(H * (1 - _BOX_H_FRAC))
        self._char_idx = 0
        self._idx      = 0

    def _font(self, size: int) -> pygame.font.Font:
        for name in ('Georgia', 'Palatino Linotype', 'serif'):
            try:
                f = pygame.font.SysFont(name, size)
                return f
            except Exception:
                pass
        return pygame.font.Font(None, size)

    def _portrait(self, key: str):
        if key in self._portraits:
            return self._portraits[key]
        path = PORTRAIT_FILES.get(key)
        surf = None
        if path:
            full = os.path.join(os.getcwd(), path)
            if os.path.isfile(full):
                try:
                    img  = pygame.image.load(full).convert_alpha()
                    surf = pygame.transform.smoothscale(img, (_PORTRAIT_W, _PORTRAIT_H))
                except Exception:
                    pass
        self._portraits[key] = surf
        return surf

    def _draw(self, bg: pygame.Surface):
        W, H   = self._W, self._H
        screen = self._screen
        screen.blit(bg, (0, 0))

        if self._idx >= len(self._lines):
            return

        entry       = self._lines[self._idx]
        side        = entry.get('side', 'left')
        speaker     = entry.get('speaker', '')
        text        = entry.get('text', '')
        port_key    = entry.get('portrait', '')

        # Semi-dark cinematic overlay above the dialog box
        overlay = pygame.Surface((W, self._box_y), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 110))
        screen.blit(overlay, (0, 0))

        # Dialog box
        box_rect = pygame.Rect(0, self._box_y, W, H - self._box_y)
        pygame.draw.rect(screen, (18, 14, 10), box_rect)
        pygame.draw.rect(screen, (180, 140, 60), box_rect, 2)

        # Portrait
        PORT_MARGIN = 28
        portrait_surf = self._portrait(port_key)
        if portrait_surf:
            py = self._box_y - _PORTRAIT_H + 24
            px = PORT_MARGIN if side == 'left' else W - _PORTRAIT_W - PORT_MARGIN
            shadow = pygame.Surface((_PORTRAIT_W + 8, _PORTRAIT_H + 8), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 90))
            screen.blit(shadow, (px - 4, py + 4))
            pygame.draw.rect(screen, (180, 140, 60),
                             (px - 2, py - 2, _PORTRAIT_W + 4, _PORTRAIT_H + 4), 2)
            screen.blit(portrait_surf, (px, py))
            text_offset = PORT_MARGIN + _PORTRAIT_W + 18
        else:
            text_offset = PORT_MARGIN

        TEXT_PAD = 20
        if side == 'left':
            text_x1 = text_offset
            text_x2 = W - TEXT_PAD
        else:
            text_x1 = TEXT_PAD
            text_x2 = W - text_offset

        text_w = max(100, text_x2 - text_x1)

        # Speaker name box — sits just above the text
        name_font = self._font(22)
        name_surf = name_font.render(speaker, True, (255, 210, 60))
        nw = name_surf.get_width() + 20
        nh = name_surf.get_height() + 8
        nbx = text_x1 if side == 'left' else text_x2 - nw
        nby = self._box_y + 8
        pygame.draw.rect(screen, (50, 40, 20), (nbx, nby, nw, nh))
        pygame.draw.rect(screen, (180, 140, 60), (nbx, nby, nw, nh), 1)
        screen.blit(name_surf, (nbx + 10, nby + 4))

        # Typewriter text with word-wrap
        revealed  = text if _TYPE_SPEED == 0 else text[:self._char_idx]
        txt_font  = self._font(20)
        line_h    = txt_font.get_linesize()
        ty        = nby + nh + 6

        for raw_line in revealed.split('\n'):
            words = raw_line.split(' ')
            line  = ''
            for w in words:
                test = (line + ' ' + w).strip()
                if txt_font.size(test)[0] <= text_w:
                    line = test
                else:
                    if line:
                        screen.blit(txt_font.render(line, True, (235, 225, 200)),
                                    (text_x1, ty))
                        ty += line_h
                    line = w
            if line:
                screen.blit(txt_font.render(line, True, (235, 225, 200)),
                            (text_x1, ty))
                ty += line_h

        # Continue hint (only when typewriter finished)
        done = _TYPE_SPEED == 0 or self._char_idx >= len(text)
        if done:
            is_last  = self._idx >= len(self._lines) - 1
            label    = "[ Sluiten ]" if is_last else "[ Verder ]"
            hint     = self._font(16).render(label, True, (180, 150, 80))
            screen.blit(hint, hint.get_rect(bottomright=(W - 24, H - 10)))

        # ESC skip hint
        skip_hint = self._font(14).render("[ ESC — overslaan ]", True, (120, 100, 60))
        screen.blit(skip_hint, skip_hint.get_rect(bottomleft=(16, H - 10)))

        pygame.display.flip()

    def run(self):
        if not self._lines:
            return

        bg = self._screen.copy()

        for entry in self._lines:
            self._portrait(entry.get('portrait', ''))

        self._idx      = 0
        self._char_idx = 0

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    full_len = len(self._lines[self._idx].get('text', ''))
                    if _TYPE_SPEED > 0 and self._char_idx < full_len:
                        self._char_idx = full_len
                    else:
                        self._idx += 1
                        self._char_idx = 0
                        if self._idx >= len(self._lines):
                            return

            if _TYPE_SPEED > 0 and self._idx < len(self._lines):
                full_len = len(self._lines[self._idx].get('text', ''))
                if self._char_idx < full_len:
                    self._char_idx = min(self._char_idx + _TYPE_SPEED, full_len)

            self._draw(bg)
            self._clock.tick(60)
