import pygame
import time
import random

SNAKE_SPEED = 15

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 480
BLOCK_SIZE = 20

BLACK = pygame.Color(0, 0, 0)
WHITE = pygame.Color(255, 255, 255)
RED = pygame.Color(255, 0, 0)
GREEN = pygame.Color(0, 255, 0)
BLUE = pygame.Color(0, 0, 255)

pygame.init()

pygame.display.set_caption('Snake game')
game_window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

fps = pygame.time.Clock()

snake_position = [100, 60]

snake_body = [[100, 60],
              [80, 60],
              [60, 60],
              [40, 60]
              ]

fruit_position = [random.randrange(1, (WINDOW_WIDTH//BLOCK_SIZE)) * BLOCK_SIZE, 
                  random.randrange(1, (WINDOW_HEIGHT//BLOCK_SIZE)) * BLOCK_SIZE]

fruit_spawn = True

direction = 'RIGHT'
change_to = direction


score = 0


def show_score(choice, color, font, size):
    score_font = pygame.font.SysFont(font, size)

    score_surface = score_font.render('Score : ' + str(score), True, color)
    
    score_rect = score_surface.get_rect()
    
    game_window.blit(score_surface, score_rect)


def game_over():
    my_font = pygame.font.SysFont('arial', 50)
    
    game_over_surface = my_font.render(
        'Your Score is : ' + str(score), True, RED)
    
    game_over_rect = game_over_surface.get_rect()
    
    game_over_rect.midtop = (WINDOW_WIDTH/2, WINDOW_HEIGHT/4)
    
    game_window.blit(game_over_surface, game_over_rect)
    pygame.display.flip()
    
    time.sleep(2)
    pygame.quit()
    quit()


while True:
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                change_to = 'UP'
            if event.key == pygame.K_DOWN:
                change_to = 'DOWN'
            if event.key == pygame.K_LEFT:
                change_to = 'LEFT'
            if event.key == pygame.K_RIGHT:
                change_to = 'RIGHT'
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()

    if change_to == 'UP' and direction != 'DOWN':
        direction = 'UP'
    if change_to == 'DOWN' and direction != 'UP':
        direction = 'DOWN'
    if change_to == 'LEFT' and direction != 'RIGHT':
        direction = 'LEFT'
    if change_to == 'RIGHT' and direction != 'LEFT':
        direction = 'RIGHT'

    if direction == 'UP':
        snake_position[1] -= BLOCK_SIZE
    if direction == 'DOWN':
        snake_position[1] += BLOCK_SIZE
    if direction == 'LEFT':
        snake_position[0] -= BLOCK_SIZE
    if direction == 'RIGHT':
        snake_position[0] += BLOCK_SIZE

    snake_body.insert(0, list(snake_position))
    if snake_position[0] == fruit_position[0] and snake_position[1] == fruit_position[1]:
        score += 10
        fruit_spawn = False
    else:
        snake_body.pop()
        
    if not fruit_spawn:
        fruit_position = [random.randrange(1, (WINDOW_WIDTH//BLOCK_SIZE)) * BLOCK_SIZE, 
                          random.randrange(1, (WINDOW_HEIGHT//BLOCK_SIZE)) * BLOCK_SIZE]
        
    fruit_spawn = True
    game_window.fill(BLACK)
    
    for pos in snake_body:
        pygame.draw.rect(game_window, GREEN,
                         pygame.Rect(pos[0], pos[1], BLOCK_SIZE, BLOCK_SIZE))
    pygame.draw.rect(game_window, WHITE, pygame.Rect(
        fruit_position[0], fruit_position[1], BLOCK_SIZE, BLOCK_SIZE))

    if snake_position[0] < 0 or snake_position[0] > WINDOW_WIDTH - BLOCK_SIZE:
        game_over()
    if snake_position[1] < 0 or snake_position[1] > WINDOW_HEIGHT - BLOCK_SIZE:
        game_over()

    for block in snake_body[1:]:
        if snake_position[0] == block[0] and snake_position[1] == block[1]:
            game_over()

    show_score(1, WHITE, 'arial', 20)

    pygame.display.update()

    fps.tick(SNAKE_SPEED)
