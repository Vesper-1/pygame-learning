"""Street Fighter style two-player game using pygame.

This module implements a simplified fighting game for two human players.
It includes:
- A name entry screen
- In-game movement and attack mechanics
- A persistent leaderboard stored in JSON
- An instructions overlay so new players know the controls

All major sections of the code contain detailed comments explaining their
purpose and any notable design choices.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import pygame

# --------------------------------------------------------------------------------------
# Constants shared across the module
# --------------------------------------------------------------------------------------
# Screen geometry and timing constants
WIDTH, HEIGHT = 960, 540
FPS = 60
GRAVITY = 1

# Gameplay tuning variables
GROUND_LEVEL = HEIGHT - 80  # Y-coordinate where fighters stand
PLAYER_SPEED = 6
JUMP_STRENGTH = 18
ATTACK_RANGE = 80
ATTACK_COOLDOWN = 20  # Frames between successive attacks
ATTACK_DAMAGE = 12
MAX_HEALTH = 100

# Dodge mechanics
DODGE_DURATION = 15  # Frames of dodge invincibility
DODGE_COOLDOWN = 90  # Frames before next dodge
DODGE_SPEED = 12  # Speed during dodge

# Special skill mechanics
SKILL_DAMAGE = 25  # Damage dealt by special skills
SKILL_COOLDOWN = 180  # Frames (3 seconds at 60 FPS)
SKILL_ENERGY_COST = 50  # Energy required to use skill
MAX_ENERGY = 100  # Maximum energy
ENERGY_REGEN_RATE = 0.3  # Energy regenerated per frame

# File storing leaderboard data. The file is placed beside the script so that the
# game can be launched from any working directory without losing track of the data.
LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), "leaderboard.json")

# Colour palette used throughout the UI.
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (50, 50, 50)
SOFT_RED = (200, 70, 70)
SOFT_BLUE = (70, 120, 220)
GREEN = (80, 200, 120)

# --------------------------------------------------------------------------------------
# Utility helpers for loading and saving leaderboard data
# --------------------------------------------------------------------------------------
def load_leaderboard() -> List[Dict[str, int]]:
    """Return the leaderboard entries sorted by wins.

    The file is stored in JSON as a list of dictionaries with keys
    ``name`` and ``wins``. Missing files are handled gracefully by returning
    an empty leaderboard, allowing first-time players to start with a clean slate.
    """

    if not os.path.exists(LEADERBOARD_FILE):
        return []

    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        # Corrupted files reset the board instead of crashing the game.
        return []

    # The stored data might not be sorted; ensure descending order by wins.
    return sorted(data, key=lambda entry: entry.get("wins", 0), reverse=True)


def save_leaderboard(entries: List[Dict[str, int]]) -> None:
    """Persist leaderboard entries to disk safely."""

    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as file:
            json.dump(entries, file, indent=2)
    except OSError:
        # Disk write failures are ignored to avoid crashing mid-game.
        pass


def update_leaderboard(winner_name: str) -> List[Dict[str, int]]:
    """Record a win for ``winner_name`` and return the updated leaderboard."""

    leaderboard = load_leaderboard()

    # Attempt to find the player in the existing leaderboard.
    for entry in leaderboard:
        if entry.get("name") == winner_name:
            entry["wins"] = entry.get("wins", 0) + 1
            break
    else:
        leaderboard.append({"name": winner_name, "wins": 1})

    leaderboard.sort(key=lambda entry: entry.get("wins", 0), reverse=True)
    save_leaderboard(leaderboard)
    return leaderboard


# --------------------------------------------------------------------------------------
# Data structures representing the fighters and inputs
# --------------------------------------------------------------------------------------
@dataclass
class ControlScheme:
    """Keyboard controls for a fighter.

    Attributes
    ----------
    left, right, jump, attack, dodge, skill: int
        ``pygame`` key constants for each action.
    """

    left: int
    right: int
    jump: int
    attack: int
    dodge: int
    skill: int


@dataclass
class Fighter:
    """A simple rectangle-based fighter with jump, attack, dodge, and special skill abilities."""

    name: str
    color: Tuple[int, int, int]
    controls: ControlScheme
    start_pos: Tuple[int, int]
    facing_right: bool
    rect: pygame.Rect = field(init=False)
    velocity_y: float = field(default=0)
    on_ground: bool = field(default=True)
    attack_cooldown: int = field(default=0)
    health: int = field(default=MAX_HEALTH)

    # Dodge mechanics
    is_dodging: bool = field(default=False)
    dodge_timer: int = field(default=0)
    dodge_cooldown: int = field(default=0)

    # Special skill mechanics
    energy: float = field(default=MAX_ENERGY)
    skill_cooldown: int = field(default=0)

    def __post_init__(self) -> None:
        # Fighters are represented by rectangles 60x120 pixels.
        self.rect = pygame.Rect(self.start_pos[0], self.start_pos[1], 60, 120)

    def apply_gravity(self) -> None:
        """Update vertical velocity and position to simulate gravity."""

        if not self.on_ground:
            self.velocity_y += GRAVITY
            self.rect.y += int(self.velocity_y)

            # Clamp to the ground and reset jump state when landing.
            if self.rect.bottom >= GROUND_LEVEL:
                self.rect.bottom = GROUND_LEVEL
                self.velocity_y = 0
                self.on_ground = True

    def handle_movement(self, keys_pressed: pygame.key.ScancodeWrapper) -> None:
        """Move fighter horizontally and handle jumping input."""

        # Cannot move normally while dodging
        if self.is_dodging:
            return

        # Horizontal movement responds directly to held keys.
        if keys_pressed[self.controls.left]:
            self.rect.x -= PLAYER_SPEED
            self.facing_right = False
        if keys_pressed[self.controls.right]:
            self.rect.x += PLAYER_SPEED
            self.facing_right = True

        # Prevent fighters from leaving the visible play area.
        self.rect.x = max(0, min(self.rect.x, WIDTH - self.rect.width))

        # Jumping is triggered once when the key is pressed while on the ground.
        if keys_pressed[self.controls.jump] and self.on_ground:
            self.on_ground = False
            self.velocity_y = -JUMP_STRENGTH

    def handle_dodge(self, keys_pressed: pygame.key.ScancodeWrapper) -> None:
        """Handle dodge mechanics with invincibility frames."""

        # Update dodge cooldown
        if self.dodge_cooldown > 0:
            self.dodge_cooldown -= 1

        # Update active dodge
        if self.is_dodging:
            self.dodge_timer -= 1
            # Move quickly in facing direction during dodge
            dodge_direction = 1 if self.facing_right else -1
            self.rect.x += DODGE_SPEED * dodge_direction
            self.rect.x = max(0, min(self.rect.x, WIDTH - self.rect.width))

            if self.dodge_timer <= 0:
                self.is_dodging = False
        else:
            # Trigger new dodge if key pressed and cooldown ready
            if keys_pressed[self.controls.dodge] and self.dodge_cooldown == 0 and self.on_ground:
                self.is_dodging = True
                self.dodge_timer = DODGE_DURATION
                self.dodge_cooldown = DODGE_COOLDOWN

    def regenerate_energy(self) -> None:
        """Gradually regenerate energy over time."""

        if self.energy < MAX_ENERGY:
            self.energy = min(self.energy + ENERGY_REGEN_RATE, MAX_ENERGY)

    def attempt_attack(self, opponent: "Fighter", keys_pressed: pygame.key.ScancodeWrapper) -> bool:
        """Perform an attack if the cooldown permits.

        Returns ``True`` when the attack successfully hits the opponent, allowing
        the caller to apply damage. Returns ``False`` if opponent is dodging.
        """

        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            return False

        if keys_pressed[self.controls.attack]:
            self.attack_cooldown = ATTACK_COOLDOWN

            # Define a hitbox extending from the fighter in the direction faced.
            if self.facing_right:
                attack_rect = pygame.Rect(
                    self.rect.right, self.rect.top + 20, ATTACK_RANGE, self.rect.height - 40
                )
            else:
                attack_rect = pygame.Rect(
                    self.rect.left - ATTACK_RANGE, self.rect.top + 20, ATTACK_RANGE, self.rect.height - 40
                )

            # Check if hit connects and opponent is not dodging (invincible)
            if attack_rect.colliderect(opponent.rect) and not opponent.is_dodging:
                return True

        return False

    def attempt_special_skill(self, opponent: "Fighter", keys_pressed: pygame.key.ScancodeWrapper) -> bool:
        """Perform a special skill attack if energy and cooldown permit.

        Returns ``True`` when the skill successfully hits the opponent.
        """

        # Update skill cooldown
        if self.skill_cooldown > 0:
            self.skill_cooldown -= 1
            return False

        # Check if skill key pressed and requirements met
        if keys_pressed[self.controls.skill]:
            if self.energy >= SKILL_ENERGY_COST and self.skill_cooldown == 0:
                # Consume energy and set cooldown
                self.energy -= SKILL_ENERGY_COST
                self.skill_cooldown = SKILL_COOLDOWN

                # Create larger hitbox for special skill
                skill_range = ATTACK_RANGE * 1.5
                if self.facing_right:
                    skill_rect = pygame.Rect(
                        self.rect.right, self.rect.top, skill_range, self.rect.height
                    )
                else:
                    skill_rect = pygame.Rect(
                        self.rect.left - skill_range, self.rect.top, skill_range, self.rect.height
                    )

                # Check if skill hits and opponent is not dodging
                if skill_rect.colliderect(opponent.rect) and not opponent.is_dodging:
                    return True

        return False

    def draw(self, surface: pygame.Surface) -> None:
        """Render the fighter and a simple outline."""

        # If dodging, make the fighter semi-transparent (visual feedback)
        if self.is_dodging:
            # Create a surface with alpha channel for transparency
            dodge_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            dodge_surface.fill((*self.color, 128))  # 50% opacity
            surface.blit(dodge_surface, self.rect.topleft)
            pygame.draw.rect(surface, WHITE, self.rect, 2)
        else:
            pygame.draw.rect(surface, self.color, self.rect)
            pygame.draw.rect(surface, WHITE, self.rect, 2)


# --------------------------------------------------------------------------------------
# UI rendering helpers
# --------------------------------------------------------------------------------------
def render_text(surface: pygame.Surface, text: str, pos: Tuple[int, int], size: int = 28,
                color: Tuple[int, int, int] = WHITE, center: bool = False) -> pygame.Rect:
    """Draw text onto the surface and return the resulting rectangle."""

    font = pygame.font.Font(None, size)
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if center:
        text_rect.center = pos
    else:
        text_rect.topleft = pos
    surface.blit(text_surface, text_rect)
    return text_rect


def draw_health_bars(surface: pygame.Surface, fighters: Tuple[Fighter, Fighter]) -> None:
    """Draw health bars and energy bars for each fighter at the top of the screen."""

    bar_width = 300
    bar_height = 24
    padding = 30
    bar_spacing = 30  # Space between health and energy bars

    for index, fighter in enumerate(fighters):
        x = padding if index == 0 else WIDTH - bar_width - padding
        y = padding

        # Draw health bar
        health_ratio = max(fighter.health, 0) / MAX_HEALTH
        health_filled = int(bar_width * health_ratio)

        pygame.draw.rect(surface, GREY, (x, y, bar_width, bar_height))
        pygame.draw.rect(surface, GREEN, (x, y, health_filled, bar_height))
        pygame.draw.rect(surface, WHITE, (x, y, bar_width, bar_height), 2)
        render_text(surface, f"{fighter.name}: {fighter.health} HP", (x, y - 26), size=24)

        # Draw energy bar
        energy_y = y + bar_height + 8
        energy_ratio = max(fighter.energy, 0) / MAX_ENERGY
        energy_filled = int(bar_width * energy_ratio)

        pygame.draw.rect(surface, GREY, (x, energy_y, bar_width, bar_height - 4))
        pygame.draw.rect(surface, (100, 150, 255), (x, energy_y, energy_filled, bar_height - 4))
        pygame.draw.rect(surface, WHITE, (x, energy_y, bar_width, bar_height - 4), 2)

        # Show skill cooldown indicator if skill is on cooldown
        if fighter.skill_cooldown > 0:
            cooldown_text = f"技能冷却: {fighter.skill_cooldown // FPS + 1}s"
            render_text(surface, cooldown_text, (x, energy_y + bar_height + 2), size=18, color=(255, 200, 100))


def draw_instructions_overlay(surface: pygame.Surface) -> None:
    """Render a fixed instructions panel at the bottom of the screen."""

    overlay_rect = pygame.Rect(0, HEIGHT - 160, WIDTH, 160)
    pygame.draw.rect(surface, (20, 20, 20), overlay_rect)
    pygame.draw.rect(surface, WHITE, overlay_rect, 2)

    render_text(surface, "控制指引 / Controls", (WIDTH // 2, HEIGHT - 150), size=32, center=True)
    render_text(surface, "玩家1: A/D移动, W跳跃, F攻击, G闪避, H技能", (30, HEIGHT - 115), size=24)
    render_text(surface, "玩家2: ←/→移动, ↑跳跃, K攻击, L闪避, ;技能", (30, HEIGHT - 85), size=24)
    render_text(surface, "提示: 技能需要50能量, 闪避时无敌", (30, HEIGHT - 55), size=22, color=(150, 255, 150))
    render_text(surface, "按ESC返回主菜单", (30, HEIGHT - 30), size=22)


def draw_leaderboard(surface: pygame.Surface, leaderboard: List[Dict[str, int]]) -> None:
    """Display the top leaderboard entries on the victory screen."""

    render_text(surface, "Leaderboard - 胜场排行", (WIDTH // 2, HEIGHT // 2 - 40), size=40, center=True)
    if not leaderboard:
        render_text(surface, "暂无记录，快来赢得第一场胜利!", (WIDTH // 2, HEIGHT // 2 + 10), size=28, center=True)
        return

    start_y = HEIGHT // 2
    for index, entry in enumerate(leaderboard[:5], start=1):
        render_text(
            surface,
            f"{index}. {entry['name']} - {entry['wins']} 胜",
            (WIDTH // 2, start_y + (index - 1) * 30),
            size=28,
            center=True,
        )


# --------------------------------------------------------------------------------------
# Screen / state handlers
# --------------------------------------------------------------------------------------
def name_entry_screen(screen: pygame.Surface, clock: pygame.time.Clock) -> Tuple[str, str] | None:
    """Collect player names via a simple text input interface.

    Returns
    -------
    tuple[str, str] | None
        Names for player one and player two. ``None`` is returned if the user
        chooses to exit the application during name entry.
    """

    player_names = ["", ""]
    active_index = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_BACKSPACE:
                    player_names[active_index] = player_names[active_index][:-1]
                elif event.key == pygame.K_RETURN:
                    if active_index == 1 and all(player_names):
                        return player_names[0], player_names[1]
                    # Move to the next player input once Enter is pressed.
                    active_index = min(active_index + 1, 1)
                else:
                    if len(player_names[active_index]) < 12:
                        player_names[active_index] += event.unicode

        screen.fill(BLACK)
        render_text(screen, "街头霸王 - 名称输入", (WIDTH // 2, 80), size=48, center=True)

        for index, prompt in enumerate(["玩家1 名称:", "玩家2 名称:"]):
            y = 200 + index * 100
            render_text(screen, prompt, (WIDTH // 2 - 200, y), size=36)

            input_box = pygame.Rect(WIDTH // 2 - 80, y - 8, 300, 50)
            pygame.draw.rect(screen, WHITE if index == active_index else GREY, input_box, 2)

            display_name = player_names[index] or "请输入..."
            render_text(screen, display_name, (input_box.x + 10, input_box.y + 10), size=32)

        render_text(screen, "按ENTER切换输入，完成后按ENTER继续", (WIDTH // 2, HEIGHT - 80), size=28, center=True)
        render_text(screen, "ESC退出游戏", (WIDTH // 2, HEIGHT - 40), size=24, center=True)

        pygame.display.flip()
        clock.tick(FPS)

        # The "return" condition is handled in the KEYDOWN block so no additional
        # checks are required here. The frame still needs to draw for responsive UI.


def instructions_screen(screen: pygame.Surface, clock: pygame.time.Clock, names: Tuple[str, str]) -> bool:
    """Show controls and wait for the players to start or exit."""

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return True

        screen.fill(BLACK)
        render_text(screen, "街头霸王 - 对战指南", (WIDTH // 2, 80), size=52, center=True)
        render_text(screen, f"玩家1: {names[0]}", (WIDTH // 2, 160), size=36, center=True)
        render_text(screen, f"玩家2: {names[1]}", (WIDTH // 2, 200), size=36, center=True)

        render_text(screen, "控制: 玩家1 A/D 左右, W 跳跃, F 攻击, G 闪避, H 技能", (WIDTH // 2, 270), size=28, center=True)
        render_text(screen, "控制: 玩家2 ←/→ 左右, ↑ 跳跃, K 攻击, L 闪避, ; 技能", (WIDTH // 2, 310), size=28, center=True)
        render_text(screen, "技能: 消耗50能量, 造成25伤害 (能量自动恢复)", (WIDTH // 2, 360), size=24, center=True, color=(100, 200, 255))
        render_text(screen, "闪避: 无敌状态, 快速移动, 有冷却时间", (WIDTH // 2, 390), size=24, center=True, color=(150, 255, 150))
        render_text(screen, "按 空格 或 回车 开始对战", (WIDTH // 2, 450), size=32, center=True)
        render_text(screen, "按 ESC 返回上一页", (WIDTH // 2, 490), size=28, center=True)

        pygame.display.flip()
        clock.tick(FPS)


def gameplay_loop(screen: pygame.Surface, clock: pygame.time.Clock, names: Tuple[str, str]) -> Tuple[str, List[Dict[str, int]]] | None:
    """Main gameplay loop handling the fight between two players.

    Returns
    -------
    tuple[str, list] | None
        The winner's name and the updated leaderboard. ``None`` indicates the
        players quit to the main menu (ESC) mid-battle.
    """

    players = (
        Fighter(
            name=names[0],
            color=SOFT_RED,
            controls=ControlScheme(
                left=pygame.K_a,
                right=pygame.K_d,
                jump=pygame.K_w,
                attack=pygame.K_f,
                dodge=pygame.K_g,
                skill=pygame.K_h
            ),
            start_pos=(WIDTH // 4, GROUND_LEVEL - 120),
            facing_right=True,
        ),
        Fighter(
            name=names[1],
            color=SOFT_BLUE,
            controls=ControlScheme(
                left=pygame.K_LEFT,
                right=pygame.K_RIGHT,
                jump=pygame.K_UP,
                attack=pygame.K_k,
                dodge=pygame.K_l,
                skill=pygame.K_SEMICOLON
            ),
            start_pos=(3 * WIDTH // 4, GROUND_LEVEL - 120),
            facing_right=False,
        ),
    )

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None

        keys_pressed = pygame.key.get_pressed()

        # Update fighters sequentially: movement -> gravity -> dodge -> energy regen
        for fighter in players:
            fighter.handle_movement(keys_pressed)
            fighter.apply_gravity()
            fighter.handle_dodge(keys_pressed)
            fighter.regenerate_energy()

        # Check attack collisions in both directions.
        if players[0].attempt_attack(players[1], keys_pressed):
            players[1].health -= ATTACK_DAMAGE
        if players[1].attempt_attack(players[0], keys_pressed):
            players[0].health -= ATTACK_DAMAGE

        # Check special skill collisions in both directions.
        if players[0].attempt_special_skill(players[1], keys_pressed):
            players[1].health -= SKILL_DAMAGE
        if players[1].attempt_special_skill(players[0], keys_pressed):
            players[0].health -= SKILL_DAMAGE

        # Determine if a player has been knocked out.
        for fighter in players:
            if fighter.health <= 0:
                winner = players[0] if fighter is players[1] else players[1]
                leaderboard = update_leaderboard(winner.name)
                return winner.name, leaderboard

        # Rendering pipeline: background -> ground -> fighters -> UI overlays.
        screen.fill((30, 30, 40))
        pygame.draw.rect(screen, (60, 60, 70), (0, GROUND_LEVEL, WIDTH, HEIGHT - GROUND_LEVEL))

        for fighter in players:
            fighter.draw(screen)

        draw_health_bars(screen, players)
        draw_instructions_overlay(screen)

        pygame.display.flip()
        clock.tick(FPS)


def victory_screen(screen: pygame.Surface, clock: pygame.time.Clock, winner_name: str,
                   leaderboard: List[Dict[str, int]]) -> bool:
    """Show the winner and leaderboard; return True to play again."""

    timer = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return True

        screen.fill((10, 10, 30))
        render_text(screen, f"{winner_name} 获胜!", (WIDTH // 2, 120), size=64, center=True)
        render_text(screen, "按 空格 或 回车 再战一局", (WIDTH // 2, 200), size=32, center=True)
        render_text(screen, "按 ESC 返回主菜单", (WIDTH // 2, 240), size=28, center=True)

        draw_leaderboard(screen, leaderboard)

        pygame.display.flip()
        clock.tick(FPS)
        timer += 1


# --------------------------------------------------------------------------------------
# Application entry point
# --------------------------------------------------------------------------------------
def main() -> None:
    """Program entry point coordinating the different screens."""

    pygame.init()
    pygame.display.set_caption("街头霸王 - 双人对战")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    while True:
        name_result = name_entry_screen(screen, clock)
        if name_result is None:
            break

        if not instructions_screen(screen, clock, name_result):
            continue

        game_result = gameplay_loop(screen, clock, name_result)
        if game_result is None:
            continue

        winner_name, leaderboard = game_result
        if not victory_screen(screen, clock, winner_name, leaderboard):
            continue

    pygame.quit()


if __name__ == "__main__":
    main()
