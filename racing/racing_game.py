#!/usr/bin/env python3
"""Neon Strip GP v2 - rotating-camera night street racer on any GeoJSON circuit, with money, garage and saves.
Run:  pip install pygame && python racing_game.py [track.geojson]
Keys: Up/W gas, Down/S brake, Left/Right/A/D steer, Space handbrake, R reset to track,
      menu: 1/2/3 laps, Enter start, G garage (Left/Right browse, Enter buy/equip, Esc back).
Save file: ~/.neon_strip_gp.json (override with env NEON_SAVE)."""

import json
import math
import os
import random
import sys
from collections import deque

import pygame

W, HALF, DS, WB = 22.0, 12.5, 4.0, 2.6
SAVE_PATH = os.environ.get(
    "NEON_SAVE", os.path.join(os.path.expanduser("~"), ".neon_strip_gp.json")
)
MODELS = [
    dict(
        id="ae80",
        name="Toyota Corolla AE80",
        tag="1983-87 sedan",
        price=0,
        vmax=48,
        acc=9.5,
        steer=0.42,
        grip=7.2,
        color=(185, 157, 120),
        L=4.17,
        Wd=1.63,
        wb=2.43,
        tw=0.24,
        spec=dict(
            prof=[
                (-1, 0.86),
                (-0.97, 0.95),
                (-0.9, 1),
                (0.9, 1),
                (0.97, 0.93),
                (1, 0.8),
            ],
            cab=(0.9, 0.5, -0.75, -1.2),
            gw=0.78,
            rf=0.94,
            doors=[0.15, -0.45],
            fl="rect",
            tl="rect",
            bump=True,
        ),
    ),
    dict(
        id="ek",
        name="Honda Civic EK",
        tag="1995-2000 hatchback",
        price=6000,
        vmax=56,
        acc=12,
        steer=0.52,
        grip=8.4,
        color=(226, 228, 232),
        L=4.18,
        Wd=1.69,
        wb=2.62,
        tw=0.25,
        spec=dict(
            prof=[
                (-1, 0.82),
                (-0.95, 0.94),
                (-0.85, 1),
                (0.8, 1),
                (0.93, 0.95),
                (1, 0.78),
            ],
            cab=(0.78, 0.42, -1.0, -1.6),
            gw=0.8,
            rf=0.94,
            doors=[0.05, -0.5],
            fl="wedge",
            tl="rect",
        ),
    ),
    dict(
        id="nc",
        name="Mazda MX-5 NC",
        tag="2005-15 roadster",
        price=14000,
        vmax=60,
        acc=13,
        steer=0.55,
        grip=8.8,
        color=(150, 156, 168),
        L=4.02,
        Wd=1.72,
        wb=2.33,
        tw=0.27,
        spec=dict(
            prof=[
                (-1, 0.8),
                (-0.93, 0.94),
                (-0.78, 1),
                (0.15, 0.95),
                (0.7, 0.96),
                (0.92, 0.9),
                (1, 0.72),
            ],
            cab=(0.55, 0.41, -0.7, -0.7),
            gw=0.78,
            open=True,
            fl="bulge",
            tl="round",
        ),
    ),
    dict(
        id="rx8",
        name="Mazda RX-8",
        tag="2003-12 coupe",
        price=24000,
        vmax=64,
        acc=14.5,
        steer=0.50,
        grip=9.0,
        color=(40, 80, 170),
        L=4.43,
        Wd=1.77,
        wb=2.70,
        tw=0.27,
        spec=dict(
            prof=[
                (-1, 0.82),
                (-0.94, 0.95),
                (-0.8, 1),
                (0.7, 1),
                (0.9, 0.95),
                (1, 0.78),
            ],
            cab=(0.95, 0.5, -0.85, -1.35),
            gw=0.8,
            rf=0.96,
            doors=[0.55, 0.1, -0.45],
            fl="slim",
            tl="round",
        ),
    ),
    dict(
        id="s2k",
        name="Honda S2000",
        tag="1999-2009 roadster",
        price=34000,
        vmax=66,
        acc=15,
        steer=0.56,
        grip=9.2,
        color=(240, 200, 30),
        L=4.12,
        Wd=1.75,
        wb=2.40,
        tw=0.27,
        spec=dict(
            prof=[
                (-1, 0.78),
                (-0.93, 0.93),
                (-0.75, 1),
                (0.2, 0.98),
                (0.75, 0.94),
                (0.93, 0.88),
                (1, 0.7),
            ],
            cab=(0.5, 0.36, -0.78, -0.78),
            gw=0.78,
            open=True,
            bulge=True,
            fl="slim",
            tl="bar",
        ),
    ),
    dict(
        id="fd",
        name="Mazda RX-7 FD",
        tag="1991-2002 coupe",
        price=60000,
        vmax=70,
        acc=17,
        steer=0.52,
        grip=9.6,
        color=(180, 30, 36),
        L=4.28,
        Wd=1.75,
        wb=2.43,
        tw=0.28,
        spec=dict(
            prof=[
                (-1, 0.8),
                (-0.9, 0.95),
                (-0.7, 1),
                (-0.3, 0.92),
                (0.1, 0.9),
                (0.5, 0.96),
                (0.75, 1),
                (0.93, 0.9),
                (1, 0.65),
            ],
            cab=(0.62, 0.28, -0.42, -1.2),
            gw=0.8,
            rf=0.78,
            bulge=True,
            wing=True,
            fl="slim",
            tl="round",
        ),
    ),
]
BYID = {m["id"]: m for m in MODELS}
AI_STATS = dict(vmax=56, acc=12, steer=0.45, grip=8)
AI_BODY = [None, 1, 2, 3, 0, 4]  # model look per car id (id 0 = player)
COLS = [
    (185, 157, 120),
    (196, 58, 58),
    (233, 233, 238),
    (59, 111, 209),
    (47, 158, 107),
    (58, 61, 70),
]
NAMES = ["You", "Aiko", "Marco", "Zoe", "Ravi", "Lena"]
PRIZE = [2000, 1300, 900, 550, 300, 150]  # x laps
clamp = lambda v, a, b: max(a, min(b, v))
lighten = lambda c, a: tuple(min(255, v + a) for v in c)
wrap = lambda d: math.atan2(math.sin(d), math.cos(d))


