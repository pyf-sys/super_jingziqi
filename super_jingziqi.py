# -*- coding: utf-8 -*-
"""超级井字棋主程序（入口文件）：负责游戏控制主循环。

运行方式：python super_jingziqi.py
规则：
1. 大棋盘 3x3，每个格子里又有一个 3x3 小棋盘，共 81 个落子点。
2. X 先手，第一步可任意落子。
3. 落子的位置决定对手下一步必须去哪个小棋盘（被“送”过去）。
4. 先在小棋盘里三连者赢下该小棋盘；小棋盘下满无人赢则算平局（都不算领地）。
5. 被送去的小棋盘已结束时，可任意选择未结束的小棋盘落子（自由落子）。
6. 谁先在大棋盘上连成三连谁获胜；全部结束仍无三连则平局。

操作：鼠标落子；R 重新开始；M 开关声音；ESC 退出。
绘制、规则、精灵与音效等功能都在 super_jingziqi_lib.py 里。
"""
import pygame as pg

from jingziqi_lib import (
    X, O, EMPTY, X_COLOR, O_COLOR, WIN_COLOR, TEXT_COLOR,
    BTN_COLOR, BTN_HOVER, make_font,
)
from super_jingziqi_lib import (
    WIDTH, HEIGHT, RESTART_RECT, PLAY_CENTER,
    render_center, cell_from_pos, is_board_open, make_move, mini_center,
    draw_playfield, draw_match_mark, draw_big_win_highlight,
    MarkSprite, burst_at, AudioPlayer,
)

TIP_COLOR = (200, 40, 40)    # 错误提示的红色
GOLD = (255, 200, 40)        # 获胜粒子金色
GREY = (190, 190, 190)       # 平局粒子灰色


def new_empty_boards():
    """新建 9 个空的小棋盘。boards[bi][r][c] 表示第 bi 个小棋盘第 r 行 c 列。"""
    return [[[EMPTY] * 3 for _ in range(3)] for _ in range(9)]


