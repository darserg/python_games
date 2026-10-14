"""
Цивилизация 2D - пошаговая стратегия на Pygame.

Ты играешь за Русов против трёх компьютерных цивилизаций. Основывай города,
развивай экономику, исследуй технологии, строй армию и захвати все чужие города.

Управление:
  ЛКМ по карте        - выбрать юнит / город (повторный клик перебирает объекты в клетке)
  ПКМ по карте        - приказ выбранному юниту: идти или атаковать
  Колесо мыши         - масштаб карты;  СКМ (зажать) - перетаскивание карты
  WASD / стрелки      - прокрутка карты;  клик по миникарте - перейти в точку
  B  - основать город (Поселенец)     F - укрепиться (охранять)
  S  - пропустить ход юнитом          Delete - распустить юнит
  T  - дерево технологий              C - центрировать на выбранном
  Tab - следующий юнит                H - справка
  Пробел / Enter      - "Следующий юнит" / "Конец хода"
  R   - новая игра (после победы или поражения)    Esc - закрыть окно / выйти

Запуск:
  pip install pygame
  python civ2d.py
"""

import heapq
import math
import random
import sys

import pygame

# ============================================================== настройки
MAP_W, MAP_H = 60, 40
NUM_AI = 3
WIN_W, WIN_H = 1200, 720
TOP_H = 34
PANEL_W = 300
MAP_VIEW_W = WIN_W - PANEL_W
MM_W, MM_H = 280, 187
HUMAN = 0
FPS = 60

DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

WATER, GRASS, PLAINS, FOREST, HILLS, DESERT, MOUNTAIN = range(7)

TERRAIN = {
    WATER: dict(name="Вода", col=(48, 98, 172), f=1, p=0, g=1, move=99, dfn=0.0, ok=False),
    GRASS: dict(name="Луга", col=(96, 164, 74), f=2, p=0, g=0, move=1, dfn=0.0, ok=True),
    PLAINS: dict(name="Равнина", col=(172, 172, 92), f=1, p=1, g=0, move=1, dfn=0.0, ok=True),
    FOREST: dict(name="Лес", col=(44, 112, 58), f=1, p=2, g=0, move=2, dfn=0.25, ok=True),
    HILLS: dict(name="Холмы", col=(142, 122, 82), f=0, p=2, g=0, move=2, dfn=0.5, ok=True),
    DESERT: dict(name="Пустыня", col=(216, 196, 132), f=0, p=0, g=0, move=1, dfn=0.0, ok=True),
    MOUNTAIN: dict(name="Горы", col=(118, 118, 126), f=0, p=0, g=0, move=99, dfn=0.0, ok=False),
}

RESOURCES = {
    "wheat": dict(name="Пшеница", col=(250, 225, 70), f=2, p=0, g=0, on=(GRASS, PLAINS)),
    "horses": dict(name="Лошади", col=(205, 150, 100), f=1, p=1, g=0, on=(PLAINS, GRASS)),
    "iron": dict(name="Железо", col=(170, 170, 200), f=0, p=2, g=0, on=(HILLS,)),
    "stone": dict(name="Камень", col=(225, 225, 225), f=0, p=1, g=0, on=(HILLS, PLAINS)),
    "gold": dict(name="Золото", col=(255, 215, 0), f=0, p=0, g=3, on=(HILLS, DESERT, PLAINS)),
    "fish": dict(name="Рыба", col=(130, 210, 235), f=2, p=0, g=0, on=(WATER,)),
    "deer": dict(name="Олени", col=(170, 105, 60), f=1, p=1, g=0, on=(FOREST,)),
}


def U(name, ch, cost, atk, dfn, rng, move, tech, civ=False):
    return dict(kind="unit", name=name, ch=ch, cost=cost, atk=atk, dfn=dfn, rng=rng,
                move=move, tech=tech, civ=civ)


def B(name, cost, tech, upkeep, desc):
    return dict(kind="bld", name=name, cost=cost, tech=tech, upkeep=upkeep, desc=desc)


ITEMS = {
    "settler": U("Поселенец", "П", 30, 0, 1, 0, 2, None, True),
    "warrior": U("Воин", "В", 15, 8, 8, 0, 2, None),
    "spearman": U("Копейщик", "К", 25, 11, 14, 0, 2, "bronze"),
    "archer": U("Лучник", "Л", 25, 12, 6, 2, 2, "archery"),
    "horseman": U("Всадник", "Г", 35, 15, 9, 0, 4, "horse"),
    "swordsman": U("Мечник", "М", 40, 20, 16, 0, 2, "iron"),
    "catapult": U("Катапульта", "Т", 50, 20, 5, 2, 1, "math"),
    "musketman": U("Мушкетёр", "Р", 70, 30, 30, 0, 2, "gunpowder"),
    "granary": B("Амбар", 40, "pottery", 1, "+2 еды"),
    "library": B("Библиотека", 60, "writing", 1, "+3 науки"),
    "walls": B("Стены", 50, "masonry", 0, "+50% к защите города"),
    "market": B("Рынок", 70, "currency", 0, "+3 золота"),
    "workshop": B("Мастерская", 80, "engineering", 1, "+3 производства"),
    "university": B("Университет", 120, "education", 2, "+5 науки"),
}

TECHS = {
    "bronze": ("Бронзовое литьё", 25, ()),
    "archery": ("Стрельба из лука", 25, ()),
    "pottery": ("Гончарное дело", 25, ()),
    "masonry": ("Каменная кладка", 30, ()),
    "horse": ("Верховая езда", 35, ()),
    "writing": ("Письменность", 40, ("pottery",)),
    "currency": ("Деньги", 50, ("bronze",)),
    "iron": ("Обработка железа", 60, ("bronze",)),
    "math": ("Математика", 70, ("masonry", "archery")),
    "engineering": ("Инженерное дело", 90, ("math", "currency")),
    "education": ("Образование", 100, ("writing", "currency")),
    "gunpowder": ("Порох", 130, ("iron", "engineering")),
}

CIV_DEFS = [
    ("Русы", (70, 130, 235),
     ["Москва", "Киев", "Новгород", "Псков", "Тверь", "Суздаль", "Владимир", "Рязань", "Смоленск", "Ростов"]),
    ("Римляне", (215, 55, 55),
     ["Рим", "Милан", "Неаполь", "Капуя", "Равенна", "Тарент", "Пиза", "Верона", "Анкона", "Генуя"]),
    ("Египтяне", (235, 195, 45),
     ["Мемфис", "Фивы", "Гиза", "Луксор", "Асуан", "Танис", "Бубастис", "Абидос", "Саис", "Коптос"]),
    ("Китайцы", (165, 80, 205),
     ["Чанъань", "Лоян", "Ханчжоу", "Ухань", "Сучжоу", "Нанкин", "Чэнду", "Ся", "Цзинань", "Тайюань"]),
]


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def clamp(v, a, b):
    return max(a, min(b, v))


# ============================================================== сущности
class Unit:
    _next = 1

    def __init__(self, owner, kind, x, y):
        self.id = Unit._next
        Unit._next += 1
        self.owner, self.kind, self.x, self.y = owner, kind, x, y
        self.hp = 100.0
        self.moves = ITEMS[kind]["move"]
        self.fortified = False
        self.skip = False
        self.path = []
        self.target = None      # цель атаки (x, y)
        self.site = None        # место будущего города (для ИИ)
        self.rested = True
        self.alive = True

    @property
    def spec(self):
        return ITEMS[self.kind]

    @property
    def civilian(self):
        return self.spec.get("civ", False)


class City:
    def __init__(self, cid, owner, name, x, y):
        self.id, self.owner, self.name, self.x, self.y = cid, owner, name, x, y
        self.pop = 1
        self.food = 0.0
        self.stock = 0.0
        self.current = None
        self.buildings = set()
        self.worked = []
        self.capital = False


class Civ:
    def __init__(self, cid, name, color, human, names):
        self.id, self.name, self.color, self.human = cid, name, color, human
        self.names = list(names)
        self.gold = 20.0
        self.bulbs = 0.0
        self.techs = set()
        self.researching = None
        self.alive = True
        self.cities = []
        self.units = []
        self.explored = None
        self.visible = None
        self.last_gold = 0.0
        self.last_sci = 0.0