# ---------------------------------------------------------------- save
def load_save():
    d = dict(money=0, owned=["ae80"], car="ae80", races=0, wins=0)
    try:
        with open(SAVE_PATH, encoding="utf-8") as f:
            d.update(json.load(f))
    except Exception:
        pass
    fix = lambda i: "ae80" if i == "corolla" else i  # ids from older versions
    d["owned"] = [
        i for i in dict.fromkeys(fix(i) for i in d.get("owned", [])) if i in BYID
    ]
    if "ae80" not in d["owned"]:
        d["owned"].append("ae80")
    d["car"] = fix(d.get("car"))
    if d["car"] not in d["owned"]:
        d["car"] = "ae80"
    d["money"] = max(0, int(d.get("money", 0)))
    return d


def write_save(d):
    try:
        tmp = SAVE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, SAVE_PATH)
    except Exception as e:
        print("Could not save:", e)


# ---------------------------------------------------------------- track
def resample(p, ds):
    n = len(p)
    L = [0.0]
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    tot = L[n]
    M = round(tot / ds)
    out = []
    j = 0
    for k in range(M):
        d = k * tot / M
        while L[j + 1] < d:
            j += 1
        a, b = p[j], p[(j + 1) % n]
        t = (d - L[j]) / ((L[j + 1] - L[j]) or 1)
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def smooth(p, w):
    n = len(p)
    o = []
    for i in range(n):
        x = y = 0
        for k in range(-w, w + 1):
            q = p[(i + k) % n]
            x += q[0]
            y += q[1]
        o.append((x / (2 * w + 1), y / (2 * w + 1)))
    return o


