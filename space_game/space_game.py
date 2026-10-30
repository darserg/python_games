# -*- coding: utf-8 -*-
"""
«Космические корабли» — игра в стиле классики на кнопочных телефонах (Nokia).

Стреляй по вражеским кораблям, которые пролетают по экрану во всех направлениях!
Стиль: монохромный «экран телефона», пиксельная сетка, звук как из динамика.

Управление:
    Стрелки / WASD  — движение корабля
    Пробел          — выстрел (можно зажать)
    P               — пауза
    Esc             — выход

Требования: Python 3.8+, pygame (pip install pygame)
"""

import math
import random
import sys

try:
    import pygame
except ImportError:
    print("Для игры нужен pygame. Установите командой: pip install pygame")
    sys.exit(1)

# ----------------------------------------------------------------------------
# Настройки
# ----------------------------------------------------------------------------

SCREEN_W, SCREEN_H = 480, 640
FPS = 60

# «Жёлто-зелёный экран старого телефона»
LCD_BG = (20, 24, 18)  # фон экрана
LCD_DIM = (70, 90, 55)  # тусклые элементы (сетка, рамка)
LCD_LIGHT = (160, 220, 110)  # яркий пиксель (всё переднее)
LCD_BRIGHT = (220, 255, 170)  # самый яркий (текст очков)
LCD_DARK = (40, 55, 32)  # затемнённый (фонные звёзды)

PLAYER_SPEED = 300.0
BULLET_SPEED = 520.0
ENEMY_SPEED_MIN, ENEMY_SPEED_MAX = 90.0, 220.0
SHOOT_COOLDOWN = 0.18  # сек между выстрелами
WAVE_PAUSE = 2.0  # пауза между волнами

GRID = 4  # размер «пикселя» экрана телефона


# ----------------------------------------------------------------------------
# Простой 8-битный звук (как из динамика телефона)
# ----------------------------------------------------------------------------


class SoundBox:
    """Генерирует короткие «писки» без внешних файлов."""

    def __init__(self):
        self.enabled = True
        try:
            pygame.mixer.pre_init(22050, -16, 1, 256)
            pygame.mixer.init(22050, -16, 1, 256)
        except pygame.error:
            self.enabled = False

    def _tone(self, freq, duration, vol=0.3, sample_rate=22050, wave="square"):
        if not self.enabled:
            return None
        n = int(sample_rate * duration)
        buf = bytearray()
        for i in range(n):
            t = i / sample_rate
            if wave == "square":
                v = 1 if math.sin(2 * math.pi * freq * t) >= 0 else -1
            elif wave == "saw":
                v = 2 * ((freq * t) % 1) - 1
            else:  # noise
                v = random.uniform(-1, 1)
            # огибающая: затухание
            env = max(0.0, 1.0 - t / duration)
            s = int(v * vol * env * 32767)
            buf += s.to_bytes(2, "little", signed=True)
        sound = pygame.mixer.Sound(buffer=bytes(buf))
        return sound

    def shoot(self):
        s = self._tone(880, 0.07, vol=0.15, wave="square")
        if s:
            s.play()

    def explode(self):
        s = self._tone(120, 0.25, vol=0.35, wave="noise")
        if s:
            s.play()

    def hit_player(self):
        s = self._tone(200, 0.35, vol=0.4, wave="saw")
        if s:
            s.play()

    def wave(self):
        for i, f in enumerate((523, 659, 784)):
            s = self._tone(f, 0.12, vol=0.2)
            if s:
                pygame.time.delay(i * 110)
                s.play()

    def game_over(self):
        for f in (392, 330, 262, 196):
            s = self._tone(f, 0.25, vol=0.25, wave="saw")
            if s:
                s.play()
                pygame.time.delay(220)


# ----------------------------------------------------------------------------
# Пиксельные спрайты (рисуем из «пикселей» размером GRID)
# ----------------------------------------------------------------------------


def pixel_art(surface, art, px, py, color, scale=GRID):
    """art — список строк, '#' = залитый пиксель."""
    for j, row in enumerate(art):
        for i, ch in enumerate(row):
            if ch == "#":
                pygame.draw.rect(
                    surface, color, (px + i * scale, py + j * scale, scale, scale)
                )


