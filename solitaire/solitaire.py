#!/usr/bin/env python3
"""Пасьянс «Косынка» на Pygame.

Запуск:  pip install pygame  &&  python solitaire.py
Управление:
  ЛКМ (перетаскивание)  - переносить карты
  клик по колоде        - открыть карту(ы); по пустой колоде - перевернуть сброс
  двойной клик / ПКМ    - отправить карту в «дом»
  N - новая игра, U - отмена хода, D - режим 1/3 карты, Esc - выход
"""
import copy
import random
import sys

import pygame

W, H = 880, 740
CW, CH = 96, 134            # размер карты
GAP = 20
X0 = (W - (7 * CW + 6 * GAP)) // 2
TOP = 20
TAB_Y = TOP + CH + 40
DOWN_OFF, UP_OFF, FAN = 22, 32, 22

GREEN = (20, 105, 60)
WHITE = (245, 245, 240)
LABELS = ["A"] + [str(n) for n in range(2, 11)] + ["J", "Q", "K"]
FONT = SMALL = BIG = None


class Card:
    __slots__ = ("suit", "rank", "up")   # масти: 0 пики, 1 трефы, 2 червы, 3 бубны

    def __init__(self, suit, rank, up=False):
        self.suit, self.rank, self.up = suit, rank, up

    @property
    def red(self):
        return self.suit >= 2


def col_x(i):
    return X0 + i * (CW + GAP)


def tab_y(pile, idx):
    y = TAB_Y
    for c in pile[:idx]:
        y += UP_OFF if c.up else DOWN_OFF
    return y


def can_tab(card, pile):
    if not pile:
        return card.rank == 13
    top = pile[-1]
    return top.up and top.rank == card.rank + 1 and top.red != card.red


def can_found(card, pile):
    if not pile:
        return card.rank == 1
    return pile[-1].suit == card.suit and card.rank == pile[-1].rank + 1


def draw_suit(s, suit, cx, cy, z, col):
    i = lambda v: int(round(v))
    d = pygame.draw
    if suit in (0, 2):  # пики / червы
        sign = -1 if suit == 0 else 1
        cyc = cy - sign * z * 0.15 if suit == 2 else cy + z * 0.1
        for dx in (-0.25, 0.25):
            d.circle(s, col, (i(cx + dx * z), i(cyc)), i(z * 0.28))
        if suit == 2:
            d.polygon(s, col, [(i(cx - .5 * z), i(cy - .05 * z)), (i(cx + .5 * z), i(cy - .05 * z)),
                               (cx, i(cy + .55 * z))])
        else:
            d.polygon(s, col, [(i(cx - .5 * z), i(cy + .05 * z)), (i(cx + .5 * z), i(cy + .05 * z)),
                               (cx, i(cy - .55 * z))])
            d.polygon(s, col, [(cx, i(cy + .1 * z)), (i(cx - .2 * z), i(cy + .55 * z)),
                               (i(cx + .2 * z), i(cy + .55 * z))])
    elif suit == 3:     # бубны
        d.polygon(s, col, [(cx, i(cy - .55 * z)), (i(cx + .4 * z), cy),
                           (cx, i(cy + .55 * z)), (i(cx - .4 * z), cy)])
    else:               # трефы
        for dx, dy in ((0, -.25), (-.27, .12), (.27, .12)):
            d.circle(s, col, (i(cx + dx * z), i(cy + dy * z)), i(z * 0.25))
        d.polygon(s, col, [(cx, i(cy)), (i(cx - .2 * z), i(cy + .55 * z)), (i(cx + .2 * z), i(cy + .55 * z))])


