# breakout.py
import pygame, sys, random
pygame.init()

W, H = 800, 600
WIN = pygame.display.set_mode((W, H))
pygame.display.set_caption("Breakout")
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 36)

BG = (15,15,24)
WHITE = (235,235,235)

PADDLE_W, PADDLE_H = 100, 16
BALL_R = 8

# bricks
BRICK_ROWS, BRICK_COLS = 6, 10
BRICK_W = (W - 100) // BRICK_COLS
BRICK_H = 22
BRICK_OFFX, BRICK_OFFY = 50, 80

def make_bricks():
    bricks = []
    colors = [(200,70,70),(200,140,70),(200,200,70),(70,180,120),(70,140,200),(140,90,200)]
    for r in range(BRICK_ROWS):
        for c in range(BRICK_COLS):
            x = BRICK_OFFX + c*BRICK_W
            y = BRICK_OFFY + r*BRICK_H
            rect = pygame.Rect(x+2, y+2, BRICK_W-4, BRICK_H-4)
            bricks.append((rect, colors[r % len(colors)]))
    return bricks

paddle = pygame.Rect(W//2 - PADDLE_W//2, H - 50, PADDLE_W, PADDLE_H)
ball_pos = pygame.Vector2(W//2, H//2 + 100)
ball_vel = pygame.Vector2(random.choice([-1,1])*5, -5)
bricks = make_bricks()
lives = 3
score = 0
running = True

def reset_ball():
    global ball_pos, ball_vel
    ball_pos = pygame.Vector2(paddle.centerx, paddle.top - BALL_R - 2)
    ball_vel = pygame.Vector2(random.choice([-1,1])*5, -5)

def draw():
    WIN.fill(BG)
    # bricks
    for rect, color in bricks:
        pygame.draw.rect(WIN, color, rect, border_radius=4)
    # paddle, ball
    pygame.draw.rect(WIN, WHITE, paddle, border_radius=6)
    pygame.draw.circle(WIN, WHITE, (int(ball_pos.x), int(ball_pos.y)), BALL_R)
    # HUD
    hud = FONT.render(f"Score: {score}   Lives: {lives}", True, WHITE)
    WIN.blit(hud, (20, 20))
    pygame.display.flip()

while running:
    dt = CLOCK.tick(60)
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]: paddle.x -= 8
    if keys[pygame.K_RIGHT]: paddle.x += 8
    paddle.x = max(0, min(W - PADDLE_W, paddle.x))

    # move ball
    ball_pos += ball_vel

    # wall bounce
    if ball_pos.x - BALL_R <= 0 or ball_pos.x + BALL_R >= W:
        ball_vel.x *= -1
    if ball_pos.y - BALL_R <= 0:
        ball_vel.y *= -1

    # paddle bounce
    if paddle.collidepoint(ball_pos.x, ball_pos.y + BALL_R) and ball_vel.y > 0:
        # add a bit of angle based on hit position
        offset = (ball_pos.x - paddle.centerx) / (PADDLE_W/2)
        ball_vel.y *= -1
        ball_vel.x = max(-7, min(7, ball_vel.x + offset * 4))

    # brick collisions
    hit_index = None
    for i, (rect, color) in enumerate(bricks):
        if rect.collidepoint(ball_pos.x, ball_pos.y - BALL_R) or \
           rect.collidepoint(ball_pos.x, ball_pos.y + BALL_R) or \
           rect.collidepoint(ball_pos.x - BALL_R, ball_pos.y) or \
           rect.collidepoint(ball_pos.x + BALL_R, ball_pos.y):
            hit_index = i
            break
    if hit_index is not None:
        rect, color = bricks.pop(hit_index)
        score += 10
        # decide bounce axis by proximity
        dx_left = abs(ball_pos.x + BALL_R - rect.left)
        dx_right = abs(rect.right - (ball_pos.x - BALL_R))
        dy_top = abs(ball_pos.y + BALL_R - rect.top)
        dy_bottom = abs(rect.bottom - (ball_pos.y - BALL_R))
        min_side = min(dx_left, dx_right, dy_top, dy_bottom)
        if min_side in (dx_left, dx_right):
            ball_vel.x *= -1
        else:
            ball_vel.y *= -1

    # lose life
    if ball_pos.y - BALL_R > H:
        lives -= 1
        if lives <= 0:
            # reset game
            bricks = make_bricks()
            score = 0
            lives = 3
        reset_ball()

    # win condition: all bricks cleared
    if not bricks:
        bricks = make_bricks()
        lives = min(5, lives + 1)
        reset_ball()

    draw()