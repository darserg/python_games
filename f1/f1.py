"""
Гран-при: гонка Формулы-1 на Pygame (псевдо-3D, вид из-за болида).

Оригинальная игра в духе ранних F1-симуляторов: вымышленные команды и пилоты,
всё рисуется кодом, внешние файлы не нужны.

Управление:
  Вверх / W     - газ
  Вниз / S      - тормоз
  Влево / Вправо или A / D - руль
  R             - рестарт гонки
  Esc           - выход

Старт: удерживай газ, когда погаснут все пять красных огней - гонка началась.
Дистанция: 3 круга, на старте 12 болидов, ты стартуешь восьмым.

Запуск:
  pip install pygame
  python f1_racing.py
"""

import math
import random
import sys

import pygame

# ---------------------------------------------------------------- параметры
W, H = 960, 540
FPS = 60

SEG = 200                  # длина сегмента трассы
RUMBLE = 3                 # длина полосы поребрика (в сегментах)
ROAD_W = 2200              # полуширина дороги
CAM_H = 1000               # высота камеры
FOV = 100
CAM_DEPTH = 1 / math.tan(math.radians(FOV / 2))
PLAYER_Z = CAM_H * CAM_DEPTH
DRAW = 180                 # дальность прорисовки в сегментах

MAX_SPEED = 14000.0
BRAKE = -MAX_SPEED * 0.9
DECEL = -MAX_SPEED / 6
OFFROAD_DECEL = -MAX_SPEED / 1.7
OFFROAD_LIMIT = MAX_SPEED / 4
CENTRIF = 0.28

CAR_W = 300                # ширина болида в мировых единицах
CAR_N = CAR_W / ROAD_W     # то же, в долях ширины дороги
LAPS = 3
GRID_SLOTS = 12
GRID_GAP = 1100
PLAYER_SLOT = 7            # 0 - поул

AI_ACCEL = MAX_SPEED / 5
AI_BRAKE = MAX_SPEED / 2.5

FOG = (170, 205, 235)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

COLORS = (
    {"road": (105, 105, 110), "grass": (
        18, 150, 30), "rumble": (235, 235, 235)},
    {"road": (100, 100, 105), "grass": (12, 138, 26), "rumble": (210, 20, 20)},
)

# вымышленные команды: название, цвет кузова, акцент, код пилота
TEAMS = [
    ("Falcon", (215, 30, 30), (250, 250, 250), "YOU"),
    ("Vortex", (30, 90, 220), (240, 240, 240), "VOR"),
    ("Apex", (250, 200, 20), (30, 30, 30), "APX"),
    ("Nova", (240, 120, 20), (30, 30, 30), "NOV"),
    ("Titan", (20, 160, 90), (240, 240, 240), "TIT"),
    ("Zenith", (160, 60, 200), (240, 240, 240), "ZEN"),
    ("Aero", (0, 190, 210), (20, 20, 20), "AER"),
    ("Quasar", (225, 225, 230), (200, 30, 30), "QSR"),
    ("Helix", (240, 80, 150), (30, 30, 30), "HLX"),
    ("Onyx", (50, 50, 60), (240, 200, 20), "ONX"),
    ("Ember", (150, 30, 30), (250, 180, 30), "EMB"),
    ("Pulse", (120, 200, 40), (30, 30, 30), "PLS"),
]


