"""
Air Hockey
==========
A keyboard-controlled Air Hockey game built with pygame, with a resizable /
full-screen window and both single-player (vs AI) and local two-player modes.

Controls:
  Menu:
    1          - Start Single Player (you vs the computer)
    2          - Start Two Player (both players on this keyboard)
    F11 / F    - Toggle full screen
    ESC        - Quit

  In-game:
    Player 1 (blue, left):   W / A / S / D
    Player 2 (red, right):   Arrow Keys        (two player mode only)
    F11 / F    - Toggle full screen
    R          - Reset the score
    ESC        - Back to menu
    SPACE      - Play again (after a win)

Requirements:
  pip install pygame

Run:
  python air_hockey.py
"""

import sys
import math
import random
import pygame

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1000, 620
FPS = 60

TABLE_COLOR = (14, 98, 133)
TABLE_LINE_COLOR = (230, 230, 230)
WALL_COLOR = (20, 40, 60)
BG_COLOR = (8, 20, 30)

PLAYER_COLOR = (70, 150, 255)
PLAYER_RING = (220, 235, 255)
AI_COLOR = (255, 90, 90)
AI_RING = (255, 220, 220)
PUCK_COLOR = (250, 250, 250)

GOAL_WIDTH = 150           # opening size in the side walls
WALL_THICKNESS = 18

PADDLE_RADIUS = 32
PUCK_RADIUS = 16

PADDLE_KEY_ACCEL = 1.6      # how fast the keyboard paddle speeds up
PADDLE_KEY_MAX_SPEED = 12   # top keyboard paddle speed
PADDLE_FRICTION = 0.80      # paddle slows down when no key is held

AI_MAX_SPEED = 11.5          # top AI paddle speed (was too slow to catch fast pucks)
AI_REACTION = 0.22           # how snappily the AI closes the gap to its target
AI_PREDICT_FRAMES = 10       # how far ahead (in frames) the AI predicts the puck's path
AI_DEFEND_X_RATIO = 0.72     # where the AI "waits" along its half when not actively chasing

PUCK_FRICTION = 0.996
MAX_PUCK_SPEED = 24
MIN_PUCK_SPEED_AFTER_HIT = 6

WIN_SCORE = 7

MENU, PLAYING, GAME_OVER = "menu", "playing", "game_over"
MODE_ONE_PLAYER, MODE_TWO_PLAYER = "1p", "2p"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def vec_length(vx, vy):
    return math.hypot(vx, vy)


