"""Minimal Breakout clone implemented with pygame.

This module intentionally keeps the game logic in a single file, so adding
generous inline comments makes it easier for new readers to understand the
control flow.  The game follows a traditional structure: configure constants,
initialise pygame, build the brick layout, and then run the main loop that
updates the paddle, ball, and bricks.
"""

import pygame
import random
import sys

# Initialise pygame once so that modules such as ``pygame.display`` and
# ``pygame.font`` are ready before the game starts.
pygame.init()

# ---------------------------------------------------------------------------
# Global configuration constants
# ---------------------------------------------------------------------------
# Screen size (width, height) and the display/window objects used throughout
# the game.  Because the game is small these can stay as globals for easy
# access.
W, H = 800, 600
WIN = pygame.display.set_mode((W, H))
pygame.display.set_caption("Breakout")

# Clock used to cap the frame rate and a default font for the score HUD.
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 36)

# Colour palette.  These are intentionally muted to give the bricks visual
# contrast.
BG = (15, 15, 24)
WHITE = (235, 235, 235)

# Paddle dimensions and the radius of the ball.  Tuning these values changes
# how agile the game feels.
PADDLE_W, PADDLE_H = 100, 16
BALL_R = 8

# Brick layout configuration: number of rows/columns, brick size, and the
# offset from the window edges.  The brick width subtracts a total margin of 100
# pixels so the layout is centred with comfortable spacing near the walls.
BRICK_ROWS, BRICK_COLS = 6, 10
BRICK_W = (W - 100) // BRICK_COLS
BRICK_H = 22
BRICK_OFFX, BRICK_OFFY = 50, 80

def make_bricks():
    """Return a list of brick rectangles paired with their colours.

    Bricks are stored as ``(rect, colour)`` tuples to simplify drawing and
    collision checks.  Each brick is shrunk by a couple of pixels on each side
    so that a thin gap appears between bricks, which visually separates them.
    """

    bricks = []
    colors = [
        (200, 70, 70),
        (200, 140, 70),
        (200, 200, 70),
        (70, 180, 120),
        (70, 140, 200),
        (140, 90, 200),
    ]
    for r in range(BRICK_ROWS):
        for c in range(BRICK_COLS):
            # Compute the brick's top-left corner using the configured offset
            # and spacing.  The ``+2``/``-4`` tweak gives each brick a thin border.
            x = BRICK_OFFX + c * BRICK_W
            y = BRICK_OFFY + r * BRICK_H
            rect = pygame.Rect(x + 2, y + 2, BRICK_W - 4, BRICK_H - 4)
            bricks.append((rect, colors[r % len(colors)]))
    return bricks

# Game state ----------------------------------------------------------------
# The paddle, ball, bricks, score, lives, and running flag live at module scope
# because this is a compact example.  ``pygame.Vector2`` keeps the ball
# movement precise without manual tuple handling.
paddle = pygame.Rect(W//2 - PADDLE_W//2, H - 50, PADDLE_W, PADDLE_H)
ball_pos = pygame.Vector2(W//2, H//2 + 100)
ball_vel = pygame.Vector2(random.choice([-1,1])*5, -5)
bricks = make_bricks()
lives = 3
score = 0
running = True

def reset_ball():
    """Place the ball just above the paddle and give it an initial velocity."""

    global ball_pos, ball_vel
    ball_pos = pygame.Vector2(paddle.centerx, paddle.top - BALL_R - 2)
    ball_vel = pygame.Vector2(random.choice([-1,1])*5, -5)

def draw():
    """Render the current game state to the window."""

    WIN.fill(BG)
    # bricks
    for rect, color in bricks:
        pygame.draw.rect(WIN, color, rect, border_radius=4)

    # paddle, ball
    pygame.draw.rect(WIN, WHITE, paddle, border_radius=6)
    pygame.draw.circle(WIN, WHITE, (int(ball_pos.x), int(ball_pos.y)), BALL_R)

    # HUD (score and lives).  ``pygame.font.Font.render`` returns a surface that
    # can be blitted directly to the main window surface.
    hud = FONT.render(f"Score: {score}   Lives: {lives}", True, WHITE)
    WIN.blit(hud, (20, 20))

    # ``flip`` swaps the back buffer with what is currently displayed so the
    # drawn frame becomes visible.
    pygame.display.flip()

while running:
    # ``tick`` both limits the frame rate to 60 FPS and returns the elapsed
    # time since the previous frame, which could be used for time-based motion
    # (even though this example relies on fixed per-frame steps).
    dt = CLOCK.tick(60)
    # Process window events such as closing the window or pressing Escape.  The
    # quit event immediately exits the program while Escape simply stops the
    # main loop so pygame can shut down cleanly.
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

    keys = pygame.key.get_pressed()
    # Move the paddle left/right.  Paddle movement is clamped to the screen
    # bounds so it never disappears.
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
    # Iterate through bricks until we find one colliding with the ball.  Four
    # checks approximate a circle-rectangle collision by sampling along each
    # axis-aligned extreme of the ball.
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
        # Whichever side the ball is closest to determines whether we flip the
        # horizontal or vertical component of the velocity.  This produces more
        # convincing bounces than always reversing both components.
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
        # Reward the player with an extra life (capped at five) and re-serve the
        # ball to continue playing.
        lives = min(5, lives + 1)
        reset_ball()

    draw()