#!/usr/bin/env python3
"""Neon Strip GP - top-down night street race on any GeoJSON circuit.
Run:  pip install pygame && python racing_game.py [track.geojson]
Keys: Up/W gas, Down/S brake, Left/Right/A/D steer, Space handbrake, R reset, 1/2/3 laps, Enter start. Drop a .geojson on the window to load it."""
import sys, os, json, math, random
import pygame

W, HALF, DS, VMAX, WB = 22.0, 12.5, 4.0, 62.0, 2.6
COLS = [(185, 157, 120), (196, 58, 58), (233, 233, 238), (59, 111, 209), (47, 158, 107), (58, 61, 70)]
NAMES = ["You", "Aiko", "Marco", "Zoe", "Ravi", "Lena"]
clamp = lambda v, a, b: max(a, min(b, v))


def resample(p, ds):
    n = len(p); L = [0.0]
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]; L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    tot = L[n]; M = round(tot / ds); out = []; j = 0
    for k in range(M):
        d = k * tot / M
        while L[j + 1] < d: j += 1
        a, b = p[j], p[(j + 1) % n]; t = (d - L[j]) / ((L[j + 1] - L[j]) or 1)
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def smooth(p, w):
    n = len(p); o = []
    for i in range(n):
        x = y = 0
        for k in range(-w, w + 1):
            q = p[(i + k) % n]; x += q[0]; y += q[1]
        o.append((x / (2 * w + 1), y / (2 * w + 1)))
    return o