class Puck:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = PUCK_RADIUS
        self.trail = []

    def reset(self, x, y, serve_towards=1):
        self.x = x
        self.y = y
        angle = random.uniform(-0.5, 0.5)
        speed = 6
        self.vx = math.cos(angle) * speed * serve_towards
        self.vy = math.sin(angle) * speed
        self.trail.clear()

    def update(self, table_rect, goal_top, goal_bottom):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)

        self.x += self.vx
        self.y += self.vy

        self.vx *= PUCK_FRICTION
        self.vy *= PUCK_FRICTION

        speed = vec_length(self.vx, self.vy)
        if speed > MAX_PUCK_SPEED:
            scale = MAX_PUCK_SPEED / speed
            self.vx *= scale
            self.vy *= scale

        top = table_rect.top + self.radius
        bottom = table_rect.bottom - self.radius
        left = table_rect.left + self.radius
        right = table_rect.right - self.radius

        if self.y < top:
            self.y = top
            self.vy *= -1
        elif self.y > bottom:
            self.y = bottom
            self.vy *= -1

        if self.x < left:
            if not (goal_top < self.y < goal_bottom):
                self.x = left
                self.vx *= -1
        elif self.x > right:
            if not (goal_top < self.y < goal_bottom):
                self.x = right
                self.vx *= -1

    def draw(self, screen):
        for i, (tx, ty) in enumerate(self.trail):
            alpha_radius = max(1, int(self.radius * (i + 1) / len(self.trail)))
            fade_surf = pygame.Surface((alpha_radius * 2, alpha_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(fade_surf, (255, 255, 255, 25), (alpha_radius, alpha_radius), alpha_radius)
            screen.blit(fade_surf, (tx - alpha_radius, ty - alpha_radius))

        pygame.draw.circle(screen, (0, 0, 0), (int(self.x), int(self.y)), self.radius + 2)
        pygame.draw.circle(screen, PUCK_COLOR, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (200, 200, 200), (int(self.x), int(self.y)), self.radius, 2)


class Paddle:
    """A paddle that can be driven either by keyboard acceleration or by AI logic."""

    def __init__(self, x, y, color, ring_color, radius=PADDLE_RADIUS):
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = radius
        self.color = color
        self.ring_color = ring_color

    def move_with_keys(self, up, down, left, right, bounds):
        ax = (right - left) * PADDLE_KEY_ACCEL
        ay = (down - up) * PADDLE_KEY_ACCEL

        self.vx = clamp(self.vx + ax, -PADDLE_KEY_MAX_SPEED, PADDLE_KEY_MAX_SPEED)
        self.vy = clamp(self.vy + ay, -PADDLE_KEY_MAX_SPEED, PADDLE_KEY_MAX_SPEED)

        if left == right:
            self.vx *= PADDLE_FRICTION
        if up == down:
            self.vy *= PADDLE_FRICTION

        self.x = clamp(self.x + self.vx, bounds.left + self.radius, bounds.right - self.radius)
        self.y = clamp(self.y + self.vy, bounds.top + self.radius, bounds.bottom - self.radius)

        # if we hit a wall, kill velocity in that direction so we don't "stick"
        if self.x in (bounds.left + self.radius, bounds.right - self.radius):
            self.vx = 0
        if self.y in (bounds.top + self.radius, bounds.bottom - self.radius):
            self.vy = 0

    def move_towards(self, target_x, target_y, bounds, max_speed, reaction):
        target_x = clamp(target_x, bounds.left + self.radius, bounds.right - self.radius)
        target_y = clamp(target_y, bounds.top + self.radius, bounds.bottom - self.radius)

        self.x += clamp((target_x - self.x) * reaction, -max_speed, max_speed)
        self.y += clamp((target_y - self.y) * reaction, -max_speed, max_speed)

    def update_velocity_from_position(self):
        self.vx = self.x - self.prev_x
        self.vy = self.y - self.prev_y
        self.prev_x, self.prev_y = self.x, self.y

    def draw(self, screen):
        pygame.draw.circle(screen, (0, 0, 0), (int(self.x), int(self.y)), self.radius + 3)
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, self.ring_color, (int(self.x), int(self.y)), self.radius - 8, 3)
        pygame.draw.circle(screen, self.ring_color, (int(self.x), int(self.y)), 6)


def resolve_paddle_puck_collision(paddle, puck):
    dx = puck.x - paddle.x
    dy = puck.y - paddle.y
    dist = vec_length(dx, dy)
    min_dist = paddle.radius + puck.radius

    if dist == 0:
        dx, dy, dist = 0, -1, 1

    if dist < min_dist:
        overlap = min_dist - dist
        nx, ny = dx / dist, dy / dist

        puck.x += nx * overlap
        puck.y += ny * overlap

        rel_vx = puck.vx - paddle.vx
        rel_vy = puck.vy - paddle.vy
        dot = rel_vx * nx + rel_vy * ny

        if dot < 0:
            puck.vx -= 2 * dot * nx
            puck.vy -= 2 * dot * ny

        puck.vx += paddle.vx * 0.55
        puck.vy += paddle.vy * 0.55

        speed = vec_length(puck.vx, puck.vy)
        if speed < MIN_PUCK_SPEED_AFTER_HIT:
            if speed == 0:
                puck.vx, puck.vy = nx, ny
                speed = 1
            scale = MIN_PUCK_SPEED_AFTER_HIT / speed
            puck.vx *= scale
            puck.vy *= scale


def compute_ai_target(puck, table_rect, ai_radius):
    """
    Decide where the AI paddle should move to.

    - If the puck is in (or heading into) the AI's half, predict where it will
      be a few frames from now -- including bounces off the top/bottom walls --
      and drive straight at that spot so the AI actually intercepts fast pucks
      instead of just mirroring the puck's current position.
    - Otherwise, fall back to a "ready" position near the goal mouth, tracking
      the puck's height loosely so it's never caught flat-footed.
    """
    top = table_rect.top + PUCK_RADIUS
    bottom = table_rect.bottom - PUCK_RADIUS
    span = max(1, bottom - top)

    puck_heading_towards_ai = puck.vx > -0.5
    puck_in_ai_half = puck.x > table_rect.centerx - 30

    if puck_in_ai_half or puck_heading_towards_ai:
        predicted_x = puck.x + puck.vx * AI_PREDICT_FRAMES
        predicted_y = puck.y + puck.vy * AI_PREDICT_FRAMES

        # reflect the predicted y off the top/bottom walls (simple triangle-wave bounce)
        offset = (predicted_y - top) % (2 * span)
        if offset > span:
            offset = 2 * span - offset
        predicted_y = top + offset

        desired_x = clamp(predicted_x, table_rect.centerx + ai_radius, table_rect.right - ai_radius)
        desired_y = clamp(predicted_y, top, bottom)
    else:
        # puck is calmly on the player's side -- hang back near the goal, but
        # keep drifting towards the puck's height so we're ready to react
        home_x = table_rect.centerx + (table_rect.right - table_rect.centerx) * AI_DEFEND_X_RATIO
        desired_x = home_x
        desired_y = table_rect.centery + (puck.y - table_rect.centery) * 0.4

    return desired_x, desired_y


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------
def compute_layout(screen_width, screen_height):
    margin_x = max(30, int(screen_width * 0.05))
    margin_top = max(80, int(screen_height * 0.14))
    margin_bottom = max(70, int(screen_height * 0.11))

    table_rect = pygame.Rect(
        margin_x, margin_top,
        screen_width - margin_x * 2,
        screen_height - margin_top - margin_bottom
    )
    goal_top = table_rect.centery - GOAL_WIDTH // 2
    goal_bottom = table_rect.centery + GOAL_WIDTH // 2
    return table_rect, goal_top, goal_bottom


# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------
def draw_table(screen, table_rect, goal_top, goal_bottom):
    screen.fill(BG_COLOR)
    pygame.draw.rect(screen, TABLE_COLOR, table_rect, border_radius=18)

    cx = table_rect.centerx
    pygame.draw.line(screen, TABLE_LINE_COLOR, (cx, table_rect.top + 6), (cx, table_rect.bottom - 6), 3)
    pygame.draw.circle(screen, TABLE_LINE_COLOR, (cx, table_rect.centery), 70, 3)
    pygame.draw.circle(screen, TABLE_LINE_COLOR, (cx, table_rect.centery), 4)

    pygame.draw.circle(screen, TABLE_LINE_COLOR, (table_rect.left, table_rect.centery), 90, 3)
    pygame.draw.circle(screen, TABLE_LINE_COLOR, (table_rect.right, table_rect.centery), 90, 3)

    wt = WALL_THICKNESS
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.left - wt, table_rect.top - wt,
                                           table_rect.width + wt * 2, wt))
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.left - wt, table_rect.bottom,
                                           table_rect.width + wt * 2, wt))
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.left - wt, table_rect.top - wt,
                                           wt, (goal_top - table_rect.top) + wt))
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.left - wt, goal_bottom,
                                           wt, (table_rect.bottom - goal_bottom) + wt))
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.right, table_rect.top - wt,
                                           wt, (goal_top - table_rect.top) + wt))
    pygame.draw.rect(screen, WALL_COLOR, (table_rect.right, goal_bottom,
                                           wt, (table_rect.bottom - goal_bottom) + wt))

    pygame.draw.rect(screen, (255, 255, 255), (table_rect.left - wt - 4, goal_top, 4, goal_bottom - goal_top))
    pygame.draw.rect(screen, (255, 255, 255), (table_rect.right + wt, goal_top, 4, goal_bottom - goal_top))


