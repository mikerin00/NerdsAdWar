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
            else:
                if self.target.hp > 0:
                    self.target.takeDamage(self.damage, self.sourceType, attacker=self.attacker)
            self.done = True
        else:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