# ============================================================== мир
class World:
    def __init__(self, seed=None, num_ai=NUM_AI):
        self.rng = random.Random(seed)
        self.w, self.h = MAP_W, MAP_H
        self.msgs = []
        self.turn = 1
        self.winner = None          # HUMAN - победа, -1 - поражение
        self.cities = {}
        self.units_at = {}
        self.next_city_id = 1
        self.generate_map()
        self.owner = [[-1] * self.w for _ in range(self.h)]
        self.civs = []
        self.setup_civs(num_ai)
        self.ais = {c.id: AI(self, c) for c in self.civs if not c.human}
        self.assign_tiles()

    # --- сообщения
    def note(self, text, ids, color=(235, 235, 240)):
        if HUMAN in ids:
            self.msgs.append((self.turn, text, color))
            self.msgs = self.msgs[-40:]

    # --- генерация карты
    def noise_field(self, layers):
        w, h = self.w, self.h
        out = [[0.0] * w for _ in range(h)]
        for scale, weight in layers:
            gw, gh = w // scale + 3, h // scale + 3
            grid = [[self.rng.random() for _ in range(gw)] for _ in range(gh)]
            for y in range(h):
                gy = y / scale
                y0 = int(gy)
                fy = gy - y0
                fy = fy * fy * (3 - 2 * fy)
                for x in range(w):
                    gx = x / scale
                    x0 = int(gx)
                    fx = gx - x0
                    fx = fx * fx * (3 - 2 * fx)
                    a = grid[y0][x0] * (1 - fx) + grid[y0][x0 + 1] * fx
                    b = grid[y0 + 1][x0] * (1 - fx) + grid[y0 + 1][x0 + 1] * fx
                    out[y][x] += weight * (a * (1 - fy) + b * fy)
        return out

    def is_land(self, x, y):
        return self.terr[y][x] not in (WATER, MOUNTAIN)

    def inb(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def land_components(self):
        seen = set()
        comps = []
        for y in range(self.h):
            for x in range(self.w):
                if (x, y) in seen or not self.is_land(x, y):
                    continue
                comp = []
                stack = [(x, y)]
                seen.add((x, y))
                while stack:
                    cx, cy = stack.pop()
                    comp.append((cx, cy))
                    for dx, dy in DIRS8:
                        nx, ny = cx + dx, cy + dy
                        if self.inb(nx, ny) and (nx, ny) not in seen and self.is_land(nx, ny):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
                comps.append(comp)
        return comps

    def generate_map(self):
        w, h, rng = self.w, self.h, self.rng
        best = None
        for _ in range(60):
            e = self.noise_field([(12, 0.55), (6, 0.30), (3, 0.15)])
            for y in range(h):
                for x in range(w):
                    edge = min(1.0, min(x, y, w - 1 - x, h - 1 - y) / (min(w, h) * 0.2))
                    e[y][x] *= 0.35 + 0.65 * edge ** 0.7
            flat = sorted(v for row in e for v in row)
            water_t = flat[int(0.40 * len(flat))]
            hills_t = flat[int(0.80 * len(flat))]
            mount_t = flat[int(0.94 * len(flat))]
            m = self.noise_field([(8, 0.6), (4, 0.4)])
            terr = [[WATER] * w for _ in range(h)]
            for y in range(h):
                for x in range(w):
                    v = e[y][x]
                    if v < water_t:
                        t = WATER
                    elif v > mount_t:
                        t = MOUNTAIN
                    elif v > hills_t:
                        t = HILLS
                    else:
                        mm = m[y][x]
                        if mm < 0.30:
                            t = DESERT
                        elif mm > 0.62:
                            t = FOREST
                        elif mm > 0.45:
                            t = GRASS
                        else:
                            t = PLAINS
                    terr[y][x] = t
            self.terr = terr
            comps = self.land_components()
            biggest = max(comps, key=len) if comps else []
            if best is None or len(biggest) > len(best[1]):
                best = (terr, biggest)
            if len(biggest) >= 420:
                break
        self.terr, self.main_land = best
        self.res = [[None] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if rng.random() < 0.09:
                    t = self.terr[y][x]
                    opts = [k for k, r in RESOURCES.items() if t in r["on"]]
                    if opts:
                        self.res[y][x] = rng.choice(opts)

    def land_around(self, x, y):
        n = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                if self.inb(nx, ny) and self.is_land(nx, ny):
                    n += 1
        return n

    def pick_starts(self, n):
        cand = [(x, y) for (x, y) in self.main_land
                if self.terr[y][x] in (GRASS, PLAINS) and self.land_around(x, y) >= 15]
        if len(cand) < n:
            cand = [(x, y) for (x, y) in self.main_land if self.terr[y][x] in (GRASS, PLAINS, FOREST, HILLS)]
        starts = [self.rng.choice(cand)]
        for _ in range(n - 1):
            sample = self.rng.sample(cand, min(400, len(cand)))
            starts.append(max(sample, key=lambda c: min(cheb(c, s) for s in starts)))
        return starts

    def setup_civs(self, num_ai):
        n = 1 + num_ai
        starts = self.pick_starts(n)
        for i in range(n):
            name, color, names = CIV_DEFS[i]
            civ = Civ(i, name, color, i == HUMAN, names)
            civ.explored = [[False] * self.w for _ in range(self.h)]
            civ.visible = [[False] * self.w for _ in range(self.h)]
            self.civs.append(civ)
            sx, sy = starts[i]
            self.add_unit(i, "settler", sx, sy)
            self.add_unit(i, "warrior", sx, sy)
        self.update_vision(self.civs[HUMAN])

    # --- юниты
    def add_unit(self, owner, kind, x, y):
        u = Unit(owner, kind, x, y)
        self.civs[owner].units.append(u)
        self.units_at.setdefault((x, y), []).append(u)
        return u

    def remove_unit(self, u):
        if not u.alive:
            return
        u.alive = False
        lst = self.units_at.get((u.x, u.y))
        if lst and u in lst:
            lst.remove(u)
            if not lst:
                del self.units_at[(u.x, u.y)]
        civ = self.civs[u.owner]
        if u in civ.units:
            civ.units.remove(u)
        self.check_alive(civ)

    def move_unit(self, u, x, y):
        lst = self.units_at.get((u.x, u.y))
        if lst and u in lst:
            lst.remove(u)
            if not lst:
                del self.units_at[(u.x, u.y)]
        u.x, u.y = x, y
        self.units_at.setdefault((x, y), []).append(u)
        u.moves = max(0, u.moves - TERRAIN[self.terr[y][x]]["move"])
        u.fortified = False
        u.rested = False

    def can_enter(self, u, x, y):
        if not TERRAIN[self.terr[y][x]]["ok"]:
            return False
        stack = self.units_at.get((x, y), [])
        for o in stack:
            if o.owner != u.owner:
                return False
        city = self.cities.get((x, y))
        if city and city.owner != u.owner:
            return False
        if u.civilian:
            return not any(o.civilian for o in stack)
        mil = sum(1 for o in stack if not o.civilian)
        return mil < (4 if city else 1)

    def passable_for(self, civ_id, x, y):
        for o in self.units_at.get((x, y), []):
            if o.owner != civ_id:
                return False
        city = self.cities.get((x, y))
        return not (city and city.owner != civ_id)

    def find_path(self, civ_id, start, goal):
        if start == goal:
            return []
        gx, gy = goal
        if not self.inb(gx, gy):
            return None
        dist = {start: 0.0}
        prev = {}
        pq = [(0.0, 0.0, start)]
        found = False
        while pq:
            _, d, cur = heapq.heappop(pq)
            if cur == goal:
                found = True
                break
            if d > dist.get(cur, 1e9):
                continue
            for dx, dy in DIRS8:
                nx, ny = cur[0] + dx, cur[1] + dy
                if not self.inb(nx, ny):
                    continue
                T = TERRAIN[self.terr[ny][nx]]
                if not T["ok"]:
                    continue
                nxt = (nx, ny)
                if nxt != goal and not self.passable_for(civ_id, nx, ny):
                    continue
                nd = d + T["move"] + (0.001 if dx and dy else 0)
                if nd < dist.get(nxt, 1e9):
                    dist[nxt] = nd
                    prev[nxt] = cur
                    h = max(abs(nx - gx), abs(ny - gy))
                    heapq.heappush(pq, (nd + h, nd, nxt))
        if not found:
            return None
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    def order_goto(self, u, tx, ty):
        u.target = None
        u.fortified = False
        u.skip = False
        path = self.find_path(u.owner, (u.x, u.y), (tx, ty))
        if path is None:
            return False
        u.path = path
        self.advance(u)
        return True

    def order_attack(self, u, tx, ty):
        spec = u.spec
        rng = max(1, spec["rng"])
        u.fortified = False
        u.skip = False
        if cheb((u.x, u.y), (tx, ty)) <= rng:
            u.path = []
            return self.attack(u, tx, ty)
        path = self.find_path(u.owner, (u.x, u.y), (tx, ty))
        if path is None:
            return False
        trimmed = []
        for p in path:
            trimmed.append(p)
            if cheb(p, (tx, ty)) <= rng:
                break
        u.path = trimmed
        u.target = (tx, ty)
        self.advance(u)
        return True

    def advance(self, u):
        while u.alive and u.moves > 0 and u.path:
            nx, ny = u.path[0]
            city = self.cities.get((nx, ny))
            if (city and city.owner != u.owner and not self.units_at.get((nx, ny))
                    and not u.civilian and u.spec["rng"] == 0):
                u.path = []
                self.attack(u, nx, ny)      # захват пустого города
                break
            if not self.can_enter(u, nx, ny):
                u.path = []
                break
            self.move_unit(u, nx, ny)
            u.path.pop(0)
        if u.alive and u.target and u.moves > 0 and not u.path:
            tx, ty = u.target
            u.target = None
            self.attack(u, tx, ty)
        if u.alive and u.owner == HUMAN:
            self.update_vision(self.civs[HUMAN])

    # --- бой
    def best_defender(self, x, y):
        stack = self.units_at.get((x, y), [])
        mil = [u for u in stack if not u.civilian]
        if mil:
            return max(mil, key=lambda d: self.defense_strength(d, x, y))
        civs = [u for u in stack if u.civilian]
        return civs[0] if civs else None

    def defense_strength(self, d, x, y):
        mod = 1.0 + TERRAIN[self.terr[y][x]]["dfn"]
        if d.fortified:
            mod += 0.25
        city = self.cities.get((x, y))
        if city and city.owner == d.owner:
            mod += 0.25
            if "walls" in city.buildings:
                mod += 0.5
        return d.spec["dfn"] * mod * (0.5 + 0.5 * d.hp / 100)

    def attack_strength(self, u, vs_city):
        base = u.spec["atk"]
        if u.kind == "catapult" and vs_city:
            base *= 1.5
        return base * (0.5 + 0.5 * u.hp / 100)

    def damage(self, a, d):
        return 30 * math.exp(0.04 * (a - d)) * self.rng.uniform(0.85, 1.15)

    def attack(self, u, tx, ty):
        spec = u.spec
        if u.civilian or spec["atk"] <= 0 or u.moves <= 0:
            return False
        ranged = spec["rng"] > 0
        if cheb((u.x, u.y), (tx, ty)) > max(1, spec["rng"]):
            return False
        d = self.best_defender(tx, ty)
        city = self.cities.get((tx, ty))
        if d is None or d.owner == u.owner:
            if (city and city.owner != u.owner and not ranged
                    and cheb((u.x, u.y), (tx, ty)) == 1):
                self.capture_city(city, u.owner)
                self.move_unit(u, tx, ty)
                u.moves = 0
                return True
            return False

        a = self.attack_strength(u, city is not None)
        u.rested = False
        d.rested = False
        victim_owner = d.owner
        if d.civilian:
            dealt = 999.0
            dfn = 0.0
        else:
            dfn = self.defense_strength(d, tx, ty)
            dealt = self.damage(a, dfn)
        d.hp -= dealt
        killed = d.hp <= 0
        names = (u.owner, victim_owner)
        if killed:
            self.note(f"{self.civs[u.owner].name}: {spec['name']} уничтожает {d.spec['name']} ({self.civs[victim_owner].name})",
                      names, (255, 170, 120) if u.owner == HUMAN else (255, 110, 110))
            self.remove_unit(d)
        elif not ranged:
            u.hp -= self.damage(dfn, a)
            if u.hp <= 0:
                self.note(f"{self.civs[u.owner].name}: {spec['name']} погибает в бою", names, (255, 110, 110))
                self.remove_unit(u)
        if u.alive:
            u.moves = 0
            u.path = []
            u.target = None
            u.fortified = False
        if killed and u.alive and not ranged:
            rest = self.units_at.get((tx, ty), [])
            if not any(not o.civilian for o in rest):
                for o in list(rest):
                    self.remove_unit(o)
                if city and city.owner != u.owner:
                    self.capture_city(city, u.owner)
                if TERRAIN[self.terr[ty][tx]]["ok"] and self.can_enter(u, tx, ty):
                    self.move_unit(u, tx, ty)
                    u.moves = 0
        if u.owner == HUMAN or victim_owner == HUMAN:
            self.update_vision(self.civs[HUMAN])
        return True

    # --- города
    def can_found(self, x, y, civ_id):
        if not self.inb(x, y) or not self.is_land(x, y):
            return False
        if self.owner[y][x] not in (-1, civ_id):
            return False
        for (cx, cy) in self.cities:
            if cheb((x, y), (cx, cy)) < 3:
                return False
        return True

    def found_city(self, u):
        if u.kind != "settler" or not self.can_found(u.x, u.y, u.owner):
            return None
        civ = self.civs[u.owner]
        name = civ.names.pop(0) if civ.names else f"{civ.name} {len(civ.cities) + 1}"
        city = City(self.next_city_id, u.owner, name, u.x, u.y)
        self.next_city_id += 1
        city.capital = not civ.cities
        civ.cities.append(city)
        self.cities[(u.x, u.y)] = city
        self.remove_unit(u)
        self.recompute_territory()
        self.assign_tiles()
        self.note(f"Основан город {name}", (u.owner,), (150, 255, 170))
        self.update_vision(self.civs[HUMAN])
        return city

    def capture_city(self, city, new_owner):
        old = self.civs[city.owner]
        new = self.civs[new_owner]
        old.cities.remove(city)
        for o in list(self.units_at.get((city.x, city.y), [])):
            if o.owner != new_owner:
                self.remove_unit(o)
        was_cap = city.capital
        city.owner = new_owner
        new.cities.append(city)
        city.capital = False
        city.pop = max(1, city.pop - 1)
        city.current = None
        city.stock = 0.0
        city.buildings = {b for b in city.buildings if self.rng.random() > 0.35}
        if was_cap and old.cities:
            max(old.cities, key=lambda c: c.pop).capital = True
        if not new.cities[:-1]:
            city.capital = True
        self.recompute_territory()
        self.assign_tiles()
        self.note(f"{new.name} захватывают город {city.name} ({old.name})", (new_owner, old.id),
                  (255, 220, 90))
        self.check_alive(old)
        self.update_vision(self.civs[HUMAN])

    def check_alive(self, civ):
        if not civ.alive:
            return
        if civ.cities or any(u.civilian for u in civ.units):
            return
        civ.alive = False
        for u in list(civ.units):
            u.alive = False
            lst = self.units_at.get((u.x, u.y))
            if lst and u in lst:
                lst.remove(u)
                if not lst:
                    del self.units_at[(u.x, u.y)]
        civ.units = []
        self.note(f"Цивилизация {civ.name} уничтожена!", (HUMAN,), (255, 120, 120))
        alive = [c for c in self.civs if c.alive]
        if not self.civs[HUMAN].alive:
            self.winner = -1
        elif len(alive) == 1:
            self.winner = HUMAN

    def recompute_territory(self):
        self.owner = [[-1] * self.w for _ in range(self.h)]
        for c in sorted(self.cities.values(), key=lambda c: c.id):
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if abs(dx) == 2 and abs(dy) == 2:
                        continue
                    x, y = c.x + dx, c.y + dy
                    if self.inb(x, y) and self.owner[y][x] == -1:
                        self.owner[y][x] = c.owner

    def tile_yield(self, x, y):
        T = TERRAIN[self.terr[y][x]]
        f, p, g = T["f"], T["p"], T["g"]
        r = self.res[y][x]
        if r:
            R = RESOURCES[r]
            f += R["f"]
            p += R["p"]
            g += R["g"]
        return f, p, g

    def assign_tiles(self):
        taken = set()
        for c in sorted(self.cities.values(), key=lambda c: c.id):
            taken.add((c.x, c.y))
        for c in sorted(self.cities.values(), key=lambda c: c.id):
            cands = []
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if (dx == 0 and dy == 0) or (abs(dx) == 2 and abs(dy) == 2):
                        continue
                    x, y = c.x + dx, c.y + dy
                    if not self.inb(x, y) or (x, y) in taken or self.owner[y][x] != c.owner:
                        continue
                    if any(o.owner != c.owner for o in self.units_at.get((x, y), [])):
                        continue
                    f, p, g = self.tile_yield(x, y)
                    score = f * 2.0 + p * 1.5 + g
                    if score > 0:
                        cands.append((score, x, y))
            cands.sort(reverse=True)
            c.worked = [(x, y) for _, x, y in cands[:c.pop]]
            taken.update(c.worked)

    def city_yields(self, c):
        f, p, g = self.tile_yield(c.x, c.y)
        f, p, g = max(f, 2), max(p, 1), max(g, 1)
        for (x, y) in c.worked:
            a, b, d = self.tile_yield(x, y)
            f, p, g = f + a, p + b, g + d
        sci = 1 + 0.7 * c.pop
        if c.capital:
            p += 1
            g += 2
            sci += 2
        B_ = c.buildings
        if "granary" in B_:
            f += 2
        if "library" in B_:
            sci += 3
        if "university" in B_:
            sci += 5
        if "market" in B_:
            g += 3
        if "workshop" in B_:
            p += 3
        upkeep = sum(ITEMS[b]["upkeep"] for b in B_)
        return dict(food=f, prod=p, gold=g, sci=sci, upkeep=upkeep)

    @staticmethod
    def growth_thr(pop):
        return 14 + 6 * (pop - 1)

    def available_items(self, civ, city):
        out = []
        for k, s in ITEMS.items():
            if s["tech"] and s["tech"] not in civ.techs:
                continue
            if s["kind"] == "bld" and k in city.buildings:
                continue
            out.append(k)
        return out

    def available_techs(self, civ):
        return [k for k, (_, _, pre) in TECHS.items()
                if k not in civ.techs and all(p in civ.techs for p in pre)]

    def buy_cost(self, c):
        spec = ITEMS[c.current]
        rem = max(0.0, spec["cost"] - c.stock)
        cost = 2 * rem + rem * rem / 20
        if c.stock == 0:
            cost *= 2
        return int(math.ceil(cost))

    def can_complete(self, c):
        if not c.current:
            return False
        spec = ITEMS[c.current]
        if spec["kind"] == "unit":
            if c.current == "settler" and c.pop < 2:
                return False
            stack = self.units_at.get((c.x, c.y), [])
            if spec.get("civ"):
                return not any(u.civilian for u in stack)
            return sum(1 for u in stack if not u.civilian) < 4
        return True

    def buy(self, c):
        civ = self.civs[c.owner]
        if not c.current or not self.can_complete(c):
            return False
        cost = self.buy_cost(c)
        if cost > civ.gold:
            return False
        civ.gold -= cost
        c.stock = max(c.stock, ITEMS[c.current]["cost"])
        self.try_complete(c)
        return True

    def try_complete(self, c):
        it = c.current
        if not it:
            return
        spec = ITEMS[it]
        if c.stock < spec["cost"] or not self.can_complete(c):
            return
        civ = self.civs[c.owner]
        c.stock -= spec["cost"]
        if spec["kind"] == "unit":
            if it == "settler":
                c.pop -= 1
            self.add_unit(c.owner, it, c.x, c.y)
            self.note(f"{c.name}: готов юнит - {spec['name']}", (c.owner,), (200, 230, 255))
            if not civ.human or it == "settler":
                c.current = None
        else:
            c.buildings.add(it)
            c.current = None
            self.note(f"{c.name}: построено - {spec['name']}", (c.owner,), (200, 230, 255))

    # --- экономика и ход
    def economy(self, civ):
        total_sci = 0.0
        net_gold = 0.0
        for c in list(civ.cities):
            y = self.city_yields(c)
            total_sci += y["sci"]
            net_gold += y["gold"] - y["upkeep"]
            c.food += y["food"] - 2 * c.pop
            thr = self.growth_thr(c.pop)
            if c.food >= thr:
                c.food -= thr
                c.pop += 1
                self.note(f"{c.name} растёт: население {c.pop}", (civ.id,), (190, 255, 190))
            elif c.food < 0:
                c.food = 0
                if c.pop > 1:
                    c.pop -= 1
                    self.note(f"{c.name}: голод, население уменьшилось", (civ.id,), (255, 150, 120))
            c.stock += y["prod"]
            self.try_complete(c)
        civ.gold += net_gold
        civ.last_gold = net_gold
        civ.last_sci = total_sci
        if civ.gold < 0:
            civ.gold = 0
            blds = [(c, b) for c in civ.cities for b in c.buildings if ITEMS[b]["upkeep"] > 0]
            if blds:
                c, b = self.rng.choice(blds)
                c.buildings.discard(b)
                self.note(f"Не хватает золота: {c.name} продаёт {ITEMS[b]['name']}", (civ.id,), (255, 150, 120))
        civ.bulbs += total_sci
        if civ.researching:
            name, cost, _ = TECHS[civ.researching]
            if civ.bulbs >= cost:
                civ.bulbs -= cost
                civ.techs.add(civ.researching)
                self.note(f"Изучена технология: {name}", (civ.id,), (255, 235, 130))
                civ.researching = None

    def start_turn_units(self, civ):
        for u in civ.units:
            u.moves = u.spec["move"]
            u.skip = False
            if u.rested and u.hp < 100:
                heal = 10 + (10 if (u.x, u.y) in self.cities else 0) + (5 if u.fortified else 0)
                u.hp = min(100.0, u.hp + heal)
            u.rested = True
        if civ.human:
            for u in list(civ.units):
                if u.path or u.target:
                    self.advance(u)

    def end_turn(self):
        for cid, ai in self.ais.items():
            civ = self.civs[cid]
            if civ.alive:
                ai.take_turn()
        for civ in self.civs:
            if civ.alive:
                self.economy(civ)
        self.assign_tiles()
        self.turn += 1
        for civ in self.civs:
            if civ.alive:
                self.start_turn_units(civ)
        self.update_vision(self.civs[HUMAN])

    def update_vision(self, civ):
        if not civ.human:
            return
        vis = [[False] * self.w for _ in range(self.h)]
        sources = [(u.x, u.y, 3 if u.kind == "horseman" else 2) for u in civ.units]
        sources += [(c.x, c.y, 3) for c in civ.cities]
        for sx, sy, r in sources:
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x, y = sx + dx, sy + dy
                    if 0 <= x < self.w and 0 <= y < self.h:
                        vis[y][x] = True
        civ.visible = vis
        for y in range(self.h):
            row, ex = vis[y], civ.explored[y]
            for x in range(self.w):
                if row[x]:
                    ex[x] = True


# ============================================================== искусственный интеллект
class AI:
    def __init__(self, world, civ):
        self.w = world
        self.civ = civ
        self.attacking = False
        self.no_site_until = 0
        self.cache = {}

    def take_turn(self):
        self.cache = {}
        self.pick_research()
        self.manage_cities()
        self.manage_settlers()
        self.manage_military()
        self.spend_gold()

    def pick_research(self):
        w, civ = self.w, self.civ
        if civ.researching:
            return
        av = w.available_techs(civ)
        if av:
            av.sort(key=lambda k: TECHS[k][1])
            civ.researching = w.rng.choice(av[:3])

    # --- города
    def defenders(self, c):
        return sum(1 for u in self.w.units_at.get((c.x, c.y), [])
                   if u.owner == self.civ.id and not u.civilian)

    def need_defenders(self):
        return 1 if self.w.turn < 60 else 2

    def pick_unit(self, kinds, key):
        if not kinds:
            return "warrior"
        weights = [max(0.1, key(ITEMS[k]) / ITEMS[k]["cost"]) for k in kinds]
        return self.w.rng.choices(kinds, weights)[0]

    def choose_build(self, c):
        w, civ = self.w, self.civ
        avail = w.available_items(civ, c)
        units = [k for k in avail if ITEMS[k]["kind"] == "unit" and not ITEMS[k].get("civ")]
        blds = [k for k in avail if ITEMS[k]["kind"] == "bld"]
        if self.defenders(c) < self.need_defenders():
            melee = [k for k in units if ITEMS[k]["rng"] == 0]
            return self.pick_unit(melee, lambda s: s["dfn"] ** 2)
        settlers = sum(1 for u in civ.units if u.kind == "settler")
        in_prod = sum(1 for cc in civ.cities if cc.current == "settler")
        max_cities = min(9, 3 + w.turn // 20)
        if (len(civ.cities) + settlers + in_prod < max_cities and c.pop >= 2
                and w.turn >= self.no_site_until):
            return "settler"
        mil = sum(1 for u in civ.units if not u.civilian)
        if blds and (w.rng.random() < 0.6 or mil >= len(civ.cities) * 3 + w.turn // 12):
            return w.rng.choice(blds)
        return self.pick_unit(units, lambda s: max(s["atk"], s["dfn"] * 0.7))

    def manage_cities(self):
        for c in self.civ.cities:
            if c.current is None:
                c.current = self.choose_build(c)
            elif self.defenders(c) == 0 and ITEMS[c.current]["kind"] == "bld":
                c.current = self.choose_build(c)

    def spend_gold(self):
        w, civ = self.w, self.civ
        if civ.gold < 90:
            return
        opts = [c for c in civ.cities if c.current and w.can_complete(c)]
        opts.sort(key=lambda c: (self.defenders(c), w.buy_cost(c)))
        for c in opts:
            if w.buy_cost(c) <= civ.gold - 30:
                w.buy(c)
                break

    # --- поселенцы
    def site_score(self, x, y):
        key = (x, y)
        if key in self.cache:
            return self.cache[key]
        w = self.w
        s = 0.0
        coast = False
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if abs(dx) == 2 and abs(dy) == 2:
                    continue
                nx, ny = x + dx, y + dy
                if not w.inb(nx, ny):
                    continue
                f, p, g = w.tile_yield(nx, ny)
                s += f * 2 + p * 1.5 + g
                if w.terr[ny][nx] == WATER and abs(dx) <= 1 and abs(dy) <= 1:
                    coast = True
        if coast:
            s += 4
        self.cache[key] = s
        return s

    def find_site(self, u):
        w = self.w
        cands = []
        for dy in range(-14, 15):
            for dx in range(-14, 15):
                x, y = u.x + dx, u.y + dy
                if not w.inb(x, y) or not w.can_found(x, y, self.civ.id):
                    continue
                if not w.passable_for(self.civ.id, x, y):
                    continue
                d = max(abs(dx), abs(dy))
                cands.append((self.site_score(x, y) - 0.8 * d, x, y))
        cands.sort(reverse=True)
        for _, x, y in cands[:5]:
            if w.find_path(self.civ.id, (u.x, u.y), (x, y)) is not None:
                return (x, y)
        return None

    def manage_settlers(self):
        w, civ = self.w, self.civ
        for u in list(civ.units):
            if u.kind != "settler" or not u.alive:
                continue
            if u.site is None or not w.can_found(u.site[0], u.site[1], civ.id):
                u.site = self.find_site(u)
            if u.site is None:
                self.no_site_until = w.turn + 10
                if w.can_found(u.x, u.y, civ.id):
                    w.found_city(u)
                continue
            if (u.x, u.y) != u.site and u.moves > 0:
                w.order_goto(u, *u.site)
            if u.alive and (u.x, u.y) == u.site:
                w.found_city(u)

    # --- армия
    def threats(self):
        w, civ = self.w, self.civ
        out = []
        for o in w.civs:
            if o.id == civ.id or not o.alive:
                continue
            for e in o.units:
                if e.civilian:
                    continue
                if any(cheb((e.x, e.y), (c.x, c.y)) <= 3 for c in civ.cities):
                    out.append(e)
        return out

    def find_target(self, u):
        w = self.w
        spec = u.spec
        r = max(1, spec["rng"])
        best, best_odds = None, 0.0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx == 0 and dy == 0:
                    continue
                x, y = u.x + dx, u.y + dy
                if not w.inb(x, y):
                    continue
                d = w.best_defender(x, y)
                city = w.cities.get((x, y))
                if d is not None and d.owner == self.civ.id:
                    continue
                if d is None:
                    if city and city.owner != self.civ.id and spec["rng"] == 0:
                        odds = 99.0
                    else:
                        continue
                elif d.civilian:
                    odds = 99.0
                else:
                    odds = w.attack_strength(u, city is not None) / max(0.1, w.defense_strength(d, x, y))
                need = 0.3 if spec["rng"] > 0 else (0.85 if u.hp >= 60 else 1.4)
                if odds >= need and odds > best_odds:
                    best, best_odds = (x, y), odds
        return best

    def manage_military(self):
        w, civ = self.w, self.civ
        mil = [u for u in civ.units if not u.civilian and u.alive]
        if not mil:
            return
        need = self.need_defenders()
        cpos = {(c.x, c.y): c for c in civ.cities}
        garrison = {c.id: [] for c in civ.cities}
        free = []
        for u in mil:
            c = cpos.get((u.x, u.y))
            if c:
                garrison[c.id].append(u)
            else:
                free.append(u)
        deficits = []
        for c in civ.cities:
            g = sorted(garrison[c.id], key=lambda u: -u.spec["dfn"])
            for u in g[:need]:
                u.fortified = True
            free.extend(g[need:])
            if len(g) < need:
                deficits.append((c, need - len(g)))
        for c, d in deficits:
            for _ in range(d):
                if not free:
                    break
                u = min(free, key=lambda u: cheb((u.x, u.y), (c.x, c.y)))
                free.remove(u)
                if u.moves > 0:
                    w.order_goto(u, c.x, c.y)
        army = [u for u in free if u.alive]
        if not army:
            return
        enemies = [c for o in w.civs if o.alive and o.id != civ.id for c in o.cities]
        threats = self.threats()
        cx = sum(u.x for u in army) / len(army)
        cy = sum(u.y for u in army) / len(army)
        target = min(enemies, key=lambda c: cheb((cx, cy), (c.x, c.y))) if enemies else None
        need_army = min(7, 3 + w.turn // 35)
        self.attacking = bool(w.turn >= 30 and target and
                              (len(army) >= need_army or (self.attacking and len(army) >= 2)))
        rally = None
        if civ.cities:
            rally = (min(civ.cities, key=lambda c: cheb((c.x, c.y), (target.x, target.y)))
                     if target else civ.cities[0])
        for u in army:
            if not u.alive or u.moves <= 0:
                continue
            tgt = self.find_target(u)
            if tgt:
                w.attack(u, *tgt)
                continue
            if threats:
                t = min(threats, key=lambda e: cheb((u.x, u.y), (e.x, e.y)))
                if cheb((u.x, u.y), (t.x, t.y)) <= 8:
                    w.order_attack(u, t.x, t.y)
                    continue
            if self.attacking and target:
                w.order_attack(u, target.x, target.y)
            elif rally:
                if (u.x, u.y) == (rally.x, rally.y):
                    u.fortified = True
                else:
                    w.order_goto(u, rally.x, rally.y)


# ============================================================== интерфейс
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Цивилизация 2D")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        names = "arial,dejavusans,liberationsans,freesans"
        self.f13 = pygame.font.SysFont(names, 13)
        self.f13b = pygame.font.SysFont(names, 13, bold=True)
        self.f15 = pygame.font.SysFont(names, 15)
        self.f15b = pygame.font.SysFont(names, 15, bold=True)
        self.f19b = pygame.font.SysFont(names, 19, bold=True)
        self.f28b = pygame.font.SysFont(names, 30, bold=True)
        self.new_game()

    def new_game(self):
        Unit._next = 1
        self.world = World()
        self.civ = self.world.civs[HUMAN]
        self.ts = 40
        self.fog_ts = None
        self.fog_surf = None
        self.sel = None
        self.modal = None           # None / "city" / "tech" / "help"
        self.modal_city = None
        self.buttons = []
        self.hover = None
        self.drag = None
        self.cam_x = self.cam_y = 0.0
        self.mini = None
        self.mini_tick = 0
        self.frame = 0
        start = self.civ.units[0]
        self.sel = start
        self.center_on(start.x, start.y)
        self.modal = "tech"

    # ------------------------------------------------------------ камера
    def view_tiles(self):
        return MAP_VIEW_W / self.ts, (WIN_H - TOP_H) / self.ts

    def clamp_cam(self):
        vw, vh = self.view_tiles()
        self.cam_x = clamp(self.cam_x, -1, self.world.w - vw + 1)
        self.cam_y = clamp(self.cam_y, -1, self.world.h - vh + 1)

    def center_on(self, x, y):
        vw, vh = self.view_tiles()
        self.cam_x = x + 0.5 - vw / 2
        self.cam_y = y + 0.5 - vh / 2
        self.clamp_cam()

    def tile_at(self, mx, my):
        if mx >= MAP_VIEW_W or my < TOP_H:
            return None
        tx = int(math.floor(self.cam_x + mx / self.ts))
        ty = int(math.floor(self.cam_y + (my - TOP_H) / self.ts))
        return (tx, ty) if self.world.inb(tx, ty) else None

    # ------------------------------------------------------------ логика интерфейса
    def needs_orders(self, u):
        return (u.alive and u.moves > 0 and not u.fortified and not u.path
                and not u.skip and not u.target)

    def pending(self):
        civ = self.civ
        if civ.researching is None and self.world.available_techs(civ):
            return ("tech", None)
        for c in civ.cities:
            if c.current is None:
                return ("city", c)
        for u in civ.units:
            if self.needs_orders(u):
                return ("unit", u)
        return ("end", None)

    def do_pending(self):
        w = self.world
        if w.winner is not None:
            return
        kind, obj = self.pending()
        if kind == "tech":
            self.modal = "tech"
        elif kind == "city":
            self.open_city(obj)
        elif kind == "unit":
            self.select(obj)
        else:
            self.end_turn()

    def end_turn(self):
        self.world.end_turn()
        self.sel = None
        kind, obj = self.pending()
        if kind == "unit":
            self.select(obj)
        elif kind == "tech":
            self.modal = "tech"

    def select(self, obj):
        self.sel = obj
        self.center_on(obj.x, obj.y)

    def open_city(self, c):
        self.sel = c
        self.modal_city = c
        self.modal = "city"
        self.center_on(c.x, c.y)

    def close_modal(self):
        self.modal = None

    def next_unit(self):
        units = [u for u in self.civ.units if self.needs_orders(u) and u is not self.sel]
        if units:
            self.select(units[0])

    def click_map(self, tx, ty):
        w = self.world
        items = [u for u in w.units_at.get((tx, ty), []) if u.owner == HUMAN]
        city = w.cities.get((tx, ty))
        if city and city.owner == HUMAN:
            items.append(city)
        if not items:
            self.sel = None
            return
        if self.sel in items:
            nxt = items[(items.index(self.sel) + 1) % len(items)]
        else:
            nxt = items[0]
        if isinstance(nxt, City):
            self.open_city(nxt)
        else:
            self.sel = nxt

    def right_click(self, tx, ty):
        u = self.sel
        w = self.world
        if not isinstance(u, Unit) or not u.alive or u.owner != HUMAN:
            return
        vis = self.civ.visible[ty][tx]
        d = w.best_defender(tx, ty) if vis else None
        city = w.cities.get((tx, ty))
        enemy_here = (d is not None and d.owner != HUMAN) or (city and city.owner != HUMAN and self.civ.explored[ty][tx])
        if enemy_here and not u.civilian and u.spec["atk"] > 0:
            w.order_attack(u, tx, ty)
        else:
            w.order_goto(u, tx, ty)
        w.update_vision(self.civ)

    def act_found(self):
        u = self.sel
        if isinstance(u, Unit) and u.kind == "settler" and self.world.can_found(u.x, u.y, HUMAN):
            c = self.world.found_city(u)
            if c:
                self.open_city(c)

    def act_fortify(self):
        u = self.sel
        if isinstance(u, Unit) and not u.civilian:
            u.fortified = True
            u.path = []
            u.target = None
            self.next_unit()

    def act_skip(self):
        u = self.sel
        if isinstance(u, Unit):
            u.skip = True
            self.next_unit()

    def act_disband(self):
        u = self.sel
        if isinstance(u, Unit):
            self.world.remove_unit(u)
            self.sel = None
            self.next_unit()

    # ------------------------------------------------------------ события
    def handle_event(self, e):
        w = self.world
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                if self.modal:
                    self.modal = None
                else:
                    pygame.quit()
                    sys.exit()
                return
            if w.winner is not None:
                if k == pygame.K_r:
                    self.new_game()
                return
            if k == pygame.K_t:
                self.modal = None if self.modal == "tech" else "tech"
            elif k == pygame.K_h:
                self.modal = None if self.modal == "help" else "help"
            elif self.modal:
                return
            elif k in (pygame.K_SPACE, pygame.K_RETURN):
                self.do_pending()
            elif k == pygame.K_TAB:
                self.next_unit()
            elif k == pygame.K_b:
                self.act_found()
            elif k == pygame.K_f:
                self.act_fortify()
            elif k == pygame.K_s:
                self.act_skip()
            elif k == pygame.K_DELETE:
                self.act_disband()
            elif k == pygame.K_c and self.sel:
                self.center_on(self.sel.x, self.sel.y)
            return

        if e.type == pygame.MOUSEWHEEL and not self.modal:
            mx, my = pygame.mouse.get_pos()
            if mx < MAP_VIEW_W and my > TOP_H:
                bx = self.cam_x + mx / self.ts
                by = self.cam_y + (my - TOP_H) / self.ts
                self.ts = clamp(self.ts + 4 * e.y, 24, 64)
                self.cam_x = bx - mx / self.ts
                self.cam_y = by - (my - TOP_H) / self.ts
                self.clamp_cam()
            return

        if e.type == pygame.MOUSEMOTION:
            if self.drag:
                dx, dy = e.pos[0] - self.drag[0], e.pos[1] - self.drag[1]
                self.cam_x -= dx / self.ts
                self.cam_y -= dy / self.ts
                self.drag = e.pos
                self.clamp_cam()
            return

        if e.type == pygame.MOUSEBUTTONUP and e.button == 2:
            self.drag = None
            return

        if e.type == pygame.MOUSEBUTTONDOWN:
            mx, my = e.pos
            if e.button == 1:
                for rect, cb in reversed(self.buttons):
                    if rect.collidepoint(mx, my):
                        cb()
                        return
                if self.modal:
                    return
                if w.winner is not None:
                    return
                mm = pygame.Rect(MAP_VIEW_W + 10, WIN_H - 56 - 8 - MM_H, MM_W, MM_H)
                if mm.collidepoint(mx, my):
                    tx = (mx - mm.x) / MM_W * w.w
                    ty = (my - mm.y) / MM_H * w.h
                    self.center_on(int(tx), int(ty))
                    return
                t = self.tile_at(mx, my)
                if t:
                    self.click_map(*t)
            elif e.button == 2 and not self.modal:
                self.drag = e.pos
            elif e.button == 3 and not self.modal and w.winner is None:
                t = self.tile_at(mx, my)
                if t:
                    self.right_click(*t)

    # ------------------------------------------------------------ рисование: вспомогательное
    def text(self, s, x, y, font=None, color=(235, 235, 240), anchor="topleft", shadow=True):
        font = font or self.f15
        img = font.render(s, True, color)
        r = img.get_rect()
        setattr(r, anchor, (x, y))
        if shadow:
            self.screen.blit(font.render(s, True, (0, 0, 0)), r.move(1, 1))
        self.screen.blit(img, r)
        return r

    def button(self, rect, label, cb, enabled=True, color=(60, 85, 130), font=None):
        rect = pygame.Rect(rect)
        hov = enabled and rect.collidepoint(pygame.mouse.get_pos())
        base = color if enabled else (46, 46, 54)
        if hov:
            base = tuple(min(255, c + 28) for c in base)
        pygame.draw.rect(self.screen, base, rect, border_radius=5)
        pygame.draw.rect(self.screen, (160, 160, 178) if enabled else (78, 78, 88), rect, 1, border_radius=5)
        img = (font or self.f15).render(label, True, (240, 240, 245) if enabled else (125, 125, 135))
        self.screen.blit(img, img.get_rect(center=rect.center))
        if enabled:
            self.buttons.append((rect, cb))

    def bar(self, rect, frac, color, back=(30, 30, 38)):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.screen, back, rect, border_radius=3)
        inner = rect.copy()
        inner.width = int(rect.width * clamp(frac, 0, 1))
        if inner.width > 0:
            pygame.draw.rect(self.screen, color, inner, border_radius=3)
        pygame.draw.rect(self.screen, (110, 110, 125), rect, 1, border_radius=3)

    # ------------------------------------------------------------ рисование карты
    def build_fog(self):
        if self.fog_ts == self.ts:
            return
        self.fog_ts = self.ts
        self.fog_surf = pygame.Surface((self.ts + 1, self.ts + 1), pygame.SRCALPHA)
        self.fog_surf.fill((6, 8, 24, 135))

    def draw_terrain(self, t, px, py, ts, x, y):
        scr = self.screen
        col = TERRAIN[t]["col"]
        shade = ((x * 7 + y * 13) % 3 - 1) * 4
        col = (clamp(col[0] + shade, 0, 255), clamp(col[1] + shade, 0, 255), clamp(col[2] + shade, 0, 255))
        pygame.draw.rect(scr, col, (px, py, ts + 1, ts + 1))
        if t == FOREST:
            for fx, fy in ((0.28, 0.62), (0.62, 0.55), (0.45, 0.30)):
                pygame.draw.circle(scr, (24, 84, 40), (px + fx * ts, py + fy * ts), ts * 0.17)
                pygame.draw.rect(scr, (80, 55, 30), (px + fx * ts - 1, py + fy * ts + ts * 0.12, 3, ts * 0.12))
        elif t == HILLS:
            pygame.draw.ellipse(scr, (112, 94, 60), (px + ts * 0.08, py + ts * 0.42, ts * 0.5, ts * 0.42))
            pygame.draw.ellipse(scr, (122, 104, 68), (px + ts * 0.42, py + ts * 0.3, ts * 0.5, ts * 0.52))
        elif t == MOUNTAIN:
            pygame.draw.polygon(scr, (88, 88, 98), [(px + ts * 0.1, py + ts * 0.88), (px + ts * 0.42, py + ts * 0.15),
                                                    (px + ts * 0.9, py + ts * 0.88)])
            pygame.draw.polygon(scr, (240, 240, 248), [(px + ts * 0.32, py + ts * 0.38), (px + ts * 0.42, py + ts * 0.15),
                                                       (px + ts * 0.52, py + ts * 0.4)])
        elif t == DESERT:
            for fx, fy in ((0.25, 0.3), (0.6, 0.55), (0.35, 0.75)):
                pygame.draw.circle(scr, (196, 174, 108), (px + fx * ts, py + fy * ts), 2)
        elif t == WATER:
            if (x + y) % 2 == 0:
                pygame.draw.line(scr, (80, 130, 200), (px + ts * 0.2, py + ts * 0.5), (px + ts * 0.5, py + ts * 0.45), 2)

    def draw_unit(self, u, px, py, ts, selected, small=False):
        scr = self.screen
        civ = self.world.civs[u.owner]
        r = ts * (0.24 if small else 0.32)
        cx = px + ts * (0.7 if small else 0.5)
        cy = py + ts * (0.7 if small else 0.5)
        pygame.draw.circle(scr, civ.color, (cx, cy), r)
        pygame.draw.circle(scr, (255, 255, 255) if selected else (20, 20, 25), (cx, cy), r, 2)
        img = self.f13b.render(u.spec["ch"], True, (255, 255, 255))
        scr.blit(img, img.get_rect(center=(cx, cy)))
        if u.hp < 100:
            pygame.draw.rect(scr, (40, 0, 0), (cx - r, cy + r + 1, 2 * r, 4))
            pygame.draw.rect(scr, (60, 220, 70) if u.hp > 50 else (230, 80, 60), (cx - r, cy + r + 1, 2 * r * u.hp / 100, 4))
        if u.fortified:
            pygame.draw.rect(scr, (255, 255, 255), (cx + r - 4, cy - r - 2, 7, 7))
            pygame.draw.rect(scr, (20, 20, 25), (cx + r - 4, cy - r - 2, 7, 7), 1)

    def draw_map(self):
        scr, w, civ, ts = self.screen, self.world, self.civ, self.ts
        self.build_fog()
        view = pygame.Rect(0, TOP_H, MAP_VIEW_W, WIN_H - TOP_H)
        scr.set_clip(view)
        scr.fill((8, 8, 12), view)
        x0, y0 = int(math.floor(self.cam_x)), int(math.floor(self.cam_y))
        ox = -(self.cam_x - x0) * ts
        oy = TOP_H - (self.cam_y - y0) * ts
        nx, ny = int(MAP_VIEW_W / ts) + 2, int((WIN_H - TOP_H) / ts) + 2
        blink = (self.frame // 20) % 2 == 0

        for j in range(ny):
            ty = y0 + j
            if ty < 0 or ty >= w.h:
                continue
            for i in range(nx):
                tx = x0 + i
                if tx < 0 or tx >= w.w or not civ.explored[ty][tx]:
                    continue
                px, py = int(ox + i * ts), int(oy + j * ts)
                self.draw_terrain(w.terr[ty][tx], px, py, ts, tx, ty)
                r = w.res[ty][tx]
                if r:
                    pygame.draw.circle(scr, RESOURCES[r]["col"], (px + ts * 0.82, py + ts * 0.18), ts * 0.12)
                    pygame.draw.circle(scr, (20, 20, 20), (px + ts * 0.82, py + ts * 0.18), ts * 0.12, 1)
                if not civ.visible[ty][tx]:
                    scr.blit(self.fog_surf, (px, py))
                # границы
                o = w.owner[ty][tx]
                if o >= 0:
                    col = w.civs[o].color
                    for dx, dy, a, b in ((0, -1, (0, 0), (1, 0)), (0, 1, (0, 1), (1, 1)),
                                         (-1, 0, (0, 0), (0, 1)), (1, 0, (1, 0), (1, 1))):
                        qx, qy = tx + dx, ty + dy
                        if not w.inb(qx, qy) or w.owner[qy][qx] != o:
                            pygame.draw.line(scr, col, (px + a[0] * ts, py + a[1] * ts),
                                             (px + b[0] * ts, py + b[1] * ts), 3)

        # путь выбранного юнита
        if isinstance(self.sel, Unit) and self.sel.alive and self.sel.path:
            pts = [(self.sel.x, self.sel.y)] + list(self.sel.path)
            for a, b in zip(pts, pts[1:]):
                pa = (ox + (a[0] - x0 + 0.5) * ts, oy + (a[1] - y0 + 0.5) * ts)
                pb = (ox + (b[0] - x0 + 0.5) * ts, oy + (b[1] - y0 + 0.5) * ts)
                pygame.draw.line(scr, (255, 235, 120), pa, pb, 2)
                pygame.draw.circle(scr, (255, 235, 120), pb, 3)

        # города и юниты
        for j in range(ny):
            ty = y0 + j
            if ty < 0 or ty >= w.h:
                continue
            for i in range(nx):
                tx = x0 + i
                if tx < 0 or tx >= w.w or not civ.explored[ty][tx]:
                    continue
                px, py = int(ox + i * ts), int(oy + j * ts)
                city = w.cities.get((tx, ty))
                if city:
                    cc = w.civs[city.owner].color
                    pygame.draw.rect(scr, (30, 30, 36), (px + ts * 0.1, py + ts * 0.2, ts * 0.8, ts * 0.7), border_radius=3)
                    pygame.draw.rect(scr, cc, (px + ts * 0.16, py + ts * 0.26, ts * 0.68, ts * 0.58), border_radius=2)
                    pygame.draw.rect(scr, (240, 240, 245), (px + ts * 0.26, py + ts * 0.12, ts * 0.14, ts * 0.2))
                    pygame.draw.rect(scr, (240, 240, 245), (px + ts * 0.6, py + ts * 0.12, ts * 0.14, ts * 0.2))
                    img = self.f15b.render(str(city.pop), True, (255, 255, 255))
                    scr.blit(img, img.get_rect(center=(px + ts * 0.5, py + ts * 0.56)))
                    self.text(city.name, px + ts / 2, py - 2, self.f13b, (255, 255, 255), "midbottom")
                if not civ.visible[ty][tx]:
                    continue
                stack = w.units_at.get((tx, ty), [])
                if not stack:
                    continue
                mil = [u for u in stack if not u.civilian]
                civs = [u for u in stack if u.civilian]
                if city is not None:
                    # в городе рисуем маленький значок гарнизона
                    if mil:
                        u = mil[0]
                        pygame.draw.circle(scr, w.civs[u.owner].color, (px + ts * 0.85, py + ts * 0.85), ts * 0.15)
                        pygame.draw.circle(scr, (20, 20, 25), (px + ts * 0.85, py + ts * 0.85), ts * 0.15, 1)
                        if len(mil) > 1:
                            self.text(str(len(mil)), px + ts * 0.85, py + ts * 0.85, self.f13b, (255, 255, 255), "center")
                    sel_here = isinstance(self.sel, Unit) and self.sel in stack
                    if sel_here and blink:
                        pygame.draw.rect(scr, (255, 255, 120), (px, py, ts, ts), 2)
                    continue
                if mil:
                    top = mil[0]
                    if self.sel in mil and not blink:
                        top = None
                    if top is not None:
                        self.draw_unit(top, px, py, ts, top is self.sel)
                if civs:
                    cu = civs[0]
                    if not (cu is self.sel and not blink):
                        self.draw_unit(cu, px, py, ts, cu is self.sel, small=bool(mil))

        # подсветка клетки под курсором
        if self.hover and not self.modal:
            hx, hy = self.hover
            pygame.draw.rect(scr, (255, 255, 255),
                             (int(ox + (hx - x0) * ts), int(oy + (hy - y0) * ts), ts, ts), 1)
        scr.set_clip(None)

    def draw_log(self):
        w = self.world
        msgs = [m for m in w.msgs if m[0] >= w.turn - 3][-6:]
        if not msgs:
            return
        y = WIN_H - 10 - 20 * len(msgs)
        bg = pygame.Surface((520, 20 * len(msgs) + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 130))
        self.screen.blit(bg, (8, y - 3))
        for t, s, col in msgs:
            self.text(s, 14, y, self.f13, col)
            y += 20

    # ------------------------------------------------------------ боковая панель
    def draw_minimap(self):
        w, civ = self.world, self.civ
        rect = pygame.Rect(MAP_VIEW_W + 10, WIN_H - 56 - 8 - MM_H, MM_W, MM_H)
        if self.mini is None or self.frame - self.mini_tick > 8:
            self.mini_tick = self.frame
            surf = pygame.Surface((w.w, w.h))
            surf.fill((8, 8, 12))
            for y in range(w.h):
                for x in range(w.w):
                    if not civ.explored[y][x]:
                        continue
                    col = TERRAIN[w.terr[y][x]]["col"]
                    o = w.owner[y][x]
                    if o >= 0:
                        oc = w.civs[o].color
                        col = tuple((col[k] + oc[k]) // 2 for k in range(3))
                    surf.set_at((x, y), col)
            for (x, y), c in w.cities.items():
                if civ.explored[y][x]:
                    surf.set_at((x, y), (255, 255, 255))
            self.mini = pygame.transform.scale(surf, (MM_W, MM_H))
        self.screen.blit(self.mini, rect)
        pygame.draw.rect(self.screen, (120, 120, 135), rect, 1)
        vw, vh = self.view_tiles()
        vr = pygame.Rect(rect.x + self.cam_x / w.w * MM_W, rect.y + self.cam_y / w.h * MM_H,
                         vw / w.w * MM_W, vh / w.h * MM_H)
        vr = vr.clip(rect)
        pygame.draw.rect(self.screen, (255, 255, 255), vr, 1)

    def draw_panel(self):
        scr, w, civ = self.screen, self.world, self.civ
        x0 = MAP_VIEW_W
        pygame.draw.rect(scr, (26, 28, 38), (x0, TOP_H, PANEL_W, WIN_H - TOP_H))
        pygame.draw.line(scr, (90, 90, 110), (x0, TOP_H), (x0, WIN_H), 2)
        x = x0 + 12
        y = TOP_H + 8

        # клетка под курсором
        if self.hover and civ.explored[self.hover[1]][self.hover[0]]:
            hx, hy = self.hover
            T = TERRAIN[w.terr[hy][hx]]
            f, p, g = w.tile_yield(hx, hy)
            res = w.res[hy][hx]
            line = T["name"] + (f" ({RESOURCES[res]['name']})" if res else "")
            self.text(line, x, y, self.f15b)
            self.text(f"еда {f}   пр-во {p}   золото {g}", x, y + 20, self.f13, (200, 200, 210))
            o = w.owner[hy][hx]
            if o >= 0:
                self.text(f"Территория: {w.civs[o].name}", x, y + 38, self.f13, w.civs[o].color)
            if civ.visible[hy][hx]:
                for k, u in enumerate(w.units_at.get((hx, hy), [])[:2]):
                    self.text(f"{u.spec['name']} ({w.civs[u.owner].name}) {int(u.hp)}%", x, y + 56 + k * 16,
                              self.f13, w.civs[u.owner].color)
        y = TOP_H + 112
        pygame.draw.line(scr, (70, 70, 90), (x0 + 8, y - 6), (x0 + PANEL_W - 8, y - 6))

        sel = self.sel
        if isinstance(sel, Unit) and sel.alive:
            s = sel.spec
            self.text(s["name"], x, y, self.f19b, civ.color)
            self.text(f"Здоровье: {int(sel.hp)}", x, y + 28, self.f13)
            self.bar((x + 90, y + 30, 170, 10), sel.hp / 100, (70, 210, 90) if sel.hp > 50 else (230, 80, 60))
            self.text(f"Ходы: {sel.moves}/{s['move']}", x, y + 46, self.f13)
            if not sel.civilian:
                rng = f", дальность {s['rng']}" if s["rng"] else ""
                self.text(f"Атака {s['atk']}   Защита {s['dfn']}{rng}", x, y + 62, self.f13)
                if sel.fortified:
                    self.text("Укреплён", x, y + 78, self.f13, (200, 255, 200))
            by = y + 100
            if sel.kind == "settler":
                self.button((x, by, 136, 30), "Основать город [B]", self.act_found,
                            w.can_found(sel.x, sel.y, HUMAN), (50, 120, 70), self.f13b)
            else:
                self.button((x, by, 136, 30), "Укрепиться [F]", self.act_fortify, True, (60, 85, 130), self.f13b)
            self.button((x + 144, by, 136, 30), "Пропустить [S]", self.act_skip, True, (60, 85, 130), self.f13b)
            self.button((x, by + 38, 136, 28), "Распустить [Del]", self.act_disband, True, (120, 55, 55), self.f13b)
            self.button((x + 144, by + 38, 136, 28), "Центр [C]", lambda: self.center_on(sel.x, sel.y),
                        True, (60, 70, 90), self.f13b)
            hint = ["ПКМ по клетке - идти / атаковать.",
                    "Лучники и катапульты бьют на 2 клетки",
                    "и не получают ответного урона."]
            for k, h in enumerate(hint):
                self.text(h, x, by + 82 + k * 17, self.f13, (170, 170, 185))
        elif isinstance(sel, City) and sel.owner == HUMAN:
            self.text(sel.name, x, y, self.f19b, civ.color)
            self.button((x, y + 30, 270, 30), "Открыть управление городом", lambda: self.open_city(sel))
        else:
            self.text("Ничего не выбрано", x, y, self.f15b, (170, 170, 185))
            self.text("ЛКМ по своему юниту или городу", x, y + 22, self.f13, (170, 170, 185))
            self.text("[H] - справка по управлению", x, y + 40, self.f13, (170, 170, 185))

        self.draw_minimap()
        # кнопка хода
        kind, obj = self.pending()
        labels = {"tech": "Выбрать исследование", "city": "Выбрать производство",
                  "unit": "Следующий юнит", "end": "Конец хода"}
        colors = {"end": (60, 130, 70)}
        self.button((x0 + 10, WIN_H - 56, PANEL_W - 20, 44), labels[kind], self.do_pending,
                    w.winner is None, colors.get(kind, (140, 110, 40)), self.f19b)

    def draw_topbar(self):
        scr, w, civ = self.screen, self.world, self.civ
        pygame.draw.rect(scr, (20, 22, 30), (0, 0, WIN_W, TOP_H))
        pygame.draw.line(scr, (90, 90, 110), (0, TOP_H), (WIN_W, TOP_H))
        self.text(f"Ход {w.turn}", 12, 8, self.f15b, (255, 235, 140))
        g = civ.last_gold
        self.text(f"Золото: {int(civ.gold)} ({g:+.0f})", 100, 8, self.f15b, (255, 215, 0))
        self.text(f"Наука: +{civ.last_sci:.1f}", 260, 8, self.f15b, (130, 200, 255))
        if civ.researching:
            name, cost, _ = TECHS[civ.researching]
            turns = max(1, int(math.ceil((cost - civ.bulbs) / max(0.1, civ.last_sci))))
            label = f"Исследование: {name} ({int(civ.bulbs)}/{cost}, ~{turns} х.)"
        else:
            label = "Исследование: выбрать... [T]"
        r = self.text(label, 390, 8, self.f15b, (200, 230, 255))
        self.buttons.append((pygame.Rect(r.x - 4, 0, r.width + 8, TOP_H), lambda: setattr(self, "modal", "tech")))
        alive = [c for c in w.civs if c.alive]
        info = f"Города: {len(civ.cities)}   Юниты: {len(civ.units)}   Цивилизаций: {len(alive)}"
        self.text(info, WIN_W - 12, 8, self.f15, (210, 210, 220), "topright")

    # ------------------------------------------------------------ окна
    def veil(self):
        v = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        v.fill((0, 0, 0, 150))
        self.screen.blit(v, (0, 0))
        self.buttons = []

    def draw_tech_modal(self):
        scr, w, civ = self.screen, self.world, self.civ
        self.veil()
        R = pygame.Rect(200, 60, 800, 600)
        pygame.draw.rect(scr, (32, 36, 48), R, border_radius=10)
        pygame.draw.rect(scr, civ.color, R, 3, border_radius=10)
        self.text("Технологии", R.x + 20, R.y + 12, self.f28b)
        self.button((R.right - 44, R.y + 10, 32, 30), "X", self.close_modal, True, (140, 50, 50))
        self.text(f"Накоплено науки: {int(civ.bulbs)}   Скорость: +{civ.last_sci:.1f}/ход", R.x + 20, R.y + 50,
                  self.f13, (190, 210, 235))
        order = sorted(TECHS.items(), key=lambda kv: kv[1][1])
        avail = set(w.available_techs(civ))
        y = R.y + 80
        for key, (name, cost, pre) in order:
            row = pygame.Rect(R.x + 16, y, R.width - 32, 38)
            unlocks = [ITEMS[k]["name"] for k, s in ITEMS.items() if s["tech"] == key]
            if key in civ.techs:
                col, status = (40, 90, 55), "изучено"
            elif key == civ.researching:
                col, status = (110, 90, 30), "изучается"
            elif key in avail:
                col, status = (50, 70, 110), f"{int(cost)}"
            else:
                col, status = (40, 40, 48), "нужны: " + ", ".join(TECHS[p][0] for p in pre if p not in civ.techs)

            def choose(k=key):
                civ.researching = k
                self.modal = None

            hov = row.collidepoint(pygame.mouse.get_pos()) and key in avail
            pygame.draw.rect(scr, tuple(min(255, c + 22) for c in col) if hov else col, row, border_radius=5)
            pygame.draw.rect(scr, (110, 110, 130), row, 1, border_radius=5)
            self.text(name, row.x + 10, row.y + 4, self.f15b)
            self.text("Открывает: " + (", ".join(unlocks) if unlocks else "-"), row.x + 10, row.y + 21,
                      self.f13, (200, 200, 215))
            self.text(status, row.right - 10, row.y + 11, self.f13b, (255, 240, 170), "topright")
            if key in avail:
                self.buttons.append((row, choose))
            y += 42

    def draw_help_modal(self):
        scr = self.screen
        self.veil()
        R = pygame.Rect(260, 90, 680, 540)
        pygame.draw.rect(scr, (32, 36, 48), R, border_radius=10)
        pygame.draw.rect(scr, (150, 150, 170), R, 2, border_radius=10)
        self.text("Справка", R.x + 20, R.y + 12, self.f28b)
        self.button((R.right - 44, R.y + 10, 32, 30), "X", self.close_modal, True, (140, 50, 50))
        lines = [
            "Цель: захватить все города соперников (или не дать им захватить твои).",
            "",
            "ЛКМ - выбрать юнит/город.  ПКМ - приказ (идти / атаковать).",
            "Колесо - масштаб, СКМ - перетаскивать карту, WASD/стрелки - прокрутка.",
            "B - основать город, F - укрепиться, S - пропустить, Del - распустить.",
            "Tab - следующий юнит, T - технологии, C - центр, Пробел - следующее действие.",
            "",
            "Города сами выбирают клетки. Еда растит население, производство -",
            "строит юнитов и здания, золото покупает производство, наука открывает новое.",
            "Новый город - основа экономики: расширяйся поселенцами (нужно население 2+).",
            "Здания: Амбар (+еда), Библиотека/Университет (+наука), Рынок (+золото),",
            "Мастерская (+производство), Стены (+защита). У зданий есть содержание.",
            "",
            "Бой: лес +25%, холмы +50% к защите, укрепление +25%, город +25%, стены +50%.",
            "Раненые юниты слабее и лечатся на отдыхе (в городе - быстрее).",
            "Одиночный юнит вне города занимает клетку один; в городе - до 4 юнитов.",
            "Город без защитников захватывается заходом ближнего юнита.",
            "Соперники нападают на всех и друг на друга. Держи гарнизоны в городах!",
        ]
        for i, s in enumerate(lines):
            self.text(s, R.x + 24, R.y + 60 + i * 24, self.f15, (220, 220, 232))

    def draw_city_modal(self):
        scr, w, civ = self.screen, self.world, self.civ
        c = self.modal_city
        if c is None or c.owner != HUMAN:
            self.modal = None
            return
        self.veil()
        R = pygame.Rect(130, 50, 940, 620)
        pygame.draw.rect(scr, (32, 36, 48), R, border_radius=10)
        pygame.draw.rect(scr, civ.color, R, 3, border_radius=10)
        self.text(f"{c.name}", R.x + 20, R.y + 12, self.f28b)
        self.text(f"население {c.pop}" + ("   (столица)" if c.capital else ""), R.x + 20, R.y + 50,
                  self.f13, (200, 210, 230))
        self.button((R.right - 44, R.y + 10, 32, 30), "X", self.close_modal, True, (140, 50, 50))
        cities = civ.cities
        if len(cities) > 1:
            i = cities.index(c)
            self.button((R.right - 150, R.y + 10, 40, 30), "<", lambda: self.open_city(cities[(i - 1) % len(cities)]),
                        True, (60, 70, 100))
            self.button((R.right - 100, R.y + 10, 40, 30), ">", lambda: self.open_city(cities[(i + 1) % len(cities)]),
                        True, (60, 70, 100))

        yv = w.city_yields(c)
        thr = w.growth_thr(c.pop)
        surplus = yv["food"] - 2 * c.pop
        lx, y = R.x + 24, R.y + 84
        self.text(f"Еда: {yv['food']} (потребление {2 * c.pop}, итого {surplus:+d})", lx, y, self.f15b, (170, 235, 150))
        self.bar((lx, y + 24, 270, 12), c.food / thr, (110, 200, 90))
        if surplus > 0:
            tt = max(1, int(math.ceil((thr - c.food) / surplus)))
            self.text(f"{int(c.food)}/{thr}, рост через ~{tt} х.", lx, y + 40, self.f13, (190, 210, 190))
        else:
            self.text(f"{int(c.food)}/{thr}, роста нет", lx, y + 40, self.f13, (255, 170, 140))
        y += 70
        self.text(f"Производство: +{yv['prod']}", lx, y, self.f15b, (255, 200, 120))
        self.text(f"Золото: +{yv['gold']}  (содержание {yv['upkeep']})", lx, y + 24, self.f15b, (255, 220, 70))
        self.text(f"Наука: +{yv['sci']:.1f}", lx, y + 48, self.f15b, (140, 205, 255))
        self.text(f"Обрабатывается клеток: {len(c.worked)} из {c.pop}", lx, y + 74, self.f13, (200, 200, 215))
        y += 104
        self.text("Постройки:", lx, y, self.f15b)
        if c.buildings:
            for k, b in enumerate(sorted(c.buildings)):
                self.text(f"- {ITEMS[b]['name']} ({ITEMS[b]['desc']})", lx, y + 22 + k * 18, self.f13, (210, 225, 210))
        else:
            self.text("нет", lx, y + 22, self.f13, (160, 160, 175))
        y += 22 + max(1, len(c.buildings)) * 18 + 14
        self.text("Гарнизон:", lx, y, self.f15b)
        stack = [u for u in w.units_at.get((c.x, c.y), []) if u.owner == HUMAN]
        if stack:
            for k, u in enumerate(stack[:5]):
                self.text(f"- {u.spec['name']} ({int(u.hp)}%)", lx, y + 22 + k * 18, self.f13, (210, 215, 235))
        else:
            self.text("пусто! город беззащитен", lx, y + 22, self.f13, (255, 140, 120))

        # производство
        rx = R.x + 330
        ry = R.y + 84
        self.text("Производство", rx, ry, self.f19b)
        if c.current:
            sp = ITEMS[c.current]
            rem = max(0.0, sp["cost"] - c.stock)
            turns = int(math.ceil(rem / max(1, yv["prod"])))
            self.text(f"{sp['name']}   {int(c.stock)}/{sp['cost']}   (~{turns} х.)", rx, ry + 28, self.f15b, (255, 220, 150))
            self.bar((rx, ry + 52, 400, 12), c.stock / sp["cost"], (240, 170, 70))
            if c.current == "settler" and c.pop < 2:
                self.text("Нужно население 2, чтобы завершить", rx, ry + 68, self.f13, (255, 170, 140))
            cost = w.buy_cost(c)
            self.button((rx + 420, ry + 24, 150, 40), f"Купить: {cost} зол.", lambda: w.buy(c),
                        civ.gold >= cost and w.can_complete(c) and c.stock < sp["cost"], (130, 105, 40), self.f13b)
        else:
            self.text("Выберите, что строить", rx, ry + 28, self.f15b, (255, 170, 140))
        items = w.available_items(civ, c)
        y0 = ry + 92
        for i, key in enumerate(items):
            sp = ITEMS[key]
            row = pygame.Rect(rx, y0 + i * 31, 590, 28)
            cur = key == c.current
            hov = row.collidepoint(pygame.mouse.get_pos())
            col = (95, 80, 40) if cur else (52, 62, 90)
            if hov:
                col = tuple(min(255, v + 24) for v in col)
            pygame.draw.rect(scr, col, row, border_radius=4)
            pygame.draw.rect(scr, (110, 110, 130), row, 1, border_radius=4)
            if sp["kind"] == "unit":
                desc = "гражданский" if sp.get("civ") else (
                    f"атака {sp['atk']}, защита {sp['dfn']}" + (f", даль {sp['rng']}" if sp['rng'] else "") + f", ход {sp['move']}")
            else:
                desc = sp["desc"]
            self.text(sp["name"], row.x + 8, row.y + 5, self.f15b)
            self.text(desc, row.x + 150, row.y + 7, self.f13, (205, 210, 225))
            t = int(math.ceil(max(0, sp["cost"] - (c.stock if cur else 0)) / max(1, yv["prod"])))
            self.text(f"{sp['cost']}  (~{t} х.)", row.right - 8, row.y + 7, self.f13b, (255, 230, 150), "topright")

            def pick(k=key):
                c.current = k

            self.buttons.append((row, pick))

    def draw_gameover(self):
        w = self.world
        v = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        v.fill((0, 0, 0, 170))
        self.screen.blit(v, (0, 0))
        self.buttons = []
        if w.winner == HUMAN:
            self.text("ПОБЕДА!", WIN_W // 2, 250, self.f28b, (255, 225, 90), "center")
            self.text(f"Ты объединил мир за {w.turn} ходов.", WIN_W // 2, 300, self.f19b, (235, 235, 240), "center")
        else:
            self.text("ПОРАЖЕНИЕ", WIN_W // 2, 250, self.f28b, (255, 110, 110), "center")
            self.text(f"Твоя цивилизация пала на {w.turn} ходу.", WIN_W // 2, 300, self.f19b, (235, 235, 240), "center")
        self.text("R - новая игра     Esc - выход", WIN_W // 2, 360, self.f15b, (220, 220, 235), "center")

    # ------------------------------------------------------------ главный цикл
    def update(self, dt):
        if self.modal:
            return
        keys = pygame.key.get_pressed()
        sp = 14 * dt
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cam_x -= sp
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cam_x += sp
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cam_y -= sp
        if keys[pygame.K_DOWN]:
            self.cam_y += sp
        self.clamp_cam()

    def draw(self):
        self.buttons = []
        self.hover = self.tile_at(*pygame.mouse.get_pos()) if not self.modal else None
        self.screen.fill((8, 8, 12))
        self.draw_map()
        self.draw_log()
        self.draw_panel()
        self.draw_topbar()
        if self.world.winner is not None:
            self.draw_gameover()
        elif self.modal == "tech":
            self.draw_tech_modal()
        elif self.modal == "city":
            self.draw_city_modal()
        elif self.modal == "help":
            self.draw_help_modal()
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.frame += 1
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