# ---------------------------------------------------------------- утилиты
def lerp_col(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_out(a, b, p):
    return a + (b - a) * (1 - (1 - p) ** 2)


def ease_in_out(a, b, p):
    return a + (b - a) * (-math.cos(p * math.pi) / 2 + 0.5)


def overlap(x1, w1, x2, w2, pct=1.0):
    half = pct / 2
    return not ((x1 + w1 * half) < (x2 - w2 * half) or (x1 - w1 * half) > (x2 + w2 * half))


def fmt_time(t):
    if t is None:
        return "--:--.---"
    m = int(t // 60)
    return f"{m}:{t - 60 * m:06.3f}"


# ---------------------------------------------------------------- трасса
class Seg:
    __slots__ = ("index", "z1", "z2", "y1", "y2", "curve", "shade", "start",
                 "cars", "sprites", "ok", "clip",
                 "sx1", "sy1", "sw1", "sc1", "sx2", "sy2", "sw2", "sc2")

    def __init__(self, index, y1, y2, curve):
        self.index = index
        self.z1 = index * SEG
        self.z2 = (index + 1) * SEG
        self.y1, self.y2 = y1, y2
        self.curve = curve
        self.shade = (index // RUMBLE) % 2
        self.start = index < 2
        self.cars = []
        self.sprites = []
        self.ok = False
        self.clip = H
        self.sx1 = self.sy1 = self.sw1 = self.sc1 = 0.0
        self.sx2 = self.sy2 = self.sw2 = self.sc2 = 0.0


def build_track():
    segs = []

    def last_y():
        return segs[-1].y2 if segs else 0.0

    def add(curve, y):
        segs.append(Seg(len(segs), last_y(), y, curve))

    def road(enter, hold, leave, curve, y=0.0):
        start_y = last_y()
        end_y = start_y + y * SEG
        total = enter + hold + leave
        for n in range(enter):
            add(ease_in(0, curve, n / enter),
                ease_in_out(start_y, end_y, n / total))
        for n in range(hold):
            add(curve, ease_in_out(start_y, end_y, (enter + n) / total))
        for n in range(leave):
            add(ease_out(curve, 0, n / leave),
                ease_in_out(start_y, end_y, (enter + hold + n) / total))

    road(40, 60, 40, 0, 0)         # стартовая прямая
    road(25, 40, 25, 4, 0)         # поворот 1 - правый
    road(30, 40, 30, 0, 6)         # подъём
    road(15, 20, 15, -4, 0)        # шикана
    road(15, 20, 15, 4, 0)
    road(15, 20, 15, -4, 0)
    road(40, 90, 40, 2.5, -2)      # длинный правый поворот
    road(30, 60, 30, 0, -6)        # спуск
    road(30, 70, 30, -6, 0)        # шпилька влево
    road(40, 120, 40, 0, 8)        # задняя прямая в горку
    road(30, 50, 30, 6, -8)        # шпилька вправо со спуском
    road(25, 30, 25, -3, 0)        # эсы
    road(25, 30, 25, 3, 0)
    road(25, 30, 25, -3, 0)
    road(40, 80, 40, 3, 4)
    road(30, 50, 30, 0, -4)
    road(30, 60, 30, -4, 0)
    road(30, 50, 30, 0, 3)
    road(25, 40, 25, 5, 0)
    road(25, 40, 25, -5, 0)
    road(30, 80, 30, 3, -3)
    road(40, 100, 40, 0, 0)
    # возвращаем высоту в 0, чтобы круг замкнулся
    road(40, 120, 40, 0, -last_y() / SEG)

    n_total = len(segs)

    # --- объекты вдоль трассы
    rnd = random.Random(3)
    for n in range(12, n_total - 150, 6):
        side = rnd.choice((-1, 1))
        segs[n].sprites.append((0, side * rnd.uniform(1.5, 3.5)))
    board = 0
    for n in range(30, n_total - 150, 80):
        side = 1 if (n // 80) % 2 else -1
        segs[n].sprites.append((2 + board % 4, side * 1.5))
        board += 1
    for rng in (range(4, 130, 16), range(n_total - 140, n_total - 10, 16)):
        for n in rng:
            segs[n].sprites.append((1, -2.4))
            segs[n].sprites.append((1, 2.4))
    return segs


# ---------------------------------------------------------------- машины
class Car:
    def __init__(self, skin, is_player=False):
        self.skin = skin
        self.is_player = is_player
        self.name, self.color, self.accent, self.code = TEAMS[skin]
        self.dist = 0.0
        self.z = 0.0
        self.offset = 0.0
        self.speed = 0.0
        self.base = 0.0
        self.percent = 0.0
        # порядок финиширования (-1 - ещё не финишировал)
        self.fin = -1


# ---------------------------------------------------------------- игра
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Гран-при - гонка Формулы-1")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.SysFont("arial", 64, bold=True)
        self.f_mid = pygame.font.SysFont("arial", 30, bold=True)
        self.f_sml = pygame.font.SysFont("arial", 19, bold=True)
        self.f_tiny = pygame.font.SysFont("arial", 15, bold=True)

        self.segs = build_track()
        self.N = len(self.segs)
        self.L = self.N * SEG

        self.fog_f = [math.exp(-2.6 * (n / DRAW) ** 2) for n in range(DRAW)]
        self.fog_cols = [
            [(lerp_col(FOG, c["grass"], f), lerp_col(FOG, c["road"], f), lerp_col(FOG, c["rumble"], f))
             for f in self.fog_f]
            for c in COLORS
        ]
        self.check_cols = [(lerp_col(FOG, (240, 240, 240), f), lerp_col(
            FOG, (25, 25, 25), f)) for f in self.fog_f]

        self.make_assets()
        self.reset()

    # ------------------------------------------------------------ графика
    def make_assets(self):
        # небо
        self.horizon = int(H * 0.56)
        self.sky = pygame.Surface((W, H))
        self.sky.fill(FOG)
        for y in range(self.horizon):
            t = y / self.horizon
            pygame.draw.line(self.sky, lerp_col(
                (60, 120, 215), FOG, t ** 1.4), (0, y), (W, y))
        self.hill_far = self.make_hills((135, 165, 205), 26, 40, (1, 2, 3), 1)
        self.hill_near = self.make_hills((95, 150, 135), 20, 24, (2, 3, 5), 2)
        self.bg_far = 0.0
        self.bg_near = 0.0

        # болиды (вид сзади)
        self.car_surfs = [self.make_car(t[1], t[2]) for t in TEAMS]

        # объекты
        self.sprite_defs = [
            (self.make_tree(), 700),
            (self.make_stand(), 2000),
        ]
        names = [("TURBO", (200, 30, 30)), ("VELOX", (30, 90, 200)),
                 ("AXIS", (30, 140, 70)), ("ZENIT", (230, 160, 20))]
        for name, col in names:
            self.sprite_defs.append((self.make_board(name, col), 1300))

        # полупрозрачная подложка табло
        self.tower_bg = pygame.Surface((168, 22), pygame.SRCALPHA)
        self.tower_bg.fill((10, 10, 20, 170))

    @staticmethod
    def make_hills(color, amp, base, freqs, seed):
        h = 170
        s = pygame.Surface((W, h), pygame.SRCALPHA)
        rnd = random.Random(seed)
        phases = [rnd.uniform(0, 6.28) for _ in freqs]
        pts = [(0, h)]
        for x in range(0, W + 1, 8):
            v = base
            for k, (f, ph) in enumerate(zip(freqs, phases)):
                v += amp / (k + 1) * math.sin(2 * math.pi * f * x / W + ph)
            pts.append((x, h - v))
        pts.append((W, h))
        pygame.draw.polygon(s, color, pts)
        return s

    @staticmethod
    def make_car(body, accent):
        s = pygame.Surface((100, 50), pygame.SRCALPHA)
        dark = (22, 22, 26)
        grey = (80, 80, 88)
        # шины
        pygame.draw.rect(s, dark, (0, 20, 24, 28), border_radius=5)
        pygame.draw.rect(s, dark, (76, 20, 24, 28), border_radius=5)
        for yy in (27, 34, 41):
            pygame.draw.line(s, grey, (3, yy), (21, yy), 2)
            pygame.draw.line(s, grey, (79, yy), (97, yy), 2)
        # подвеска
        pygame.draw.line(s, grey, (24, 33), (36, 28), 3)
        pygame.draw.line(s, grey, (76, 33), (64, 28), 3)
        # диффузор
        pygame.draw.polygon(
            s, (35, 35, 40), [(27, 42), (73, 42), (66, 49), (34, 49)])
        # кузов
        pygame.draw.polygon(s, body, [(33, 16), (67, 16), (71, 43), (29, 43)])
        pygame.draw.rect(s, accent, (46, 16, 8, 27))
        # воздухозаборник и шлем
        pygame.draw.rect(s, dark, (44, 6, 12, 11), border_radius=3)
        pygame.draw.circle(s, accent, (50, 16), 5)
        pygame.draw.rect(s, dark, (47, 15, 6, 2))
        # заднее крыло
        pygame.draw.rect(s, dark, (46, 9, 8, 9))
        pygame.draw.rect(s, body, (12, 2, 76, 8), border_radius=2)
        pygame.draw.rect(s, accent, (12, 9, 76, 3))
        pygame.draw.rect(s, dark, (10, 0, 5, 19))
        pygame.draw.rect(s, dark, (85, 0, 5, 19))
        # дождевой фонарь
        pygame.draw.rect(s, (255, 30, 30), (47, 38, 6, 4))
        return s

    @staticmethod
    def make_tree():
        s = pygame.Surface((60, 100), pygame.SRCALPHA)
        pygame.draw.rect(s, (90, 60, 30), (26, 62, 8, 38))
        pygame.draw.ellipse(s, (20, 105, 35), (2, 14, 56, 56))
        pygame.draw.ellipse(s, (35, 135, 50), (10, 0, 40, 44))
        pygame.draw.ellipse(s, (55, 160, 70), (16, 6, 18, 14))
        return s

    def make_board(self, name, color):
        s = pygame.Surface((110, 90), pygame.SRCALPHA)
        pygame.draw.rect(s, (90, 90, 96), (12, 45, 6, 45))
        pygame.draw.rect(s, (90, 90, 96), (92, 45, 6, 45))
        pygame.draw.rect(s, color, (0, 0, 110, 56), border_radius=4)
        pygame.draw.rect(s, WHITE, (0, 0, 110, 56), 3, border_radius=4)
        pygame.draw.rect(s, WHITE, (0, 40, 110, 4))
        img = self.f_sml.render(name, True, WHITE)
        s.blit(img, img.get_rect(center=(55, 21)))
        return s

    @staticmethod
    def make_stand():
        s = pygame.Surface((180, 90), pygame.SRCALPHA)
        pygame.draw.rect(s, (55, 55, 62), (0, 0, 180, 10))
        pygame.draw.rect(s, (110, 110, 120), (0, 10, 180, 80))
        rnd = random.Random(5)
        palette = [(220, 50, 50), (240, 240, 240), (50, 90, 220),
                   (250, 210, 40), (40, 40, 50), (60, 170, 80)]
        for row in range(6):
            y = 14 + row * 12
            pygame.draw.line(s, (80, 80, 90), (0, y + 10), (180, y + 10), 2)
            for col in range(28):
                pygame.draw.rect(s, rnd.choice(palette),
                                 (4 + col * 6, y, 4, 8))
        return s

    def blit_scaled(self, src, cx, by, dw, clip):
        dw = int(dw)
        if dw < 2 or dw > 1600:
            return
        if cx + dw / 2 < 0 or cx - dw / 2 > W:
            return
        dh = int(dw * src.get_height() / src.get_width())
        if clip - (by - dh) <= 0:
            return
        img = pygame.transform.scale(src, (dw, dh))
        clipped = clip < H
        if clipped:
            self.screen.set_clip((0, 0, W, max(0, int(clip))))
        self.screen.blit(img, (int(cx - dw / 2), int(by - dh)))
        if clipped:
            self.screen.set_clip(None)

    # ------------------------------------------------------------ состояние
    def seg_at(self, z):
        return self.segs[int(z // SEG) % self.N]

    def reset(self):
        for s in self.segs:
            s.cars = []
        self.state = "grid"        # grid -> race -> finished
        self.grid_t = 0.0
        self.go_at = 4.6 + random.uniform(0.6, 1.8)
        self.lit = 0
        self.go_t = 0.0
        self.race_time = 0.0
        self.lap_mark = 0.0
        self.lap_times = []
        self.best_lap = None
        self.fin_counter = 0
        self.fin_t = 0.0
        self.final_rank = 0
        self.rev = 0.0
        self.frame = 0
        self.shake = 0.0
        self.bg_far = self.bg_near = 0.0

        # пилот
        self.pcar = Car(0, True)
        slot_dist = -(PLAYER_SLOT + 1) * GRID_GAP
        self.pcar.dist = slot_dist
        self.player_x = -0.45 if PLAYER_SLOT % 2 == 0 else 0.45
        self.total = slot_dist - PLAYER_Z
        self.position = self.total % self.L
        self.speed = 0.0

        # соперники
        skins = list(range(1, len(TEAMS)))
        random.shuffle(skins)
        self.ai = []
        k = 0
        for slot in range(GRID_SLOTS):
            if slot == PLAYER_SLOT:
                continue
            car = Car(skins[k])
            k += 1
            car.dist = -(slot + 1) * GRID_GAP
            car.z = car.dist % self.L
            car.offset = -0.45 if slot % 2 == 0 else 0.45
            car.base = random.uniform(0.80, 0.935) * MAX_SPEED
            car.percent = (car.z % SEG) / SEG
            self.seg_at(car.z).cars.append(car)
            self.ai.append(car)
        self.field = self.ai + [self.pcar]

    def order(self):
        return sorted(self.field, key=lambda c: (1, -c.fin) if c.fin >= 0 else (0, c.dist), reverse=True)

    # ------------------------------------------------------------ обновление
    def update(self, dt):
        keys = pygame.key.get_pressed()
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        self.frame += 1

        if self.state == "grid":
            self.grid_t += dt
            self.lit = 0 if self.grid_t < 1.0 else min(
                5, int((self.grid_t - 1.0) / 0.9) + 1)
            self.rev = min(1.0, self.rev + dt *
                           1.6) if up else max(0.0, self.rev - dt * 1.2)
            if self.grid_t >= self.go_at:
                self.state = "race"
                self.go_t = 2.0
                self.lit = 0
            return

        if self.go_t > 0:
            self.go_t -= dt
        if self.state == "race":
            self.race_time += dt
        else:
            self.fin_t += dt

        self.update_player(dt, up, down, left, right)
        self.update_cars(dt)

        # фон-параллакс
        pseg = self.seg_at(self.position + PLAYER_Z)
        travel = self.speed * dt / SEG
        self.bg_far = (self.bg_far + pseg.curve * travel * 0.35) % W
        self.bg_near = (self.bg_near + pseg.curve * travel * 0.8) % W
        self.shake = max(0.0, self.shake - dt * 3)

    def update_player(self, dt, up, down, left, right):
        fin = self.state == "finished"
        pseg = self.seg_at(self.position + PLAYER_Z)
        pct = self.speed / MAX_SPEED
        dx = dt * 2.4 * pct
        prev_dist = self.pcar.dist

        self.total += self.speed * dt
        self.position = self.total % self.L

        if not fin:
            if left:
                self.player_x -= dx
            if right:
                self.player_x += dx
            self.player_x -= dx * pct * pseg.curve * CENTRIF
            if up:
                self.speed += MAX_SPEED / 3.2 * (1 - 0.8 * pct) * dt
            elif down:
                self.speed += BRAKE * dt
            else:
                self.speed += DECEL * dt
        else:
            self.player_x += (0.5 - self.player_x) * min(1.0, dt * 1.5)
            self.speed += BRAKE * 0.3 * dt

        off_road = abs(self.player_x) > 1.12
        if off_road and self.speed > OFFROAD_LIMIT:
            self.speed += OFFROAD_DECEL * dt
            self.shake = max(self.shake, 0.6)

        # столкновения с болидами
        for car in pseg.cars:
            if self.speed > car.speed and overlap(self.player_x, CAR_N, car.offset, CAR_N, 0.8):
                self.speed = car.speed * (car.speed / max(self.speed, 1))
                self.shake = 1.0
                break

        # столкновения с объектами у трассы
        if off_road:
            for kind, off in pseg.sprites:
                if kind == 1:
                    continue
                sw = self.sprite_defs[kind][1] / ROAD_W
                sign = 1 if off > 0 else -1
                sx = off  # offset - это центр объекта
                if overlap(self.player_x, CAR_N, sx, sw):
                    self.speed = min(self.speed, MAX_SPEED * 0.1)
                    self.player_x = sx - sign * (sw / 2 + CAR_N / 2 + 0.03)
                    self.shake = 1.0
                    break

        self.player_x = max(-3.5, min(3.5, self.player_x))
        self.speed = max(0.0, min(MAX_SPEED, self.speed))
        self.pcar.dist = self.total + PLAYER_Z

        # круги
        if self.state == "race":
            idx_prev = math.floor(prev_dist / self.L)
            idx = math.floor(self.pcar.dist / self.L)
            if idx > idx_prev and idx >= 1:
                lap = self.race_time - self.lap_mark
                self.lap_mark = self.race_time
                self.lap_times.append(lap)
                if self.best_lap is None or lap < self.best_lap:
                    self.best_lap = lap
                if idx >= LAPS:
                    self.pcar.fin = self.fin_counter
                    self.fin_counter += 1
                    self.state = "finished"
                    self.fin_t = 0.0
                    self.final_rank = self.order().index(self.pcar) + 1

    def car_offset(self, car, car_seg, player_seg):
        """Простое объезжание: смотрим вперёд на 20 сегментов."""
        segs, N = self.segs, self.N
        for i in range(1, 20):
            seg = segs[(car_seg.index + i) % N]
            if seg is player_seg and car.speed > self.speed and overlap(self.player_x, CAR_N, car.offset, CAR_N, 1.2):
                if self.player_x > 0.5:
                    d = -1
                elif self.player_x < -0.5:
                    d = 1
                else:
                    d = 1 if car.offset > self.player_x else -1
                return d / i * (car.speed - self.speed) / MAX_SPEED
            for other in seg.cars:
                if car.speed > other.speed and overlap(car.offset, CAR_N, other.offset, CAR_N, 1.2):
                    if other.offset > 0.5:
                        d = -1
                    elif other.offset < -0.5:
                        d = 1
                    else:
                        d = 1 if car.offset > other.offset else -1
                    return d / i * (car.speed - other.speed) / MAX_SPEED
        if car.offset < -0.9:
            return 0.1
        if car.offset > 0.9:
            return -0.1
        return 0.0

    def update_cars(self, dt):
        pseg = self.seg_at(self.position + PLAYER_Z)
        segs, N = self.segs, self.N
        f60 = dt * 60
        for c in self.ai:
            old = self.seg_at(c.z)
            c.offset += self.car_offset(c, old, pseg) * f60
            c.offset = max(-1.3, min(1.3, c.offset))

            if c.fin >= 0:
                target = 0.45 * MAX_SPEED
            else:
                worst = 0.0
                for i in range(12):
                    worst = max(worst, abs(segs[(old.index + i) % N].curve))
                target = min(c.base, max(0.5, 1 - 0.06 * worst) * MAX_SPEED)
            if c.speed < target:
                c.speed = min(target, c.speed + AI_ACCEL * dt)
            else:
                c.speed = max(target, c.speed - AI_BRAKE * dt)

            c.dist += c.speed * dt
            c.z = c.dist % self.L
            c.percent = (c.z % SEG) / SEG
            new = self.seg_at(c.z)
            if new is not old:
                old.cars.remove(c)
                new.cars.append(c)
            if c.fin < 0 and c.dist >= LAPS * self.L:
                c.fin = self.fin_counter
                self.fin_counter += 1

    # ------------------------------------------------------------ рисование мира
    def draw_background(self):
        scr = self.screen
        scr.blit(self.sky, (0, 0))
        y_far = self.horizon - self.hill_far.get_height() + 6
        y_near = self.horizon - self.hill_near.get_height() + 10
        ox = int(self.bg_far)
        scr.blit(self.hill_far, (-ox, y_far))
        scr.blit(self.hill_far, (-ox + W, y_far))
        ox = int(self.bg_near)
        scr.blit(self.hill_near, (-ox, y_near))
        scr.blit(self.hill_near, (-ox + W, y_near))

    def render_road(self):
        scr = self.screen
        segs, N, L = self.segs, self.N, self.L
        pos = self.position
        base_i = int(pos // SEG) % N
        base = segs[base_i]
        base_pct = (pos % SEG) / SEG
        pz = pos + PLAYER_Z
        pseg = segs[int(pz // SEG) % N]
        ppct = (pz % SEG) / SEG
        py = pseg.y1 + (pseg.y2 - pseg.y1) * ppct
        cam_y = py + CAM_H
        px = self.player_x * ROAD_W
        hw, hh = W / 2, H / 2

        maxy = H
        x = 0.0
        dx = -(base.curve * base_pct)
        poly = pygame.draw.polygon
        rect = pygame.draw.rect

        for n in range(DRAW):
            s = segs[(base_i + n) % N]
            cz = pos - (L if s.index < base_i else 0)
            s.clip = maxy
            dz1 = s.z1 - cz
            dz2 = s.z2 - cz
            s.ok = dz1 > CAM_DEPTH
            if s.ok:
                sc1 = CAM_DEPTH / dz1
                sc2 = CAM_DEPTH / dz2
                s.sc1, s.sc2 = sc1, sc2
                s.sx1 = hw + sc1 * (x - px) * hw
                s.sy1 = hh - sc1 * (s.y1 - cam_y) * hh
                s.sw1 = sc1 * ROAD_W * hw
                s.sx2 = hw + sc2 * (x + dx - px) * hw
                s.sy2 = hh - sc2 * (s.y2 - cam_y) * hh
                s.sw2 = sc2 * ROAD_W * hw
            x += dx
            dx += s.curve

            if not s.ok or s.sy2 >= s.sy1 or s.sy2 >= maxy:
                continue

            x1, y1, w1 = s.sx1, s.sy1, s.sw1
            x2, y2, w2 = s.sx2, s.sy2, s.sw2
            grass, road, rumble = self.fog_cols[s.shade][n]
            r1, r2 = w1 / 8, w2 / 8

            rect(scr, grass, (0, y2, W, y1 - y2 + 1))
            poly(scr, rumble, [(x1 - w1 - r1, y1), (x1 - w1,
                 y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
            poly(scr, rumble, [(x1 + w1 + r1, y1), (x1 + w1,
                 y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            if s.start:
                white, black = self.check_cols[n]
                cols = 10
                for k in range(cols):
                    a, b = k / cols, (k + 1) / cols
                    col = white if (k + s.index) % 2 == 0 else black
                    poly(scr, col, [
                        (x1 - w1 + 2 * w1 * a, y1), (x1 - w1 + 2 * w1 * b, y1),
                        (x2 - w2 + 2 * w2 * b, y2), (x2 - w2 + 2 * w2 * a, y2)])
            else:
                poly(scr, road, [(x1 - w1, y1), (x1 + w1, y1),
                     (x2 + w2, y2), (x2 - w2, y2)])
                # тёмная колея в центре
                if s.shade == 0:
                    poly(scr, (road[0] - 8, road[1] - 8, road[2] - 8),
                         [(x1 - w1 * 0.3, y1), (x1 + w1 * 0.3, y1), (x2 + w2 * 0.3, y2), (x2 - w2 * 0.3, y2)])
            maxy = y1

        # болиды и объекты - от дальних к ближним
        hw = W / 2
        for n in range(DRAW - 1, 0, -1):
            s = segs[(base_i + n) % N]
            if not s.ok:
                continue
            for kind, off in s.sprites:
                src, ww = self.sprite_defs[kind]
                sx = s.sx1 + s.sc1 * off * ROAD_W * hw
                self.blit_scaled(src, sx, s.sy1, s.sc1 * ww * hw, s.clip)
            for car in s.cars:
                sc = s.sc1 + (s.sc2 - s.sc1) * car.percent
                sx = s.sx1 + (s.sx2 - s.sx1) * car.percent + \
                    sc * car.offset * ROAD_W * hw
                sy = s.sy1 + (s.sy2 - s.sy1) * car.percent
                self.blit_scaled(
                    self.car_surfs[car.skin], sx, sy, sc * CAR_W * hw, s.clip)

    def draw_player_car(self):
        pct = self.speed / MAX_SPEED
        bounce = 0.0
        if self.speed > 100:
            bounce = random.uniform(-1, 1) * (1.2 * pct + 3.0 * self.shake)
        dw = (1 / CAM_H) * CAR_W * (W / 2)
        by = H - 26 + bounce
        self.blit_scaled(self.car_surfs[0], W / 2, by, dw, H)

    # ------------------------------------------------------------ HUD
    def txt(self, s, x, y, font, color=WHITE, anchor="topleft"):
        img = font.render(s, True, color)
        r = img.get_rect()
        setattr(r, anchor, (x, y))
        self.screen.blit(font.render(s, True, BLACK), r.move(2, 2))
        self.screen.blit(img, r)

    def gear_rpm(self):
        pct = self.speed / MAX_SPEED
        bounds = [0, 0.10, 0.22, 0.36, 0.50, 0.65, 0.80, 1.0001]
        gear = 1
        for g in range(1, 8):
            if pct >= bounds[g - 1]:
                gear = g
        lo, hi = bounds[gear - 1], bounds[gear]
        rpm = 0.35 + 0.65 * (pct - lo) / (hi - lo)
        if self.state == "grid":
            rpm = max(0.3, self.rev * 0.85)
            gear = 1
        return gear, min(1.0, rpm)

    def draw_lights(self):
        scr = self.screen
        cx, y = W // 2, 92
        pygame.draw.rect(scr, (18, 18, 22), (cx - 150, y -
                         38, 300, 76), border_radius=10)
        pygame.draw.rect(scr, (70, 70, 80), (cx - 150, y -
                         38, 300, 76), 2, border_radius=10)
        for i in range(5):
            lx = cx - 110 + i * 55
            on = self.state == "grid" and i < self.lit
            for dy in (-17, 17):
                pygame.draw.circle(scr, (255, 35, 35) if on else (
                    65, 18, 18), (lx, y + dy), 15)
                if on:
                    pygame.draw.circle(scr, (255, 150, 150),
                                       (lx - 4, y + dy - 4), 4)

    def draw_hud(self):
        scr = self.screen
        order = self.order()
        rank = order.index(self.pcar) + 1
        idx = math.floor(self.pcar.dist / self.L)
        lap = max(1, min(LAPS, idx + 1))

        # позиция и круг
        self.txt(f"P{rank}", 16, 6, self.f_big, (255, 255, 255))
        self.txt(f"/{GRID_SLOTS}", 16 + 112 if rank >=
                 10 else 16 + 88, 36, self.f_mid, (200, 200, 210))
        self.txt(f"КРУГ {lap}/{LAPS}", 16, 70, self.f_sml, (255, 230, 120))

        # табло
        y0 = 100
        leader = order[0]
        for i, c in enumerate(order):
            y = y0 + i * 23
            scr.blit(self.tower_bg, (12, y))
            pygame.draw.rect(scr, c.color, (12, y, 6, 22))
            col = (255, 235, 120) if c.is_player else WHITE
            self.txt(str(i + 1), 24, y + 2, self.f_tiny, col)
            self.txt(c.code, 48, y + 2, self.f_tiny, col)
            if i > 0 and c.fin < 0 and leader.fin < 0:
                gap = (leader.dist - c.dist) / 9000
                self.txt(f"+{gap:.1f}", 172, y + 2, self.f_tiny,
                         (190, 190, 200), "topright")
            elif c.fin >= 0:
                self.txt("FIN", 172, y + 2, self.f_tiny,
                         (120, 230, 120), "topright")

        # времена круга
        cur = self.race_time - self.lap_mark if self.state == "race" else 0.0
        last = self.lap_times[-1] if self.lap_times else None
        self.txt("КРУГ", W - 16, 8, self.f_tiny, (200, 200, 210), "topright")
        self.txt(fmt_time(cur), W - 16, 24, self.f_mid, WHITE, "topright")
        self.txt(f"прошлый  {fmt_time(last)}", W - 16, 62,
                 self.f_sml, (220, 220, 230), "topright")
        self.txt(f"лучший  {fmt_time(self.best_lap)}", W -
                 16, 86, self.f_sml, (200, 120, 255), "topright")

        # обороты (светодиоды)
        gear, rpm = self.gear_rpm()
        lit = int(rpm * 15)
        blink = rpm > 0.94 and (self.frame // 4) % 2 == 0
        for i in range(15):
            lx = W // 2 - 7 * 22 + i * 22
            if i < 5:
                on_c, off_c = (40, 220, 60), (15, 50, 20)
            elif i < 10:
                on_c, off_c = (240, 40, 40), (60, 15, 15)
            else:
                on_c, off_c = (70, 120, 255), (20, 30, 70)
            on = i < lit or (blink and i >= 0)
            pygame.draw.circle(scr, on_c if on else off_c, (lx, 22), 8)
            pygame.draw.circle(scr, (20, 20, 25), (lx, 22), 8, 1)

        # скорость и передача
        kmh = int(self.speed / MAX_SPEED * 335)
        panel = pygame.Surface((190, 120), pygame.SRCALPHA)
        panel.fill((10, 10, 20, 170))
        scr.blit(panel, (W - 206, H - 136))
        self.txt(str(gear) if self.speed > 0 or self.state == "grid" else "N",
                 W - 40, H - 134, self.f_big, (255, 230, 120), "topright")
        self.txt("ПЕРЕД.", W - 190, H - 126, self.f_tiny, (190, 190, 200))
        self.txt(f"{kmh}", W - 70, H - 62, self.f_mid, WHITE, "topright")
        self.txt("км/ч", W - 64, H - 54, self.f_tiny, (190, 190, 200))
        keys = pygame.key.get_pressed()
        gas = keys[pygame.K_UP] or keys[pygame.K_w]
        brk = keys[pygame.K_DOWN] or keys[pygame.K_s]
        pygame.draw.rect(scr, (60, 200, 80) if gas else (
            25, 60, 30), (W - 196, H - 40, 80, 8))
        pygame.draw.rect(scr, (230, 60, 60) if brk else (
            70, 25, 25), (W - 108, H - 40, 80, 8))

        # огни на старте и надписи
        if self.state == "grid":
            self.draw_lights()
            self.txt("Держи газ и жди, пока погаснут огни",
                     W // 2, 150, self.f_sml, WHITE, "midtop")
            self.txt("↑ газ   ↓ тормоз   ← → руль   R - заново", W //
                     2, H - 24, self.f_tiny, (230, 230, 240), "midbottom")
        elif self.go_t > 0 and self.state == "race":
            self.txt("ПОЕХАЛИ!", W // 2, 90, self.f_big,
                     (90, 255, 120), "center")

    def draw_finish(self):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        self.screen.blit(veil, (0, 0))
        cx = W // 2
        self.txt("ФИНИШ!", cx, 70, self.f_big, (255, 230, 120), "midtop")
        medal = {1: (255, 215, 0), 2: (210, 210, 220), 3: (
            205, 130, 60)}.get(self.final_rank, WHITE)
        self.txt(f"Место: P{self.final_rank} из {
                 GRID_SLOTS}", cx, 160, self.f_mid, medal, "midtop")
        total = sum(self.lap_times)
        self.txt(f"Время гонки: {fmt_time(total)}",
                 cx, 210, self.f_sml, WHITE, "midtop")
        for i, t in enumerate(self.lap_times):
            col = (200, 120, 255) if t == self.best_lap else WHITE
            self.txt(f"Круг {i + 1}:  {fmt_time(t)}", cx,
                     250 + i * 30, self.f_sml, col, "midtop")
        self.txt("R - новая гонка     Esc - выход", cx,
                 H - 70, self.f_sml, WHITE, "midtop")

    def draw(self):
        self.draw_background()
        self.render_road()
        self.draw_player_car()
        self.draw_hud()
        if self.state == "finished" and self.fin_t > 2.0:
            self.draw_finish()
        pygame.display.flip()

    # ------------------------------------------------------------ цикл
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    elif event.key == pygame.K_r:
                        self.reset()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
