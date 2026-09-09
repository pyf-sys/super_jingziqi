# -*- coding: utf-8 -*-
"""井字棋功能库：常量、字体、绘制、胜负判断等（不含主循环）。"""
import os
import pygame as pg

# ---------- 窗口与棋盘尺寸 ----------
CELL = 200            # 每个格子的边长
BOARD_TOP = 120       # 棋盘顶部离窗口顶部的距离
SCREEN_W = CELL * 3   # 窗口宽度 = 600
SCREEN_H = 800        # 窗口高度
RESTART_RECT = pg.Rect(SCREEN_W // 2 - 100, SCREEN_H - 60, 200, 42)
LINE_W = 6            # 棋盘线宽
MARK_W = 6            # X / O 的线宽

# 颜色（用 RGB 表示）
BG_COLOR   = (245, 245, 245)   # 背景
GRID_COLOR = (60, 60, 60)      # 棋盘线
X_COLOR    = (220, 80, 80)     # X 的红色
O_COLOR    = (70, 130, 220)    # O 的蓝色
WIN_COLOR  = (255, 200, 40)    # 获胜高亮的金色
TEXT_COLOR = (40, 40, 40)      # 普通文字
BTN_COLOR  = (200, 200, 200)   # 按钮
BTN_HOVER  = (170, 170, 170)   # 鼠标悬停时的按钮

# 玩家标记
X = "X"
O = "O"
EMPTY = ""


def find_font_file(*names):
    """在 Windows 字体目录里按文件名找字体，返回第一个存在的完整路径。"""
    font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in names:
        path = os.path.join(font_dir, name)
        if os.path.exists(path):
            return path
    return None


def make_font(size, bold=False):
    """加载一个能显示中文的字体。

    注意：不要用 pygame 的 SysFont / match_font，它们在部分 Windows 上
    枚举注册表字体时会报 TypeError（这是 pygame 2.6.1 自身的 bug）。
    这里直接按字体文件路径加载，稳定可靠。
    """
    if bold:
        # 优先用微软雅黑粗体，找不到就用普通字体再加粗
        path = (find_font_file("msyhbd.ttc", "msyhbd.ttf")   # 微软雅黑 Bold
                or find_font_file("msyh.ttc", "msyh.ttf")     # 微软雅黑
                or find_font_file("simhei.ttf")               # 黑体
                or find_font_file("simsun.ttc", "simsun.ttf"))  # 宋体
    else:
        path = (find_font_file("msyh.ttc", "msyh.ttf")       # 微软雅黑
                or find_font_file("simhei.ttf")               # 黑体
                or find_font_file("simsun.ttc", "simsun.ttf"))  # 宋体

    if path:
        font = pg.font.Font(path, size)
        if bold:
            font.set_bold(True)   # 找不到粗体文件时，用普通字体模拟加粗
        return font

    # 兜底：上面字体都没找到时用 pygame 默认字体（此时中文可能显示为方块）
    return pg.font.Font(None, size)


def cell_center(row, col):
    """返回 (row, col) 格子的中心坐标，用于画棋子、高亮连线。"""
    x = col * CELL + CELL // 2
    y = BOARD_TOP + row * CELL + CELL // 2
    return x, y


def draw_grid(screen):
    """画 3x3 的棋盘（先清空背景，再画 4 条线）。"""
    screen.fill(BG_COLOR)
    for i in range(1, 3):
        # 两条竖线
        pg.draw.line(screen, GRID_COLOR, (i * CELL, BOARD_TOP),
                     (i * CELL, BOARD_TOP + 3 * CELL), LINE_W)
        # 两条横线
        pg.draw.line(screen, GRID_COLOR, (0, BOARD_TOP + i * CELL),
                     (3 * CELL, BOARD_TOP + i * CELL), LINE_W)


def draw_mark(screen, row, col, player):
    """在某个格子里画出 X 或 O。"""
    cx, cy = cell_center(row, col)
    pad = 40  # 图形边缘到格子边缘的间距
    if player == X:
        # X 就是两条交叉的斜线
        pg.draw.line(screen, X_COLOR, (cx - pad, cy - pad), (cx + pad, cy + pad), MARK_W)
        pg.draw.line(screen, X_COLOR, (cx - pad, cy + pad), (cx + pad, cy - pad), MARK_W)
    elif player == O:
        # O 就是一个空心圆
        pg.draw.circle(screen, O_COLOR, (cx, cy), CELL // 2 - pad, MARK_W)


def get_winner(board):
    """检查是否有人获胜。

    返回 (胜者, 获胜的三个格子坐标列表)；没人获胜则返回 (None, [])。
    """
    lines = [  # 所有可能连成一线的情况：3 行 + 3 列 + 2 条对角线
        [(0, 0), (0, 1), (0, 2)],
        [(1, 0), (1, 1), (1, 2)],
        [(2, 0), (2, 1), (2, 2)],
        [(0, 0), (1, 0), (2, 0)],
        [(0, 1), (1, 1), (2, 1)],
        [(0, 2), (1, 2), (2, 2)],
        [(0, 0), (1, 1), (2, 2)],
        [(0, 2), (1, 1), (2, 0)],
    ]
    for line in lines:
        marks = {board[r][c] for r, c in line}
        if len(marks) == 1 and EMPTY not in marks:
            return next(iter(marks)), line
    return None, []


def is_draw(board):
    """所有格子都被占满、且没有人获胜，就是平局。"""
    return all(cell != EMPTY for row in board for cell in row)


def render_center(screen, text, font, color, y):
    """在窗口水平正中、纵坐标 y 的位置显示一行文字。"""
    img = font.render(text, True, color)
    screen.blit(img, (SCREEN_W // 2 - img.get_width() // 2, y))