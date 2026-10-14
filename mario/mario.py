"""
Платформер в стиле Марио на Pygame (вся графика рисуется кодом, внешние файлы не нужны).

Управление:
  <- / -> или A / D   - бег
  Shift               - ускорение
  Пробел / Вверх / W  - прыжок (чем дольше держишь, тем выше)
  R                   - начать заново
  Esc                 - выход

Цель: дойти до флага. Собирай монеты, бей блоки снизу головой,
прыгай на врагов сверху. Не упади в яму и не касайся врагов сбоку.

Запуск:
  pip install pygame
  python mario.py
"""

import math
import random
import sys

import pygame

# ---------------------------------------------------------------- константы
SCREEN_W, SCREEN_H = 960, 560
TILE = 40
ROWS = SCREEN_H // TILE        # 14 рядов тайлов
FPS = 60

GRAVITY = 0.7
MAX_FALL = 16
WALK_ACC, RUN_ACC = 0.5, 0.8
MAX_WALK, MAX_RUN = 4.5, 7.0
FRICTION = 0.45
JUMP_V = -16

SOLID = set("#BQUPS")          # символы твёрдых тайлов
START_LIVES = 3
LEVEL_TIME = 200               # секунд на уровень

SKY = (92, 148, 252)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 40, 40)
SKIN = (250, 190, 130)
BROWN = (110, 60, 20)
BLUE = (40, 70, 200)


def tiles_overlapping(level, x, y, w, h):
    """Все твёрдые тайлы, пересекающиеся с прямоугольником (x, y, w, h)."""
    x0 = int(math.floor(x / TILE))
    x1 = int(math.floor((x + w - 0.001) / TILE))
    y0 = int(math.floor(y / TILE))
    y1 = int(math.floor((y + h - 0.001) / TILE))
    for cy in range(y0, y1 + 1):
        for cx in range(x0, x1 + 1):
            if level.solid(cx, cy):
                yield cx, cy


# ---------------------------------------------------------------- враг
class Enemy:
    W = H = 36

    def __init__(self, tx, ty):
        self.x = tx * TILE + 2
        self.y = (ty + 1) * TILE - self.H
        self.vx = -1.3
        self.vy = 0.0
        self.squish = 0        # >0 - раздавлен, счётчик до исчезновения
        self.flying = False    # сбит ударом снизу
        self.remove = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)

    @property
    def dying(self):
        return self.squish > 0 or self.flying

    def stomp(self):
        self.squish = 30

    def knock(self):
        self.flying = True
        self.vy = -9
        self.vx = random.choice((-2, 2))

    def update(self, level, cam_x):
        if self.squish > 0:
            self.squish -= 1
            if self.squish == 0:
                self.remove = True
            return
        if self.flying:
            self.vy += GRAVITY
            self.x += self.vx
            self.y += self.vy
            if self.y > SCREEN_H + 100:
                self.remove = True
            return
        # враги "спят", пока не появятся рядом с экраном
        if self.x + self.W < cam_x - 80 or self.x > cam_x + SCREEN_W + 80:
            if self.x + self.W < cam_x - 80:
                self.remove = True
            return

        self.vy = min(self.vy + GRAVITY, MAX_FALL)

        self.x += self.vx
        if list(tiles_overlapping(level, self.x, self.y, self.W, self.H)):
            self.x -= self.vx
            self.vx = -self.vx

        self.y += self.vy
        hits = list(tiles_overlapping(level, self.x, self.y, self.W, self.H))
        if hits and self.vy > 0:
            self.y = min(cy for _, cy in hits) * TILE - self.H
            self.vy = 0
        if self.y > SCREEN_H + 100:
            self.remove = True