class Track:
    def __init__(self, geo):
        lines = []
        feats = geo["features"] if geo.get("type") == "FeatureCollection" else [geo if geo.get("type") == "Feature" else {"geometry": geo}]
        for f in feats:
            m = f.get("geometry") or {}; t = m.get("type")
            if t == "LineString": lines.append(m["coordinates"])
            elif t == "MultiLineString": lines += m["coordinates"]
            elif t == "Polygon": lines.append(m["coordinates"][0])
            elif t == "MultiPolygon": lines.append(m["coordinates"][0][0])
        if not lines: raise ValueError("No line or polygon geometry found")
        co = max(lines, key=len)
        lat0 = sum(q[1] for q in co) / len(co); kx = 111320 * math.cos(math.radians(lat0))
        p = [((q[0] - co[0][0]) * kx, -(q[1] - co[0][1]) * 110574) for q in co]
        self.c = c = resample(smooth(smooth(resample(p, 3), 6), 6), DS); N = self.N = len(c)
        if N < 60: raise ValueError("Track too short")
        self.tx = []; self.ty = []; self.hd = []
        for i in range(N):
            a, b = c[i - 1], c[(i + 1) % N]; d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            self.tx.append((b[0] - a[0]) / d); self.ty.append((b[1] - a[1]) / d); self.hd.append(math.atan2(self.ty[-1], self.tx[-1]))
        self.vmax = []
        for i in range(N):
            d = self.hd[(i + 4) % N] - self.hd[i - 4]; d = math.atan2(math.sin(d), math.cos(d))
            self.vmax.append(clamp(math.sqrt(22 / max(abs(d) / (8 * DS), 1e-4)), 20, 80))
        edge = lambda h, s: [(c[i][0] - self.ty[i] * h * s, c[i][1] + self.tx[i] * h * s) for i in range(N)]
        self.bl, self.br, self.al, self.ar = edge(HALF + 1, 1), edge(HALF + 1, -1), edge(W / 2, 1), edge(W / 2, -1)
        self.grid = {}
        for i, q in enumerate(c): self.grid.setdefault((int(q[0] // 40), int(q[1] // 40)), []).append(i)
        xs, ys = [q[0] for q in c], [q[1] for q in c]; self.bb = (min(xs), min(ys), max(xs), max(ys))
        self.name = next((f["properties"]["Name"] for f in feats if f.get("properties", {}).get("Name")), "Custom circuit")
        self.blds = []
        pal = [(26, 32, 54), (34, 26, 54), (22, 42, 51), (43, 34, 51), (31, 36, 48)]
        neon = [(255, 61, 154), (53, 224, 255), (255, 179, 71), (140, 255, 106)]
        for i in range(0, N, 4):
            for s in (-1, 1):
                w, d = 12 + random.random() * 18, 12 + random.random() * 18
                o = HALF + 10 + w / 2 + random.random() * 30
                x, y = c[i][0] - self.ty[i] * s * o, c[i][1] + self.tx[i] * s * o
                if self.near(x, y, HALF + max(w, d) * .72 + 5): continue
                ca, sa = math.cos(self.hd[i]), math.sin(self.hd[i])
                pts = [(x + ca * u - sa * v, y + sa * u + ca * v) for u, v in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]
                self.blds.append((x, y, pts, random.choice(pal), random.choice(neon) if random.random() < .4 else None))

    def near(self, x, y, r):
        k = math.ceil(r / 40)
        for i in range(-k, k + 1):
            for j in range(-k, k + 1):
                for m in self.grid.get((int(x // 40) + i, int(y // 40) + j), ()):
                    if math.hypot(self.c[m][0] - x, self.c[m][1] - y) < r: return True
        return False


class Car:
    def __init__(s, g, cid, idx, lane, skill):
        s.g, s.id, s.idx, s.lane, s.skill, s.ai = g, cid, idx, lane, skill, cid > 0
        t = g.track; s.x = t.c[idx][0] - t.ty[idx] * lane; s.y = t.c[idx][1] + t.tx[idx] * lane; s.a = t.hd[idx]
        s.vx = s.vy = s.steer = s.vf = 0.0; s.laps = -1; s.fin = None; s.brake = False; s.best = 1e9; s.ls = 0.0; s.prog = -t.N + idx

    def step(s, dt, st, th, hs):
        t, N = s.g.track, s.g.track.N
        s.steer += (st - s.steer) * min(1, 8 * dt)
        fx, fy = math.cos(s.a), math.sin(s.a); vf = s.vx * fx + s.vy * fy; vl = -s.vx * fy + s.vy * fx
        acc = 0.0; s.brake = False
        if th > 0: acc = 13 * th * max(0, 1 - vf / VMAX)
        elif th < 0:
            if vf > 1: acc = 30 * th; s.brake = True
            else: acc = 9 * th
        acc -= vf * .03 + vf * abs(vf) * .0006; vf += acc * dt
        if hs: vf *= math.exp(-.35 * dt)
        vl *= math.exp(-(1.6 if hs else 8) * dt)
        s.a += vf / WB * math.tan(s.steer * .45 / (1 + (vf / 14) ** 2)) * (1.5 if hs else 1) * dt
        fx, fy = math.cos(s.a), math.sin(s.a)
        s.vx, s.vy = fx * vf - fy * vl, fy * vf + fx * vl; s.vf = vf; s.x += s.vx * dt; s.y += s.vy * dt
        b, bi = 1e18, s.idx
        for k in range(-30, 31):
            j = (s.idx + k) % N; d = (t.c[j][0] - s.x) ** 2 + (t.c[j][1] - s.y) ** 2
            if d < b: b, bi = d, j
        if s.idx > N * .75 and bi < N * .25: s.laps += 1; s.g.on_lap(s)
        elif s.idx < N * .25 and bi > N * .75: s.laps -= 1
        s.idx = bi; s.prog = s.laps * N + bi; d = math.sqrt(b)
        if d > HALF:
            nx, ny = (s.x - t.c[bi][0]) / d, (s.y - t.c[bi][1]) / d
            s.x, s.y = t.c[bi][0] + nx * HALF, t.c[bi][1] + ny * HALF
            vn = s.vx * nx + s.vy * ny
            if vn > 0: s.vx = (s.vx - nx * vn * 1.4) * .98; s.vy = (s.vy - ny * vn * 1.4) * .98

    def drive(s, dt):
        t, N, i = s.g.track, s.g.track.N, s.idx
        j = (i + 6 + int(max(0, s.vf) * .25)) % N
        e = math.atan2(t.c[j][1] + t.tx[j] * s.lane - s.y, t.c[j][0] - t.ty[j] * s.lane - s.x) - s.a
        e = math.atan2(math.sin(e), math.cos(e))
        m = min(t.vmax[(i + k) % N] + k * 2.5 for k in range(0, 27, 2))
        tg = min(m, VMAX) * s.skill
        s.step(dt, clamp(e * 2, -1, 1), clamp((tg - s.vf) * .4, -1, 1), False)


K = 24  # sprite pixels per metre


def make_car(col, brake):
    sf = pygame.Surface((int(4.8 * K), int(2.2 * K)), pygame.SRCALPHA); cx, cy = sf.get_width() / 2, sf.get_height() / 2
    R = lambda x, y, w, h, c, r=0: pygame.draw.rect(sf, c, (cx + x * K, cy + y * K, w * K, h * K), border_radius=int(r * K))
    P = lambda pts, c: pygame.draw.polygon(sf, c, [(cx + x * K, cy + y * K) for x, y in pts])
    for x, y in ((1.4, -.9), (1.4, .9), (-1.4, -.9), (-1.4, .9)): R(x - .34, y - .13, .68, .26, (13, 14, 16))
    R(-2.2, -.82, 4.4, 1.64, col, .3); lite = tuple(min(255, v + 25) for v in col); R(1, -.7, .95, 1.4, lite)
    R(1.95, -.86, .34, 1.72, (21, 23, 27), .1); R(-2.3, -.86, .34, 1.72, (21, 23, 27), .1); R(2.02, -.42, .1, .84, (36, 39, 44))
    R(1.96, -.74, .16, .3, (255, 246, 216)); R(1.96, .44, .16, .3, (255, 246, 216)); R(2.0, -.8, .12, .12, (255, 154, 26)); R(2.0, .68, .12, .12, (255, 154, 26))
    tl = (255, 42, 42) if brake else (143, 22, 22); R(-2.26, -.78, .12, .32, tl); R(-2.26, .46, .12, .32, tl)
    glass = (27, 36, 48); P([(1.05, -.7), (.5, -.64), (.5, .64), (1.05, .7)], glass); P([(-.85, -.62), (-1.3, -.7), (-1.3, .7), (-.85, .62)], glass)
    R(-.85, -.66, 1.35, 1.32, lite); R(.1, -.82, .04, 1.64, (0, 0, 0)); R(-.45, -.82, .04, 1.64, (0, 0, 0))
    R(.7, -.95, .25, .14, (17, 17, 17)); R(.7, .81, .25, .14, (17, 17, 17))
    return sf


class Game:
    def __init__(s, path):
        pygame.init(); s.scr = pygame.display.set_mode((1100, 700), pygame.RESIZABLE); pygame.display.set_caption("Neon Strip GP")
        s.f1, s.f2, s.f3 = pygame.font.SysFont("arial", 34, True), pygame.font.SysFont("arial", 20, True), pygame.font.SysFont("arial", 140, True)
        s.sprites = {}; s.laps = 2; s.state = "menu"; s.cars = []; s.me = None; s.cnt = 0; s.t0 = 0; s.cam = [0, 0]; s.load(path)

    def load(s, path):
        try:
            with open(path, encoding="utf-8") as f: s.track = Track(json.load(f))
        except Exception as e:
            print("Could not load", path, e)
            if not hasattr(s, "track"): raise
            return
        s.state = "menu"; s.cars = []; s.me = None; b = s.track.bb; s.sc = min(240 / (b[2] - b[0] + 1), 240 / (b[3] - b[1] + 1))
        s.mm = pygame.Surface((260, 260), pygame.SRCALPHA); s.mm.fill((0, 0, 0, 140))
        pygame.draw.lines(s.mm, (138, 147, 176), True, [s.mp(q) for q in s.track.c], 3)

    def mp(s, q): b = s.track.bb; return (10 + (q[0] - b[0]) * s.sc, 10 + (q[1] - b[1]) * s.sc)
    def rank(s): return sorted(s.cars, key=lambda c: -(1e9 - c.fin) if c.fin is not None else -c.prog)

    def start(s):
        N = s.track.N; s.cars = []
        for k, cid in enumerate([1, 2, 3, 0, 4, 5]):
            c = Car(s, cid, (N - 3 - k * 3) % N, 4.5 if k % 2 else -4.5, 1.0 if cid == 0 else .86 + random.random() * .1); s.cars.append(c)
            if cid == 0: s.me = c
        s.state = "count"; s.cnt = 3.2; s.cam = [s.me.x, s.me.y]

    def on_lap(s, c):
        if s.state != "race" or c.laps < 1: return
        t = (pygame.time.get_ticks() - s.t0) / 1000; c.best = min(c.best, t - c.ls); c.ls = t
        if c.laps >= s.laps and c.fin is None:
            c.fin = t; c.ai = True
            if c is s.me: s.state = "done"

    def update(s, dt):
        k = pygame.key.get_pressed()
        if s.state == "count":
            s.cnt -= dt
            if s.cnt <= 0: s.state = "race"; s.t0 = pygame.time.get_ticks(); s.go = s.t0 + 800
        for _ in range(2):
            h = dt / 2
            for c in s.cars:
                if s.state == "count": c.step(h, 0, 0, True)
                elif c.ai: c.drive(h)
                else:
                    st = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (k[pygame.K_LEFT] or k[pygame.K_a])
                    th = (k[pygame.K_UP] or k[pygame.K_w]) - (k[pygame.K_DOWN] or k[pygame.K_s])
                    c.step(h, st, th, k[pygame.K_SPACE])
            for i, a in enumerate(s.cars):
                for b in s.cars[i + 1:]:
                    dx, dy = b.x - a.x, b.y - a.y; d = math.hypot(dx, dy)
                    if .01 < d < 3.8:
                        nx, ny, p = dx / d, dy / d, (3.8 - d) / 2; a.x -= nx * p; a.y -= ny * p; b.x += nx * p; b.y += ny * p
                        rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                        if rv < 0: a.vx += nx * rv * .5; a.vy += ny * rv * .5; b.vx -= nx * rv * .5; b.vy -= ny * rv * .5

    def draw(s):
        t, scr = s.track, s.scr; w, h = scr.get_size(); me = s.me; fx, fy, vx, vy = (me.x, me.y, me.vx, me.vy) if me else (*t.c[0], 0, 0)
        sp = math.hypot(vx, vy); s.cam[0] += (fx + vx * .5 - s.cam[0]) * .12; s.cam[1] += (fy + vy * .5 - s.cam[1]) * .12
        sc = (7 - sp * .035) * clamp(min(w, h) / 800, .6, 1.5); cx, cy = s.cam
        T = lambda p: ((p[0] - cx) * sc + w / 2, (p[1] - cy) * sc + h / 2)
        scr.fill((16, 19, 28)); R = math.hypot(w, h) / sc / 2 + 40
        for x, y, pts, col, neon in t.blds:
            if abs(x - cx) > R or abs(y - cy) > R: continue
            pygame.draw.polygon(scr, (8, 9, 14), [T((p[0] + 3, p[1] + 3)) for p in pts]); q = [T(p) for p in pts]
            pygame.draw.polygon(scr, col, q)
            if neon: pygame.draw.polygon(scr, neon, q, max(1, int(.5 * sc)))
        vis = [i for i in range(t.N) if abs(t.c[i][0] - cx) < R and abs(t.c[i][1] - cy) < R]
        for i in vis:
            j = (i + 1) % t.N; pygame.draw.polygon(scr, (214, 52, 58) if (i // 2) % 2 else (217, 220, 227), [T(t.bl[i]), T(t.bl[j]), T(t.br[j]), T(t.br[i])])
        for i in vis:
            j = (i + 1) % t.N; pygame.draw.polygon(scr, (42, 44, 51), [T(t.al[i]), T(t.al[j]), T(t.ar[j]), T(t.ar[i])])
            if i % 3 == 0: pygame.draw.line(scr, (110, 112, 118), T(t.c[i]), T(t.c[j]), max(1, int(.35 * sc)))
        ca, sa = math.cos(t.hd[0]), math.sin(t.hd[0])
        for r in range(2):
            for k in range(-7, 7):
                u0, v0 = r * 1.5 - .75, k * 1.5; pts = [(t.c[0][0] + ca * u - sa * v, t.c[0][1] + sa * u + ca * v) for u, v in ((u0, v0), (u0 + 1.5, v0), (u0 + 1.5, v0 + 1.5), (u0, v0 + 1.5))]
                pygame.draw.polygon(scr, (255, 255, 255) if (r + k) & 1 else (17, 17, 17), [T(p) for p in pts])
        for c in [c for c in s.cars if c is not me] + ([me] if me else []):
            key = (c.id, c.brake)
            if key not in s.sprites: s.sprites[key] = make_car(COLS[c.id], c.brake)
            img = pygame.transform.rotozoom(s.sprites[key], -math.degrees(c.a), sc / K); scr.blit(img, img.get_rect(center=T((c.x, c.y))))
        scr.blit(s.mm, (w - 270, 8))
        for c in s.cars: p = s.mp((c.x, c.y)); pygame.draw.circle(scr, (255, 179, 71) if c is me else COLS[c.id], (w - 270 + p[0], 8 + p[1]), 6 if c is me else 4)
        txt = lambda f, m, col, pos, ctr=False: scr.blit(f.render(m, True, col), f.render(m, True, col).get_rect(center=pos) if ctr else pos)
        if me:
            now = pygame.time.get_ticks(); txt(s.f1, f"{int(sp * 3.6)} km/h", (255, 179, 71), (14, 10))
            txt(s.f2, f"Lap {clamp(me.laps + 1, 1, s.laps)} / {s.laps}   P{s.rank().index(me) + 1} / {len(s.cars)}", (238, 241, 248), (14, 52))
            if s.state == "race": txt(s.f2, f"{(now - s.t0) / 1000:.1f} s" + (f"   best {me.best:.1f}" if me.best < 1e8 else ""), (200, 205, 220), (14, 78))
            if s.state == "count": txt(s.f3, str(math.ceil(s.cnt)), (255, 179, 71), (w / 2, h / 2), True)
            elif s.state == "race" and now < getattr(s, "go", 0): txt(s.f3, "GO!", (255, 179, 71), (w / 2, h / 2), True)
        if s.state in ("menu", "done"):
            ov = pygame.Surface((w, h), pygame.SRCALPHA); ov.fill((11, 13, 20, 217)); scr.blit(ov, (0, 0)); L = (238, 241, 248)
            if s.state == "menu":
                lines = ["NEON STRIP GP", f"{t.name} - {t.N * DS / 1000:.1f} km", f"Laps: {s.laps}  (press 1 / 2 / 3)", "Enter = start", "Up/W gas, Down/S brake, Left/Right steer, Space handbrake, R reset", "Drop a .geojson file on the window to race on it"]
            else:
                lines = ["RESULTS"] + [f"{i + 1}. {NAMES[c.id]}" + (f" - {c.fin:.1f} s" if c.fin is not None else "") for i, c in enumerate(s.rank())] + ["", "Enter = race again"]
            for i, m in enumerate(lines): txt(s.f1 if i == 0 else s.f2, m, (255, 179, 71) if i == 0 else L, (w / 2, h / 2 - 110 + i * 34), True)
        pygame.display.flip()

    def run(s):
        clock = pygame.time.Clock(); frames = int(os.environ.get("GAME_FRAMES", 0)); n = 0
        while True:
            dt = min(.033, clock.tick(60) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): return
                if e.type == pygame.DROPFILE: s.load(e.file)
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN and s.state in ("menu", "done"): s.start()
                    elif e.key in (pygame.K_1, pygame.K_2, pygame.K_3) and s.state == "menu": s.laps = e.key - pygame.K_0
                    elif e.key == pygame.K_r and s.state == "race":
                        m = s.me; m.x, m.y = s.track.c[m.idx]; m.a = s.track.hd[m.idx]; m.vx = m.vy = 0
            if s.cars: s.update(dt)
            s.draw(); n += 1
            if frames and n == 5 and s.state == "menu": s.start()
            if frames and n >= frames: return


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    Game(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "us-2023.geojson")).run()
