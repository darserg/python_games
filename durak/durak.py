#!/usr/bin/env python3
"""Дурак (Durak) - pygame version. You vs. the computer.

Install:  pip install pygame
Run:      python durak_pygame.py

Rules (classic "podkidnoy" Durak, 36 cards):
  * 6 cards each; the bottom card of the deck shows the trump suit.
  * The attacker plays a card, the defender beats it with a higher card of the
    same suit or with any trump (a trump only loses to a higher trump).
  * The attacker may add cards whose rank is already on the table
    (max 6 attacks, never more than the defender's hand size).
  * The defender can TAKE the cards instead; the attacker may throw in more first.
  * If everything is beaten and nothing more is added -> "Бито" (discard), roles swap.
  * After each round both draw up to 6 (attacker first).
  * When the deck is empty, whoever still holds cards at the end is the Дурак.

Controls: click a highlighted card to play it, use the button for Take / Done.
          Esc = quit, Enter/Space = play again (after the game ends).
"""

import random
import sys
from dataclasses import dataclass

import pygame

W, H = 1100, 720
CW, CH = 88, 128  # card size
FPS = 60
HAND_SIZE = 6
RANKS = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RED = (200, 30, 40)
BLACK = (25, 25, 30)
GOLD = (255, 214, 64)

DECK_X, DECK_Y = 40, 285
DISC_X, DISC_Y = W - 150, 285
TABLE_X, TABLE_Y = 262, 262
SLOT_DX = 108
AI_DELAY = 700  # ms the computer "thinks"


# ------------------------------------------------------------------ cards ---


@dataclass(frozen=True)
class Card:
    rank: int  # index into RANKS
    suit: int  # 0 spades, 1 hearts, 2 diamonds, 3 clubs

    def __str__(self):
        return RANKS[self.rank] + "SHDC"[self.suit]


def beats(attack: Card, defence: Card, trump: int) -> bool:
    if attack.suit == defence.suit:
        return defence.rank > attack.rank
    return defence.suit == trump and attack.suit != trump


def ai_sort_key(trump):
    return lambda c: (c.suit == trump, c.rank, c.suit)


# --------------------------------------------------------------------- AI ---


def ai_attack(game, options, table, taking):
    """Pick a card to attack/throw in, or None to stop."""
    trump = game.trump
    options = sorted(options, key=ai_sort_key(trump))
    if not table:
        return options[0]
    cheap = [c for c in options if c.suit != trump]
    if taking:  # defender takes anyway: dump non-trumps
        return cheap[0] if cheap else None
    cheap = [c for c in cheap if c.rank <= RANKS.index("10")]
    if not game.deck:  # endgame: get rid of cards
        cheap = [c for c in options if c.suit != trump] or options
    return cheap[0] if cheap else None


def ai_defend(game, card, options):
    """Pick a beating card or None to take."""
    if not options:
        return None
    options = sorted(options, key=ai_sort_key(game.trump))
    best = options[0]
    if best.suit == game.trump and card.suit != game.trump and len(game.deck) > 4:
        if card.rank < RANKS.index("J") and best.rank > RANKS.index("8"):
            return None  # not worth a good trump
    return best


# ------------------------------------------------------------- game logic ---


class Player:
    def __init__(self, name, human):
        self.name = name
        self.human = human
        self.hand = []