class Track:
    def __init__(self, geo):
        lines = []
        feats = (
            geo["features"]
            if geo.get("type") == "FeatureCollection"
            else [geo if geo.get("type") == "Feature" else {"geometry": geo}]
        )
        for f in feats:
            m = f.get("geometry") or {}
            t = m.get("type")
            if t == "LineString":
                lines.append(m["coordinates"])
            elif t == "MultiLineString":
                lines += m["coordinates"]
            elif t == "Polygon":
                lines.append(m["coordinates"][0])
            elif t == "MultiPolygon":
                lines.append(m["coordinates"][0][0])
        if not lines:
            raise ValueError("No line or polygon geometry found")
        co = max(lines, key=len)
        lat0 = sum(q[1] for q in co) / len(co)
        kx = 111320 * math.cos(math.radians(lat0))
        p = [((q[0] - co[0][0]) * kx, -(q[1] - co[0][1]) * 110574) for q in co]
        self.c = c = resample(smooth(smooth(resample(p, 3), 6), 6), DS)
        N = self.N = len(c)
        if N < 60:
            raise ValueError("Track too short")
        self.tx = []
        self.ty = []
        self.hd = []
        for i in range(N):
            a, b = c[i - 1], c[(i + 1) % N]
            d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            self.tx.append((b[0] - a[0]) / d)
            self.ty.append((b[1] - a[1]) / d)
            self.hd.append(math.atan2(self.ty[-1], self.tx[-1]))
        self.vmax = []
        for i in range(N):
            d = wrap(self.hd[(i + 4) % N] - self.hd[i - 4])
            self.vmax.append(
                clamp(math.sqrt(22 / max(abs(d) / (8 * DS), 1e-4)), 20, 80)
            )
        edge = lambda h, s: [
            (c[i][0] - self.ty[i] * h * s, c[i][1] + self.tx[i] * h * s)
            for i in range(N)
        ]
        self.bl, self.br, self.al, self.ar = (
            edge(HALF + 1, 1),
            edge(HALF + 1, -1),
            edge(W / 2, 1),
            edge(W / 2, -1),
        )
        self.grid = {}
        for i, q in enumerate(c):
            self.grid.setdefault((int(q[0] // 40), int(q[1] // 40)), []).append(i)
        xs, ys = [q[0] for q in c], [q[1] for q in c]
        self.bb = (min(xs), min(ys), max(xs), max(ys))
        self.name = next(
            (
                f["properties"]["Name"]
                for f in feats
                if (f.get("properties") or {}).get("Name")
            ),
            "Custom circuit",
        )
        self.blds = []
        self.lamps = []
        pal = [(30, 38, 64), (40, 30, 64), (26, 50, 60), (52, 40, 60), (36, 42, 56)]
        neon = [(255, 61, 154), (53, 224, 255), (255, 179, 71), (140, 255, 106)]
        light = (-0.7, -0.7)
        for i in range(0, N, 4):
            for s in (-1, 1):
                w, d = 12 + random.random() * 18, 12 + random.random() * 18
                o = HALF + 10 + w / 2 + random.random() * 30
                x, y = c[i][0] - self.ty[i] * s * o, c[i][1] + self.tx[i] * s * o
                if self.near(x, y, HALF + max(w, d) * 0.72 + 5):
                    continue
                ca, sa = math.cos(self.hd[i]), math.sin(self.hd[i])
                pts = [
                    (x + ca * u - sa * v, y + sa * u + ca * v)
                    for u, v in (
                        (-w / 2, -d / 2),
                        (w / 2, -d / 2),
                        (w / 2, d / 2),
                        (-w / 2, d / 2),
                    )
                ]
                sh = []
                for k in range(4):
                    a, b = pts[k], pts[(k + 1) % 4]
                    mx, my = (a[0] + b[0]) / 2 - x, (a[1] + b[1]) / 2 - y
                    l = math.hypot(mx, my) or 1
                    sh.append(0.4 + 0.5 * max(0, (mx * light[0] + my * light[1]) / l))
                self.blds.append(
                    (
                        x,
                        y,
                        pts,
                        random.choice(pal),
                        random.choice(neon) if random.random() < 0.4 else None,
                        8 + random.random() * 50,
                        sh,
                    )
                )
        for i in range(0, N, 10):
            s = 1 if (i // 10) % 2 else -1
            q = self.bl[i] if s > 0 else self.br[i]
            self.lamps.append(
                (q[0], q[1], (255, 61, 154) if (i // 20) % 2 else (53, 224, 255))
            )

    def near(self, x, y, r):
        k = math.ceil(r / 40)
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                for m in self.grid.get((int(x // 40) + i, int(y // 40) + j), ()):
                    if math.hypot(self.c[m][0] - x, self.c[m][1] - y) < r:
                        return True
        return False


# ---------------------------------------------------------------- cars
class Car:
    def __init__(s, g, cid, idx, lane, skill, stats, body, col):
        s.g, s.id, s.idx, s.lane, s.skill, s.m, s.body, s.col, s.ai = (
            g,
            cid,
            idx,
            lane,
            skill,
            stats,
            body,
            col,
            cid > 0,
        )
        t = g.track
        s.x = t.c[idx][0] - t.ty[idx] * lane
        s.y = t.c[idx][1] + t.tx[idx] * lane
        s.a = t.hd[idx]
        s.vx = s.vy = s.steer = s.vf = s.vl = 0.0
        s.laps = -1
        s.fin = None
        s.brake = False
        s.skid = False
        s.pw = None
        s.best = 1e9
        s.ls = 0.0
        s.prog = -t.N + idx

    def step(s, dt, st, th, hs):
        t, N, m = s.g.track, s.g.track.N, s.m
        s.steer += (st - s.steer) * min(1, 8 * dt)
        fx, fy = math.cos(s.a), math.sin(s.a)
        vf = s.vx * fx + s.vy * fy
        vl = -s.vx * fy + s.vy * fx
        s.skid = abs(vl) > 3.5 or (hs and vf > 8)
        acc = 0.0
        s.brake = False
        if th > 0:
            acc = m["acc"] * th * max(0, 1 - vf / m["vmax"])
        elif th < 0:
            if vf > 1:
                acc = 30 * th
                s.brake = True
            else:
                acc = 9 * th
        acc -= vf * 0.03 + vf * abs(vf) * 0.0006
        vf += acc * dt
        if hs:
            vf *= math.exp(-0.35 * dt)
        vl *= math.exp(-(1.6 if hs else m["grip"]) * dt)
        s.a += (
            vf
            / s.body["wb"]
            * math.tan(s.steer * m["steer"] / (1 + (vf / 16) ** 2))
            * (1.5 if hs else 1)
            * dt
        )
        fx, fy = math.cos(s.a), math.sin(s.a)
        s.vx, s.vy = fx * vf - fy * vl, fy * vf + fx * vl
        s.vf = vf
        s.vl = vl
        s.x += s.vx * dt
        s.y += s.vy * dt
        b, bi = 1e18, s.idx
        for k in range(-30, 31):
            j = (s.idx + k) % N
            d = (t.c[j][0] - s.x) ** 2 + (t.c[j][1] - s.y) ** 2
            if d < b:
                b, bi = d, j
        if s.idx > N * 0.75 and bi < N * 0.25:
            s.laps += 1
            s.g.on_lap(s)
        elif s.idx < N * 0.25 and bi > N * 0.75:
            s.laps -= 1
        s.idx = bi
        s.prog = s.laps * N + bi
        d = math.sqrt(b)
        if d > HALF:
            nx, ny = (s.x - t.c[bi][0]) / d, (s.y - t.c[bi][1]) / d
            s.x, s.y = t.c[bi][0] + nx * HALF, t.c[bi][1] + ny * HALF
            vn = s.vx * nx + s.vy * ny
            if vn > 0:
                s.vx = (s.vx - nx * vn * 1.4) * 0.98
                s.vy = (s.vy - ny * vn * 1.4) * 0.98

    def drive(s, dt):
        t, N, i = s.g.track, s.g.track.N, s.idx
        j = (i + 6 + int(max(0, s.vf) * 0.25)) % N
        e = wrap(
            math.atan2(
                t.c[j][1] + t.tx[j] * s.lane - s.y, t.c[j][0] - t.ty[j] * s.lane - s.x
            )
            - s.a
        )
        m = min(t.vmax[(i + k) % N] + k * 2.5 for k in range(0, 27, 2))
        tg = min(m, s.m["vmax"]) * s.skill
        s.step(dt, clamp(e * 2, -1, 1), clamp((tg - s.vf) * 0.4, -1, 1), False)


# ---------------------------------------------------------------- sprites
K = 24  # sprite pixels per metre


def make_car(m, col, brake):
    """Top-down sprite in real metres (+x = forward) from the model's real length/width/wheelbase."""
    L, Wd, wb, sp = m["L"], m["Wd"], m["wb"], m["spec"]
    hl, hw = L / 2, Wd / 2
    sf = pygame.Surface((int(5.2 * K), int(2.5 * K)), pygame.SRCALPHA)
    cx, cy = sf.get_width() / 2, sf.get_height() / 2
    X = lambda x: cx + x * K
    Y = lambda y: cy + y * K
    R = lambda x, y, w, h, c, r=0: pygame.draw.rect(
        sf, c, (X(x), Y(y), w * K, h * K), border_radius=int(r * K)
    )
    P = lambda pts, c: pygame.draw.polygon(sf, c, [(X(x), Y(y)) for x, y in pts])
    E = lambda x, y, w, h, c: pygame.draw.ellipse(sf, c, (X(x), Y(y), w * K, h * K))
    dark = (21, 23, 27)
    lite = lighten(col, 20)
    glass = (27, 40, 56)
    seam = tuple(int(v * 0.6) for v in col)
    wf, wt, re, rg = sp["cab"]
    g = sp["gw"] * hw
    for x in (wb / 2, -wb / 2):
        for s_ in (-1, 1):
            R(
                x - 0.33,
                s_ * (hw - 0.05) - m["tw"] / 2,
                0.66,
                m["tw"],
                (13, 14, 16),
                0.05,
            )
    top = [(xf * hl, -wf_ * hw) for xf, wf_ in sp["prof"]]
    P(top + [(x, -y) for x, y in reversed(top)], col)
    R(wf, -hw * 0.82, hl - 0.25 - wf, hw * 1.64, lite, 0.1)
    R(-hl + 0.2, -hw * 0.8, rg + hl - 0.2, hw * 1.6, lite, 0.1)
    if sp.get("bulge"):
        R(wf + 0.1, -0.2, hl - 0.45 - wf, 0.4, lighten(col, 38), 0.08)
    if m["id"] == "fd":
        for s_ in (-1, 1):
            R(1.15, s_ * 0.38 - 0.04, 0.45, 0.08, dark, 0.02)
    if sp.get("open"):
        wt_ = wf - 0.14
        P([(wf, -g), (wt_, -g * 0.96), (wt_, g * 0.96), (wf, g)], (60, 74, 92))
        R(rg, -g * 0.88, wt_ - rg, g * 1.76, (24, 24, 28), 0.12)
        for s_ in (-1, 1):
            R(wt_ - 0.62, s_ * 0.36 - 0.2, 0.5, 0.4, (52, 52, 58), 0.1)
            E(wt_ - 0.8, s_ * 0.36 - 0.1, 0.18, 0.2, (74, 74, 82))
            E(rg + 0.06, s_ * 0.4 - 0.08, 0.16, 0.16, (150, 152, 160))
        R(rg + 0.1, -0.4, 0.08, 0.8, (120, 122, 130))
    else:
        r_ = g * sp.get("rf", 0.92)
        P([(wf, -g), (wt, -r_), (wt, r_), (wf, g)], glass)
        P([(re, -r_), (rg, -g * 0.9), (rg, g * 0.9), (re, r_)], glass)
        R(re, -r_, wt - re, 2 * r_, lite, 0.08)
        R(re + 0.1, -r_ * 0.8, wt - re - 0.2, 1.6 * r_, lighten(col, 10), 0.06)
        for dx in sp.get("doors", ()):
            R(dx, -hw * 0.98, 0.03, hw * 1.96, seam)
    for s_ in (-1, 1):
        R(wf - 0.25, s_ * hw * 0.96 - 0.07, 0.2, 0.14, dark)
    if sp.get("bump"):
        R(hl - 0.12, -hw * 0.97, 0.16, hw * 1.94, dark, 0.06)
        R(-hl - 0.04, -hw * 0.97, 0.16, hw * 1.94, dark, 0.06)
    else:
        R(hl - 0.1, -hw * 0.3, 0.08, hw * 0.6, (30, 32, 36), 0.03)
    lamp = (255, 246, 216)
    amber = (255, 154, 26)
    tl = (255, 42, 42) if brake else (143, 22, 22)
    fl = sp["fl"]
    for s_ in (-1, 1):
        yc = s_ * hw * 0.66
        if fl == "rect":
            R(hl - 0.2, yc - 0.16, 0.16, 0.32, lamp)
        elif fl == "wedge":
            P(
                [
                    (hl - 0.38, yc - 0.14),
                    (hl - 0.06, yc - 0.06),
                    (hl - 0.06, yc + 0.14),
                    (hl - 0.38, yc + 0.14),
                ],
                lamp,
            )
        elif fl == "slim":
            R(hl - 0.3, yc - 0.09, 0.3, 0.18, lamp, 0.08)
        else:
            E(hl - 0.4, yc - 0.2, 0.32, 0.4, lamp)
        R(hl - 0.06, s_ * hw * 0.9 - 0.05, 0.07, 0.1, amber)
        if sp["tl"] == "rect":
            R(-hl, s_ * hw * 0.66 - 0.16, 0.12, 0.32, tl)
        elif sp["tl"] == "round":
            for f_ in (0.72, 0.48):
                E(-hl + 0.01, s_ * hw * f_ - 0.1, 0.15, 0.2, tl)
        else:
            R(-hl + 0.02, s_ * hw * 0.62 - 0.2, 0.1, 0.4, tl, 0.04)
    if sp.get("wing"):
        R(-hl + 0.1, -hw * 0.84, 0.3, hw * 1.68, dark, 0.05)
    return sf


def make_shadow(m):
    sf = pygame.Surface((int(5.2 * K), int(2.5 * K)), pygame.SRCALPHA)
    pygame.draw.rect(
        sf,
        (0, 0, 0, 110),
        (
            sf.get_width() / 2 - m["L"] / 2 * K,
            sf.get_height() / 2 - m["Wd"] / 2 * K,
            m["L"] * K,
            m["Wd"] * K,
        ),
        border_radius=int(0.4 * K),
    )
    return sf


def make_glow(col, r=48):
    sf = pygame.Surface((2 * r, 2 * r))
    for x in range(2 * r):
        for y in range(2 * r):
            d = math.hypot(x - r, y - r) / r
            f = max(0, 1 - d) ** 2 * 0.75
            sf.set_at((x, y), (int(col[0] * f), int(col[1] * f), int(col[2] * f)))
    return sf


def make_cone():
    Wd, Hd = 160, 90
    sf = pygame.Surface((Wd, Hd))
    for x in range(Wd):
        hw = 6 + x * 0.26
        for y in range(Hd):
            dy = abs(y - Hd / 2)
            f = max(0, 1 - dy / hw) * (1 - x / Wd) ** 1.4 * 0.5
            sf.set_at((x, y), (int(255 * f), int(240 * f), int(200 * f)))
    return sf


def make_vignette(w, h):
    sm = pygame.Surface((48, 48), pygame.SRCALPHA)
    for x in range(48):
        for y in range(48):
            d = math.hypot((x - 23.5) / 24, (y - 23.5) / 24)
            sm.set_at((x, y), (0, 0, 8, int(clamp((d - 0.55) * 230, 0, 170))))
    return pygame.transform.smoothscale(sm, (w, h))


# ---------------------------------------------------------------- game
class Game:
    def __init__(s, path):
        pygame.init()
        s.scr = pygame.display.set_mode((1100, 700), pygame.RESIZABLE)
        pygame.display.set_caption("Neon Strip GP")
        s.f1, s.f2, s.f3 = (
            pygame.font.SysFont("arial", 34, True),
            pygame.font.SysFont("arial", 20, True),
            pygame.font.SysFont("arial", 140, True),
        )
        s.sv = load_save()
        s.sprites = {}
        s.shadows = {}
        s.glows = {}
        s.cone = make_cone()
        s.vig = None
        s.vsz = None
        s.laps = 2
        s.state = "menu"
        s.cars = []
        s.me = None
        s.cnt = 0
        s.t0 = 0
        s.go = 0
        s.cam = [0.0, 0.0]
        s.ca = 0.0
        s.dt = 0.016
        s.skids = deque(maxlen=900)
        s.gi = 0
        s.result = None
        s.mi = 0.0
        s.tick = 0.0
        s.load(path)

    def load(s, path):
        try:
            with open(path, encoding="utf-8") as f:
                s.track = Track(json.load(f))
        except Exception as e:
            print("Could not load", path, e)
            if not hasattr(s, "track"):
                raise
            return
        s.state = "menu"
        s.cars = []
        s.me = None
        s.skids.clear()
        b = s.track.bb
        s.sc = min(240 / (b[2] - b[0] + 1), 240 / (b[3] - b[1] + 1))
        s.mm = pygame.Surface((260, 260), pygame.SRCALPHA)
        s.mm.fill((0, 0, 0, 140))
        pygame.draw.lines(s.mm, (138, 147, 176), True, [s.mp(q) for q in s.track.c], 3)

    def mp(s, q):
        b = s.track.bb
        return (10 + (q[0] - b[0]) * s.sc, 10 + (q[1] - b[1]) * s.sc)

    def rank(s):
        return sorted(
            s.cars, key=lambda c: -(1e9 - c.fin) if c.fin is not None else -c.prog
        )

    def sprite(s, m, col, brake):
        k = (m["id"], col, brake)
        if k not in s.sprites:
            s.sprites[k] = make_car(m, col, brake)
        return s.sprites[k]

    def start(s):
        N = s.track.N
        s.cars = []
        s.skids.clear()
        s.result = None
        pm = BYID[s.sv["car"]]
        for k, cid in enumerate([1, 2, 3, 0, 4, 5]):
            lane = 4.5 if k % 2 else -4.5
            idx = (N - 3 - k * 3) % N
            if cid == 0:
                c = Car(s, 0, idx, lane, 1.0, pm, pm, pm["color"])
                s.me = c
            else:
                c = Car(
                    s,
                    cid,
                    idx,
                    lane,
                    0.82 + random.random() * 0.1,
                    AI_STATS,
                    MODELS[AI_BODY[cid]],
                    COLS[cid],
                )
            s.cars.append(c)
        s.state = "count"
        s.cnt = 3.2
        s.cam = [s.me.x, s.me.y]
        s.ca = s.me.a

    def on_lap(s, c):
        if s.state != "race" or c.laps < 1:
            return
        t = (pygame.time.get_ticks() - s.t0) / 1000
        c.best = min(c.best, t - c.ls)
        c.ls = t
        if c.laps >= s.laps and c.fin is None:
            c.fin = t
            c.ai = True
            if c is s.me:
                s.state = "done"
                s.payout()

    def payout(s):
        pos = s.rank().index(s.me)
        prize = PRIZE[pos] * s.laps
        others = [c.best for c in s.cars if c is not s.me]
        fl = 500 if s.me.best < 1e8 and s.me.best < min(others) else 0
        s.result = dict(pos=pos + 1, prize=prize, fl=fl)
        d = s.sv
        d["money"] += prize + fl
        d["races"] += 1
        d["wins"] += 1 if pos == 0 else 0
        write_save(d)

    def update(s, dt):
        k = pygame.key.get_pressed()
        if s.state == "count":
            s.cnt -= dt
            if s.cnt <= 0:
                s.state = "race"
                s.t0 = pygame.time.get_ticks()
                s.go = s.t0 + 800
        for _ in range(2):
            h = dt / 2
            for c in s.cars:
                if s.state == "count":
                    c.step(h, 0, 0, True)
                elif c.ai:
                    c.drive(h)
                else:
                    st = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (
                        k[pygame.K_LEFT] or k[pygame.K_a]
                    )
                    th = (k[pygame.K_UP] or k[pygame.K_w]) - (
                        k[pygame.K_DOWN] or k[pygame.K_s]
                    )
                    c.step(h, st, th, k[pygame.K_SPACE])
            for i, a in enumerate(s.cars):
                for b in s.cars[i + 1 :]:
                    dx, dy = b.x - a.x, b.y - a.y
                    d = math.hypot(dx, dy)
                    if 0.01 < d < 3.8:
                        nx, ny, p = dx / d, dy / d, (3.8 - d) / 2
                        a.x -= nx * p
                        a.y -= ny * p
                        b.x += nx * p
                        b.y += ny * p
                        rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                        if rv < 0:
                            a.vx += nx * rv * 0.5
                            a.vy += ny * rv * 0.5
                            b.vx -= nx * rv * 0.5
                            b.vy -= ny * rv * 0.5
        for c in s.cars:
            if c.skid and s.state != "count":
                fx, fy = math.cos(c.a), math.sin(c.a)
                hw = c.body["Wd"] * 0.42
                rx_ = c.body["wb"] / 2
                cur = (
                    c.x - fx * rx_ - fy * hw,
                    c.y - fy * rx_ + fx * hw,
                    c.x - fx * rx_ + fy * hw,
                    c.y - fy * rx_ - fx * hw,
                )
                if c.pw:
                    s.skids.append(((c.pw[0], c.pw[1]), (cur[0], cur[1])))
                    s.skids.append(((c.pw[2], c.pw[3]), (cur[2], cur[3])))
                c.pw = cur
            else:
                c.pw = None

    # ------------------------------------------------------------ drawing
    def txt(s, f, m, col, pos, ctr=False):
        sh = f.render(m, True, (0, 0, 0))
        im = f.render(m, True, col)
        r = im.get_rect(center=pos) if ctr else im.get_rect(topleft=pos)
        s.scr.blit(sh, r.move(2, 2))
        s.scr.blit(im, r)

    def glow(s, col, size):
        k = (col, size)
        if k not in s.glows:
            s.glows[k] = pygame.transform.smoothscale(make_glow(col), (size, size))
        return s.glows[k]

    def draw_world(s):
        t, scr = s.track, s.scr
        w, h = scr.get_size()
        me = s.me
        dt = s.dt
        if me:
            sp = math.hypot(me.vx, me.vy)
            tx_, ty_ = me.x + me.vx * 0.15, me.y + me.vy * 0.15
            s.cam[0] += (tx_ - s.cam[0]) * min(1, 10 * dt)
            s.cam[1] += (ty_ - s.cam[1]) * min(1, 10 * dt)
            s.ca += wrap(me.a - s.ca) * min(1, 5 * dt)
        else:
            sp = 30
            s.mi = (s.mi + 7.5 * dt) % t.N
            i = int(s.mi)
            s.cam = [t.c[i][0], t.c[i][1]]
            s.ca = t.hd[i]
        sc = (6.5 - sp * 0.03) * clamp(min(w, h) / 800, 0.6, 1.5)
        cx, cy = s.cam
        ax, ay = w / 2, h * 0.68
        th = -math.pi / 2 - s.ca
        ct, st = math.cos(th), math.sin(th)

        def T(p):
            dx, dy = p[0] - cx, p[1] - cy
            return (ax + (dx * ct - dy * st) * sc, ay + (dx * st + dy * ct) * sc)

        scr.fill((14, 17, 26))
        R = math.hypot(w, h) / sc * 0.7 + 40
        g0x, g0y = int(cx // 50) * 50, int(cy // 50) * 50
        for q in range(-int(R // 50) - 1, int(R // 50) + 2):
            pygame.draw.line(
                scr,
                (22, 27, 40),
                T((g0x + q * 50, cy - R)),
                T((g0x + q * 50, cy + R)),
                1,
            )
            pygame.draw.line(
                scr,
                (22, 27, 40),
                T((cx - R, g0y + q * 50)),
                T((cx + R, g0y + q * 50)),
                1,
            )
        vis = [
            i for i in range(t.N) if abs(t.c[i][0] - cx) < R and abs(t.c[i][1] - cy) < R
        ]
        for i in vis:
            j = (i + 1) % t.N
            pygame.draw.polygon(
                scr,
                (214, 52, 58) if (i // 2) % 2 else (217, 220, 227),
                [T(t.bl[i]), T(t.bl[j]), T(t.br[j]), T(t.br[i])],
            )
        for i in vis:
            j = (i + 1) % t.N
            pygame.draw.polygon(
                scr, (40, 42, 50), [T(t.al[i]), T(t.al[j]), T(t.ar[j]), T(t.ar[i])]
            )
            if i % 3 == 0:
                pygame.draw.line(
                    scr, (110, 112, 118), T(t.c[i]), T(t.c[j]), max(1, int(0.35 * sc))
                )
        for a, b in s.skids:
            if abs(a[0] - cx) < R and abs(a[1] - cy) < R:
                pygame.draw.line(scr, (22, 22, 26), T(a), T(b), max(1, int(0.35 * sc)))
        ca_, sa_ = math.cos(t.hd[0]), math.sin(t.hd[0])
        for r in range(2):
            for k in range(-7, 7):
                u0, v0 = r * 1.5 - 0.75, k * 1.5
                pts = [
                    (t.c[0][0] + ca_ * u - sa_ * v, t.c[0][1] + sa_ * u + ca_ * v)
                    for u, v in (
                        (u0, v0),
                        (u0 + 1.5, v0),
                        (u0 + 1.5, v0 + 1.5),
                        (u0, v0 + 1.5),
                    )
                ]
                pygame.draw.polygon(
                    scr,
                    (255, 255, 255) if (r + k) & 1 else (17, 17, 17),
                    [T(p) for p in pts],
                )
        for c in s.cars:  # shadows, then headlights
            key = c.body["id"]
            if key not in s.shadows:
                s.shadows[key] = make_shadow(c.body)
            im = pygame.transform.rotozoom(
                s.shadows[key], -math.degrees(c.a + th), sc / K
            )
            p = T((c.x, c.y))
            scr.blit(im, im.get_rect(center=(p[0] + 3 * sc / 6, p[1] + 4 * sc / 6)))
        for c in s.cars:
            fx, fy = math.cos(c.a), math.sin(c.a)
            im = pygame.transform.rotozoom(s.cone, -math.degrees(c.a + th), sc / 8)
            scr.blit(
                im,
                im.get_rect(center=T((c.x + fx * 12, c.y + fy * 12))),
                special_flags=pygame.BLEND_RGB_ADD,
            )
        bl = [b for b in t.blds if abs(b[0] - cx) < R and abs(b[1] - cy) < R]
        bl.sort(key=lambda b: -((b[0] - cx) ** 2 + (b[1] - cy) ** 2))
        for x, y, pts, col, neon, hg, shs in bl:
            base = [T(p) for p in pts]
            k = 1 + hg * 0.0045
            roof = [(ax + (q[0] - ax) * k, ay + (q[1] - ay) * k) for q in base]
            for e in range(4):
                f = shs[e]
                pygame.draw.polygon(
                    scr,
                    tuple(int(v * f) for v in col),
                    [base[e], base[(e + 1) % 4], roof[(e + 1) % 4], roof[e]],
                )
            pygame.draw.polygon(scr, lighten(col, 22), roof)
            mx, my = sum(q[0] for q in roof) / 4, sum(q[1] for q in roof) / 4
            pygame.draw.polygon(
                scr,
                lighten(col, 8),
                [(mx + (q[0] - mx) * 0.6, my + (q[1] - my) * 0.6) for q in roof],
            )
            if neon:
                pygame.draw.polygon(scr, neon, roof, max(1, int(0.5 * sc)))
        for c in [c for c in s.cars if c is not me] + ([me] if me else []):
            im = pygame.transform.rotozoom(
                s.sprite(c.body, c.col, c.brake), -math.degrees(c.a + th), sc / K
            )
            scr.blit(im, im.get_rect(center=T((c.x, c.y))))
        gs = int(18 * sc) // 8 * 8 + 8
        for x, y, col in t.lamps:
            if abs(x - cx) < R and abs(y - cy) < R:
                scr.blit(
                    s.glow(col, gs),
                    s.glow(col, gs).get_rect(center=T((x, y))),
                    special_flags=pygame.BLEND_RGB_ADD,
                )
        if s.vsz != (w, h):
            s.vig = make_vignette(w, h)
            s.vsz = (w, h)
        scr.blit(s.vig, (0, 0))

    def draw_hud(s):
        scr = s.scr
        w, h = scr.get_size()
        me = s.me
        scr.blit(s.mm, (w - 270, 8))
        for c in s.cars:
            p = s.mp((c.x, c.y))
            pygame.draw.circle(
                scr,
                (255, 179, 71) if c is me else COLS[c.id],
                (w - 270 + p[0], 8 + p[1]),
                6 if c is me else 4,
            )
        if not me:
            return
        now = pygame.time.get_ticks()
        sp = math.hypot(me.vx, me.vy)
        s.txt(s.f1, f"{int(sp * 3.6)} km/h", (255, 179, 71), (14, 10))
        pygame.draw.rect(scr, (30, 34, 48), (14, 52, 200, 8), border_radius=4)
        pygame.draw.rect(
            scr,
            (255, 179, 71),
            (14, 52, 200 * clamp(sp / me.m["vmax"], 0, 1), 8),
            border_radius=4,
        )
        s.txt(
            s.f2,
            f"Lap {clamp(me.laps + 1, 1, s.laps)} / {s.laps}   P{s.rank().index(me) + 1} / {len(s.cars)}",
            (238, 241, 248),
            (14, 68),
        )
        s.txt(s.f2, f"$ {s.sv['money']:,}", (140, 255, 106), (14, 94))
        if s.state == "race":
            s.txt(
                s.f2,
                f"{(now - s.t0) / 1000:.1f} s"
                + (f"   best {me.best:.1f}" if me.best < 1e8 else ""),
                (200, 205, 220),
                (14, 120),
            )
        if s.state == "count":
            s.txt(s.f3, str(math.ceil(s.cnt)), (255, 179, 71), (w / 2, h / 2), True)
        elif s.state == "race" and pygame.time.get_ticks() < s.go:
            s.txt(s.f3, "GO!", (255, 179, 71), (w / 2, h / 2), True)

    def overlay(s, a=200):
        w, h = s.scr.get_size()
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((11, 13, 20, a))
        s.scr.blit(ov, (0, 0))

    def draw_menu(s):
        w, h = s.scr.get_size()
        s.overlay(150)
        t = s.track
        pm = BYID[s.sv["car"]]
        L = (238, 241, 248)
        lines = [
            ("NEON STRIP GP", s.f1, (255, 179, 71)),
            (f"{t.name} - {t.N * DS / 1000:.1f} km", s.f2, L),
            (f"Car: {pm['name']}     $ {s.sv['money']:,}", s.f2, (140, 255, 106)),
            (f"Laps: {s.laps}  (press 1 / 2 / 3)", s.f2, L),
            ("Enter = start race     G = garage", s.f2, L),
            (
                "Up/W gas, Down/S brake, Left/Right steer, Space handbrake, R reset",
                s.f2,
                (170, 176, 196),
            ),
            ("Drop a .geojson file on the window to race on it", s.f2, (170, 176, 196)),
        ]
        for i, (m, f, c) in enumerate(lines):
            s.txt(f, m, c, (w / 2, h / 2 - 120 + i * 38), True)

    def draw_done(s):
        w, h = s.scr.get_size()
        s.overlay(190)
        r = s.result
        s.txt(s.f1, "RESULTS", (255, 179, 71), (w / 2, h / 2 - 190), True)
        for i, c in enumerate(s.rank()):
            s.txt(
                s.f2,
                f"{i + 1}. {NAMES[c.id]}"
                + (f" - {c.fin:.1f} s" if c.fin is not None else ""),
                (238, 241, 248),
                (w / 2, h / 2 - 140 + i * 28),
                True,
            )
        s.txt(
            s.f2,
            f"Prize P{r['pos']}: ${r['prize']:,}"
            + (f"   + fastest lap ${r['fl']:,}" if r["fl"] else ""),
            (140, 255, 106),
            (w / 2, h / 2 + 50),
            True,
        )
        s.txt(
            s.f2,
            f"Balance: ${s.sv['money']:,}",
            (140, 255, 106),
            (w / 2, h / 2 + 80),
            True,
        )
        s.txt(
            s.f2,
            "Enter = race again     G = garage",
            (238, 241, 248),
            (w / 2, h / 2 + 125),
            True,
        )

    def draw_garage(s):
        w, h = s.scr.get_size()
        scr = s.scr
        scr.fill((12, 14, 22))
        m = MODELS[s.gi]
        sv = s.sv
        owned = m["id"] in sv["owned"]
        eq = sv["car"] == m["id"]
        L = (238, 241, 248)
        s.txt(s.f1, "GARAGE", (255, 179, 71), (w / 2, 40), True)
        s.txt(s.f2, f"$ {sv['money']:,}", (140, 255, 106), (w / 2, 80), True)
        pygame.draw.ellipse(scr, (24, 28, 42), (w / 2 - 200, h * 0.36, 400, 90))
        im = pygame.transform.rotozoom(
            s.sprite(m, m["color"], False), -(s.tick * 35) % 360, 2.6
        )
        scr.blit(im, im.get_rect(center=(w / 2, h * 0.36 + 45)))
        s.txt(s.f1, m["name"], L, (w / 2, h * 0.36 + 118), True)
        s.txt(
            s.f2,
            f"{m['tag']}  -  {m['L']:.2f} x {m['Wd']:.2f} m",
            (170, 176, 196),
            (w / 2, h * 0.36 + 152),
            True,
        )
        for i, (lab, key) in enumerate(
            (
                ("Top speed", "vmax"),
                ("Acceleration", "acc"),
                ("Handling", "steer"),
                ("Grip", "grip"),
            )
        ):
            y = h * 0.36 + 185 + i * 30
            fr = m[key] / max(x[key] for x in MODELS)
            s.txt(s.f2, lab, (170, 176, 196), (w / 2 - 230, y))
            pygame.draw.rect(
                scr, (30, 34, 48), (w / 2 - 70, y + 4, 300, 14), border_radius=6
            )
            pygame.draw.rect(
                scr, (255, 179, 71), (w / 2 - 70, y + 4, 300 * fr, 14), border_radius=6
            )
        s.txt(s.f2, f"{int(m['vmax'] * 3.6)} km/h", L, (w / 2 + 245, h * 0.36 + 185))
        if eq:
            msg, col = "EQUIPPED", (140, 255, 106)
        elif owned:
            msg, col = "Owned - Enter to equip", L
        elif sv["money"] >= m["price"]:
            msg, col = f"Enter to buy for ${m['price']:,}", (255, 179, 71)
        else:
            msg, col = f"${m['price']:,} - not enough money", (255, 90, 90)
        s.txt(s.f1, msg, col, (w / 2, h - 90), True)
        s.txt(
            s.f2,
            f"<  {s.gi + 1} / {len(MODELS)}  >      Esc = back",
            (170, 176, 196),
            (w / 2, h - 45),
            True,
        )

    def garage_enter(s):
        m = MODELS[s.gi]
        sv = s.sv
        if m["id"] not in sv["owned"] and sv["money"] >= m["price"]:
            sv["money"] -= m["price"]
            sv["owned"].append(m["id"])
            sv["car"] = m["id"]
            write_save(sv)
        elif m["id"] in sv["owned"] and sv["car"] != m["id"]:
            sv["car"] = m["id"]
            write_save(sv)

    def run(s):
        clock = pygame.time.Clock()
        frames = int(os.environ.get("GAME_FRAMES", 0))
        n = 0
        while True:
            s.dt = dt = min(0.033, clock.tick(60) / 1000)
            s.tick += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.DROPFILE:
                    s.load(e.file)
                if e.type != pygame.KEYDOWN:
                    continue
                if e.key == pygame.K_ESCAPE:
                    if s.state == "garage":
                        s.state = "menu"
                    else:
                        return
                elif s.state == "garage":
                    if e.key in (pygame.K_RIGHT, pygame.K_d):
                        s.gi = (s.gi + 1) % len(MODELS)
                    elif e.key in (pygame.K_LEFT, pygame.K_a):
                        s.gi = (s.gi - 1) % len(MODELS)
                    elif e.key == pygame.K_RETURN:
                        s.garage_enter()
                elif e.key == pygame.K_g and s.state in ("menu", "done"):
                    s.state = "garage"
                    s.gi = MODELS.index(BYID[s.sv["car"]])
                elif e.key == pygame.K_RETURN and s.state in ("menu", "done"):
                    s.start()
                elif (
                    e.key in (pygame.K_1, pygame.K_2, pygame.K_3) and s.state == "menu"
                ):
                    s.laps = e.key - pygame.K_0
                elif e.key == pygame.K_r and s.state == "race":
                    m = s.me
                    m.x, m.y = s.track.c[m.idx]
                    m.a = s.track.hd[m.idx]
                    m.vx = m.vy = 0
            if s.state == "garage":
                s.draw_garage()
            else:
                if s.cars:
                    s.update(dt)
                s.draw_world()
                s.draw_hud()
                if s.state == "menu":
                    s.draw_menu()
                elif s.state == "done":
                    s.draw_done()
            pygame.display.flip()
            n += 1
            if frames and n == 5 and s.state == "menu":
                s.start()
            if frames and n >= frames:
                return


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    Game(
        sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "us-2023.geojson")
    ).run()