# ---------------------------------------------------------------- игрок
class Player:
    W, H = 28, 40

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0        # "койот-тайм": можно прыгнуть сразу после схода с края
        self.buffer = 0        # буфер прыжка: нажал чуть раньше приземления
        self.jumping = False
        self.run_anim = 0.0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)

    def update(self, level, keys):
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        jump_held = keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]

        acc = RUN_ACC if run else WALK_ACC
        max_v = MAX_RUN if run else MAX_WALK

        if left and not right:
            self.vx -= acc
            self.facing = -1
        elif right and not left:
            self.vx += acc
            self.facing = 1
        else:
            if abs(self.vx) < FRICTION:
                self.vx = 0
            else:
                self.vx -= math.copysign(FRICTION, self.vx)
        self.vx = max(-max_v, min(max_v, self.vx))

        # --- прыжок
        if self.buffer > 0:
            self.buffer -= 1
        if self.on_ground:
            self.coyote = 6
        elif self.coyote > 0:
            self.coyote -= 1
        if self.buffer > 0 and self.coyote > 0:
            self.vy = JUMP_V - abs(self.vx) * 0.25
            self.buffer = self.coyote = 0
            self.on_ground = False
            self.jumping = True
        if self.jumping:
            if self.vy >= 0:
                self.jumping = False
            elif not jump_held and self.vy < -5:
                self.vy = -5        # отпустил кнопку - прыжок короче

        self.vy = min(self.vy + GRAVITY, MAX_FALL)

        # --- движение по X
        self.x += self.vx
        for cx, cy in list(tiles_overlapping(level, self.x, self.y, self.W, self.H)):
            if self.vx > 0:
                self.x = min(self.x, cx * TILE - self.W)
            elif self.vx < 0:
                self.x = max(self.x, (cx + 1) * TILE)
            self.vx = 0

        # --- движение по Y
        self.on_ground = False
        self.y += self.vy
        hits = list(tiles_overlapping(level, self.x, self.y, self.W, self.H))
        if hits:
            if self.vy > 0:
                self.y = min(cy for _, cy in hits) * TILE - self.H
                self.on_ground = True
                self.jumping = False
                self.vy = 0
            elif self.vy < 0:
                top_row = max(cy for _, cy in hits)
                self.y = (top_row + 1) * TILE
                center = self.x + self.W / 2
                row_hits = [cx for cx, cy in hits if cy == top_row]
                best = min(row_hits, key=lambda cx: abs(
                    cx * TILE + TILE / 2 - center))
                self.vy = 0
                self.jumping = False
                level.hit_block(best, top_row)

        if self.on_ground and abs(self.vx) > 0.1:
            self.run_anim += abs(self.vx) * 0.08

    def stomp_bounce(self, jump_held):
        self.vy = -14 if jump_held else -9
        self.on_ground = False
        self.jumping = jump_held


