# Module: effect
# Visual effect class — handles impact, explosion, slash and smoke animations

import pygame


class Effect:
    DURATION = {'impact': 12, 'explosion': 25, 'slash': 15, 'smoke': 55}

    def __init__(self, x, y, effectType):
        self.x     = x
        self.y     = y
        self.type  = effectType
        self.max   = self.DURATION[effectType]
        self.timer = self.max

    @property
    def done(self):
        return self.timer <= 0

    def update(self):
        self.timer -= 1

    def draw(self, screen):
        ratio  = self.timer / self.max
        ix, iy = int(self.x), int(self.y)

        if self.type == 'impact':
            r         = int((1 - ratio) * 10) + 2
            alphaSurf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(alphaSurf, (255, 255, 150, int(ratio * 200)), (r + 1, r + 1), r)
            screen.blit(alphaSurf, (ix - r - 1, iy - r - 1))

        elif self.type == 'explosion':
            r         = int((1 - ratio) * 35) + 3
            alphaSurf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            color     = (255, int(100 * ratio), 0, int(ratio * 220))
            pygame.draw.circle(alphaSurf, color, (r + 1, r + 1), r, 3)
            screen.blit(alphaSurf, (ix - r - 1, iy - r - 1))

        elif self.type == 'slash':
            alphaSurf = pygame.Surface((30, 30), pygame.SRCALPHA)
            c         = int(ratio * 255)
            pygame.draw.line(alphaSurf, (255, 255, c, int(ratio * 220)), (2, 2),   (27, 27), 2)
            pygame.draw.line(alphaSurf, (255, 255, c, int(ratio * 220)), (27, 2),  (2,  27), 2)
            screen.blit(alphaSurf, (ix - 15, iy - 15))

        elif self.type == 'smoke':
            r         = int((1 - ratio) * 22) + 6
            alpha     = int(ratio * 110)
            grey      = int(180 + ratio * 40)
            alphaSurf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(alphaSurf, (grey, grey, grey, alpha), (r + 1, r + 1), r)
            screen.blit(alphaSurf, (ix - r - 1, iy - r - 1))
