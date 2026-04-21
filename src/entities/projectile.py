# Module: projectile
# Projectile class — handles musket balls and cannonballs in flight

import math
import random

import pygame

from src.entities.effect import Effect


class Projectile:
    STYLES = {
        'musket':     {'speed': 7.0, 'radius': 2, 'color': (220, 215, 200)},
        'cannonball': {'speed': 3.5, 'radius': 5, 'color': (50,  50,  50)},
    }

    def __init__(self, x, y, target, damage, projType,
                 angleOffset=0.0, sourceType='infantry', attacker=None):
        self.x          = float(x)
        self.y          = float(y)
        self.target     = target
        self.damage     = damage
        self.type       = projType
        self.done       = False
        self.sourceType = sourceType
        self.attacker   = attacker

        style       = self.STYLES[projType]
        self.speed  = style['speed']
        self.radius = style['radius']
        self.color  = style['color']

        spread = 55 if projType == 'cannonball' else 0
        baseX  = float(target.x) + random.uniform(-spread, spread)
        baseY  = float(target.y) + random.uniform(-spread, spread)

        if angleOffset != 0.0:
            dx, dy = baseX - x, baseY - y
            dist   = math.hypot(dx, dy)
            if dist > 0:
                baseAngle = math.atan2(dy, dx) + math.radians(angleOffset)
                baseX     = x + math.cos(baseAngle) * dist
                baseY     = y + math.sin(baseAngle) * dist

        self.destX = baseX
        self.destY = baseY

    def update(self, effects, allUnits):
        dx   = self.destX - self.x
        dy   = self.destY - self.y
        dist = math.hypot(dx, dy)

        if dist <= self.speed:
            if self.type == 'cannonball':
                for u in allUnits:
                    if u.team == self.target.team:
                        if math.hypot(u.x - self.destX, u.y - self.destY) <= 35:
                            u.takeDamage(self.damage, 'artillery')
                effects.append(Effect(self.destX, self.destY, 'explosion'))
                effects.append(Effect(self.destX, self.destY, 'blood', angle=14))
            else:
                if self.target.hp > 0:
                    self.target.takeDamage(self.damage, self.sourceType, attacker=self.attacker)
                    effects.append(Effect(self.target.x, self.target.y, 'blood', angle=5))
            self.done = True
        else:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed

    def draw(self, screen):
        ix, iy = int(self.x), int(self.y)

        if self.type == 'musket':
            dx = self.destX - self.x
            dy = self.destY - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                nx, ny = dx / dist, dy / dist
                # Streak tail (8 px behind)
                tx, ty = int(self.x - nx * 8), int(self.y - ny * 8)
                pygame.draw.line(screen, (180, 175, 160), (tx, ty), (ix, iy), 1)
            # Bright leading tip
            pygame.draw.circle(screen, (240, 235, 210), (ix, iy), 2)

        elif self.type == 'cannonball':
            # Dark sphere body
            pygame.draw.circle(screen, (40, 40, 40), (ix, iy), self.radius)
            # Mid-tone rim to give roundness
            pygame.draw.circle(screen, (70, 65, 60), (ix, iy), self.radius, 1)
            # Small highlight dot top-left
            hx = ix - max(1, self.radius // 2)
            hy = iy - max(1, self.radius // 2)
            pygame.draw.circle(screen, (140, 135, 125), (hx, hy), max(1, self.radius // 3))