# ---------------------------------------------------------------- уровень
class Level:
    def __init__(self, game):
        self.game = game
        self.tiles = {}
        self.coins = []        # центры монет [x, y]
        self.enemies = []
        self.particles = []    # осколки кирпичей
        self.pops = []         # монетки, вылетающие из блоков
        self.floaters = []     # всплывающие очки
        self.flag_x = 133
        self.build()

    def build(self):
        W = 140
        self.cols = W
        self.width = W * TILE
        T = self.tiles

        pits = [(32, 35), (66, 69), (100, 103)]

        def in_pit(x):
            return any(a <= x < b for a, b in pits)

        for x in range(W):
            if not in_pit(x):
                T[(x, 12)] = "#"
                T[(x, 13)] = "#"

        def row(x0, x1, y, ch):
            for x in range(x0, x1):
                T[(x, y)] = ch

        def pipe(x, h):
            for dx in (0, 1):
                for i in range(h):
                    T[(x + dx, 11 - i)] = "P"

        def coins(x0, x1, y):
            for x in range(x0, x1):
                self.coins.append([x * TILE + TILE / 2, y * TILE + TILE / 2])

        def enemy(x, y=11):
            self.enemies.append(Enemy(x, y))

        # старт
        coins(7, 10, 9)
        # блоки
        T[(14, 8)] = "Q"
        T[(16, 8)] = "B"
        T[(17, 8)] = "Q"
        T[(18, 8)] = "B"
        T[(19, 8)] = "Q"
        T[(17, 4)] = "Q"
        # трубы
        pipe(24, 2)
        pipe(29, 3)
        pipe(38, 2)
        pipe(45, 3)
        # платформы
        row(51, 56, 8, "B")
        T[(53, 8)] = "Q"
        coins(52, 55, 6)
        row(58, 63, 5, "B")
        T[(60, 5)] = "Q"
        # над ямой
        coins(65, 70, 9)
        # лестница-горка
        for i in range(4):
            for j in range(i + 1):
                T[(74 + i, 11 - j)] = "S"
        for i in range(4):
            for j in range(4 - i):
                T[(78 + i, 11 - j)] = "S"
        pipe(86, 2)
        pipe(91, 3)
        row(95, 98, 8, "B")
        T[(96, 8)] = "Q"
        row(99, 104, 9, "S")
        coins(99, 104, 7)
        # финальная лестница
        for i in range(8):
            for j in range(i + 1):
                T[(120 + i, 11 - j)] = "S"
        # флаг
        T[(self.flag_x, 11)] = "S"
        coins(110, 114, 8)

        # враги
        for x in (20, 27, 41, 48, 84, 88, 94, 106, 110, 113, 116):
            enemy(x)
        enemy(56, 7)
        enemy(59, 4)

    def solid(self, cx, cy):
        if cx < 0 or cx >= self.cols:
            return True
        if cy < 0 or cy >= ROWS:
            return False
        return self.tiles.get((cx, cy), ".") in SOLID

    # --- удар головой по блоку
    def hit_block(self, cx, cy):
        ch = self.tiles.get((cx, cy))
        g = self.game
        if ch == "Q":
            self.tiles[(cx, cy)] = "U"
            self.pops.append({"x": cx * TILE + TILE / 2,
                             "y": cy * TILE, "vy": -10, "life": 30})
            g.add_coin()
            g.add_score(200, cx * TILE, cy * TILE - 10)
        elif ch == "B":
            del self.tiles[(cx, cy)]
            for dx, dy in ((-2, -9), (2, -9), (-3, -6), (3, -6)):
                self.particles.append(
                    {"x": cx * TILE + TILE / 2, "y": cy * TILE +
                        TILE / 2, "vx": dx, "vy": dy, "life": 60}
                )
            g.add_score(50, cx * TILE, cy * TILE - 10)
        else:
            return
        # враги, стоявшие на блоке, сбиваются
        top = cy * TILE
        for e in self.enemies:
            if not e.dying and abs((e.y + e.H) - top) < 6 and e.x + e.W > cx * TILE and e.x < (cx + 1) * TILE:
                e.knock()
                g.add_score(100, e.x, e.y - 10)

    def update(self, cam_x, enemies=True):
        if enemies:
            for e in self.enemies:
                e.update(self, cam_x)
            self.enemies = [e for e in self.enemies if not e.remove]
        for p in self.particles:
            p["vy"] += GRAVITY
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
        self.particles = [p for p in self.particles if p["life"] > 0]
        for p in self.pops:
            p["vy"] += 0.6
            p["y"] += p["vy"]
            p["life"] -= 1
        self.pops = [p for p in self.pops if p["life"] > 0]
        for f in self.floaters:
            f["y"] -= 1
            f["life"] -= 1
        self.floaters = [f for f in self.floaters if f["life"] > 0]