def draw_scoreboard(screen, font, big_font, score_left, score_right, table_rect, mode):
    text = big_font.render(f"{score_left}", True, PLAYER_COLOR)
    screen.blit(text, (table_rect.centerx - 90 - text.get_width() // 2, 18))

    text2 = big_font.render(f"{score_right}", True, AI_COLOR)
    screen.blit(text2, (table_rect.centerx + 90 - text2.get_width() // 2, 18))

    dash = font.render("-", True, TABLE_LINE_COLOR)
    screen.blit(dash, (table_rect.centerx - dash.get_width() // 2, 26))

    p2_label = "Player 2" if mode == MODE_TWO_PLAYER else "Computer"
    labels = font.render(f"Player 1 (WASD)        vs        {p2_label} ({'Arrows' if mode == MODE_TWO_PLAYER else 'AI'})",
                          True, (170, 190, 200))
    screen.blit(labels, (table_rect.centerx - labels.get_width() // 2, table_rect.top - 30))

    hint = font.render("R = reset score   |   F11 = fullscreen   |   ESC = menu", True, (170, 190, 200))
    screen.blit(hint, (table_rect.centerx - hint.get_width() // 2, table_rect.bottom + 20))


def draw_winner_banner(screen, font, big_font, winner_text, table_rect):
    overlay = pygame.Surface((table_rect.width, 120), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (table_rect.left, table_rect.centery - 60))

    text = big_font.render(winner_text, True, (255, 255, 255))
    screen.blit(text, (table_rect.centerx - text.get_width() // 2, table_rect.centery - 45))

    sub = font.render("Press SPACE to play again   |   ESC for menu", True, (230, 230, 230))
    screen.blit(sub, (table_rect.centerx - sub.get_width() // 2, table_rect.centery + 15))


def draw_menu(screen, font, big_font, mid_font, screen_width, screen_height, fullscreen):
    screen.fill(BG_COLOR)

    title = big_font.render("AIR HOCKEY", True, (255, 255, 255))
    screen.blit(title, (screen_width // 2 - title.get_width() // 2, screen_height * 0.22))

    options = [
        ("1", "Single Player  (vs Computer)"),
        ("2", "Two Player  (WASD  vs  Arrow Keys)"),
    ]
    y = screen_height * 0.42
    for key, label in options:
        line = mid_font.render(f"[{key}]   {label}", True, (220, 230, 240))
        screen.blit(line, (screen_width // 2 - line.get_width() // 2, y))
        y += 55

    fs_state = "ON" if fullscreen else "OFF"
    extra = [
        f"F11 / F  -  Toggle full screen (currently {fs_state})",
        "ESC  -  Quit",
    ]
    y += 30
    for line_text in extra:
        line = font.render(line_text, True, (150, 170, 185))
        screen.blit(line, (screen_width // 2 - line.get_width() // 2, y))
        y += 32


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def make_display(width, height, fullscreen):
    if fullscreen:
        info = pygame.display.Info()
        return pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    return pygame.display.set_mode((width, height), pygame.RESIZABLE)


def main():
    pygame.init()
    pygame.display.set_caption("Air Hockey")

    fullscreen = False
    windowed_size = (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    screen = make_display(*windowed_size, fullscreen)

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 22, bold=True)
    mid_font = pygame.font.SysFont("arial", 30, bold=True)
    big_font = pygame.font.SysFont("arial", 54, bold=True)

    def current_size():
        surf = pygame.display.get_surface()
        return surf.get_width(), surf.get_height()

    table_rect, goal_top, goal_bottom = compute_layout(*current_size())

    def fresh_entities():
        p1 = Paddle(table_rect.left + 80, table_rect.centery, PLAYER_COLOR, PLAYER_RING)
        p2 = Paddle(table_rect.right - 80, table_rect.centery, AI_COLOR, AI_RING)
        pk = Puck(table_rect.centerx, table_rect.centery)
        pk.reset(table_rect.centerx, table_rect.centery, serve_towards=random.choice([-1, 1]))
        return p1, p2, pk

    player, opponent, puck = fresh_entities()

    state = MENU
    mode = MODE_ONE_PLAYER
    score_left = 0
    score_right = 0
    winner_text = ""

    def relayout():
        nonlocal table_rect, goal_top, goal_bottom
        table_rect, goal_top, goal_bottom = compute_layout(*current_size())
        # keep paddles / puck sensibly positioned within the new table
        player.x = clamp(player.x, table_rect.left + player.radius, table_rect.centerx - player.radius)
        player.y = clamp(player.y, table_rect.top + player.radius, table_rect.bottom - player.radius)
        opponent.x = clamp(opponent.x, table_rect.centerx + opponent.radius, table_rect.right - opponent.radius)
        opponent.y = clamp(opponent.y, table_rect.top + opponent.radius, table_rect.bottom - opponent.radius)
        puck.x = clamp(puck.x, table_rect.left + puck.radius, table_rect.right - puck.radius)
        puck.y = clamp(puck.y, table_rect.top + puck.radius, table_rect.bottom - puck.radius)

    def toggle_fullscreen():
        nonlocal fullscreen, screen
        fullscreen = not fullscreen
        screen = make_display(*windowed_size, fullscreen)
        relayout()

    def start_game(chosen_mode):
        nonlocal state, mode, score_left, score_right, player, opponent, puck
        mode = chosen_mode
        score_left = 0
        score_right = 0
        player, opponent, puck = fresh_entities()
        state = PLAYING

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                if not fullscreen:
                    windowed_size = (event.w, event.h)
                    screen = pygame.display.set_mode(windowed_size, pygame.RESIZABLE)
                relayout()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == MENU:
                        running = False
                    else:
                        state = MENU

                elif event.key in (pygame.K_F11, pygame.K_f):
                    toggle_fullscreen()

                elif state == MENU:
                    if event.key == pygame.K_1:
                        start_game(MODE_ONE_PLAYER)
                    elif event.key == pygame.K_2:
                        start_game(MODE_TWO_PLAYER)

                elif state == PLAYING:
                    if event.key == pygame.K_r:
                        score_left = 0
                        score_right = 0

                elif state == GAME_OVER:
                    if event.key == pygame.K_SPACE:
                        start_game(mode)

        keys = pygame.key.get_pressed()

        if state == MENU:
            draw_menu(screen, font, big_font, mid_font, *current_size(), fullscreen)

        elif state == PLAYING:
            left_half = pygame.Rect(table_rect.left, table_rect.top,
                                     table_rect.width // 2, table_rect.height)
            right_half = pygame.Rect(table_rect.centerx, table_rect.top,
                                      table_rect.width - table_rect.width // 2, table_rect.height)

            # player 1: WASD, confined to left half
            player.move_with_keys(
                up=keys[pygame.K_w], down=keys[pygame.K_s],
                left=keys[pygame.K_a], right=keys[pygame.K_d],
                bounds=left_half
            )

            if mode == MODE_TWO_PLAYER:
                # player 2: arrow keys, confined to right half
                opponent.move_with_keys(
                    up=keys[pygame.K_UP], down=keys[pygame.K_DOWN],
                    left=keys[pygame.K_LEFT], right=keys[pygame.K_RIGHT],
                    bounds=right_half
                )
            else:
                # AI opponent
                desired_x, desired_y = compute_ai_target(puck, table_rect, opponent.radius)
                opponent.move_towards(desired_x, desired_y, right_half, AI_MAX_SPEED, AI_REACTION)
                opponent.update_velocity_from_position()

            puck.update(table_rect, goal_top, goal_bottom)
            resolve_paddle_puck_collision(player, puck)
            resolve_paddle_puck_collision(opponent, puck)

            if puck.x < table_rect.left - puck.radius:
                score_right += 1
                puck.reset(table_rect.centerx, table_rect.centery, serve_towards=1)
            elif puck.x > table_rect.right + puck.radius:
                score_left += 1
                puck.reset(table_rect.centerx, table_rect.centery, serve_towards=-1)

            if score_left >= WIN_SCORE:
                winner_text = "Player 1 Wins!"
                state = GAME_OVER
            elif score_right >= WIN_SCORE:
                winner_text = "Player 2 Wins!" if mode == MODE_TWO_PLAYER else "Computer Wins!"
                state = GAME_OVER

            draw_table(screen, table_rect, goal_top, goal_bottom)
            puck.draw(screen)
            player.draw(screen)
            opponent.draw(screen)
            draw_scoreboard(screen, font, big_font, score_left, score_right, table_rect, mode)

        elif state == GAME_OVER:
            draw_table(screen, table_rect, goal_top, goal_bottom)
            puck.draw(screen)
            player.draw(screen)
            opponent.draw(screen)
            draw_scoreboard(screen, font, big_font, score_left, score_right, table_rect, mode)
            draw_winner_banner(screen, font, big_font, winner_text, table_rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()