class Game:
    """Pure game state machine (no drawing). `now` is set by the main loop."""

    def __init__(self):
        self.deck = [Card(r, s) for r in range(len(RANKS)) for s in range(4)]
        random.shuffle(self.deck)
        self.trump_card = self.deck[0]  # bottom of the deck, drawn last
        self.trump = self.trump_card.suit
        self.discard = []
        self.table = []  # [[attack, defence_or_None], ...]
        self.human = Player("You", True)
        self.ai = Player("Computer", False)
        self.players = [self.human, self.ai]
        self.att = self.dfn = None
        self.draw_queue = [self.human, self.ai] * HAND_SIZE
        self.phase = "DEAL"  # DEAL ATTACK DEFEND END DRAW OVER
        self.now = 0
        self.wait_until = 0
        self.taking = False
        self.defended = True
        self.attacks = 0
        self.limit = 0
        self.end_msg = ""
        self.over_msg = ""
        self.flash_text = ""
        self.flash_until = 0

    # ---- helpers
    def other(self, p):
        return self.ai if p is self.human else self.human

    def sort_hand(self, p):
        t = self.trump
        p.hand.sort(key=lambda c: (c.suit == t, c.suit, c.rank))

    def flash(self, text, ms=1800):
        self.flash_text = text
        self.flash_until = self.now + ms

    def table_ranks(self):
        return {c.rank for pair in self.table for c in pair if c}

    def attack_options(self):
        if not self.table:
            return list(self.att.hand)
        ranks = self.table_ranks()
        return [c for c in self.att.hand if c.rank in ranks]

    def can_continue(self):
        return (
            self.attacks < self.limit
            and bool(self.att.hand)
            and (bool(self.dfn.hand) or self.taking)
        )

    def legal_cards(self):
        """Cards the human may click right now."""
        if self.phase == "ATTACK" and self.att.human:
            return set(self.attack_options())
        if self.phase == "DEFEND" and self.dfn.human:
            a = self.table[-1][0]
            return {c for c in self.dfn.hand if beats(a, c, self.trump)}
        return set()

    def status(self):
        ph = self.phase
        if ph == "DEAL":
            return "Dealing the cards..."
        if ph == "DRAW":
            return "Drawing cards..."
        if ph == "ATTACK":
            if self.att.human:
                if not self.table:
                    return "Your attack - pick a card"
                if self.taking:
                    return "Computer takes - throw in more or press Done"
                return "Add a card of the same rank, or press Done"
            return (
                "Computer is throwing in more..."
                if self.taking
                else "Computer is attacking..."
            )
        if ph == "DEFEND":
            if self.dfn.human:
                if not self.legal_cards():
                    return "You can't beat it - press Take"
                return "Beat the card, or press Take"
            return "Computer is thinking..."
        if ph == "END":
            return self.end_msg
        return self.over_msg

    def button(self):
        """(label, callback) for the action button, or None."""
        if self.phase == "ATTACK" and self.att.human and self.table:
            return ("Done", self.end_round)
        if self.phase == "DEFEND" and self.dfn.human:
            return ("Take", lambda: self.do_defend(None))
        if self.phase == "OVER":
            return ("Play again", None)  # handled by the main loop
        return None

    # ---- state transitions
    def begin_round(self):
        self.table = []
        self.taking = False
        self.attacks = 0
        self.limit = min(HAND_SIZE, len(self.dfn.hand))
        self.begin_attack()

    def begin_attack(self):
        if self.table and (not self.can_continue() or not self.attack_options()):
            self.end_round()
            return
        self.phase = "ATTACK"
        self.wait_until = self.now + (0 if self.att.human else AI_DELAY)

    def do_attack(self, card):
        self.att.hand.remove(card)
        self.table.append([card, None])
        self.attacks += 1
        if self.taking:
            self.begin_attack()
        else:
            self.phase = "DEFEND"
            self.wait_until = self.now + (0 if self.dfn.human else AI_DELAY)

    def do_defend(self, card):
        if card is None:
            self.taking = True
            self.flash(
                f"{self.dfn.name} {'take' if self.dfn.human else 'takes'} the cards"
            )
        else:
            self.dfn.hand.remove(card)
            self.table[-1][1] = card
        self.begin_attack()

    def end_round(self):
        self.phase = "END"
        self.defended = not self.taking
        if self.defended:
            self.end_msg = "Бито! The cards go to the discard pile"
        else:
            self.end_msg = (
                f"{self.dfn.name} {'take' if self.dfn.human else 'takes'} the cards"
            )
        self.wait_until = self.now + 1100

    def finish_round(self):
        pile = [c for pair in self.table for c in pair if c]
        if self.taking:
            self.dfn.hand.extend(pile)
        else:
            self.discard.extend(pile)
        self.table = []
        self.sort_hand(self.dfn)
        self.draw_queue = [self.att] * max(0, HAND_SIZE - len(self.att.hand)) + [
            self.dfn
        ] * max(0, HAND_SIZE - len(self.dfn.hand))
        self.phase = "DRAW"

    def after_draw(self):
        if not self.deck:
            empty = [p for p in self.players if not p.hand]
            if len(empty) == 2:
                self.finish_game(None)
                return
            if len(empty) == 1:
                self.finish_game(self.other(empty[0]))
                return
        if self.defended:
            self.att, self.dfn = self.dfn, self.att
        self.begin_round()

    def finish_game(self, fool):
        self.phase = "OVER"
        if fool is None:
            self.over_msg = "Draw - nobody is the Дурак!"
        elif fool.human:
            self.over_msg = "You are the Дурак!  Better luck next time"
        else:
            self.over_msg = "Computer is the Дурак - you win!"

    def start_play(self):
        lowest = None
        for p in self.players:
            for c in p.hand:
                if c.suit == self.trump and (lowest is None or c.rank < lowest[1].rank):
                    lowest = (p, c)
        if lowest:
            self.att = lowest[0]
            self.flash(
                f"{self.att.name} {'have' if self.att.human else 'has'} the lowest trump "
                f"({RANKS[lowest[1].rank]}) and {'go' if self.att.human else 'goes'} first",
                2600,
            )
        else:
            self.att = random.choice(self.players)
            self.flash(
                f"No trumps in hands - {self.att.name} {'go' if self.att.human else 'goes'} first",
                2600,
            )
        self.dfn = self.other(self.att)
        self.begin_round()

    # ---- human input
    def human_play(self, card):
        if self.phase == "ATTACK" and self.att.human:
            if card in self.attack_options():
                self.do_attack(card)
            else:
                self.flash("Only a rank that is already on the table")
        elif self.phase == "DEFEND" and self.dfn.human:
            if beats(self.table[-1][0], card, self.trump):
                self.do_defend(card)
            else:
                self.flash("That card doesn't beat it")

    # ---- per-frame update
    def update(self, now):
        self.now = now
        if now < self.wait_until:
            return
        ph = self.phase
        if ph in ("DEAL", "DRAW"):
            while self.draw_queue:
                p = self.draw_queue.pop(0)
                if self.deck and len(p.hand) < HAND_SIZE:
                    p.hand.append(self.deck.pop())
                    self.sort_hand(p)
                    self.wait_until = now + 130
                    return
            if ph == "DEAL":
                self.start_play()
            else:
                self.after_draw()
        elif ph == "ATTACK" and not self.att.human:
            card = ai_attack(self, self.attack_options(), self.table, self.taking)
            if card is None:
                self.end_round()
            else:
                self.do_attack(card)
        elif ph == "DEFEND" and not self.dfn.human:
            a = self.table[-1][0]
            opts = [c for c in self.dfn.hand if beats(a, c, self.trump)]
            self.do_defend(ai_defend(self, a, opts))
        elif ph == "END":
            self.finish_round()