def main():
    # 音频初始化要在 pg.init() 之前用 pre_init 设置格式，能降低播放延迟
    pg.mixer.pre_init(22050, -16, 1, 512)
    pg.init()

    audio = AudioPlayer()
    audio.init()

    pg.display.set_caption("超级井字棋 Super Tic-Tac-Toe")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()

    status_font = make_font(46, bold=True)  # 顶部大字（轮到谁 / 谁赢了）
    sub_font = make_font(26)                # 顶部提示小字
    btn_font = make_font(28, bold=True)     # 按钮文字
    small_font = make_font(20)              # 底部小字（声音开关提示）
    draw_font = make_font(40, bold=True)    # 小棋盘里的“平”字

    # 精灵组：marks 放棋子，fx 放粒子特效
    marks = pg.sprite.Group()
    fx = pg.sprite.Group()

    # ---------- 游戏状态 ----------
    boards = new_empty_boards()   # 9 个小棋盘
    owners = [EMPTY] * 9          # 每个小棋盘归属：EMPTY / X / O / "draw"
    turn = X                      # 当前轮到谁
    forced = None                 # 必须去的小棋盘编号；None 表示自由落子
    winner = None                 # 整局胜者；"draw" 表示平局
    win_line = []                 # 获胜的三个小棋盘
    game_over = False
    tip = None                    # (提示文字, 过期毫秒时间戳)

    def reset():
        """开始新的一局。"""
        nonlocal boards, owners, turn, forced, winner, win_line, game_over, tip
        boards = new_empty_boards()
        owners = [EMPTY] * 9
        turn = X
        forced = None
        winner = None
        win_line = []
        game_over = False
        tip = None
        marks.empty()   # 清掉旧棋子精灵
        fx.empty()      # 清掉旧粒子

    def show_tip(msg):
        nonlocal tip
        tip = (msg, pg.time.get_ticks() + 1600)

    running = True
    while running:
        now = pg.time.get_ticks()

        # ---------- 1. 处理事件 ----------
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            elif ev.type == pg.KEYDOWN:
                if ev.key == pg.K_r:          # R：重新开始
                    reset()
                elif ev.key == pg.K_ESCAPE:   # ESC：退出
                    running = False
                elif ev.key == pg.K_m:        # M：开关声音
                    audio.toggle_mute()
            elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if RESTART_RECT.collidepoint(mx, my):
                    reset()
                elif not game_over:
                    cell = cell_from_pos((mx, my))
                    if cell is None:
                        show_tip("请点击小棋盘里的格子")
                        continue
                    bi, r, c = cell
                    if not is_board_open(bi, owners):
                        show_tip("这个小棋盘已经结束，不能再落子")
                    elif boards[bi][r][c] != EMPTY:
                        show_tip("这个格子已经有棋子了")
                    elif forced is not None and bi != forced:
                        show_tip("请先在被送到的小棋盘里落子")
                    else:
                        mover = turn   # 记下这一步是谁下的
                        # 落子并更新规则状态
                        bw, bline, closed_all, forced = make_move(
                            boards, owners, bi, r, c, turn)
                        tip = None
                        marks.add(MarkSprite(bi, r, c, mover))  # 新棋子精灵（带弹出动画）
                        audio.play_place()                      # 落子音效
                        if bw:
                            winner, win_line, game_over = bw, bline, True
                            # 获胜庆祝：在三个获胜小棋盘和大棋盘中心迸发金色粒子
                            for br, bc in win_line:
                                burst_at(fx, mini_center(br * 3 + bc), GOLD, 10)
                            burst_at(fx, PLAY_CENTER, GOLD, 16)
                            audio.play_win()
                        elif closed_all:
                            winner, game_over = "draw", True
                            burst_at(fx, PLAY_CENTER, GREY, 14)  # 平局也放一点灰粒子
                        else:
                            turn = O if turn == X else X

        # ---------- 2. 更新精灵 ----------
        marks.update(now)
        fx.update(now)

        # ---------- 3. 绘制画面 ----------
        draw_playfield(screen, owners, forced, draw_font, marks, game_over)

        # 整局有人获胜：盖大符号 + 金色框出获胜的三个小棋盘
        if game_over and winner != "draw":
            draw_match_mark(screen, winner)
            draw_big_win_highlight(screen, win_line)

        fx.draw(screen)   # 粒子特效画在最上层

        # 顶部状态文字
        if game_over:
            if winner == "draw":
                render_center(screen, "平局！", status_font, TEXT_COLOR, 18)
            else:
                render_center(screen, f"{winner} 获胜！", status_font, WIN_COLOR, 18)
            render_center(screen, "按 R 或点击下方按钮再来一局", sub_font, TEXT_COLOR, 78)
        else:
            color = X_COLOR if turn == X else O_COLOR
            render_center(screen, f"轮到 {turn} 落子", status_font, color, 18)
            if tip and now < tip[1]:
                render_center(screen, tip[0], sub_font, TIP_COLOR, 82)
            elif forced is not None:
                render_center(screen, "请在被送到的小棋盘内落子", sub_font, TEXT_COLOR, 82)
            else:
                render_center(screen, "自由落子：可点任意未结束的小棋盘", sub_font, TEXT_COLOR, 82)

        # 底部“再来一局”按钮
        mx, my = pg.mouse.get_pos()
        btn_color = BTN_HOVER if RESTART_RECT.collidepoint(mx, my) else BTN_COLOR
        pg.draw.rect(screen, btn_color, RESTART_RECT, border_radius=10)
        pg.draw.rect(screen, (70, 70, 70), RESTART_RECT, 2, border_radius=10)
        btn_img = btn_font.render("再来一局", True, TEXT_COLOR)
        screen.blit(btn_img, (RESTART_RECT.centerx - btn_img.get_width() // 2,
                              RESTART_RECT.centery - btn_img.get_height() // 2))

        # 左下角声音状态提示（没有音频设备时这一行不显示）
        if audio.enabled:
            text = "声音：关（按 M 开启）" if audio.muted else "声音：开（按 M 关闭）"
            img = small_font.render(text, True, (140, 140, 140))
            screen.blit(img, (14, HEIGHT - 32))

        pg.display.update()
        clock.tick(60)

    audio.stop()
    pg.quit()


if __name__ == "__main__":
    main()