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

扫雷与技能：
- 棋盘里藏有 9 个雷；每落一子，格子右下角会持续显示同棋盘周围 8 格的雷数。
- 踩雷后随机获得一种技能，并立即进入技能回合；可连续使用技能，点击“结束回合”后再交给对手。
- 调换两个小棋盘；调换两个棋子；指定对手下一步去哪个小棋盘。

操作：鼠标落子；右键或 ESC 取消技能选择；空格/回车结束技能回合；R 重新开始；M 开关声音。
"""
import pygame as pg

from jingziqi_lib import (
    X, O, EMPTY, X_COLOR, O_COLOR, WIN_COLOR, TEXT_COLOR,
    BTN_COLOR, BTN_HOVER, make_font,
)
from super_jingziqi_lib import (
    WIDTH, HEIGHT, RESTART_RECT, BUTTON_Y, PLAY_CENTER,
    render_center, cell_from_pos, cell_center, is_board_open, make_move, mini_center,
    make_mine_setup, random_skill, recompute_owners,
    swap_mini_boards, swap_pieces,
    draw_playfield, draw_match_mark, draw_big_win_highlight,
    MarkSprite, burst_at, AudioPlayer,
    SKILL_KEYS, SKILL_SWAP_BOARDS, SKILL_SWAP_PIECES, SKILL_FORCE_BOARD,
    SKILL_NAMES,
)

TIP_COLOR = (200, 40, 40)      # 错误提示的红色
GOLD = (255, 200, 40)          # 获胜粒子金色
GREY = (190, 190, 190)         # 平局粒子灰色
SKILL_COLOR = (35, 130, 75)    # 技能提示绿色
MINE_COLOR = (255, 145, 30)    # 踩雷特效橙色
SKILL_ACTIVE = (255, 225, 110)
SKILL_DISABLED = (205, 205, 205)

SKILL_BTN_W = 158
SKILL_BTN_Y = BUTTON_Y
SKILL_RECTS = {
    key: pg.Rect(12 + i * (SKILL_BTN_W + 8), SKILL_BTN_Y, SKILL_BTN_W, 42)
    for i, key in enumerate(SKILL_KEYS)
}
SKILL_BUTTON_LABELS = {
    SKILL_SWAP_BOARDS: "换棋盘",
    SKILL_SWAP_PIECES: "换棋子",
    SKILL_FORCE_BOARD: "指定落点",
}


def new_empty_boards():
    """新建 9 个空的小棋盘。boards[bi][r][c] 表示第 bi 个小棋盘第 r 行 c 列。"""
    return [[[EMPTY] * 3 for _ in range(3)] for _ in range(9)]


def main():
    # 音频初始化要在 pg.init() 之前用 pre_init 设置格式，能降低播放延迟
    pg.mixer.pre_init(22050, -16, 1, 512)
    pg.init()

    audio = AudioPlayer()
    audio.init()

    pg.display.set_caption("扫雷超级井字棋 Minesweeper Super Tic-Tac-Toe")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    clock = pg.time.Clock()

    status_font = make_font(46, bold=True)  # 顶部大字（轮到谁 / 谁赢了）
    sub_font = make_font(26)                # 顶部提示小字
    btn_font = make_font(24, bold=True)     # 按钮文字
    small_font = make_font(20)              # 底部小字
    draw_font = make_font(40, bold=True)    # 小棋盘里的“平”字
    count_font = make_font(16, bold=True)   # 棋子旁的雷数
    skill_font = make_font(17, bold=True)   # 技能按钮

    # 精灵组：marks 放棋子，fx 放粒子特效
    marks = pg.sprite.Group()
    fx = pg.sprite.Group()

    # ---------- 游戏状态 ----------
    boards = new_empty_boards()   # 9 个小棋盘
    owners = [EMPTY] * 9          # 每个小棋盘归属：EMPTY / X / O / "draw"
    mine_maps, mine_counts = make_mine_setup()
    skills = {player: {key: 0 for key in SKILL_KEYS} for player in (X, O)}
    turn = X                      # 当前轮到谁
    forced = None                 # 必须去的小棋盘编号；None 表示自由落子
    pending_force = None          # 技能：当前玩家落子后，对手必须去的棋盘
    post_mine_turn = False        # 踩雷后的立即技能阶段；结束后才换手
    winner = None                 # 整局胜者；"draw" 表示平局
    win_line = []                 # 获胜的三个小棋盘
    game_over = False
    skill_mode = None             # 正在选择目标的技能
    skill_targets = []            # 技能已选择的目标
    tip = None                    # (提示文字, 过期毫秒时间戳, 颜色)

    def rebuild_marks():
        """技能移动棋盘或棋子后，按 boards 重建所有棋子精灵。"""
        marks.empty()
        for bi in range(9):
            for r in range(3):
                for c in range(3):
                    if boards[bi][r][c] != EMPTY:
                        marks.add(MarkSprite(bi, r, c, boards[bi][r][c]))

    def apply_outcome(bw, bline, closed_all):
        """应用整局胜负结果；返回游戏是否已经结束。"""
        nonlocal winner, win_line, game_over, post_mine_turn
        if bw:
            winner, win_line, game_over = bw, bline, True
            for br, bc in win_line:
                burst_at(fx, mini_center(br * 3 + bc), GOLD, 10)
            burst_at(fx, PLAY_CENTER, GOLD, 16)
            post_mine_turn = False
            audio.play_win()
            return True
        if closed_all:
            winner, win_line, game_over = "draw", [], True
            post_mine_turn = False
            burst_at(fx, PLAY_CENTER, GREY, 14)
            return True
        winner, win_line, game_over = None, [], False
        return False

    def refresh_after_skill():
        """技能改变棋盘后，重算归属、胜负，并清理失效的目标。"""
        nonlocal forced, pending_force
        bw, bline, closed_all = recompute_owners(boards, owners)
        if forced is not None and not is_board_open(forced, owners):
            forced = None
        if pending_force is not None and not is_board_open(pending_force, owners):
            pending_force = None
        apply_outcome(bw, bline, closed_all)

    def reset():
        """开始新的一局。"""
        nonlocal boards, owners, mine_maps, mine_counts, skills
        nonlocal turn, forced, pending_force, post_mine_turn, winner, win_line, game_over
        nonlocal skill_mode, skill_targets, tip
        boards = new_empty_boards()
        owners = [EMPTY] * 9
        mine_maps, mine_counts = make_mine_setup()
        skills = {player: {key: 0 for key in SKILL_KEYS} for player in (X, O)}
        turn = X
        forced = None
        pending_force = None
        post_mine_turn = False
        winner = None
        win_line = []
        game_over = False
        skill_mode = None
        skill_targets = []
        tip = None
        marks.empty()
        fx.empty()

    def show_tip(msg, color=TIP_COLOR):
        nonlocal tip
        tip = (msg, pg.time.get_ticks() + 2200, color)

    def end_post_mine_turn():
        """结束踩雷后的技能阶段，把落子权交给对手。"""
        nonlocal turn, post_mine_turn, skill_mode, skill_targets, tip
        post_mine_turn = False
        turn = O if turn == X else X
        skill_mode = None
        skill_targets = []
        tip = None

    def choose_skill(skill):
        """点击技能按钮，进入目标选择状态。"""
        nonlocal skill_mode, skill_targets, tip
        if skill_mode == skill:
            skill_mode = None
            skill_targets = []
            tip = None
            return
        if skills[turn][skill] <= 0:
            show_tip(f"当前没有可用的“{SKILL_NAMES[skill]}”")
            return
        if skill == SKILL_FORCE_BOARD and pending_force is not None:
            show_tip("本回合已经指定过对手的下一步棋盘")
            return
        skill_mode = skill
        skill_targets = []
        if skill == SKILL_SWAP_BOARDS:
            show_tip("请选择要调换的第 1 个小棋盘", SKILL_COLOR)
        elif skill == SKILL_SWAP_PIECES:
            show_tip("请选择要调换的第 1 个棋子", SKILL_COLOR)
        else:
            show_tip("请选择对手下一步必须去的小棋盘", SKILL_COLOR)

    def handle_skill_click(cell):
        """处理技能目标点击。cell 为 (小棋盘, 行, 列) 或 None。"""
        nonlocal skill_mode, skill_targets, pending_force, forced
        if cell is None:
            show_tip("请点击棋盘区域来选择技能目标")
            return
        bi, r, c = cell

        if skill_mode == SKILL_SWAP_BOARDS:
            if not skill_targets:
                skill_targets.append(bi)
                show_tip(f"已选择小棋盘 {bi + 1}，请选择第 2 个", SKILL_COLOR)
                return
            first = skill_targets[0]
            if first == bi:
                show_tip("两个小棋盘不能相同")
                return
            skills[turn][SKILL_SWAP_BOARDS] -= 1
            swap_mini_boards(boards, mine_maps, mine_counts, owners, first, bi)
            skill_mode = None
            skill_targets = []
            rebuild_marks()
            refresh_after_skill()
            show_tip(f"已调换小棋盘 {first + 1} 与 {bi + 1}", SKILL_COLOR)
            return

        if skill_mode == SKILL_SWAP_PIECES:
            if boards[bi][r][c] == EMPTY:
                show_tip("这里没有棋子，请选择已有棋子的格子")
                return
            target = (bi, r, c)
            if not skill_targets:
                skill_targets.append(target)
                show_tip("已选择第 1 个棋子，请选择第 2 个", SKILL_COLOR)
                return
            first = skill_targets[0]
            if first == target:
                show_tip("两个棋子的位置不能相同")
                return
            skills[turn][SKILL_SWAP_PIECES] -= 1
            swap_pieces(boards, owners, first, target)
            skill_mode = None
            skill_targets = []
            rebuild_marks()
            refresh_after_skill()
            show_tip("两个棋子已经调换位置", SKILL_COLOR)
            return

        if skill_mode == SKILL_FORCE_BOARD:
            if not is_board_open(bi, owners):
                show_tip("这个小棋盘已经结束，不能指定")
                return
            skills[turn][SKILL_FORCE_BOARD] -= 1
            if post_mine_turn:
                forced = bi
            else:
                pending_force = bi
            skill_mode = None
            skill_targets = []
            show_tip(f"已指定对手下一步去小棋盘 {bi + 1}", SKILL_COLOR)

    def draw_skill_button(rect, label, enabled, active, mouse_pos):
        if active:
            color = SKILL_ACTIVE
        elif not enabled:
            color = SKILL_DISABLED
        elif rect.collidepoint(mouse_pos):
            color = BTN_HOVER
        else:
            color = BTN_COLOR
        border = SKILL_COLOR if active else (70, 70, 70)
        pg.draw.rect(screen, color, rect, border_radius=8)
        pg.draw.rect(screen, border, rect, 2, border_radius=8)
        text_color = TEXT_COLOR if enabled or active else (130, 130, 130)
        img = skill_font.render(label, True, text_color)
        screen.blit(img, (rect.centerx - img.get_width() // 2,
                          rect.centery - img.get_height() // 2))

    running = True
    while running:
        now = pg.time.get_ticks()

        # ---------- 1. 处理事件 ----------
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            elif ev.type == pg.KEYDOWN:
                if ev.key == pg.K_r:
                    reset()
                elif ev.key == pg.K_ESCAPE:
                    if skill_mode is not None:
                        skill_mode = None
                        skill_targets = []
                        tip = None
                    else:
                        running = False
                elif ev.key == pg.K_m:
                    audio.toggle_mute()
                elif ev.key in (pg.K_RETURN, pg.K_SPACE) and post_mine_turn:
                    end_post_mine_turn()
            elif ev.type == pg.MOUSEBUTTONDOWN:
                if ev.button == 3:
                    if skill_mode is not None:
                        skill_mode = None
                        skill_targets = []
                        tip = None
                    continue
                if ev.button != 1:
                    continue

                mx, my = ev.pos
                if RESTART_RECT.collidepoint(mx, my):
                    if post_mine_turn:
                        end_post_mine_turn()
                    else:
                        reset()
                    continue
                if game_over:
                    continue

                clicked_skill = None
                for skill, rect in SKILL_RECTS.items():
                    if rect.collidepoint(mx, my):
                        clicked_skill = skill
                        break
                if clicked_skill is not None:
                    choose_skill(clicked_skill)
                    continue

                cell = cell_from_pos((mx, my))
                if skill_mode is not None:
                    handle_skill_click(cell)
                    continue
                if post_mine_turn:
                    show_tip("请先使用技能，或点击“结束回合”")
                    continue

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
                    mover = turn
                    bw, bline, closed_all, normal_forced = make_move(
                        boards, owners, bi, r, c, turn)
                    forced = normal_forced
                    if pending_force is not None:
                        if is_board_open(pending_force, owners):
                            forced = pending_force
                        pending_force = None

                    tip = None
                    marks.add(MarkSprite(bi, r, c, mover))
                    audio.play_place()

                    gained_skill = None
                    if mine_maps[bi][r][c]:
                        gained_skill = random_skill()
                        skills[mover][gained_skill] += 1
                        burst_at(fx, cell_center(bi, r, c), MINE_COLOR, 12)

                    if not apply_outcome(bw, bline, closed_all):
                        if gained_skill is not None:
                            post_mine_turn = True
                            show_tip(
                                f"{mover} 踩到雷！获得技能：{SKILL_NAMES[gained_skill]}，可立即使用",
                                SKILL_COLOR,
                            )
                        else:
                            turn = O if turn == X else X

        # ---------- 2. 更新精灵 ----------
        marks.update(now)
        fx.update(now)

        # ---------- 3. 绘制画面 ----------
        draw_playfield(
            screen, owners, forced, draw_font, marks, game_over,
            boards=boards, mine_counts=mine_counts, count_font=count_font,
        )

        if game_over and winner != "draw":
            draw_match_mark(screen, winner)
            draw_big_win_highlight(screen, win_line)

        fx.draw(screen)

        # 顶部状态文字
        if game_over:
            if winner == "draw":
                render_center(screen, "平局！", status_font, TEXT_COLOR, 18)
            else:
                render_center(screen, f"{winner} 获胜！", status_font, WIN_COLOR, 18)
            render_center(screen, "按 R 或点击右下角按钮再来一局", sub_font, TEXT_COLOR, 78)
        else:
            color = X_COLOR if turn == X else O_COLOR
            if post_mine_turn:
                render_center(screen, f"{turn} 技能回合", status_font, SKILL_COLOR, 18)
            else:
                render_center(screen, f"轮到 {turn} 落子", status_font, color, 18)
            if tip and now < tip[1]:
                render_center(screen, tip[0], sub_font, tip[2], 82)
            elif skill_mode == SKILL_SWAP_BOARDS:
                if skill_targets:
                    msg = f"换棋盘：已选 {skill_targets[0] + 1}，请选第 2 个小棋盘"
                else:
                    msg = "换棋盘：请选择第 1 个小棋盘"
                render_center(screen, msg, sub_font, SKILL_COLOR, 82)
            elif skill_mode == SKILL_SWAP_PIECES:
                if skill_targets:
                    bi, r, c = skill_targets[0]
                    msg = f"换棋子：已选 {bi + 1}-{r + 1}-{c + 1}，请选第 2 个棋子"
                else:
                    msg = "换棋子：请选择第 1 个棋子"
                render_center(screen, msg, sub_font, SKILL_COLOR, 82)
            elif skill_mode == SKILL_FORCE_BOARD:
                render_center(screen, "指定落点：请选择对手下一步的小棋盘",
                              sub_font, SKILL_COLOR, 82)
            elif post_mine_turn:
                if forced is not None:
                    msg = f"可使用其他技能；结束后，对手将去小棋盘 {forced + 1}"
                else:
                    msg = "可立即使用技能；完成后点击右下角“结束回合”"
                render_center(screen, msg, sub_font, SKILL_COLOR, 82)
            elif pending_force is not None:
                render_center(screen, f"当前落子后，对手将被送到小棋盘 {pending_force + 1}",
                              sub_font, SKILL_COLOR, 82)
            elif forced is not None:
                render_center(screen, "请在被送到的小棋盘内落子", sub_font, TEXT_COLOR, 82)
            else:
                render_center(screen, "自由落子：可点任意未结束的小棋盘",
                              sub_font, TEXT_COLOR, 82)

        # 底部技能栏：显示当前玩家的剩余次数
        mouse_pos = pg.mouse.get_pos()
        for skill, rect in SKILL_RECTS.items():
            count = skills[turn][skill]
            enabled = (not game_over and count > 0 and
                       not (skill == SKILL_FORCE_BOARD and pending_force is not None))
            label = f"{SKILL_BUTTON_LABELS[skill]} ×{count}"
            draw_skill_button(rect, label, enabled, skill_mode == skill, mouse_pos)

        # 右下角按钮：踩雷技能阶段显示“结束回合”，其余时候显示“再来一局”
        hovering = RESTART_RECT.collidepoint(mouse_pos)
        if post_mine_turn:
            btn_color = SKILL_ACTIVE if hovering else (255, 242, 180)
            btn_text = "结束回合"
        else:
            btn_color = BTN_HOVER if hovering else BTN_COLOR
            btn_text = "再来一局"
        pg.draw.rect(screen, btn_color, RESTART_RECT, border_radius=10)
        pg.draw.rect(screen, (70, 70, 70), RESTART_RECT, 2, border_radius=10)
        btn_img = btn_font.render(btn_text, True, TEXT_COLOR)
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
