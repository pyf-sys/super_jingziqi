# -*- coding: utf-8 -*-
"""超级井字棋共享功能：标记、颜色、字体与单盘胜负判断（不含主循环）。"""
import os
import pygame as pg

# ---------- 共享颜色（RGB） ----------
X_COLOR    = (220, 80, 80)     # X 的红色
O_COLOR    = (70, 130, 220)    # O 的蓝色
WIN_COLOR  = (255, 200, 40)    # 获胜高亮的金色
TEXT_COLOR = (40, 40, 40)      # 普通文字
BTN_COLOR  = (200, 200, 200)   # 按钮
BTN_HOVER  = (170, 170, 170)   # 鼠标悬停时的按钮

# ---------- 玩家标记 ----------
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