# ---------------------------------------------------------------- игра
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Платформер в стиле Марио")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.font_big = pygame.font.SysFont("arial", 56, bold=True)
        self.font_q = pygame.font.SysFont("arial", 30, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16, bold=True)

        rnd = random.Random(7)
        self.clouds = [(i * 330 + rnd.randint(0, 150), rnd.randint(30,
                        140), rnd.uniform(0.8, 1.4)) for i in range(40)]
        self.hills = [(i * 620 + rnd.randint(0, 200), rnd.randint(90,
                       150), rnd.randint(220, 340)) for i in range(40)]

        self.reset_game()

    # --- состояние
    def reset_game(self):
        self.score = 0
        self.coins = 0
        self.lives = START_LIVES
        self.restart_level()

    def restart_level(self):
        self.level = Level(self)
        self.player = Player(3 * TILE, 12 * TILE - Player.H)
        self.cam_x = 0.0
        self.time_frames = LEVEL_TIME * FPS
        self.state = "playing"     # playing, dying, flag, won, gameover
        self.timer = 0
        self.frame = 0

    def add_score(self, pts, x=None, y=None):
        self.score += pts
        if x is not None:
            self.level.floaters.append(
                {"x": x, "y": y, "text": str(pts), "life": 45})

    def add_coin(self):
        self.coins += 1
        if self.coins >= 100:
            self.coins -= 100
            self.lives += 1

    def kill_player(self):
        if self.state != "playing":
            return
        self.state = "dying"
        self.player.vy = -13
        self.player.vx = 0
        self.timer = 110

    # --- обновление
    def update(self):
        self.frame += 1
        keys = pygame.key.get_pressed()
        p = self.player
        jump_held = keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]

        if self.state == "playing":
            self.time_frames -= 1
            if self.time_frames <= 0:
                self.kill_player()
                return
            p.update(self.level, keys)

            # камера только вперёд (как в оригинале), назад вернуться нельзя
            target = p.x + p.W / 2 - SCREEN_W * 0.4
            self.cam_x = max(self.cam_x, min(
                target, self.level.width - SCREEN_W))
            if p.x < self.cam_x:
                p.x = self.cam_x
                p.vx = max(p.vx, 0)
            if p.x > self.level.width - p.W:
                p.x = self.level.width - p.W

            self.level.update(self.cam_x)
            self.check_coins()
            self.check_enemies(jump_held)
            self.check_flag()
            if p.y > SCREEN_H + 40:
                self.kill_player()

        elif self.state == "dying":
            p.vy += GRAVITY
            p.y += p.vy
            self.level.update(self.cam_x, enemies=False)
            self.timer -= 1
            if self.timer <= 0:
                self.lives -= 1
                if self.lives > 0:
                    keep = (self.score, self.coins, self.lives)
                    self.restart_level()
                    self.score, self.coins, self.lives = keep
                else:
                    self.state = "gameover"

        elif self.state == "flag":
            p.y += 4
            floor = 11 * TILE - p.H
            if p.y >= floor:
                p.y = floor
                self.timer -= 1
                if self.timer <= 0:
                    self.state = "won"
            self.level.update(self.cam_x, enemies=False)

        else:  # won / gameover
            self.level.update(self.cam_x, enemies=False)

    def check_coins(self):
        pr = self.player.rect
        left = []
        for cx, cy in self.level.coins:
            if pr.colliderect(pygame.Rect(cx - 12, cy - 16, 24, 32)):
                self.add_coin()
                self.add_score(100, cx - 10, cy - 20)
            else:
                left.append([cx, cy])
        self.level.coins = left

    def check_enemies(self, jump_held):
        p = self.player
        pr = p.rect
        for e in self.level.enemies:
            if e.dying or not pr.colliderect(e.rect):
                continue
            if p.vy > 0 and (p.y + p.H) < e.y + e.H * 0.6:
                e.stomp()
                p.stomp_bounce(jump_held)
                self.add_score(100, e.x, e.y - 10)
            else:
                self.kill_player()
                return

    def check_flag(self):
        fx = self.level.flag_x * TILE
        pole = pygame.Rect(fx + 15, 2 * TILE, 10, 9 * TILE)
        if self.player.rect.colliderect(pole):
            self.state = "flag"
            self.timer = 60
            self.player.x = fx + 20 - Player.W / 2
            self.player.vx = self.player.vy = 0
            bonus = (self.time_frames // FPS) * 10
            self.add_score(bonus, fx - 60, 2 * TILE)

    # ------------------------------------------------------------ рисование
    def text(self, s, x, y, font=None, color=WHITE, center=False):
        font = font or self.font
        shadow = font.render(s, True, BLACK)
        surf = font.render(s, True, color)
        r = surf.get_rect()
        if center:
            r.center = (x, y)
        else:
            r.topleft = (x, y)
        self.screen.blit(shadow, r.move(2, 2))
        self.screen.blit(surf, r)

    def draw_background(self):
        scr = self.screen
        scr.fill(SKY)
        cam = self.cam_x
        ground_y = 12 * TILE
        for hx, hh, hw in self.hills:
            sx = hx - cam * 0.6
            if -hw < sx < SCREEN_W + hw:
                pygame.draw.ellipse(scr, (70, 170, 80),
                                    (sx, ground_y - hh, hw, hh * 2))
                pygame.draw.ellipse(
                    scr, (90, 195, 100), (sx + hw * 0.2, ground_y - hh * 0.85, hw * 0.35, hh * 0.5))
        for cx, cy, s in self.clouds:
            sx = cx - cam * 0.35
            if -150 < sx < SCREEN_W + 50:
                pygame.draw.circle(scr, WHITE, (sx, cy), 18 * s)
                pygame.draw.circle(
                    scr, WHITE, (sx + 24 * s, cy - 10 * s), 24 * s)
                pygame.draw.circle(scr, WHITE, (sx + 50 * s, cy), 18 * s)
                pygame.draw.rect(scr, WHITE, (sx, cy, 50 * s, 18 * s))

    def draw_tile(self, ch, cx, cy, sx, sy):
        scr = self.screen
        r = pygame.Rect(sx, sy, TILE, TILE)
        if ch == "#":
            pygame.draw.rect(scr, (150, 95, 45), r)
            seed = (cx * 7 + cy * 13) % 5
            pygame.draw.circle(scr, (120, 70, 30),
                               (sx + 10 + seed * 4, sy + 24), 3)
            pygame.draw.circle(scr, (120, 70, 30),
                               (sx + 30 - seed * 3, sy + 32), 2)
            pygame.draw.rect(scr, (120, 70, 30), r, 1)
            if not self.level.solid(cx, cy - 1):
                pygame.draw.rect(scr, (80, 180, 60), (sx, sy, TILE, 10))
                pygame.draw.rect(scr, (50, 140, 40), (sx, sy + 10, TILE, 3))
        elif ch == "B":
            pygame.draw.rect(scr, (190, 95, 45), r)
            line = (110, 50, 20)
            for yy in (10, 20, 30):
                pygame.draw.line(scr, line, (sx, sy + yy),
                                 (sx + TILE, sy + yy), 2)
            for i, yy in enumerate((0, 10, 20, 30)):
                off = 20 if i % 2 else 10
                pygame.draw.line(scr, line, (sx + off, sy + yy),
                                 (sx + off, sy + yy + 10), 2)
            pygame.draw.rect(scr, line, r, 2)
        elif ch == "Q":
            glow = 20 if (self.frame // 20) % 2 == 0 else 0
            pygame.draw.rect(scr, (240, 180 + glow, 40), r)
            pygame.draw.rect(scr, (255, 230, 120), (sx, sy, TILE, 3))
            pygame.draw.rect(scr, (255, 230, 120), (sx, sy, 3, TILE))
            pygame.draw.rect(scr, (150, 90, 10), r, 2)
            q = self.font_q.render("?", True, (130, 70, 10))
            scr.blit(q, q.get_rect(center=r.center))
        elif ch == "U":
            pygame.draw.rect(scr, (130, 90, 50), r)
            pygame.draw.rect(scr, (80, 50, 25), r, 2)
        elif ch == "S":
            pygame.draw.rect(scr, (160, 160, 170), r)
            pygame.draw.rect(scr, (210, 210, 220), (sx, sy, TILE, 4))
            pygame.draw.rect(scr, (210, 210, 220), (sx, sy, 4, TILE))
            pygame.draw.rect(scr, (90, 90, 100), (sx, sy + TILE - 4, TILE, 4))
            pygame.draw.rect(scr, (90, 90, 100), (sx + TILE - 4, sy, 4, TILE))
        elif ch == "P":
            top = not self.level.solid(
                cx, cy - 1) or self.level.tiles.get((cx, cy - 1)) != "P"
            pygame.draw.rect(scr, (40, 170, 60), r)
            pygame.draw.rect(scr, (110, 220, 120), (sx + 4, sy, 6, TILE))
            pygame.draw.rect(scr, (20, 110, 40), (sx + TILE - 6, sy, 6, TILE))
            if top:
                pygame.draw.rect(scr, (30, 150, 50), (sx, sy, TILE, 12))
                pygame.draw.rect(scr, (110, 220, 120), (sx + 4, sy + 2, 6, 8))
                pygame.draw.rect(scr, (10, 90, 30), (sx, sy, TILE, 12), 2)

    def draw_tiles(self):
        c0 = int(self.cam_x // TILE)
        c1 = c0 + SCREEN_W // TILE + 2
        for cy in range(ROWS):
            for cx in range(c0, c1):
                ch = self.level.tiles.get((cx, cy))
                if ch:
                    self.draw_tile(ch, cx, cy, cx * TILE -
                                   self.cam_x, cy * TILE)

    def draw_flag(self):
        fx = self.level.flag_x * TILE - self.cam_x
        pole_x = fx + 17
        if not (-100 < pole_x < SCREEN_W + 100):
            return
        pygame.draw.rect(self.screen, (230, 230, 230),
                         (pole_x, 2 * TILE, 6, 9 * TILE))
        pygame.draw.circle(self.screen, (250, 200, 40),
                           (pole_x + 3, 2 * TILE - 4), 8)
        pygame.draw.polygon(
            self.screen, RED,
            [(pole_x, 2 * TILE + 6), (pole_x - 32,
                                      2 * TILE + 22), (pole_x, 2 * TILE + 38)],
        )

    def draw_coin(self, x, y):
        w = abs(math.cos(self.frame * 0.1 + x * 0.05)) * 10 + 2
        pygame.draw.ellipse(self.screen, (255, 210, 40),
                            (x - w, y - 14, w * 2, 28))
        pygame.draw.ellipse(self.screen, (200, 140, 10),
                            (x - w, y - 14, w * 2, 28), 2)

    def draw_enemy(self, e):
        sx, sy = e.x - self.cam_x, e.y
        scr = self.screen
        if e.squish > 0:
            pygame.draw.ellipse(scr, (150, 90, 40), (sx, sy + 24, e.W, 12))
            pygame.draw.ellipse(scr, BROWN, (sx, sy + 24, e.W, 12), 2)
            return
        surf = pygame.Surface((e.W, e.H), pygame.SRCALPHA)
        step = (self.frame // 10) % 2
        pygame.draw.ellipse(surf, (60, 30, 10), (2 + step * 3, 26, 14, 10))
        pygame.draw.ellipse(surf, (60, 30, 10), (20 - step * 3, 26, 14, 10))
        pygame.draw.ellipse(surf, (170, 100, 45), (0, 0, e.W, 30))
        pygame.draw.ellipse(surf, BROWN, (0, 0, e.W, 30), 2)
        pygame.draw.rect(surf, SKIN, (8, 18, 20, 8))
        pygame.draw.ellipse(surf, WHITE, (7, 10, 9, 11))
        pygame.draw.ellipse(surf, WHITE, (20, 10, 9, 11))
        pygame.draw.circle(surf, BLACK, (12, 16), 2)
        pygame.draw.circle(surf, BLACK, (24, 16), 2)
        pygame.draw.line(surf, BLACK, (6, 8), (15, 12), 3)
        pygame.draw.line(surf, BLACK, (30, 8), (21, 12), 3)
        if e.flying:
            surf = pygame.transform.flip(surf, False, True)
        scr.blit(surf, (sx, sy))

    def draw_player(self):
        p = self.player
        s = pygame.Surface((Player.W, Player.H), pygame.SRCALPHA)
        # кепка
        pygame.draw.rect(s, RED, (5, 0, 18, 6))
        pygame.draw.rect(s, RED, (13, 4, 13, 3))
        # волосы, лицо
        pygame.draw.rect(s, BROWN, (3, 6, 5, 8))
        pygame.draw.rect(s, SKIN, (7, 6, 17, 11))
        pygame.draw.rect(s, SKIN, (22, 9, 5, 5))
        pygame.draw.rect(s, BLACK, (17, 8, 2, 4))
        pygame.draw.rect(s, BROWN, (14, 13, 12, 3))
        # туловище
        pygame.draw.rect(s, RED, (5, 17, 18, 9))
        pygame.draw.rect(s, BLUE, (7, 20, 14, 13))
        pygame.draw.rect(s, BLUE, (7, 17, 3, 5))
        pygame.draw.rect(s, BLUE, (18, 17, 3, 5))
        pygame.draw.rect(s, (250, 210, 40), (9, 22, 3, 3))
        pygame.draw.rect(s, (250, 210, 40), (16, 22, 3, 3))
        in_air = not p.on_ground
        # руки
        if in_air:
            pygame.draw.rect(s, RED, (19, 13, 5, 8))
            pygame.draw.rect(s, WHITE, (19, 10, 6, 5))
        else:
            pygame.draw.rect(s, RED, (3, 19, 5, 8))
            pygame.draw.rect(s, WHITE, (3, 26, 5, 4))
        # ноги
        if in_air:
            pygame.draw.rect(s, BLUE, (5, 32, 7, 4))
            pygame.draw.rect(s, BLUE, (16, 32, 7, 4))
            pygame.draw.rect(s, BROWN, (3, 35, 10, 5))
            pygame.draw.rect(s, BROWN, (16, 35, 11, 5))
        elif abs(p.vx) > 0.3 and int(p.run_anim) % 2 == 0:
            pygame.draw.rect(s, BLUE, (5, 32, 7, 4))
            pygame.draw.rect(s, BLUE, (16, 32, 7, 4))
            pygame.draw.rect(s, BROWN, (2, 36, 11, 4))
            pygame.draw.rect(s, BROWN, (16, 36, 11, 4))
        else:
            pygame.draw.rect(s, BLUE, (7, 32, 6, 4))
            pygame.draw.rect(s, BLUE, (15, 32, 6, 4))
            pygame.draw.rect(s, BROWN, (5, 36, 9, 4))
            pygame.draw.rect(s, BROWN, (14, 36, 10, 4))
        if p.facing < 0:
            s = pygame.transform.flip(s, True, False)
        self.screen.blit(s, (p.x - self.cam_x, p.y))

    def draw_hud(self):
        secs = max(0, math.ceil(self.time_frames / FPS))
        self.text(f"ОЧКИ  {self.score:06d}", 20, 12)
        self.text(f"МОНЕТЫ  x{self.coins:02d}", 260, 12)
        self.text(f"ЖИЗНИ  x{self.lives}", 480, 12)
        self.text(f"ВРЕМЯ  {secs:03d}", SCREEN_W - 170, 12)

    def draw_overlay(self, title, sub, color=WHITE):
        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 140))
        self.screen.blit(veil, (0, 0))
        self.text(title, SCREEN_W // 2, SCREEN_H // 2 -
                  40, self.font_big, color, center=True)
        for i, line in enumerate(sub):
            self.text(line, SCREEN_W // 2, SCREEN_H // 2 + 20 +
                      i * 32, self.font, WHITE, center=True)

    def draw(self):
        self.draw_background()
        self.draw_tiles()
        self.draw_flag()
        for cx, cy in self.level.coins:
            sx = cx - self.cam_x
            if -20 < sx < SCREEN_W + 20:
                self.draw_coin(sx, cy)
        for pop in self.level.pops:
            self.draw_coin(pop["x"] - self.cam_x, pop["y"])
        for e in self.level.enemies:
            if -60 < e.x - self.cam_x < SCREEN_W + 60:
                self.draw_enemy(e)
        for part in self.level.particles:
            pygame.draw.rect(self.screen, (190, 95, 45),
                             (part["x"] - self.cam_x - 6, part["y"] - 6, 12, 12))
            pygame.draw.rect(self.screen, (110, 50, 20),
                             (part["x"] - self.cam_x - 6, part["y"] - 6, 12, 12), 2)
        self.draw_player()
        for f in self.level.floaters:
            self.text(f["text"], f["x"] - self.cam_x, f["y"], self.font_small)
        self.draw_hud()

        if self.state == "won":
            self.draw_overlay(
                "УРОВЕНЬ ПРОЙДЕН!",
                [f"Очки: {self.score}", "R - сыграть ещё раз, Esc - выход"],
                (255, 220, 60),
            )
        elif self.state == "gameover":
            self.draw_overlay("ИГРА ОКОНЧЕНА", [
                              f"Очки: {self.score}", "R - начать заново, Esc - выход"], RED)

        pygame.display.flip()

    # ------------------------------------------------------------ цикл
    def run(self):
        jump_keys = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    elif event.key == pygame.K_r:
                        self.reset_game()
                    elif event.key in jump_keys:
                        self.player.buffer = 8
            self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
