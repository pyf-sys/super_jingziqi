# -*- coding: utf-8 -*-
"""超级井字棋（Ultimate Tic-Tac-Toe）功能库：布局、绘制、规则、精灵与音效。

依赖同目录的 jingziqi_lib.py（复用其中文字体加载和三连判断逻辑）。
游戏控制主循环在 super_jingziqi.py 里。

精灵技术的用法：
- MarkSprite：每个落下的棋子都是一个精灵，落子时有“从小到大弹出”的动画；
- Particle：获胜/平局时迸发的小光点，用 update() 更新位置、kill() 自动清理。
"""
import os
import math
import random
import array
import wave

import pygame as pg

from jingziqi_lib import X, O, EMPTY, X_COLOR, O_COLOR, make_font, get_winner, is_draw

# ---------- 布局尺寸 ----------
MICRO = 54                 # 每个小格子的边长（总共 81 个）
MINI = MICRO * 3           # 每个小棋盘的边长 = 156
GAP = 18                   # 小棋盘之间的间隔
TOTAL = MINI * 3 + GAP * 2 # 整个大棋盘的边长 = 522
WIDTH = 760                # 窗口宽度
HEADER_H = 130             # 顶部状态文字区域高度
BOTTOM_H = 86              # 底部按钮区域高度
HEIGHT = HEADER_H + TOTAL + BOTTOM_H  # 窗口高度 = 738
BOARD_LEFT = (WIDTH - TOTAL) // 2      # 大棋盘左边距 = 119
BOARD_TOP = HEADER_H                    # 大棋盘上边距 = 130
PLAY_CENTER = (BOARD_LEFT + TOTAL // 2, BOARD_TOP + TOTAL // 2)  # 大棋盘正中心
RESTART_RECT = pg.Rect(WIDTH // 2 - 100,
                       HEADER_H + TOTAL + (BOTTOM_H - 46) // 2,
                       200, 46)

# ---------- 颜色 ----------
BG           = (238, 238, 240)   # 窗口背景
CELL_BG      = (250, 250, 250)   # 空格子背景
BIG_LINE     = (70, 70, 70)      # 大棋盘粗线
MINI_LINE    = (150, 150, 150)   # 小棋盘细线
MINI_LINE_DIM = (205, 205, 205)  # 已结束小棋盘的细线（变淡）
WIN_BG_X     = (255, 227, 227)   # X 赢下的小棋盘背景
WIN_BG_O     = (223, 237, 255)   # O 赢下的小棋盘背景
DRAW_BG      = (231, 231, 231)   # 平局小棋盘背景
DRAW_COLOR   = (130, 130, 130)   # “平”字的灰色
DRAW_MARK    = "draw"            # owners 里表示平局小棋盘
GOLD         = (255, 200, 40)    # 获胜粒子的金色
HIGHLIGHT_INSET = 8       # 金色获胜高亮框向内缩进，避免贴住大棋盘黑色边界
# 下一步落子提示：不再画红/蓝粗框，改用淡色底高亮“该去的小棋盘”
HIGHLIGHT_FREE   = (255, 244, 178)   # 自由落子：可落子小棋盘的淡黄底
HIGHLIGHT_FORCED = (196, 232, 164)   # 被“送”到的小棋盘的淡绿底
SHOW_TARGET_HIGHLIGHT = True         # False 可完全关闭这层高亮

# ---------- 音效相关 ----------
SAMPLE_RATE = 22050
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
BGM_PATH = os.path.join(ASSETS_DIR, "bgm.wav")     # 背景音乐
PLACE_PATH = os.path.join(ASSETS_DIR, "place.wav") # 落子音效
WIN_PATH = os.path.join(ASSETS_DIR, "win.wav")     # 获胜音效

# ---------- 精灵参数 ----------
POP_MS = 150   # 棋子“弹出”动画时长（毫秒）


# ---------- 几何换算 ----------
def mini_rect(bi):
    """返回第 bi 个小棋盘（0~8，按行优先）在屏幕上的矩形。"""
    br, bc = divmod(bi, 3)
    left = BOARD_LEFT + bc * (MINI + GAP)
    top = BOARD_TOP + br * (MINI + GAP)
    return pg.Rect(left, top, MINI, MINI)


def mini_center(bi):
    """返回第 bi 个小棋盘的中心坐标。"""
    return mini_rect(bi).center


def cell_center(bi, r, c):
    """返回第 bi 个小棋盘里 (r, c) 格子的中心坐标。"""
    rect = mini_rect(bi)
    return (rect.left + c * MICRO + MICRO // 2,
            rect.top + r * MICRO + MICRO // 2)


def _chunk_index(v):
    """把相对大棋盘左上角的偏移换算成所在的大棋盘行/列；落在分隔缝里返回 None。"""
    for k in range(3):
        lo = k * (MINI + GAP)
        if lo <= v < lo + MINI:
            return k
    return None


def cell_from_pos(pos):
    """根据鼠标坐标 (x, y) 找到对应 (小棋盘编号 bi, 行 r, 列 c)；点在外面/缝隙里返回 None。"""
    x, y = pos
    if not (BOARD_LEFT <= x < BOARD_LEFT + TOTAL and
            BOARD_TOP <= y < BOARD_TOP + TOTAL):
        return None
    br = _chunk_index(y - BOARD_TOP)
    bc = _chunk_index(x - BOARD_LEFT)
    if br is None or bc is None:
        return None
    bi = br * 3 + bc
    r = (y - BOARD_TOP - br * (MINI + GAP)) // MICRO
    c = (x - BOARD_LEFT - bc * (MINI + GAP)) // MICRO
    return bi, r, c


# ---------- 规则判断 ----------
def is_board_open(bi, owners):
    """小棋盘是否还能落子（没被任何人赢下、也没下满）。"""
    return owners[bi] == EMPTY


def all_closed(owners):
    """9 个小棋盘是否全部结束。"""
    return all(o != EMPTY for o in owners)


def big_winner(owners):
    """在大棋盘上判断整局胜负。

    平局小棋盘不算任何人的领地，所以折算成空格再判断三连。
    返回 (胜者, 获胜的三个小棋盘列表, 是否全部结束)。
    """
    big = [[(owners[br * 3 + bc] if owners[br * 3 + bc] in (X, O) else EMPTY)
            for bc in range(3)] for br in range(3)]
    w, line = get_winner(big)
    return w, line, all_closed(owners)


def next_forced_board(r, c, owners):
    """对手下一步被送去的小棋盘编号；如果那个棋盘已结束则返回 None（自由落子）。"""
    nb = r * 3 + c
    return nb if owners[nb] == EMPTY else None


def make_move(boards, owners, bi, r, c, turn):
    """在 (bi, r, c) 落子并更新小棋盘归属。

    返回 (大棋盘胜者, 获胜连线, 是否全部结束, 对手被强制的小棋盘)。
    调用方要保证这一步是合法的。
    """
    boards[bi][r][c] = turn
    w, _ = get_winner(boards[bi])
    if w:
        owners[bi] = w
    elif is_draw(boards[bi]):
        owners[bi] = DRAW_MARK
    forced = next_forced_board(r, c, owners)
    bw, bline, closed_all = big_winner(owners)
    return bw, bline, closed_all, forced


# ---------- 音频合成与播放 ----------
def _tone(freq, dur, vol=0.4, rate=SAMPLE_RATE):
    """生成一个带轻微泛音的柔和单音（含淡入淡出，避免爆音）。"""
    n = int(rate * dur)
    if n <= 0:
        return []
    attack = max(1, int(rate * 0.008))
    release = max(1, int(rate * 0.05))
    if attack + release >= n:
        attack = release = max(1, n // 4)
    out = []
    for i in range(n):
        if i < attack:
            env = i / attack
        elif i >= n - release:
            env = (n - 1 - i) / release
        else:
            env = 1.0
        t = i / rate
        v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
        out.append(int(32767 * vol * env * v / 1.25))
    return out


def _silence(dur, rate=SAMPLE_RATE):
    return [0] * int(rate * dur)


def _make_bgm_samples():
    """一段轻柔的五声音阶循环旋律。"""
    notes = [  # (频率 Hz, 时长 秒)
        (523.25, 0.30), (659.25, 0.30), (783.99, 0.30), (659.25, 0.30),
        (587.33, 0.30), (698.46, 0.30), (880.00, 0.55),
        (783.99, 0.30), (659.25, 0.30), (587.33, 0.30), (523.25, 0.55),
    ]
    out = []
    for f, d in notes:
        out += _tone(f, d, vol=0.36)
        out += _silence(0.02)
    out += _silence(0.6)
    return out


def _make_place_samples():
    """落子时的短促“滴”声（频率快速下滑 + 快速衰减）。"""
    dur = 0.13
    n = int(SAMPLE_RATE * dur)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 900 - (900 - 320) * (i / n)
        phase += 2 * math.pi * f / SAMPLE_RATE
        env = math.exp(-9.0 * t)
        out.append(int(32767 * 0.6 * env * math.sin(phase)))
    return out


def _make_win_samples():
    """获胜时上扬的三连音。"""
    out = []
    for f in (523.25, 659.25, 783.99, 1046.50):
        out += _tone(f, 0.16, vol=0.45)
    return out


def _write_wav(path, samples):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = array.array("h", samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())


def ensure_sound_files():
    """第一次运行时在 assets 目录生成 3 个 wav（已有就跳过）。"""
    jobs = ((BGM_PATH, _make_bgm_samples()),
            (PLACE_PATH, _make_place_samples()),
            (WIN_PATH, _make_win_samples()))
    for path, samples in jobs:
        if not os.path.exists(path):
            _write_wav(path, samples)


class AudioPlayer:
    """背景音乐 + 音效播放器。没有音频设备时自动静音，不影响游戏运行。"""

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.place = None
        self.win = None

    def init(self):
        try:
            if pg.mixer.get_init() is None:
                pg.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
            ensure_sound_files()
            self.place = pg.mixer.Sound(PLACE_PATH)
            self.win = pg.mixer.Sound(WIN_PATH)
            pg.mixer.music.load(BGM_PATH)
            self.enabled = True
            self._apply_volume()
            pg.mixer.music.play(loops=-1)   # 背景音乐循环播放
        except Exception:
            self.enabled = False

    def _apply_volume(self):
        if not self.enabled:
            return
        level = 0.0 if self.muted else 1.0
        pg.mixer.music.set_volume(0.30 * level)
        self.place.set_volume(0.55 * level)
        self.win.set_volume(0.60 * level)

    def toggle_mute(self):
        """开关所有声音，返回当前是否静音。"""
        self.muted = not self.muted
        self._apply_volume()
        return self.muted

    def play_place(self):
        if self.enabled and not self.muted:
            self.place.play()

    def play_win(self):
        if self.enabled and not self.muted:
            self.win.play()

    def stop(self):
        if self.enabled:
            pg.mixer.music.stop()


# ---------- 精灵：棋子与粒子 ----------
def _make_mark_surface(player):
    """预渲染一枚 X 或 O 的透明图片（精灵用的 image）。"""
    surf = pg.Surface((MICRO, MICRO), pg.SRCALPHA)
    half = MICRO // 2 - 13
    cx = cy = MICRO // 2
    if player == X:
        pg.draw.line(surf, X_COLOR, (cx - half, cy - half), (cx + half, cy + half), 4)
        pg.draw.line(surf, X_COLOR, (cx - half, cy + half), (cx + half, cy - half), 4)
    elif player == O:
        pg.draw.circle(surf, O_COLOR, (cx, cy), half - 1, 4)
    return surf


class MarkSprite(pg.sprite.Sprite):
    """一个落下的棋子精灵。落子后 0.15 秒内从小弹到正常大小。"""

    def __init__(self, bi, r, c, player):
        super().__init__()
        self.born = pg.time.get_ticks()
        self.base = _make_mark_surface(player)
        self.image = self.base
        cx, cy = cell_center(bi, r, c)
        self.rect = self.image.get_rect(center=(cx, cy))

    def update(self, now=None):
        """根据出生时间调整缩放；动画结束后换回清晰的原始图片。"""
        if now is None:
            now = pg.time.get_ticks()
        age = now - self.born
        if age >= POP_MS:
            if self.image is not self.base:
                self.image = self.base
                self.rect = self.image.get_rect(center=self.rect.center)
            return
        t = age / POP_MS
        # easeOutBack 缓动：先快后慢，结束时轻微回弹
        c1 = 1.70158
        c3 = c1 + 1
        scale = max(0.05, 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2)
        self.image = pg.transform.rotozoom(self.base, 0, scale)
        self.rect = self.image.get_rect(center=self.rect.center)


class Particle(pg.sprite.Sprite):
    """获胜/平局时迸发的一个小光点：移动、淡出，寿命结束自动 kill()。"""

    def __init__(self, pos, color, now):
        super().__init__()
        self.born = now
        self.life = random.randint(450, 850)          # 存活毫秒
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 5.5)              # 每帧移动像素
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.radius = random.randint(2, 4)
        self.color = color
        self.rect = pg.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.rect.center = pos
        self._render(1.0)

    def _render(self, alpha):
        """按当前透明度重画小圆点。"""
        size = self.radius * 2
        surf = pg.Surface((size, size), pg.SRCALPHA)
        a = max(0, min(255, int(255 * alpha)))
        pg.draw.circle(surf, (*self.color, a), (self.radius, self.radius), self.radius)
        self.image = surf

    def update(self, now=None):
        if now is None:
            now = pg.time.get_ticks()
        age = now - self.born
        if age >= self.life:
            self.kill()      # 精灵技术：生命周期结束自己从 Group 移除
            return
        self.rect.move_ip(self.vx, self.vy)
        self._render(1.0 - age / self.life)


def burst_at(group, pos, color, count=16):
    """在 pos 处向四周迸发 count 个小光点，放进 group（一般是特效 Group）。"""
    now = pg.time.get_ticks()
    for _ in range(count):
        group.add(Particle(pos, color, now))


# ---------- 绘制 ----------
def draw_big_symbol(screen, center, half, player, width):
    """在 center 处画一个大 X 或 O（half 是半边长/半径）。"""
    cx, cy = center
    if player == X:
        pg.draw.line(screen, X_COLOR, (cx - half, cy - half), (cx + half, cy + half), width)
        pg.draw.line(screen, X_COLOR, (cx - half, cy + half), (cx + half, cy - half), width)
    elif player == O:
        pg.draw.circle(screen, O_COLOR, (cx, cy), half, width)


def draw_mini_base(screen, bi, owner, highlight=None):
    """画小棋盘的底色与内部细线（棋子由精灵组负责绘制）。

    highlight 给颜色时，表示这个小棋盘是“下一步落子目标”，用淡色底代替默认白底。
    """
    rect = mini_rect(bi)
    if highlight is not None:
        screen.fill(highlight, rect)
    elif owner == X:
        screen.fill(WIN_BG_X, rect)
    elif owner == O:
        screen.fill(WIN_BG_O, rect)
    elif owner == DRAW_MARK:
        screen.fill(DRAW_BG, rect)
    else:
        screen.fill(CELL_BG, rect)

    line_color = MINI_LINE if owner == EMPTY else MINI_LINE_DIM
    for i in (1, 2):
        x = rect.left + i * MICRO
        pg.draw.line(screen, line_color, (x, rect.top), (x, rect.bottom - 1), 2)
        y = rect.top + i * MICRO
        pg.draw.line(screen, line_color, (rect.left, y), (rect.right - 1, y), 2)


def draw_mini_overlay(screen, bi, owner, draw_font):
    """在已结束的小棋盘上盖大 X/O 或写“平”（画在棋子上面）。"""
    rect = mini_rect(bi)
    if owner in (X, O):
        draw_big_symbol(screen, rect.center, MINI // 2 - 24, owner, 10)
    elif owner == DRAW_MARK:
        img = draw_font.render("平", True, DRAW_COLOR)
        screen.blit(img, (rect.centerx - img.get_width() // 2,
                          rect.centery - img.get_height() // 2))


def draw_big_grid(screen):
    """画大棋盘的粗线（把 9 个小棋盘隔开）和外边框。"""
    pg.draw.rect(screen, BIG_LINE, (BOARD_LEFT, BOARD_TOP, TOTAL, TOTAL), 6)
    for k in (1, 2):
        x = BOARD_LEFT + k * (MINI + GAP) - GAP // 2
        pg.draw.line(screen, BIG_LINE, (x, BOARD_TOP), (x, BOARD_TOP + TOTAL), 8)
        y = BOARD_TOP + k * (MINI + GAP) - GAP // 2
        pg.draw.line(screen, BIG_LINE, (BOARD_LEFT, y), (BOARD_LEFT + TOTAL, y), 8)


def target_highlight(forced, owners, bi, game_over):
    """计算第 bi 个小棋盘的高亮底色；不需要高亮时返回 None。

    forced 有值：只把“被送到”的那个小棋盘用淡绿底标出；
    forced 为 None（自由落子）：把所有还没结束的小棋盘都用淡黄底标出。
    游戏结束后不再高亮，避免和获胜特效抢眼。
    """
    if game_over or not SHOW_TARGET_HIGHLIGHT or not is_board_open(bi, owners):
        return None
    if forced is not None:
        return HIGHLIGHT_FORCED if bi == forced else None
    return HIGHLIGHT_FREE


def draw_playfield(screen, owners, forced, draw_font, marks, game_over=False):
    """画整个棋盘区域：底色/高亮 → 细线 → 粗线 → 棋子精灵 → 结束标记。

    marks 是一个 pygame.sprite.Group，里面装着所有已落下的 MarkSprite。
    """
    screen.fill(BG)
    for bi in range(9):
        draw_mini_base(screen, bi, owners[bi], target_highlight(forced, owners, bi, game_over))
    draw_big_grid(screen)
    marks.draw(screen)                     # 精灵组批量绘制棋子
    for bi in range(9):
        draw_mini_overlay(screen, bi, owners[bi], draw_font)


def draw_match_mark(screen, winner):
    """整局获胜后，在整个大棋盘中间画一个大 X/O。"""
    draw_big_symbol(screen, PLAY_CENTER, TOTAL // 2 - 80, winner, 18)


def draw_big_win_highlight(screen, win_line):
    """整局获胜后，用金色框把构成三连的三个小棋盘标出来。"""
    for br, bc in win_line:
        rect = mini_rect(br * 3 + bc).inflate(-2 * HIGHLIGHT_INSET, -2 * HIGHLIGHT_INSET)
        pg.draw.rect(screen, GOLD, rect, 6)


def render_center(screen, text, font, color, y):
    """在窗口水平正中、纵坐标 y 处显示一行文字。"""
    img = font.render(text, True, color)
    screen.blit(img, (WIDTH // 2 - img.get_width() // 2, y))