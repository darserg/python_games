"""
Сапер на Pygame.

Управление:
  ЛКМ            - открыть клетку (на открытой цифре - открыть соседей, если флагов достаточно)
  ПКМ            - поставить / убрать флажок
  СКМ (колесо)   - то же, что ЛКМ по открытой цифре
  R или смайлик  - новая игра
  1 / 2 / 3      - сложность: Новичок / Любитель / Профи
  Esc            - выход

Запуск:
  pip install pygame
  python minesweeper.py
"""

import random
import sys

import pygame

# ---------------------------------------------------------------- настройки
DIFFICULTIES = {
    1: ("Новичок", 9, 9, 10),
    2: ("Любитель", 16, 16, 40),
    3: ("Профи", 30, 16, 99),
}

CELL = 32          # размер клетки в пикселях
HEADER = 70        # высота верхней панели
FPS = 60

# цвета
BG = (192, 192, 192)
LIGHT = (255, 255, 255)
SHADOW = (118, 118, 118)
DARK = (60, 60, 60)
CLOSED = (192, 192, 192)
OPENED = (214, 214, 214)
RED = (220, 30, 30)
YELLOW = (255, 220, 40)
BLACK = (0, 0, 0)
LED_BG = (20, 0, 0)
LED_FG = (255, 40, 40)

NUMBER_COLORS = {
    1: (0, 0, 255),
    2: (0, 128, 0),
    3: (255, 0, 0),
    4: (0, 0, 128),
    5: (128, 0, 0),
    6: (0, 128, 128),
    7: (0, 0, 0),
    8: (100, 100, 100),
}

READY, PLAYING, WON, LOST = "ready", "playing", "won", "lost"


# ---------------------------------------------------------------- логика
class Board:
    def __init__(self, cols, rows, mines):
        self.cols = cols
        self.rows = rows
        self.mines = mines
        self.reset()

    def reset(self):
        self.mine = [[False] * self.cols for _ in range(self.rows)]
        self.count = [[0] * self.cols for _ in range(self.rows)]
        self.revealed = [[False] * self.cols for _ in range(self.rows)]
        self.flagged = [[False] * self.cols for _ in range(self.rows)]
        self.exploded = None
        self.state = READY
        self.start_ticks = 0
        self.final_seconds = 0

    # --- вспомогательное
    def neighbors(self, c, r):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nc, nr = c + dc, r + dr
                if 0 <= nc < self.cols and 0 <= nr < self.rows:
                    yield nc, nr

    def flags_used(self):
        return sum(sum(row) for row in self.flagged)

    def seconds(self):
        if self.state == READY:
            return 0
        if self.state == PLAYING:
            return (pygame.time.get_ticks() - self.start_ticks) // 1000
        return self.final_seconds

    # --- генерация мин (после первого клика, чтобы он был безопасным)
    def place_mines(self, safe_c, safe_r):
        forbidden = {(safe_c, safe_r)} | set(self.neighbors(safe_c, safe_r))
        cells = [
            (c, r)
            for r in range(self.rows)
            for c in range(self.cols)
            if (c, r) not in forbidden
        ]
        # если поле слишком мало для зоны безопасности - защищаем только саму клетку
        if len(cells) < self.mines:
            cells = [
                (c, r)
                for r in range(self.rows)
                for c in range(self.cols)
                if (c, r) != (safe_c, safe_r)
            ]
        for c, r in random.sample(cells, self.mines):
            self.mine[r][c] = True
        for r in range(self.rows):
            for c in range(self.cols):
                self.count[r][c] = sum(self.mine[nr][nc]
                                       for nc, nr in self.neighbors(c, r))

    # --- действия игрока
    def open_cell(self, c, r):
        if self.state in (WON, LOST):
            return
        if self.flagged[r][c] or self.revealed[r][c]:
            return

        if self.state == READY:
            self.place_mines(c, r)
            self.state = PLAYING
            self.start_ticks = pygame.time.get_ticks()

        if self.mine[r][c]:
            self.exploded = (c, r)
            self.lose()
            return

        self.flood_open(c, r)
        self.check_win()

    def flood_open(self, c, r):
        stack = [(c, r)]
        while stack:
            cc, rr = stack.pop()
            if self.revealed[rr][cc] or self.flagged[rr][cc]:
                continue
            self.revealed[rr][cc] = True
            if self.count[rr][cc] == 0:
                for nc, nr in self.neighbors(cc, rr):
                    if not self.revealed[nr][nc]:
                        stack.append((nc, nr))

    def toggle_flag(self, c, r):
        if self.state in (WON, LOST) or self.revealed[r][c]:
            return
        self.flagged[r][c] = not self.flagged[r][c]

    def chord(self, c, r):
        """Открыть всех соседей открытой цифры, если рядом стоит нужное число флагов."""
        if self.state != PLAYING or not self.revealed[r][c] or self.count[r][c] == 0:
            return
        flags = sum(self.flagged[nr][nc] for nc, nr in self.neighbors(c, r))
        if flags != self.count[r][c]:
            return
        for nc, nr in self.neighbors(c, r):
            if not self.flagged[nr][nc] and not self.revealed[nr][nc]:
                self.open_cell(nc, nr)
                if self.state == LOST:
                    return

    # --- конец игры
    def lose(self):
        self.state = LOST
        self.final_seconds = (pygame.time.get_ticks() -
                              self.start_ticks) // 1000
        for r in range(self.rows):
            for c in range(self.cols):
                if self.mine[r][c] and not self.flagged[r][c]:
                    self.revealed[r][c] = True

    def check_win(self):
        closed_safe = sum(
            1
            for r in range(self.rows)
            for c in range(self.cols)
            if not self.mine[r][c] and not self.revealed[r][c]
        )
        if closed_safe == 0:
            self.state = WON
            self.final_seconds = (
                pygame.time.get_ticks() - self.start_ticks) // 1000
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.mine[r][c]:
                        self.flagged[r][c] = True