def draw_card(s, card, x, y):
    r = pygame.Rect(x, y, CW, CH)
    if not card.up:
        pygame.draw.rect(s, (40, 70, 160), r, border_radius=8)
        pygame.draw.rect(s, (225, 230, 245), r.inflate(-14, -14), 2, border_radius=6)
        pygame.draw.rect(s, WHITE, r, 2, border_radius=8)
        return
    pygame.draw.rect(s, (252, 252, 247), r, border_radius=8)
    pygame.draw.rect(s, (60, 60, 60), r, 2, border_radius=8)
    col = (200, 30, 40) if card.red else (25, 25, 25)
    s.blit(FONT.render(LABELS[card.rank - 1], True, col), (x + 7, y + 4))
    draw_suit(s, card.suit, x + 15, y + 40, 16, col)
    draw_suit(s, card.suit, x + CW // 2 + 8, y + CH // 2 + 12, 46, col)


class Game:
    def __init__(self):
        self.draw = 1
        self.new()

    def new(self):
        deck = [Card(s, r) for s in range(4) for r in range(1, 14)]
        random.shuffle(deck)
        self.tab = []
        for i in range(7):
            pile = [deck.pop() for _ in range(i + 1)]
            pile[-1].up = True
            self.tab.append(pile)
        self.stock, self.waste = deck, []
        self.found = [[] for _ in range(4)]
        self.drag = None
        self.undo_stack = []
        self.moves = 0
        self.last_click, self.last_card = 0, None

    # ---------- состояние ----------
    def pile_of(self, kind, i):
        return {"tab": self.tab, "found": self.found}.get(kind, [self.waste])[i if kind != "waste" else 0]

    def snapshot(self):
        return copy.deepcopy((self.stock, self.waste, self.found, self.tab, self.moves))

    def push_undo(self):
        self.undo_stack.append(self.snapshot())

    def undo(self):
        if self.undo_stack and not self.drag:
            self.stock, self.waste, self.found, self.tab, self.moves = self.undo_stack.pop()

    @property
    def won(self):
        return all(len(f) == 13 for f in self.found)

    def flip_top(self, i):
        if self.tab[i] and not self.tab[i][-1].up:
            self.tab[i][-1].up = True

    def waste_x(self):
        n = min(len(self.waste), 3 if self.draw == 3 else 1)
        return col_x(1) + max(n - 1, 0) * FAN

    def origin(self, kind, i, idx):
        if kind == "waste":
            return self.waste_x(), TOP
        if kind == "found":
            return col_x(3 + i), TOP
        return col_x(i), tab_y(self.tab[i], idx)

    # ---------- действия ----------
    def click_stock(self):
        if not self.stock and not self.waste:
            return
        self.push_undo()
        if self.stock:
            for _ in range(min(self.draw, len(self.stock))):
                c = self.stock.pop()
                c.up = True
                self.waste.append(c)
        else:
            while self.waste:
                c = self.waste.pop()
                c.up = False
                self.stock.append(c)
        self.moves += 1

    def auto_found(self, kind, i):
        pile = self.pile_of(kind, i)
        if not pile:
            return False
        c = pile[-1]
        for f in self.found:
            if can_found(c, f):
                self.push_undo()
                f.append(pile.pop())
                self.moves += 1
                if kind == "tab":
                    self.flip_top(i)
                return True
        return False

    def pick(self, pos):
        R = lambda x, y: pygame.Rect(x, y, CW, CH).collidepoint(pos)
        if self.waste and R(self.waste_x(), TOP):
            return "waste", 0, len(self.waste) - 1
        for j in range(4):
            if self.found[j] and R(col_x(3 + j), TOP):
                return "found", j, len(self.found[j]) - 1
        for i, pile in enumerate(self.tab):
            for idx in reversed(range(len(pile))):
                if R(col_x(i), tab_y(pile, idx)):
                    return "tab", i, idx
        return None

    def mouse_down(self, pos, button):
        if self.won or self.drag:
            return
        if button == 1 and pygame.Rect(col_x(0), TOP, CW, CH).collidepoint(pos):
            self.click_stock()
            return
        hit = self.pick(pos)
        if not hit:
            return
        kind, i, idx = hit
        pile = self.pile_of(kind, i)
        card = pile[idx]
        if not card.up:
            if kind == "tab" and button == 1:
                self.push_undo()
                card.up = True
            return
        now = pygame.time.get_ticks()
        dbl = button == 3 or (now - self.last_click < 350 and self.last_card is card)
        self.last_click, self.last_card = now, card
        if dbl and idx == len(pile) - 1 and kind != "found" and self.auto_found(kind, i):
            return
        if button != 1:
            return
        ox, oy = self.origin(kind, i, idx)
        self.drag = {"cards": pile[idx:], "src": (kind, i), "dx": pos[0] - ox, "dy": pos[1] - oy,
                     "x": ox, "y": oy, "snap": self.snapshot()}
        del pile[idx:]

    def mouse_move(self, pos):
        if self.drag:
            self.drag["x"], self.drag["y"] = pos[0] - self.drag["dx"], pos[1] - self.drag["dy"]

    def mouse_up(self):
        d = self.drag
        if not d:
            return
        self.drag = None
        cards, (kind, i) = d["cards"], d["src"]
        rect = pygame.Rect(d["x"], d["y"], CW, CH)
        cands = []
        for j in range(7):
            pile = self.tab[j]
            t = pygame.Rect(col_x(j), tab_y(pile, max(len(pile) - 1, 0)), CW, CH)
            o = rect.clip(t)
            if o.w * o.h > 0 and not (kind == "tab" and i == j) and can_tab(cards[0], pile):
                cands.append((o.w * o.h, ("tab", j)))
        if len(cards) == 1:
            for j in range(4):
                o = rect.clip(pygame.Rect(col_x(3 + j), TOP, CW, CH))
                if o.w * o.h > 0 and not (kind == "found" and i == j) and can_found(cards[0], self.found[j]):
                    cands.append((o.w * o.h, ("found", j)))
        if cands:
            _, (tk, tj) = max(cands)
            self.undo_stack.append(d["snap"])
            self.pile_of(tk, tj).extend(cards)
            self.moves += 1
            if kind == "tab":
                self.flip_top(i)
        else:
            self.pile_of(kind, i).extend(cards)

    # ---------- отрисовка ----------
    def render(self, s):
        s.fill(GREEN)
        slot = lambda x, y: pygame.draw.rect(s, (15, 80, 45), (x, y, CW, CH), 2, border_radius=8)
        # колода
        if self.stock:
            draw_card(s, Card(0, 1), col_x(0), TOP)
        else:
            slot(col_x(0), TOP)
            pygame.draw.circle(s, (15, 80, 45), (col_x(0) + CW // 2, TOP + CH // 2), 22, 4)
        # сброс
        slot(col_x(1), TOP)
        vis = self.waste[-3:] if self.draw == 3 else self.waste[-1:]
        for k, c in enumerate(vis):
            draw_card(s, c, col_x(1) + k * FAN, TOP)
        # «дома»
        for j in range(4):
            slot(col_x(3 + j), TOP)
            if self.found[j]:
                draw_card(s, self.found[j][-1], col_x(3 + j), TOP)
            else:
                t = BIG.render("A", True, (15, 80, 45))
                s.blit(t, t.get_rect(center=(col_x(3 + j) + CW // 2, TOP + CH // 2)))
        # стопки
        for i, pile in enumerate(self.tab):
            if not pile:
                slot(col_x(i), TAB_Y)
            for idx, c in enumerate(pile):
                draw_card(s, c, col_x(i), tab_y(pile, idx))
        if self.drag:
            for k, c in enumerate(self.drag["cards"]):
                draw_card(s, c, self.drag["x"], self.drag["y"] + k * UP_OFF)
        info = f"Ходы: {self.moves}   |   N - новая   U - отмена   D - режим: {self.draw} карт" \
               f"{'а' if self.draw == 1 else 'ы'}   Esc - выход"
        s.blit(SMALL.render(info, True, (220, 235, 225)), (X0, H - 32))
        if self.won:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 150))
            s.blit(veil, (0, 0))
            t = BIG.render(f"Победа! Ходов: {self.moves}", True, (255, 230, 120))
            s.blit(t, t.get_rect(center=(W // 2, H // 2 - 14)))
            t = SMALL.render("Нажмите N для новой игры", True, WHITE)
            s.blit(t, t.get_rect(center=(W // 2, H // 2 + 30)))


def main():
    global FONT, SMALL, BIG
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Косынка")
    names = "arial,dejavusans,freesans"
    FONT = pygame.font.SysFont(names, 26, bold=True)
    SMALL = pygame.font.SysFont(names, 18)
    BIG = pygame.font.SysFont(names, 44, bold=True)
    clock, game = pygame.time.Clock(), Game()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_n:
                    game.new()
                elif e.key == pygame.K_u:
                    game.undo()
                elif e.key == pygame.K_d:
                    game.draw = 3 if game.draw == 1 else 1
                    game.new()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                game.mouse_down(e.pos, e.button)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                game.mouse_up()
            elif e.type == pygame.MOUSEMOTION:
                game.mouse_move(e.pos)
        game.render(screen)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
