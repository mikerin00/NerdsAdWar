# Module: effect
# Visual effect class — impact flashes, cannon explosions, smoke, slash sparks

import math
import random

import pygame


class Effect:
    DURATION = {'impact': 10, 'explosion': 45, 'slash': 15, 'smoke': 55,
                'spear': 18, 'sword': 22, 'blood': 28, 'splash': 22}

    def __init__(self, x, y, effectType, angle=0.0):
        self.x     = float(x)
        self.y     = float(y)
        self.type  = effectType
        self.angle = float(angle)   # degrees, attacker→target direction
        self.max   = self.DURATION[effectType]
        self.timer = self.max
        self._sparks = []

        if effectType == 'explosion':
            rng = random.Random()
            for _ in range(16):
                angle = rng.uniform(0, math.pi * 2)
                speed = rng.uniform(1.6, 5.2)
                self._sparks.append([
                    float(x), float(y),             # [0] x, [1] y
                    math.cos(angle) * speed,         # [2] vx
                    math.sin(angle) * speed,         # [3] vy
                    rng.uniform(1.5, 3.0),           # [4] radius
                    rng.choice([                     # [5] color
                        (255, 220, 55),
                        (255, 145, 20),
                        (255, 75,  10),
                        (230, 230, 200),
                    ]),
                ])

        elif effectType == 'splash':
            # Droplet arcs flying outward
            rng = random.Random()
            for _ in range(7):
                a  = rng.uniform(0, math.pi * 2)
                sp = rng.uniform(1.0, 2.8)
                self._sparks.append([
                    float(x), float(y),
                    math.cos(a) * sp,
                    math.sin(a) * sp - 1.5,   # initial upward bias
                    rng.uniform(1.0, 2.0),
                    (180, 210, 240),
                ])

        elif effectType == 'blood':
            rng = random.Random()
            count = int(self.angle) if self.angle > 0 else 10  # angle field reused as particle count
            for _ in range(count):
                a  = rng.uniform(0, math.pi * 2)
                sp = rng.uniform(0.6, 3.0)
                self._sparks.append([
                    float(x), float(y),
                    math.cos(a) * sp,
                    math.sin(a) * sp,
                    rng.uniform(1.0, 2.5),
                    rng.choice([(185, 18, 18), (220, 30, 30), (155, 8, 8), (200, 50, 50)]),
                ])

    @property
    def done(self):
        return self.timer <= 0

    def update(self):
        self.timer -= 1
        for sp in self._sparks:
            sp[0] += sp[2]
            sp[1] += sp[3]
            sp[2] *= 0.90   # drag
            sp[3] *= 0.90
            sp[3] += 0.12   # gravity

    def draw(self, screen):
        ratio  = self.timer / self.max
        ix, iy = int(self.x), int(self.y)

        if self.type == 'impact':
            r = int((1 - ratio) * 9) + 2
            a = int(ratio * 230)
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 250, 140, a), (r + 1, r + 1), r)
            screen.blit(s, (ix - r - 1, iy - r - 1))

        elif self.type == 'explosion':
            # ── Initial flash (ratio > 0.85 → first ~7 frames) ───────────
            if ratio > 0.85:
                ft    = (ratio - 0.85) / 0.15
                fr    = int(ft * 32) + 4
                fa    = int(ft * 255)
                fls   = pygame.Surface((fr * 2 + 2, fr * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(fls, (255, 255, 235, fa), (fr + 1, fr + 1), fr)
                screen.blit(fls, (ix - fr - 1, iy - fr - 1))

            # ── Fireball (ratio 0.35 → 1.0) ──────────────────────────────
            if ratio > 0.35:
                ft      = (ratio - 0.35) / 0.65       # 1 → 0 as it burns out
                peak    = math.sin(ft * math.pi)       # bell curve: grows then shrinks
                fire_r  = max(2, int(peak * 22) + 3)
                fire_a  = int(ft * 215)
                # Outer orange ring
                fbs = pygame.Surface((fire_r * 2 + 2, fire_r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(fbs, (255, int(60 + 90 * ft), 0, fire_a),
                                   (fire_r + 1, fire_r + 1), fire_r)
                screen.blit(fbs, (ix - fire_r - 1, iy - fire_r - 1))
                # Inner yellow-white core
                core_r = max(1, fire_r - 6)
                crs    = pygame.Surface((core_r * 2 + 2, core_r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(crs, (255, 240, 160, min(255, fire_a + 30)),
                                   (core_r + 1, core_r + 1), core_r)
                screen.blit(crs, (ix - core_r - 1, iy - core_r - 1))

            # ── Smoke cloud (full duration, lingers longest) ─────────────
            smoke_r = int((1 - ratio) * 32) + 7
            smoke_a = int(ratio * 80)
            grey    = int(145 + ratio * 60)
            sms     = pygame.Surface((smoke_r * 2 + 2, smoke_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(sms, (grey, grey, grey, smoke_a),
                               (smoke_r + 1, smoke_r + 1), smoke_r)
            screen.blit(sms, (ix - smoke_r - 1, iy - smoke_r - 1))

            # ── Sparks (first 55% of lifetime) ───────────────────────────
            age = 1.0 - ratio
            if age < 0.55:
                fade = 1.0 - age / 0.55
                for sp in self._sparks:
                    sx, sy = int(sp[0]), int(sp[1])
                    sr     = max(1, int(sp[4] * fade))
                    col    = tuple(int(c * fade) for c in sp[5])
                    # Streak tail
                    tx = int(sp[0] - sp[2] * 3.5)
                    ty = int(sp[1] - sp[3] * 3.5)
                    pygame.draw.line(screen, col, (tx, ty), (sx, sy), 1)
                    pygame.draw.circle(screen, col, (sx, sy), sr)

        elif self.type == 'slash':
            s = pygame.Surface((30, 30), pygame.SRCALPHA)
            c = int(ratio * 255)
            pygame.draw.line(s, (255, 255, c, int(ratio * 220)), (2, 2),  (27, 27), 2)
            pygame.draw.line(s, (255, 255, c, int(ratio * 220)), (27, 2), (2,  27), 2)
            screen.blit(s, (ix - 15, iy - 15))

        elif self.type == 'smoke':
            r     = int((1 - ratio) * 22) + 6
            alpha = int(ratio * 110)
            grey  = int(180 + ratio * 40)
            s     = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (grey, grey, grey, alpha), (r + 1, r + 1), r)
            screen.blit(s, (ix - r - 1, iy - r - 1))

        elif self.type == 'spear':
            # Thrust phase: lunge in during first half, retract in second half
            base_rad = math.radians(self.angle)
            perp_rad = base_rad + math.pi / 2   # perpendicular for side-by-side offset

            # thrust_t: 0→1→0 (peak at halfway)
            thrust_t  = math.sin(ratio * math.pi)
            shaft_len = int(6 + thrust_t * 18)  # spear length grows then shrinks
            alpha     = int(ratio * 240)

            # Direction unit vectors
            fdx, fdy = math.cos(base_rad), math.sin(base_rad)  # forward (toward target)
            pdx, pdy = math.cos(perp_rad), math.sin(perp_rad)  # perpendicular

            spacing = 7  # pixels between spears
            for lane in (-1, 0, 1):
                # Origin: offset perpendicular from center, slightly behind impact
                ox = ix + pdx * spacing * lane - fdx * (shaft_len // 2)
                oy = iy + pdy * spacing * lane - fdy * (shaft_len // 2)
                # Tip: forward from origin
                tx = ox + fdx * shaft_len
                ty = oy + fdy * shaft_len

                shaft_col = (150, 130, 90)
                tip_col   = (215, 215, 195)
                pygame.draw.line(screen, shaft_col, (int(ox), int(oy)), (int(tx), int(ty)), 2)
                pygame.draw.circle(screen, tip_col, (int(tx), int(ty)), 2)

            # Red impact flash ring at peak of thrust
            if thrust_t > 0.5:
                flash_a = int((thrust_t - 0.5) / 0.5 * 160)
                flash_r = int(thrust_t * 10) + 3
                fs = pygame.Surface((flash_r * 2 + 4, flash_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(fs, (220, 30, 30, flash_a),
                                   (flash_r + 2, flash_r + 2), flash_r, 2)
                screen.blit(fs, (ix - flash_r - 2, iy - flash_r - 2))

        elif self.type == 'blood':
            age  = 1.0 - ratio
            fade = max(0.0, 1.0 - age / 0.75)
            for sp in self._sparks:
                sx2, sy2 = int(sp[0]), int(sp[1])
                sr       = max(1, int(sp[4] * fade))
                col      = tuple(int(c * fade) for c in sp[5])
                pygame.draw.circle(screen, col, (sx2, sy2), sr)

        elif self.type == 'splash':
            # Expanding concentric ripple rings
            for ring_i, (base_r, base_a) in enumerate(((5, 90), (9, 55), (13, 28))):
                ring_r = base_r + int((1.0 - ratio) * 8)
                ring_a = int(ratio * base_a)
                if ring_a > 0 and ring_r > 0:
                    rs = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(rs, (180, 215, 245, ring_a),
                                       (ring_r + 2, ring_r + 2), ring_r, 1)
                    screen.blit(rs, (ix - ring_r - 2, iy - ring_r - 2))
            # Droplet particles
            age  = 1.0 - ratio
            fade = max(0.0, 1.0 - age / 0.7)
            for sp in self._sparks:
                sx2, sy2 = int(sp[0]), int(sp[1])
                sr       = max(1, int(sp[4] * fade))
                col      = tuple(int(c * fade) for c in sp[5])
                pygame.draw.circle(screen, col, (sx2, sy2), sr)

        elif self.type == 'sword':
            # Arc sweep: a curved swipe across the target, fading out
            base_rad  = math.radians(self.angle)
            sweep_ang = math.pi * 0.75   # 135° arc
            progress  = 1.0 - ratio      # 0→1 as animation plays
            alpha     = int(ratio * 240)
            arc_r     = int(16 + progress * 10)  # arc grows outward

            n_points = 14
            pts = []
            for i in range(n_points):
                t   = i / (n_points - 1)
                ang = base_rad - sweep_ang / 2 + sweep_ang * (t + progress * 0.4)
                px  = ix + int(math.cos(ang) * arc_r)
                py  = iy + int(math.sin(ang) * arc_r)
                pts.append((px, py))

            if len(pts) >= 2:
                fade = int(ratio * 210)
                # White-blue arc (sword shine)
                for i in range(len(pts) - 1):
                    seg_ratio = i / (len(pts) - 1)
                    r_col = int(180 + 75 * seg_ratio)
                    g_col = int(200 + 55 * seg_ratio)
                    col   = (r_col, g_col, 255, fade)
                    surf  = pygame.Surface((3, 3), pygame.SRCALPHA)
                    pygame.draw.line(screen, (r_col, g_col, 255), pts[i], pts[i + 1], 2)
                # Bright tip flash at the leading edge
                tip = pts[-1]
                ts  = pygame.Surface((8, 8), pygame.SRCALPHA)
                pygame.draw.circle(ts, (255, 255, 255, fade), (4, 4), 3)
                screen.blit(ts, (tip[0] - 4, tip[1] - 4))