SHIP_ART = [
    "....##....",
    "...####...",
    "...####...",
    "..######..",
    ".########.",
    ".########.",
    "##.####.##",
    "#...##...#",
]

ENEMY_SMALL_ART = [
    "..##..",
    ".####.",
    "######",
    ".#..#.",
]

ENEMY_MID_ART = [
    "...####...",
    "..######..",
    "############",
    ".###..###.",
    "..#.##.#..",
]

ENEMY_BIG_ART = [
    "....######....",
    "...########...",
    "..##########..",
    "##############",
    "####.####.####",
    "##...####...##",
]

ARTS = {
    "small": (ENEMY_SMALL_ART, 1),
    "mid": (ENEMY_MID_ART, 1),
    "big": (ENEMY_BIG_ART, 1),
}


# ----------------------------------------------------------------------------
# Игровые объекты
# ----------------------------------------------------------------------------


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life")

    def __init__(self, x, y):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(40, 220)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd
        self.max_life = random.uniform(0.25, 0.6)
        self.life = self.max_life

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0


class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "from_enemy")

    def __init__(self, x, y, vx, vy, from_enemy=False):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.from_enemy = from_enemy

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def rect(self):
        w = GRID * 2 if self.from_enemy else GRID
        h = GRID * 2
        return pygame.Rect(int(self.x - w // 2), int(self.y - h), w, h)


class Enemy:
    """Вражеский корабль летит по прямой через экран, как в старых играх."""

    def __init__(self, kind, score):
        self.kind = kind
        art, _ = ARTS[kind]
        self.w = len(art[0]) * GRID
        self.h = len(art) * GRID
        self.hp = {"small": 1, "mid": 2, "big": 3}[kind]
        self.points = {"small": 50, "mid": 100, "big": 150}[kind]
        base = {"small": ENEMY_SPEED_MAX, "mid": 160, "big": ENEMY_SPEED_MIN}[kind]
        speed = base + score * 0.05 + random.uniform(-20, 20)
        speed = max(ENEMY_SPEED_MIN, speed)

        # Случайное направление: с любой стороны экрана
        side = random.choice(("left", "right", "top", "bottom"))
        m = 40
        if side == "left":
            self.x, self.y = -m, random.uniform(m, SCREEN_H - m)
            ang = random.uniform(-0.35, 0.35)
            self.vx, self.vy = speed * math.cos(ang), speed * math.sin(ang)
        elif side == "right":
            self.x, self.y = SCREEN_W + m, random.uniform(m, SCREEN_H - m)
            ang = random.uniform(math.pi - 0.35, math.pi + 0.35)
            self.vx, self.vy = speed * math.cos(ang), speed * math.sin(ang)
        elif side == "top":
            self.x, self.y = random.uniform(m, SCREEN_W - m), -m
            ang = random.uniform(math.pi / 2 - 0.35, math.pi / 2 + 0.35)
            self.vx, self.vy = speed * math.cos(ang), speed * math.sin(ang)
        else:
            self.x, self.y = random.uniform(m, SCREEN_W - m), SCREEN_H + m
            ang = random.uniform(-math.pi / 2 - 0.35, -math.pi / 2 + 0.35)
            self.vx, self.vy = speed * math.cos(ang), speed * math.sin(ang)

        self.shoot_timer = random.uniform(1.0, 3.0)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.shoot_timer -= dt

    @property
    def can_shoot(self):
        return self.shoot_timer <= 0

    def reset_shot(self):
        self.shoot_timer = random.uniform(2.2, 4.5)

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h
        )

    def offscreen(self):
        m = 80
        return (
            self.x < -m or self.x > SCREEN_W + m or self.y < -m or self.y > SCREEN_H + m
        )


class Player:
    def __init__(self):
        self.x = SCREEN_W / 2
        self.y = SCREEN_H - 70
        self.w = len(SHIP_ART[0]) * GRID
        self.h = len(SHIP_ART) * GRID
        self.cooldown = 0.0
        self.invulnerable = 0.0  # сек неуязвимости после попадания

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h
        )

    def update(self, dt, keys):
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x += dx * PLAYER_SPEED * dt
        self.y += dy * PLAYER_SPEED * dt
        self.x = max(self.w / 2, min(SCREEN_W - self.w / 2, self.x))
        self.y = max(self.h / 2, min(SCREEN_H - self.h / 2, self.y))
        self.cooldown = max(0.0, self.cooldown - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)

    def try_shoot(self):
        if self.cooldown <= 0.0:
            self.cooldown = SHOOT_COOLDOWN
            return Bullet(self.x, self.y - self.h / 2, 0, -BULLET_SPEED)
        return None