# ---------------------------------------------------------------- drawing ---


def load_font(size, bold=True):
    return pygame.font.SysFont(
        "dejavusans,arial,liberationsans,freesans,verdana", size, bold=bold
    )


def draw_suit(surf, suit, cx, cy, s, col):
    """Draw a suit symbol with primitives (no font glyphs needed)."""

    def circ(x, y, r):
        pygame.draw.circle(surf, col, (int(x), int(y)), max(1, int(r)))

    def poly(pts):
        pygame.draw.polygon(surf, col, [(int(x), int(y)) for x, y in pts])

    if suit == 2:  # diamonds
        poly([(cx, cy - s), (cx + 0.7 * s, cy), (cx, cy + s), (cx - 0.7 * s, cy)])
    elif suit == 1:  # hearts
        circ(cx - 0.5 * s, cy - 0.35 * s, 0.55 * s)
        circ(cx + 0.5 * s, cy - 0.35 * s, 0.55 * s)
        poly(
            [
                (cx - 1.02 * s, cy - 0.1 * s),
                (cx + 1.02 * s, cy - 0.1 * s),
                (cx, cy + 0.95 * s),
            ]
        )
    elif suit == 0:  # spades
        circ(cx - 0.5 * s, cy + 0.15 * s, 0.55 * s)
        circ(cx + 0.5 * s, cy + 0.15 * s, 0.55 * s)
        poly(
            [
                (cx, cy - 0.98 * s),
                (cx - 1.02 * s, cy + 0.0 * s),
                (cx + 1.02 * s, cy + 0.0 * s),
            ]
        )
        poly(
            [
                (cx, cy + 0.1 * s),
                (cx - 0.45 * s, cy + 0.98 * s),
                (cx + 0.45 * s, cy + 0.98 * s),
            ]
        )
    else:  # clubs
        circ(cx, cy - 0.5 * s, 0.5 * s)
        circ(cx - 0.55 * s, cy + 0.2 * s, 0.5 * s)
        circ(cx + 0.55 * s, cy + 0.2 * s, 0.5 * s)
        poly([(cx, cy), (cx - 0.45 * s, cy + 0.98 * s), (cx + 0.45 * s, cy + 0.98 * s)])


