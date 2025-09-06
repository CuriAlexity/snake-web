import sys
import os
import math
import wave
import struct
import random
import json
import time

import pygame


# --- Env
IS_WEB = (sys.platform == "emscripten")

# --- Config
CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
BASE_FPS = 12  # baseline speed
MIN_FPS = 2
MAX_FPS = 24
START_FPS = max(MIN_FPS, BASE_FPS // 5)  # 5x slower start

# Layout: reserve top area for HUD so snake never overlaps text
HUD_RESERVED_PX = 56  # height reserved at the top

COLOR_SNAKE = (0, 200, 120)
COLOR_FOOD = (220, 80, 90)
COLOR_TEXT = (230, 230, 230)
COLOR_OBSTACLE = (140, 160, 220)
# macOS-like visuals
GRADIENT_TOP = (34, 38, 58)      # deep indigo
GRADIENT_BOTTOM = (12, 14, 20)   # near-black
SNAKE_SHADOW_ALPHA = 90
FOOD_SHADOW_ALPHA = 110
CELL_INSET = 3  # visual spacing for rounded cells
HUD_ALPHA = 48
HUD_BORDER_ALPHA = 96


# Red border style
BORDER_COLOR = (200, 60, 60)
BORDER_THICKNESS = 3

# Apple spawn margin (cells) from borders
APPLE_MARGIN = 1

# Recompute window height to include HUD area
WINDOW_HEIGHT = HUD_RESERVED_PX + GRID_HEIGHT * CELL_SIZE

# Logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "last_run.jsonl")


def log_event(event: dict):
    if IS_WEB:
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def build_app_icon_surface(size: int = 64) -> pygame.Surface:
    """Create the same icon used for the app bundle and window icon."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # gradient background
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(GRADIENT_TOP[0] + (GRADIENT_BOTTOM[0] - GRADIENT_TOP[0]) * t)
        g = int(GRADIENT_TOP[1] + (GRADIENT_BOTTOM[1] - GRADIENT_TOP[1]) * t)
        b = int(GRADIENT_TOP[2] + (GRADIENT_BOTTOM[2] - GRADIENT_TOP[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (size, y))
    # three green dots
    dot_r = max(3, size // 12)
    y0 = int(size * 0.66)
    for x in (int(size * 0.5), int(size * 0.62), int(size * 0.74)):
        pygame.draw.circle(surf, COLOR_SNAKE, (x, y0), dot_r)
    return surf


def get_cell_rect(grid_pos, inset: int = CELL_INSET) -> pygame.Rect:
    x, y = grid_pos
    return pygame.Rect(
        x * CELL_SIZE + inset,
        HUD_RESERVED_PX + y * CELL_SIZE + inset,
        CELL_SIZE - inset * 2,
        CELL_SIZE - inset * 2,
    )


def get_playfield_rect() -> pygame.Rect:
    # Exact pixel rect that bounds all cell rects when inset is applied
    left = CELL_INSET
    top = HUD_RESERVED_PX + CELL_INSET
    width = GRID_WIDTH * CELL_SIZE - 2 * CELL_INSET
    height = GRID_HEIGHT * CELL_SIZE - 2 * CELL_INSET
    return pygame.Rect(left, top, width, height)


def draw_vertical_gradient(size, top_color, bottom_color) -> pygame.Surface:
    width, height = size
    gradient = pygame.Surface((width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        pygame.draw.line(gradient, (r, g, b), (0, y), (width, y))
    return gradient


def draw_snake_segment(surface: pygame.Surface, grid_pos):
    rect = get_cell_rect(grid_pos)
    # shadow
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow,
        (0, 0, 0, SNAKE_SHADOW_ALPHA),
        shadow.get_rect(),
        border_radius=rect.width // 3,
    )
    surface.blit(shadow, (rect.x, rect.y + 2))
    # body
    pygame.draw.rect(surface, COLOR_SNAKE, rect, border_radius=rect.width // 3)


def draw_food(surface: pygame.Surface, grid_pos):
    rect = get_cell_rect(grid_pos)
    # shadow
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, FOOD_SHADOW_ALPHA), shadow.get_rect())
    surface.blit(shadow, (rect.x, rect.y + 3))

    # base glossy sphere
    sphere = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(sphere, COLOR_FOOD, sphere.get_rect())
    # highlight
    highlight = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(
        highlight,
        (255, 255, 255, 90),
        pygame.Rect(int(rect.width * 0.15), int(rect.height * 0.10), int(rect.width * 0.45), int(rect.height * 0.35)),
    )
    sphere.blit(highlight, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
    surface.blit(sphere, (rect.x, rect.y))


def draw_obstacle(surface: pygame.Surface, grid_pos):
    rect = get_cell_rect(grid_pos)
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 80), shadow.get_rect(), border_radius=rect.width // 4)
    surface.blit(shadow, (rect.x, rect.y + 2))
    pygame.draw.rect(surface, COLOR_OBSTACLE, rect, border_radius=rect.width // 4)


def draw_glass_panel(surface: pygame.Surface, rect: pygame.Rect):
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (255, 255, 255, HUD_ALPHA), panel.get_rect(), border_radius=12)
    pygame.draw.rect(panel, (255, 255, 255, HUD_BORDER_ALPHA), panel.get_rect(), width=1, border_radius=12)
    # top sheen
    sheen = pygame.Surface((rect.width, rect.height // 2), pygame.SRCALPHA)
    for y in range(sheen.get_height()):
        alpha = int(70 * (1 - y / max(1, sheen.get_height() - 1)))
        pygame.draw.line(sheen, (255, 255, 255, alpha), (0, y), (sheen.get_width(), y))
    panel.blit(sheen, (0, 0))
    surface.blit(panel, rect.topleft)


def random_empty_cell(exclude_cells):
    # Respect margin from borders; build candidate list deterministically
    min_x = APPLE_MARGIN
    max_x = GRID_WIDTH - 1 - APPLE_MARGIN
    min_y = APPLE_MARGIN
    max_y = GRID_HEIGHT - 1 - APPLE_MARGIN
    candidates = []
    exclude = set(exclude_cells)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if (x, y) not in exclude:
                candidates.append((x, y))
    if not candidates:
        return None
    return random.choice(candidates)


def spawn_obstacles(num: int, exclude_cells):
    """Spawn up to num obstacle cells avoiding excluded cells and borders."""
    min_x = APPLE_MARGIN
    max_x = GRID_WIDTH - 1 - APPLE_MARGIN
    min_y = APPLE_MARGIN
    max_y = GRID_HEIGHT - 1 - APPLE_MARGIN
    exclude = set(exclude_cells)
    candidates = [(x, y) for y in range(min_y, max_y + 1) for x in range(min_x, max_x + 1) if (x, y) not in exclude]
    if not candidates:
        return set()
    k = min(num, len(candidates))
    return set(random.sample(candidates, k))


# --- Audio generation (simple procedural WAVs)

def _write_wav(path: str, samples, sample_rate: int = 22050):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as wf:
        n_channels = 1
        sampwidth = 2  # 16-bit
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s))
            frames += struct.pack('<h', int(v * 32767))
        wf.writeframes(frames)


def _triangle_like(t: float, f: float) -> float:
    w = 2 * math.pi * f
    return (8 / (math.pi ** 2)) * (
        math.sin(w * t) / (1 ** 2)
        - math.sin(3 * w * t) / (3 ** 2)
        + math.sin(5 * w * t) / (5 ** 2)
        - math.sin(7 * w * t) / (7 ** 2)
    ) * 0.7


def _tone_triangle(freq: float, duration_sec: float, volume: float = 0.16, sample_rate: int = 22050):
    total = int(duration_sec * sample_rate)
    env_attack = int(0.02 * sample_rate)
    env_release = int(0.15 * sample_rate)
    for i in range(total):
        t = i / sample_rate
        amp = 1.0
        if i < env_attack:
            amp = i / max(1, env_attack)
        elif i > total - env_release:
            amp = (total - i) / max(1, env_release)
        yield _triangle_like(t, freq) * volume * amp


def _render_tone_triangle(freq: float, duration_sec: float, volume: float = 0.16, sample_rate: int = 22050):
    return list(_tone_triangle(freq, duration_sec, volume=volume, sample_rate=sample_rate))


def _melody_sequence_groove():
    # Upbeat, cheerful groove ~1.5x faster than before (~61.9 BPM)
    sr = 22050
    beat = 60.0 / 61.9  # ~0.97s per beat
    q = beat * 0.45
    e = beat * 0.25
    s = beat * 0.16
    r = beat * 0.12

    C4, D4, E4, F4, G4, A4, B4, C5 = 261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25

    bars = [
        # Bar 1: C E G C5 with pickups
        (C4, e), (E4, e), (None, r), (G4, e), (None, r/2), (C5, q), (None, r), (E4, s), (G4, s),
        # Bar 2: walk down with bounce
        (A4, e), (None, r/2), (G4, e), (None, r/2), (E4, e), (D4, s), (E4, s), (F4, e), (G4, q),
        # Bar 3: bright lift
        (E4, e), (G4, e), (None, r/2), (C5, e), (B4, s), (A4, s), (G4, e), (None, r/2), (E4, e),
        # Bar 4: cadence
        (F4, e), (E4, e), (D4, e), (C4, q), (None, r),
    ]

    data = []
    for _ in range(2):
        for f, dur in bars:
            if f is None:
                data.extend((0.0 for _ in range(int(dur * sr))))
            else:
                data.extend(_render_tone_triangle(f, dur, volume=0.18))
    return data


def _eat_sfx():
    data = []
    for f in [520, 640, 760, 900]:
        data.extend(_tone_triangle(f, 0.06, volume=0.18))
    return data


def _game_over_sfx():
    data = []
    for f in [660, 520, 390, 260]:
        data.extend(_tone_triangle(f, 0.16, volume=0.16))
    return data


def ensure_audio_assets(asset_dir: str):
    # In web, just use bundled assets; don't write files
    base_music = os.path.join(asset_dir, "music.wav")
    base_eat = os.path.join(asset_dir, "eat.wav")
    base_over = os.path.join(asset_dir, "game_over.wav")
    if IS_WEB:
        return base_music, base_eat, base_over

    # Allow user-provided custom track to take precedence
    music_custom = None
    for ext in (".mp3", ".ogg", ".wav"):
        path = os.path.join(asset_dir, "music_custom" + ext)
        if os.path.exists(path):
            music_custom = path
            break

    music_path = os.path.join(asset_dir, "music.wav")
    eat_path = os.path.join(asset_dir, "eat.wav")
    over_path = os.path.join(asset_dir, "game_over.wav")

    os.makedirs(asset_dir, exist_ok=True)

    # Always regenerate our procedural music if no custom track
    if music_custom is None:
        _write_wav(music_path, _melody_sequence_groove())

    if not os.path.exists(eat_path):
        _write_wav(eat_path, _eat_sfx())
    if not os.path.exists(over_path):
        _write_wav(over_path, _game_over_sfx())

    return (music_custom or music_path), eat_path, over_path


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()
    try:
        font = pygame.font.SysFont("SF Pro Text", 24)
        title_font = pygame.font.SysFont("SF Pro Text", 48)
        button_font = pygame.font.SysFont("SF Pro Text", 26)
    except Exception:
        font = pygame.font.SysFont(None, 24)
        title_font = pygame.font.SysFont(None, 48)
        button_font = pygame.font.SysFont(None, 26)

    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "assets")
    music_path, eat_path, over_path = ensure_audio_assets(assets_dir)
    try:
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.set_volume(0.15)
    except Exception:
        pass
    eat_sound = pygame.mixer.Sound(eat_path)
    eat_sound.set_volume(0.45)
    game_over_sound = pygame.mixer.Sound(over_path)
    game_over_sound.set_volume(0.45)

    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    def reset_game():
        start = (GRID_WIDTH // 2, GRID_HEIGHT // 2)
        snake = [start, (start[0] - 1, start[1]), (start[0] - 2, start[1])]
        direction = RIGHT
        food = random_empty_cell(set(snake))
        score = 0
        return snake, direction, food, score

    snake, direction, food, score = reset_game()
    paused = False
    game_over = False
    you_win = False
    death_reason = ""
    played_game_over = False
    on_menu = True
    current_fps = START_FPS
    start_button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 80, WINDOW_HEIGHT // 2 - 22, 160, 44)
    pending_direction = direction
    obstacles = set()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                if on_menu:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        snake, direction, food, score = reset_game()
                        game_over = False
                        played_game_over = False
                        paused = False
                        on_menu = False
                        current_fps = START_FPS
                        pending_direction = direction
                        obstacles = set()
                        if not pygame.mixer.music.get_busy():
                            try:
                                pygame.mixer.music.play(-1)
                            except Exception:
                                pass
                elif game_over:
                    if event.key == pygame.K_r:
                        snake, direction, food, score = reset_game()
                        game_over = False
                        you_win = False
                        played_game_over = False
                        paused = False
                        on_menu = False
                        current_fps = START_FPS
                        pending_direction = direction
                        obstacles = set()
                        if not pygame.mixer.music.get_busy():
                            try:
                                pygame.mixer.music.play(-1)
                            except Exception:
                                pass
                elif you_win:
                    if event.key == pygame.K_r:
                        snake, direction, food, score = reset_game()
                        you_win = False
                        played_game_over = False
                        paused = False
                        on_menu = False
                        current_fps = START_FPS
                        pending_direction = direction
                        obstacles = set()
                        if not pygame.mixer.music.get_busy():
                            try:
                                pygame.mixer.music.play(-1)
                            except Exception:
                                pass
                else:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                        try:
                            if paused:
                                pygame.mixer.music.pause()
                            else:
                                if not game_over and not on_menu and not you_win:
                                    pygame.mixer.music.unpause()
                        except Exception:
                            pass
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        current_fps = max(MIN_FPS, current_fps - 1)
                    elif event.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                        current_fps = min(MAX_FPS, current_fps + 1)
                    else:
                        # one change per tick: update pending_direction only if it's not opposite of current direction
                        cur_dx, cur_dy = direction
                        if event.key in (pygame.K_UP, pygame.K_w):
                            if not (cur_dx == 0 and cur_dy == 1):
                                pending_direction = (0, -1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            if not (cur_dx == 0 and cur_dy == -1):
                                pending_direction = (0, 1)
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
                            if not (cur_dx == 1 and cur_dy == 0):
                                pending_direction = (-1, 0)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            if not (cur_dx == -1 and cur_dy == 0):
                                pending_direction = (1, 0)

            if event.type == pygame.MOUSEBUTTONUP and on_menu:
                if start_button_rect.collidepoint(event.pos):
                    snake, direction, food, score = reset_game()
                    game_over = False
                    played_game_over = False
                    paused = False
                    on_menu = False
                    current_fps = START_FPS
                    pending_direction = direction
                    obstacles = set()
                    if not pygame.mixer.music.get_busy():
                        try:
                            pygame.mixer.music.play(-1)
                        except Exception:
                            pass

        if not on_menu and not paused and not game_over and not you_win:
            # apply pending direction exactly once per tick
            direction = pending_direction
            head_x, head_y = snake[0]
            dx, dy = direction
            new_head = (head_x + dx, head_y + dy)

            # Wall collision
            if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
                game_over = True
                death_reason = "Hit wall"
            else:
                will_eat = (new_head == food)
                # Obstacle collision
                if new_head in obstacles:
                    game_over = True
                    death_reason = "Hit obstacle"
                else:
                    body_to_check = snake if will_eat else snake[:-1]
                    if new_head in body_to_check:
                        game_over = True
                        death_reason = "Hit self"
                    else:
                        snake.insert(0, new_head)
                        if will_eat:
                            score += 1
                            next_food = random_empty_cell(set(snake) | obstacles)
                            if next_food is None:
                                you_win = True
                                food = (-1, -1)
                            else:
                                food = next_food
                            current_fps = min(MAX_FPS, current_fps + 1)
                            try:
                                eat_sound.play()
                            except Exception:
                                pass
                            # Reset obstacles and spawn ~3 new ones
                            obstacles = spawn_obstacles(3, set(snake) | {food})
                        else:
                            snake.pop()

        if game_over and not played_game_over:
            try:
                pygame.mixer.music.fadeout(800)
                game_over_sound.play()
            except Exception:
                pass
            played_game_over = True
            log_event({
                "ts": int(time.time()),
                "event": "game_over",
                "reason": death_reason,
                "score": score,
                "length": len(snake),
                "speed": current_fps,
            })

        if you_win:
            try:
                pygame.mixer.music.fadeout(800)
            except Exception:
                pass
            log_event({
                "ts": int(time.time()),
                "event": "win",
                "score": score,
                "length": len(snake),
                "speed": current_fps,
            })
            win_text = f"You Win! Score: {score}. Press R to restart."
            win_surf = font.render(win_text, True, COLOR_TEXT)
            screen.blit(win_surf, (WINDOW_WIDTH // 2 - win_surf.get_width() // 2, WINDOW_HEIGHT // 2 - 12))

        # --- Draw
        bg = draw_vertical_gradient((WINDOW_WIDTH, WINDOW_HEIGHT), GRADIENT_TOP, GRADIENT_BOTTOM)
        screen.blit(bg, (0, 0))

        if on_menu:
            title_surf = title_font.render("Snake", True, COLOR_TEXT)
            screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, WINDOW_HEIGHT // 2 - 120))
            draw_glass_panel(screen, start_button_rect)
            btn_text = button_font.render("Start", True, COLOR_TEXT)
            screen.blit(btn_text, (start_button_rect.centerx - btn_text.get_width() // 2, start_button_rect.centery - btn_text.get_height() // 2))
            hint = "Space/Enter to start"
            hint_surf = font.render(hint, True, COLOR_TEXT)
            screen.blit(hint_surf, (WINDOW_WIDTH // 2 - hint_surf.get_width() // 2, start_button_rect.bottom + 12))
            pygame.display.flip()
            clock.tick(30)
            continue

        # HUD panel occupies top
        hud_rect = pygame.Rect(8, 8, WINDOW_WIDTH - 16, HUD_RESERVED_PX - 16)
        draw_glass_panel(screen, hud_rect)
        hud_text = f"Score: {score}   Speed: {current_fps}   Keys: arrows/WASD, +/- speed, Space pause, R restart, Esc quit"
        hud_surf = font.render(hud_text, True, COLOR_TEXT)
        screen.blit(hud_surf, (hud_rect.x + 12, hud_rect.y + (hud_rect.height - hud_surf.get_height()) // 2))

        # Red border around the playable area (below HUD)
        playfield_rect_outer = pygame.Rect(4, HUD_RESERVED_PX, WINDOW_WIDTH - 8, WINDOW_HEIGHT - HUD_RESERVED_PX - 4)
        pygame.draw.rect(screen, BORDER_COLOR, playfield_rect_outer, BORDER_THICKNESS, border_radius=8)

        # Draw food and snake below HUD
        # Obstacles
        for ob in obstacles:
            draw_obstacle(screen, ob)
        if not you_win:
            draw_food(screen, food)
        for segment in snake:
            draw_snake_segment(screen, segment)

        if paused and not game_over and not you_win:
            overlay = font.render("Paused", True, COLOR_TEXT)
            screen.blit(overlay, (WINDOW_WIDTH // 2 - overlay.get_width() // 2, WINDOW_HEIGHT // 2 - 12))

        if game_over:
            go_text = f"Game Over ({death_reason}). Score: {score}. Press R to restart or Esc to quit."
            go_surf = font.render(go_text, True, COLOR_TEXT)
            screen.blit(go_surf, (WINDOW_WIDTH // 2 - go_surf.get_width() // 2, WINDOW_HEIGHT // 2 - 12))

        pygame.display.flip()
        clock.tick(current_fps)


if __name__ == "__main__":
    main()