# ----------------------------------------------------------------------------
# Звёздный фон (тусклые пиксели, как на LCD)
# ----------------------------------------------------------------------------


class Starfield:
    def __init__(self, count=60):
        self.stars = [
            [
                random.uniform(0, SCREEN_W),
                random.uniform(0, SCREEN_H),
                random.uniform(20, 60),
            ]
            for _ in range(count)
        ]

    def update(self, dt):
        for s in self.stars:
            s[1] += s[2] * dt
            if s[1] > SCREEN_H:
                s[1] = 0
                s[0] = random.uniform(0, SCREEN_W)

    def draw(self, surf):
        for x, y, _ in self.stars:
            pygame.draw.rect(surf, LCD_DARK, (int(x), int(y), GRID, GRID))


# ----------------------------------------------------------------------------
# Игра
# ----------------------------------------------------------------------------


class Game:
    STATE_MENU, STATE_PLAY, STATE_PAUSE, STATE_GAMEOVER = range(4)

    def __init__(self):
        pygame.init()
        self.sound = SoundBox()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("SpaceCraft - Nokia Style")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.Font(None, 56)
        self.font = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 26)
        self.starfield = Starfield()
        self.best = self._load_best()
        self.state = self.STATE_MENU
        self.flash = 0.0

    # --- рекорд ---
    @staticmethod
    def _best_path():
        import os

        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "space_highscore.txt"
        )

    def _load_best(self):
        try:
            with open(self._best_path()) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _save_best(self):
        try:
            with open(self._best_path(), "w") as f:
                f.write(str(self.best))
        except Exception:
            pass

    # --- запуск раунда ---
    def start_round(self):
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.particles = []
        self.score = 0
        self.lives = 3
        self.wave = 0
        self.spawn_queue = []
        self.wave_timer = 0.5
        self.paused = False

    def next_wave(self):
        self.wave += 1
        count = 3 + self.wave
        kinds = ["small"] * count
        if self.wave >= 2:
            kinds += ["mid"] * max(1, self.wave // 2)
        if self.wave >= 4:
            kinds += ["big"] * max(1, self.wave // 3)
        self.spawn_queue = kinds
        random.shuffle(self.spawn_queue)
        self.spawn_timer = 0.0
        self.sound.wave()

    # --- обновление ---
    def update(self, dt):
        self.starfield.update(dt)
        self.flash = max(0.0, self.flash - dt * 3)

        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)
        if keys[pygame.K_SPACE]:
            b = self.player.try_shoot()
            if b:
                self.bullets.append(b)
                self.sound.shoot()

        # спавн волны
        if not self.spawn_queue and not self.enemies:
            self.wave_timer -= dt
            if self.wave_timer <= 0:
                self.next_wave()
                self.wave_timer = WAVE_PAUSE
        else:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0 and self.spawn_queue:
                kind = self.spawn_queue.pop()
                self.enemies.append(Enemy(kind, self.score))
                self.spawn_timer = max(0.35, 1.1 - self.wave * 0.05)

        # пули игрока
        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.y > -20]

        # враги
        for e in self.enemies:
            e.update(dt)
            if e.can_shoot and GRID and self._in_screen(e):
                e.reset_shot()
                dx = self.player.x - e.x
                dy = self.player.y - e.y
                d = math.hypot(dx, dy) or 1
                spd = 240 + self.wave * 8
                self.enemy_bullets.append(
                    Bullet(
                        e.x, e.y + e.h / 2, dx / d * spd, dy / d * spd, from_enemy=True
                    )
                )
        self.enemies = [e for e in self.enemies if not e.offscreen()]

        # пули врагов
        for b in self.enemy_bullets:
            b.update(dt)
        self.enemy_bullets = [
            b
            for b in self.enemy_bullets
            if -20 < b.y < SCREEN_H + 20 and -20 < b.x < SCREEN_W + 20
        ]

        # столкновения: пули игрока -> враги
        dead_enemies = set()
        for b in self.bullets:
            br = b.rect
            for idx, e in enumerate(self.enemies):
                if idx in dead_enemies:
                    continue
                if br.colliderect(e.rect):
                    b.x = -9999  # пометить на удаление
                    e.hp -= 1
                    if e.hp <= 0:
                        dead_enemies.add(idx)
                        self.score += e.points
                        self._explode(e.x, e.y, big=(e.kind != "small"))
                        self.sound.explode()
                    else:
                        self._spawn_sparks(b.x, b.y, 4)
                    break
        self.enemies = [e for i, e in enumerate(self.enemies) if i not in dead_enemies]
        self.bullets = [b for b in self.bullets if b.x > -9000]

        # столкновения с игроком
        pr = self.player.rect
        hit = False
        if self.player.invulnerable <= 0:
            for b in self.enemy_bullets:
                if b.rect.colliderect(pr):
                    hit = True
                    break
            if not hit:
                for e in self.enemies:
                    if e.rect.colliderect(pr):
                        hit = True
                        self._explode(e.x, e.y, big=True)
                        self.enemies.remove(e)
                        break
            if hit:
                self.lives -= 1
                self.player.invulnerable = 2.0
                self.flash = 1.0
                self.sound.hit_player()
                self._spawn_sparks(self.player.x, self.player.y, 20)
                if self.lives <= 0:
                    self._game_over()

        # частицы
        self.particles = [p for p in self.particles if p.update(dt)]

    def _in_screen(self, e):
        return 0 < e.x < SCREEN_W and 0 < e.y < SCREEN_H * 0.85

    def _explode(self, x, y, big=False):
        n = 24 if big else 12
        self._spawn_sparks(x, y, n)

    def _spawn_sparks(self, x, y, n):
        for _ in range(n):
            self.particles.append(Particle(x, y))

    def _game_over(self):
        self.state = self.STATE_GAMEOVER
        if self.score > self.best:
            self.best = self.score
            self._save_best()
        self.sound.game_over()

    # --- отрисовка ---
    def draw_lcd_frame(self, surf):
        """Рамка «телефона» и пиксельная сетка."""
        # лёгкая сетка, имитирующая точки LCD
        grid_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for x in range(0, SCREEN_W, GRID * 3):
            pygame.draw.line(grid_surf, (*LCD_DIM, 18), (x, 0), (x, SCREEN_H))
        for y in range(0, SCREEN_H, GRID * 3):
            pygame.draw.line(grid_surf, (*LCD_DIM, 18), (0, y), (SCREEN_W, y))
        surf.blit(grid_surf, (0, 0))

    def draw_hud(self, surf):
        # очки
        t = self.font.render(f"{self.score:06d}", True, LCD_BRIGHT)
        surf.blit(t, (12, 8))
        best = self.font_small.render(f"RECORD {self.best:06d}", True, LCD_DIM)
        surf.blit(best, (12, 30))
        # жизни — маленькие кораблики
        for i in range(self.lives):
            pixel_art(surf, SHIP_ART, SCREEN_W - 110 + i * 34, 10, LCD_LIGHT, scale=2)
        # волна
        w = self.font_small.render(f"WAVE {self.wave}", True, LCD_DIM)
        surf.blit(w, (SCREEN_W // 2 - w.get_width() // 2, 10))

    def draw(self):
        surf = self.screen
        surf.fill(LCD_BG)
        self.starfield.draw(surf)

        if self.state == self.STATE_MENU:
            self._draw_center_menu(surf)
            self.draw_lcd_frame(surf)
            return

        # игровые объекты
        for p in self.particles:
            a = max(0, min(255, int(255 * p.life / p.max_life)))
            c = (
                a * LCD_LIGHT[0] // 255,
                a * LCD_LIGHT[1] // 255,
                a * LCD_LIGHT[2] // 255,
            )
            pygame.draw.rect(surf, c, (int(p.x), int(p.y), GRID, GRID))

        for b in self.bullets:
            r = b.rect
            pygame.draw.rect(surf, LCD_BRIGHT, r)
        for b in self.enemy_bullets:
            r = b.rect
            pygame.draw.rect(surf, LCD_LIGHT, r)

        for e in self.enemies:
            art, _ = ARTS[e.kind]
            blink = e.hp < {"small": 1, "mid": 2, "big": 3}[e.kind]
            col = (
                LCD_DIM if blink and pygame.time.get_ticks() % 200 < 100 else LCD_LIGHT
            )
            pixel_art(surf, art, int(e.x - e.w / 2), int(e.y - e.h / 2), col)

        # корабль игрока (мигает при неуязвимости)
        if (
            self.state == self.STATE_PLAY
            or self.player.invulnerable <= 0
            or pygame.time.get_ticks() % 160 < 90
        ):
            pixel_art(
                surf,
                SHIP_ART,
                int(self.player.x - self.player.w / 2),
                int(self.player.y - self.player.h / 2),
                LCD_BRIGHT,
            )

        if self.flash > 0:
            fs = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            fs.fill((*LCD_LIGHT, int(70 * self.flash)))
            surf.blit(fs, (0, 0))

        self.draw_hud(surf)
        self.draw_lcd_frame(surf)

        if self.state == self.STATE_PAUSE:
            self._overlay_text(surf, "PAUSE", "P — CONTINUE")
        elif self.state == self.STATE_GAMEOVER:
            self._overlay_text(
                surf,
                "GAME_OVER",
                f"SCORE: {self.score}   RECORD: {self.best}",
                "SPACE — NEW GAME, ESC — EXIT",
            )

    def _draw_center_menu(self, surf):
        title = self.font_big.render("COSMIC SHIPS", True, LCD_BRIGHT)
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 90))
        # sub = self.font.render("v styare Nokia", True, LCD_LIGHT)
        # surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 150))

        ship = SHIP_ART
        sw = len(ship[0]) * GRID * 2
        pixel_art(surf, ship, SCREEN_W // 2 - sw // 2, 210, LCD_LIGHT, scale=GRID * 2)

        lines = [
            "ARROWS / WASD - MOVEMENT",
            "SPACE - SHOOT",
            "P - PAUSE    ESC - EXIT",
            "",
            "PRESS SPACE TO START",
        ]
        y = 320
        for ln in lines:
            t = self.font_small.render(
                ln, True, LCD_BRIGHT if "SPACE TO" in ln else LCD_LIGHT
            )
            if pygame.time.get_ticks() % 1000 < 500 or "SPACE TO" not in ln:
                surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, y))
            y += 30
        rec = self.font_small.render(f"Best result: {self.best}", True, LCD_DIM)
        surf.blit(rec, (SCREEN_W // 2 - rec.get_width() // 2, 560))

    def _overlay_text(self, surf, big, mid="", small=""):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((*LCD_BG, 200))
        surf.blit(ov, (0, 0))
        tb = self.font_big.render(big, True, LCD_BRIGHT)
        surf.blit(tb, (SCREEN_W // 2 - tb.get_width() // 2, SCREEN_H // 2 - 90))
        if mid:
            tm = self.font.render(mid, True, LCD_LIGHT)
            surf.blit(tm, (SCREEN_W // 2 - tm.get_width() // 2, SCREEN_H // 2 - 10))
        if small:
            ts = self.font_small.render(small, True, LCD_DIM)
            surf.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2, SCREEN_H // 2 + 40))

    # --- главный цикл ---
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    if self.state == self.STATE_MENU and ev.key in (
                        pygame.K_SPACE,
                        pygame.K_RETURN,
                    ):
                        self.start_round()
                        self.state = self.STATE_PLAY
                    elif self.state == self.STATE_PLAY and ev.key == pygame.K_p:
                        self.state = self.STATE_PAUSE
                    elif self.state == self.STATE_PAUSE and ev.key == pygame.K_p:
                        self.state = self.STATE_PLAY
                    elif self.state == self.STATE_GAMEOVER and ev.key == pygame.K_SPACE:
                        self.start_round()
                        self.state = self.STATE_PLAY

            if self.state == self.STATE_PLAY:
                self.update(dt)

            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    Game().run()