def suit_color(suit):
    return RED if suit in (1, 2) else BLACK


class View:
    def __init__(self, game):
        self.f_rank = load_font(22)
        self.f_text = load_font(24)
        self.f_small = load_font(17)
        self.f_big = load_font(34)
        self.faces = {}
        self.back = self.make_back()
        self.shadow = pygame.Surface((CW + 8, CH + 8), pygame.SRCALPHA)
        pygame.draw.rect(
            self.shadow, (0, 0, 0, 70), self.shadow.get_rect(), border_radius=12
        )
        self.bg = self.make_bg()
        self.slots = self.make_slots()
        self.reset(game)

    def reset(self, game):
        self.game = game
        self.pos = {}
        for c, t in self.targets().items():
            self.pos[c] = [float(t[0]), float(t[1])]

    # ---- surfaces
    def make_back(self):
        s = pygame.Surface((CW, CH), pygame.SRCALPHA)
        pygame.draw.rect(s, (245, 245, 245), (0, 0, CW, CH), border_radius=9)
        pygame.draw.rect(s, (35, 70, 150), (4, 4, CW - 8, CH - 8), border_radius=7)
        pygame.draw.rect(
            s, (90, 130, 215), (10, 10, CW - 20, CH - 20), 2, border_radius=5
        )
        for y in range(18, CH - 14, 18):
            for x in range(18, CW - 14, 18):
                pygame.draw.circle(s, (90, 130, 215), (x, y), 2)
        pygame.draw.rect(s, (60, 60, 60), (0, 0, CW, CH), 2, border_radius=9)
        return s

    def face(self, card):
        s = self.faces.get(card)
        if s:
            return s
        s = pygame.Surface((CW, CH), pygame.SRCALPHA)
        pygame.draw.rect(s, (252, 252, 246), (0, 0, CW, CH), border_radius=9)
        pygame.draw.rect(s, (60, 60, 60), (0, 0, CW, CH), 2, border_radius=9)
        col = suit_color(card.suit)
        corner = pygame.Surface((34, 56), pygame.SRCALPHA)
        r = self.f_rank.render(RANKS[card.rank], True, col)
        corner.blit(r, ((34 - r.get_width()) // 2, 2))
        draw_suit(corner, card.suit, 17, 40, 9, col)
        s.blit(corner, (3, 3))
        s.blit(pygame.transform.rotate(corner, 180), (CW - 37, CH - 59))
        draw_suit(s, card.suit, CW // 2, CH // 2, 21, col)
        self.faces[card] = s
        return s

    def make_bg(self):
        bg = pygame.Surface((W, H))
        bg.fill((16, 70, 44))
        steps = 40
        for i in range(steps):
            k = i / steps
            col = (int(16 + 22 * k), int(70 + 38 * k), int(44 + 26 * k))
            rect = pygame.Rect(
                0, 0, int(W * (1.25 - 0.8 * k)), int(H * (1.25 - 0.8 * k))
            )
            rect.center = (W // 2, H // 2)
            pygame.draw.ellipse(bg, col, rect)
        return bg

    def make_slots(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(6):
            r = pygame.Rect(TABLE_X + i * SLOT_DX - 4, TABLE_Y - 4, CW + 30, CH + 34)
            pygame.draw.rect(s, (255, 255, 255, 28), r, 2, border_radius=12)
        return s

    # ---- layout
    def hand_xs(self, n, area_w, max_gap):
        if n <= 0:
            return []
        if n == 1:
            gap = 0
        else:
            gap = min(max_gap, (area_w - CW) / (n - 1))
        total = CW + gap * (n - 1)
        x0 = (W - total) / 2
        return [x0 + i * gap for i in range(n)]

    def targets(self, hovered=None, legal=()):
        """card -> (x, y, face_up, z, rotated)"""
        g = self.game
        out = {}
        for i, c in enumerate(g.deck):
            if i == 0:
                out[c] = (DECK_X + 50, DECK_Y + (CH - CW) // 2, True, 0.0, True)
            else:
                k = min(i, 12) * 0.5
                out[c] = (DECK_X - k, DECK_Y - k, False, 0.001 * i, False)
        for i, c in enumerate(g.discard):
            jx = (i * 7) % 9 - 4
            jy = (i * 5) % 7 - 3
            out[c] = (DISC_X + jx, DISC_Y + jy, False, 1 + 0.001 * i, False)
        for i, (a, d) in enumerate(g.table):
            x = TABLE_X + i * SLOT_DX
            out[a] = (x, TABLE_Y, True, 2 + 0.1 * i, False)
            if d:
                out[d] = (x + 22, TABLE_Y + 26, True, 2.05 + 0.1 * i, False)
        n = len(g.ai.hand)
        for i, (c, x) in enumerate(zip(g.ai.hand, self.hand_xs(n, 560, 34))):
            out[c] = (x, 22, False, 3 + 0.001 * i, False)
        hy = H - CH - 24
        for i, (c, x) in enumerate(
            zip(g.human.hand, self.hand_xs(len(g.human.hand), W - 300, CW + 12))
        ):
            y = hy
            if c in legal:
                y -= 16
                if c == hovered:
                    y -= 10
            out[c] = (x, y, True, 4 + 0.001 * i, False)
        return out

    def hovered_card(self, mouse):
        """Topmost legal human card under the mouse."""
        g = self.game
        legal = g.legal_cards()
        if not legal:
            return None
        hy = H - CH - 24
        xs = self.hand_xs(len(g.human.hand), W - 300, CW + 12)
        for c, x in reversed(list(zip(g.human.hand, xs))):
            top = hy - 16 if c in legal else hy
            if pygame.Rect(int(x), int(top), CW, CH + 16).collidepoint(mouse):
                return c if c in legal else None
        return None

    # ---- main drawing
    def text(self, screen, font, msg, pos, color=(245, 245, 245), center=False):
        shadow = font.render(msg, True, (0, 0, 0))
        img = font.render(msg, True, color)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        screen.blit(shadow, (r.x + 2, r.y + 2))
        screen.blit(img, r)
        return r

    def button_rect(self):
        return pygame.Rect(W - 250, 458, 180, 50)

    def draw(self, screen, mouse):
        g = self.game
        legal = g.legal_cards()
        hov = self.hovered_card(mouse)
        tg = self.targets(hov, legal)

        # move cards towards their targets
        moving = set()
        for c, t in tg.items():
            p = self.pos.setdefault(c, [float(t[0]), float(t[1])])
            dx, dy = t[0] - p[0], t[1] - p[1]
            if abs(dx) < 0.6 and abs(dy) < 0.6:
                p[0], p[1] = float(t[0]), float(t[1])
            else:
                p[0] += dx * 0.24
                p[1] += dy * 0.24
                if abs(dx) > 4 or abs(dy) > 4:
                    moving.add(c)

        screen.blit(self.bg, (0, 0))
        screen.blit(self.slots, (0, 0))

        # labels / HUD
        self.text(screen, self.f_small, "Deck", (DECK_X, DECK_Y - 32))
        self.text(
            screen, self.f_small, str(len(g.deck)), (DECK_X + 46, DECK_Y - 32), GOLD
        )
        self.text(screen, self.f_small, "Trump", (DECK_X, DECK_Y - 62))
        box = pygame.Rect(DECK_X + 66, DECK_Y - 68, 34, 30)
        pygame.draw.rect(screen, (252, 252, 246), box, border_radius=7)
        draw_suit(screen, g.trump, box.centerx, box.centery, 8, suit_color(g.trump))
        self.text(
            screen,
            self.f_small,
            f"Discard: {len(g.discard)}",
            (DISC_X - 4, DISC_Y + CH + 12),
        )

        in_round = g.phase in ("ATTACK", "DEFEND", "END") and g.att is not None
        for p, pos in ((g.ai, (20, 170)), (g.human, (20, H - 175))):
            self.text(screen, self.f_text, p.name, pos)
            if in_round:
                role = "ATTACK" if p is g.att else "DEFENCE"
                self.text(
                    screen,
                    self.f_small,
                    role,
                    (pos[0], pos[1] + 30),
                    GOLD if p is g.att else (150, 200, 255),
                )
        self.text(screen, self.f_small, f"{len(g.ai.hand)} cards", (20, 70))

        # cards
        items = []
        for c, t in tg.items():
            z = t[3] + (10 if c in moving else 0)
            items.append((z, c, t))
        items.sort(key=lambda it: it[0])
        for z, c, t in items:
            px, py = self.pos[c]
            if t[2]:
                img = self.face(c)
            else:
                img = self.back
            if t[4]:
                img = pygame.transform.rotate(img, 90)
            else:
                screen.blit(self.shadow, (px - 2, py))
            screen.blit(img, (px, py))
            if c in legal:
                pygame.draw.rect(screen, GOLD, (px, py, CW, CH), 3, border_radius=9)

        # status line + button
        if g.flash_text and g.now < g.flash_until:
            self.text(
                screen,
                self.f_small,
                g.flash_text,
                (W // 2 - 40, 438),
                (255, 190, 120),
                center=True,
            )
        self.text(screen, self.f_text, g.status(), (W // 2 - 40, 478), center=True)

        btn = g.button()
        if btn:
            r = self.button_rect()
            hot = r.collidepoint(mouse)
            pygame.draw.rect(
                screen, (230, 170, 40) if hot else (200, 140, 30), r, border_radius=12
            )
            pygame.draw.rect(screen, (255, 235, 170), r, 2, border_radius=12)
            img = self.f_text.render(btn[0], True, (30, 20, 0))
            screen.blit(img, img.get_rect(center=r.center))

        self.text(
            screen, self.f_small, "Esc - quit", (W - 100, H - 26), (190, 220, 200)
        )


# ------------------------------------------------------------------- main ---


def main():
    pygame.init()
    pygame.display.set_caption("Дурак")
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    game = Game()
    view = View(game)

    def new_game():
        nonlocal game
        game = Game()
        view.reset(game)

    running = True
    while running:
        now = pygame.time.get_ticks()
        mouse = pygame.mouse.get_pos()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif (
                    ev.key in (pygame.K_RETURN, pygame.K_SPACE) and game.phase == "OVER"
                ):
                    new_game()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                btn = game.button()
                if btn and view.button_rect().collidepoint(ev.pos):
                    if game.phase == "OVER":
                        new_game()
                    else:
                        btn[1]()
                else:
                    c = view.hovered_card(ev.pos)
                    if c is not None:
                        game.human_play(c)
                    elif game.phase in ("ATTACK", "DEFEND") and game.human.hand:
                        pass
        game.update(now)
        view.draw(screen, mouse)
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