# ---------------------------------------------------------------- отрисовка
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Сапер")
        self.clock = pygame.time.Clock()
        self.font_num = pygame.font.SysFont("arial", 22, bold=True)
        self.font_led = pygame.font.SysFont("couriernew", 34, bold=True)
        self.font_small = pygame.font.SysFont("arial", 15)
        self.difficulty = 1
        self.new_board()

    def new_board(self):
        name, cols, rows, mines = DIFFICULTIES[self.difficulty]
        self.name = name
        self.board = Board(cols, rows, mines)
        self.width = cols * CELL
        self.height = HEADER + rows * CELL
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.face_rect = pygame.Rect(0, 0, 44, 44)
        self.face_rect.center = (self.width // 2, 28)

    # --- примитивы
    def draw_bevel(self, rect, raised=True, width=3):
        pygame.draw.rect(self.screen, BG, rect)
        top_left = LIGHT if raised else SHADOW
        bottom_right = SHADOW if raised else LIGHT
        x, y, w, h = rect
        for i in range(width):
            pygame.draw.line(self.screen, top_left,
                             (x + i, y + i), (x + w - 1 - i, y + i))
            pygame.draw.line(self.screen, top_left,
                             (x + i, y + i), (x + i, y + h - 1 - i))
            pygame.draw.line(self.screen, bottom_right, (x + i,
                             y + h - 1 - i), (x + w - 1 - i, y + h - 1 - i))
            pygame.draw.line(self.screen, bottom_right, (x +
                             w - 1 - i, y + i), (x + w - 1 - i, y + h - 1 - i))

    def draw_led(self, value, right_edge_x=None, left_edge_x=None):
        value = max(-99, min(999, value))
        text = f"{value:03d}" if value >= 0 else f"-{abs(value):02d}"
        surf = self.font_led.render(text, True, LED_FG)
        rect = pygame.Rect(0, 0, 78, 44)
        rect.y = 6
        if left_edge_x is not None:
            rect.x = left_edge_x
        else:
            rect.right = right_edge_x
        pygame.draw.rect(self.screen, LED_BG, rect)
        self.draw_bevel(rect, raised=False, width=2)
        pygame.draw.rect(self.screen, LED_BG, rect.inflate(-4, -4))
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def draw_face(self):
        self.draw_bevel(self.face_rect, raised=True)
        cx, cy = self.face_rect.center
        pygame.draw.circle(self.screen, YELLOW, (cx, cy), 16)
        pygame.draw.circle(self.screen, BLACK, (cx, cy), 16, 1)
        state = self.board.state
        if state == LOST:
            for dx in (-6, 6):
                pygame.draw.line(
                    self.screen, BLACK, (cx + dx - 3, cy - 7), (cx + dx + 3, cy - 1), 2)
                pygame.draw.line(
                    self.screen, BLACK, (cx + dx - 3, cy - 1), (cx + dx + 3, cy - 7), 2)
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 7, cy + 3, 14, 10), 0.4, 2.7, 2)
        elif state == WON:
            pygame.draw.rect(self.screen, BLACK, (cx - 11, cy - 7, 9, 6))
            pygame.draw.rect(self.screen, BLACK, (cx + 2, cy - 7, 9, 6))
            pygame.draw.line(self.screen, BLACK,
                             (cx - 2, cy - 5), (cx + 2, cy - 5), 2)
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 8, cy - 2, 16, 12), 3.5, 5.9, 2)
        else:
            pygame.draw.circle(self.screen, BLACK, (cx - 6, cy - 4), 2)
            pygame.draw.circle(self.screen, BLACK, (cx + 6, cy - 4), 2)
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 8, cy - 2, 16, 12), 3.5, 5.9, 2)

    def draw_flag(self, rect):
        cx, cy = rect.center
        pygame.draw.polygon(self.screen, RED, [
                            (cx - 6, cy - 8), (cx + 6, cy - 3), (cx - 6, cy + 2)])
        pygame.draw.line(self.screen, BLACK, (cx - 6, cy - 8),
                         (cx - 6, cy + 8), 2)
        pygame.draw.rect(self.screen, BLACK, (cx - 10, cy + 8, 14, 3))

    def draw_mine(self, rect):
        cx, cy = rect.center
        pygame.draw.circle(self.screen, BLACK, (cx, cy), 8)
        for dx, dy in ((-11, 0), (11, 0), (0, -11), (0, 11), (-8, -8), (8, -8), (-8, 8), (8, 8)):
            pygame.draw.line(self.screen, BLACK, (cx, cy),
                             (cx + dx, cy + dy), 2)
        pygame.draw.circle(self.screen, LIGHT, (cx - 3, cy - 3), 2)

    def draw_cross(self, rect):
        pygame.draw.line(self.screen, RED, rect.topleft, rect.bottomright, 3)
        pygame.draw.line(self.screen, RED, rect.topright, rect.bottomleft, 3)

    # --- кадр
    def draw(self):
        b = self.board
        self.screen.fill(BG)

        # верхняя панель
        header_rect = pygame.Rect(0, 0, self.width, HEADER)
        self.draw_bevel(header_rect, raised=False, width=3)
        self.draw_led(b.mines - b.flags_used(), left_edge_x=10)
        self.draw_led(b.seconds(), right_edge_x=self.width - 10)
        self.draw_face()
        hint = self.font_small.render(
            f"{self.name}  |  1/2/3 - сложность  |  R - заново", True, DARK
        )
        self.screen.blit(hint, hint.get_rect(
            center=(self.width // 2, HEADER - 10)))

        # поле
        for r in range(b.rows):
            for c in range(b.cols):
                rect = pygame.Rect(c * CELL, HEADER + r * CELL, CELL, CELL)
                if b.revealed[r][c]:
                    pygame.draw.rect(self.screen, OPENED, rect)
                    pygame.draw.rect(self.screen, SHADOW, rect, 1)
                    if b.mine[r][c]:
                        if b.exploded == (c, r):
                            pygame.draw.rect(self.screen, RED,
                                             rect.inflate(-1, -1))
                        self.draw_mine(rect)
                    elif b.count[r][c] > 0:
                        n = b.count[r][c]
                        surf = self.font_num.render(
                            str(n), True, NUMBER_COLORS[n])
                        self.screen.blit(
                            surf, surf.get_rect(center=rect.center))
                else:
                    self.draw_bevel(rect, raised=True, width=3)
                    if b.flagged[r][c]:
                        self.draw_flag(rect)
                        # показать ошибочно поставленные флажки после проигрыша
                        if b.state == LOST and not b.mine[r][c]:
                            self.draw_cross(rect.inflate(-10, -10))

        pygame.display.flip()

    # --- события
    def cell_at(self, pos):
        x, y = pos
        if y < HEADER:
            return None
        c, r = x // CELL, (y - HEADER) // CELL
        if 0 <= c < self.board.cols and 0 <= r < self.board.rows:
            return c, r
        return None

    def handle_click(self, event):
        if event.button == 1 and self.face_rect.collidepoint(event.pos):
            self.board.reset()
            return
        cell = self.cell_at(event.pos)
        if cell is None:
            return
        c, r = cell
        b = self.board
        if event.button == 1:
            if b.revealed[r][c]:
                b.chord(c, r)
            else:
                b.open_cell(c, r)
        elif event.button == 3:
            b.toggle_flag(c, r)
        elif event.button == 2:
            b.chord(c, r)

    def run(self):
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
                        self.board.reset()
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        self.difficulty = {
                            pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}[event.key]
                        self.new_board()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(event)

            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
