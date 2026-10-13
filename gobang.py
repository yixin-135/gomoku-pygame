"""
五子棋（Gomoku）— 基于 Pygame
优雅五子棋 · Elegant Gomoku
布局：左侧棋盘 + 右侧控制面板
"""

import sys
import math
import random
import pygame

# ============================================================
# 常量定义
# ============================================================

BOARD_SIZE = 15                 # 棋盘行列数：15 x 15
CELL_SIZE = 34                  # 每格像素大小

# AI 难度等级
AI_EASY   = 0
AI_MEDIUM = 1
AI_HARD   = 2
AI_DIFF_NAMES = {AI_EASY: "简单", AI_MEDIUM: "中等", AI_HARD: "困难"}

# 棋盘网格区域像素
BOARD_GRID_PX = (BOARD_SIZE - 1) * CELL_SIZE  # 14 x 34 = 476

# 棋盘区域左上角偏移
BOARD_OFFSET_X = 46
BOARD_OFFSET_Y = 58

# 木质边框厚度
FRAME_THICKNESS = 28

# 棋盘区域（含木质边框）的尺寸
BOARD_AREA_W = BOARD_GRID_PX + FRAME_THICKNESS * 2
BOARD_AREA_H = BOARD_GRID_PX + FRAME_THICKNESS * 2

# 右侧控制面板
PANEL_X = BOARD_OFFSET_X + BOARD_AREA_W + 24
PANEL_WIDTH = 240

# 窗口尺寸
WIN_WIDTH = PANEL_X + PANEL_WIDTH + 20
WIN_HEIGHT = BOARD_OFFSET_Y + BOARD_AREA_H + 40 + 20

# ============================================================
# 颜色定义 — 柔和木质调色板
# ============================================================

# 全局背景（深色胡桃木底）
COLOR_BG               = (58, 45, 35)

# 棋盘面（温润象牙米色）
COLOR_BOARD_FILL       = (238, 218, 176)

# 木质边框（金黄胡桃木）
COLOR_BOARD_FRAME      = (130, 85, 45)
COLOR_BOARD_FRAME_TOP  = (170, 120, 65)    # 顶部高光
COLOR_BOARD_FRAME_BOT  = (80, 48, 22)      # 底部阴影

# 网格线（温润棕灰色）
COLOR_LINE             = (108, 92, 72)
COLOR_STAR             = (88, 72, 55)       # 星位点

# 棋子颜色
PC_BLACK_OUTER   = (18, 18, 18)            # 黑子外圈
PC_BLACK_MID     = (32, 32, 32)            # 黑子中部
PC_BLACK_INNER   = (48, 48, 48)            # 黑子内圈
PC_BLACK_HL      = (72, 72, 72)            # 黑子高光

PC_WHITE_OUTLINE = (148, 142, 135)         # 白子外描边
PC_WHITE_SHADOW  = (118, 112, 105)         # 白子阴影
PC_WHITE_OUTER   = (228, 224, 216)         # 白子外圈
PC_WHITE_MID     = (240, 237, 230)         # 白子中部
PC_WHITE_INNER   = (250, 248, 244)         # 白子内圈
PC_WHITE_HL      = (255, 255, 254)         # 白子高光

# 面板
COLOR_PANEL_BG     = (250, 243, 230)       # 面板背景
COLOR_PANEL_BORDER = (160, 130, 90)        # 面板边框
COLOR_PANEL_ACCENT = (225, 208, 178)       # 面板装饰条

# 坐标标签
COLOR_LABEL = (125, 100, 70)

# ============================================================
# 字体（延迟初始化）
# ============================================================

FONT_LABEL        = None
FONT_PANEL_TITLE  = None
FONT_PANEL_TEXT   = None
FONT_TURN_LARGE   = None
FONT_BTN          = None
FONT_TOAST        = None
FONT_WINNER       = None
FONT_WINNER_HINT  = None
FONT_STAT_NUM     = None

# ============================================================
# 工具函数
# ============================================================

def board_to_screen(row, col):
    """将棋盘坐标转换为窗口像素坐标"""
    x = BOARD_OFFSET_X + FRAME_THICKNESS + col * CELL_SIZE
    y = BOARD_OFFSET_Y + FRAME_THICKNESS + row * CELL_SIZE
    return x, y


def screen_to_board(mx, my):
    """将窗口像素坐标转换为最近的棋盘坐标"""
    grid_left   = BOARD_OFFSET_X + FRAME_THICKNESS
    grid_top    = BOARD_OFFSET_Y + FRAME_THICKNESS
    grid_right  = grid_left + BOARD_GRID_PX
    grid_bottom = grid_top + BOARD_GRID_PX

    if mx < grid_left - CELL_SIZE // 2 or mx > grid_right + CELL_SIZE // 2:
        return None
    if my < grid_top - CELL_SIZE // 2 or my > grid_bottom + CELL_SIZE // 2:
        return None

    col = round((mx - grid_left) / CELL_SIZE)
    row = round((my - grid_top) / CELL_SIZE)

    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
        cx, cy = board_to_screen(row, col)
        if abs(mx - cx) <= CELL_SIZE // 2 and abs(my - cy) <= CELL_SIZE // 2:
            return row, col
    return None


# ============================================================
# 游戏核心类
# ============================================================

class GomokuGame:
    """五子棋游戏主类，管理游戏状态与绘制"""

    def __init__(self):
        self.board          = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current_player = 1
        self.game_over      = False
        self.winner         = 0
        self.is_draw        = False
        self.win_line       = []    # 获胜五连棋子坐标列表
        self.move_history   = []
        self.last_move      = None
        self.panel_buttons  = []
        self.toast_message  = ""
        self.toast_timer    = 0
        self.ai_mode        = False
        self.ai_difficulty  = AI_MEDIUM  # 默认中等难度
        self.ai_thinking    = False
        self.ai_move_timer  = 0
        self.victory_frame  = 0          # 胜利动画帧计数
        self._victory_sparks = []        # 胜利粒子预计算
        self.selecting_color = True      # 是否正在选择先后手
        self.player_color    = 1         # 玩家执子颜色（1=黑, 2=白）
        self._selection_buttons = []     # 选择界面按钮区域

    # ---- 游戏逻辑 ----

    def reset(self):
        """重置游戏到初始状态"""
        self.board          = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current_player = 1
        self.game_over      = False
        self.winner         = 0
        self.is_draw        = False
        self.win_line.clear()
        self.move_history.clear()
        self.last_move      = None
        self.toast_message  = ""
        self.toast_timer    = 0
        self.ai_thinking    = False
        self.ai_move_timer  = 0
        self.victory_frame  = 0
        self._victory_sparks.clear()
        self.selecting_color = True     # 新开局回到先后手选择

    def undo(self):
        """
        悔棋：
        - 双人对战：撤销上一步棋子，恢复为上一玩家的回合
        - 人机对战：同时撤销 AI 上一步 + 玩家上一步（共 2 手），
          恢复到玩家落子前的状态
        - 无棋子可悔时给出提示
        """
        # ---- 无棋子可悔 ----
        if not self.move_history:
            self.toast_message = "没有棋子可以悔棋"
            self.toast_timer   = 90
            return False

        # ---- 取消 AI 思考状态 ----
        self.ai_thinking   = False
        self.ai_move_timer = 0

        # ---- 游戏结束状态必须清除 ----
        was_game_over = self.game_over
        if self.game_over:
            self.game_over    = False
            self.winner       = 0
            self.is_draw      = False
            self.win_line.clear()
            self.victory_frame = 0
            self._victory_sparks.clear()

        undo_count = 0

        if self.ai_mode:
            # ================================================
            #  人机对战模式：需要同时撤销玩家的落子
            #  move_history 结构：[玩家, AI, 玩家, AI, ...]
            #  若末尾是 AI 的棋 → 连撤 2 手（AI + 玩家）
            #  若末尾是玩家的棋 → 只撤 1 手（玩家还未轮到 AI）
            # ================================================

            # 撤销末尾一手
            row, col, player = self.move_history.pop()
            self.board[row][col] = 0
            undo_count += 1

            # 如果撤销的是 AI 的棋，则继续撤销上一手（玩家）
            if player == self.ai_color and self.move_history:
                r2, c2, _ = self.move_history.pop()
                self.board[r2][c2] = 0
                undo_count += 1

            # 人机模式下悔棋后，始终恢复到玩家回合
            self.current_player = self.player_color

            # 更新 last_move
            if self.move_history:
                self.last_move = (self.move_history[-1][0],
                                  self.move_history[-1][1])
            else:
                self.last_move = None

            # 提示信息
            if was_game_over:
                self.toast_message = f"已撤销 {undo_count} 手，请重新落子"
            elif undo_count >= 2:
                self.toast_message = "已撤回你与AI的棋子，请重新落子"
            else:
                self.toast_message = "已撤回棋子，请重新落子"
        else:
            # ================================================
            #  双人对战模式：只撤销上一步
            # ================================================
            row, col, player = self.move_history.pop()
            self.board[row][col] = 0
            self.current_player  = player
            undo_count = 1

            if self.move_history:
                self.last_move = (self.move_history[-1][0],
                                  self.move_history[-1][1])
            else:
                self.last_move = None

            piece_name = "黑棋" if player == 1 else "白棋"
            if was_game_over:
                self.toast_message = f"已撤销 {piece_name} 的致胜一子"
            else:
                self.toast_message = f"已悔棋，轮到 {piece_name} 重新落子"

        self.toast_timer = 90
        return True

    def place_piece(self, row, col):
        """在 (row, col) 处落子"""
        if self.game_over:
            return False
        if self.board[row][col] != 0:
            return False

        self.board[row][col] = self.current_player
        self.move_history.append((row, col, self.current_player))
        self.last_move = (row, col)

        if self._check_win(row, col):
            self.game_over = True
            self.winner    = self.current_player
            self.victory_frame = 0
            self._init_victory_sparks()
        elif len(self.move_history) >= BOARD_SIZE * BOARD_SIZE:
            self.game_over = True
            self.is_draw   = True
            self.victory_frame = 0
            self._init_draw_sparks()
        else:
            self.current_player = 3 - self.current_player

        return True

    def _check_win(self, row, col):
        """检查最后落子处是否形成五连，同时记录获胜连线坐标"""
        player = self.board[row][col]
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for dr, dc in directions:
            line = [(row, col)]
            r, c = row + dr, col + dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
                  self.board[r][c] == player:
                line.append((r, c)); r += dr; c += dc
            r, c = row - dr, col - dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
                  self.board[r][c] == player:
                line.append((r, c)); r -= dr; c -= dc
            if len(line) >= 5:
                self.win_line = line
                return True
        self.win_line = []
        return False

    @property
    def ai_color(self):
        """AI 执子颜色（玩家颜色的对立面）"""
        return 3 - self.player_color

    def toggle_mode(self):
        """切换对战模式"""
        self.reset()
        self.ai_mode = not self.ai_mode
        mode_name = "人机对战" if self.ai_mode else "双人对战"
        self.toast_message = f"已切换为「{mode_name}」模式"
        self.toast_timer = 90

    # ---- 胜利粒子 ----

    def _init_victory_sparks(self):
        """初始化胜利粒子"""
        self._victory_sparks = []
        cx, cy = WIN_WIDTH // 2, WIN_HEIGHT // 2 - 20
        for _ in range(40):
            angle     = random.uniform(0, 2 * math.pi)
            speed     = random.uniform(1.5, 5.0)
            distance  = 0
            max_dist  = random.uniform(60, 220)
            life      = random.randint(25, 70)
            size      = random.randint(2, 5)
            hue       = random.choice([
                (255, 215, 0),   # 金色
                (255, 180, 40),  # 橙金
                (255, 240, 150), # 浅金
                (255, 160, 60),  # 暖橙
                (255, 255, 200), # 米白
            ])
            self._victory_sparks.append({
                'angle': angle, 'speed': speed, 'distance': distance,
                'max_dist': max_dist, 'life': life, 'max_life': life,
                'size': size, 'hue': hue, 'cx': cx, 'cy': cy,
            })

    def _init_draw_sparks(self):
        """初始化平局粒子（银蓝柔和色调）"""
        self._victory_sparks = []
        cx, cy = WIN_WIDTH // 2, WIN_HEIGHT // 2 - 20
        for _ in range(35):
            angle     = random.uniform(0, 2 * math.pi)
            speed     = random.uniform(1.0, 3.5)
            distance  = 0
            max_dist  = random.uniform(50, 180)
            life      = random.randint(20, 55)
            size      = random.randint(2, 4)
            hue       = random.choice([
                (160, 180, 200),  # 银蓝
                (140, 155, 175),  # 灰蓝
                (180, 190, 210),  # 浅蓝灰
                (200, 200, 210),  # 银白
                (150, 140, 160),  # 淡紫灰
            ])
            self._victory_sparks.append({
                'angle': angle, 'speed': speed, 'distance': distance,
                'max_dist': max_dist, 'life': life, 'max_life': life,
                'size': size, 'hue': hue, 'cx': cx, 'cy': cy,
            })

    # ---- AI 算法 ---- 核心—候选集与模式评估 ----

    def _get_candidates(self):
        """收集所有候选落子点（现有棋子周围2格内的空位）"""
        candidates = set()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != 0:
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r + dr, c + dc
                            if (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
                                    and self.board[nr][nc] == 0):
                                candidates.add((nr, nc))
        return candidates

    def _count_in_direction(self, row, col, dr, dc, player):
        """从 (row,col) 沿 (dr,dc) 方向连续数同色棋子数"""
        count = 0
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
              self.board[r][c] == player:
            count += 1; r += dr; c += dc
        return count

    def _evaluate_line(self, row, col, player, dr, dc):
        """评估一条方向线的连子数与开放端数"""
        count = 1
        open_ends = 0

        # 正方向
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
              self.board[r][c] == player:
            count += 1; r += dr; c += dc
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
           self.board[r][c] == 0:
            open_ends += 1

        # 反方向
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
              self.board[r][c] == player:
            count += 1; r -= dr; c -= dc
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and \
           self.board[r][c] == 0:
            open_ends += 1

        return count, open_ends

    @staticmethod
    def _pattern_score(count, open_ends):
        """根据连子数与开放端数计算威胁分"""
        if count >= 5:
            return 100000                    # 必胜
        if count == 4:
            if open_ends == 2: return 50000   # 活四
            elif open_ends == 1: return 8000   # 冲四
            return 0                          # 死四
        if count == 3:
            if open_ends == 2: return 3000    # 活三
            elif open_ends == 1: return 500    # 眠三
            return 0
        if count == 2:
            if open_ends == 2: return 200     # 活二
            elif open_ends == 1: return 40     # 眠二
            return 0
        if count == 1:
            return 5 if open_ends == 2 else 1
        return 0

    def _score_cell_full(self, row, col, player):
        """全面评估在 (row,col) 落子对 'player' 的价值"""
        if self.board[row][col] != 0:
            return -1
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        total = 0
        for dr, dc in directions:
            cnt, ends = self._evaluate_line(row, col, player, dr, dc)
            total += self._pattern_score(cnt, ends)
        return total

    def _find_winning_move(self, player):
        """检查是否有一步必胜的落子，有则返回坐标，否则返回 None"""
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] == 0:
                    self.board[r][c] = player
                    is_win = self._check_win(r, c)
                    self.board[r][c] = 0
                    if is_win:
                        return (r, c)
        return None

    # ---- AI 策略 ---- 简单 ----

    def _get_ai_move_easy(self):
        """简单级 AI：从候选点中随机选择，偶尔偏中心"""
        candidates = self._get_candidates()
        center = BOARD_SIZE // 2
        if not candidates:
            return (center, center)
        # 30% 概率倾向靠近中心的位置
        if random.random() < 0.3:
            best = None
            best_dist = float('inf')
            for r, c in candidates:
                d = (r - center) ** 2 + (c - center) ** 2
                if d < best_dist:
                    best_dist = d
                    best = (r, c)
            if best:
                return best
        return random.choice(list(candidates))

    # ---- AI 策略 ---- 中等 ----

    def _get_ai_move_medium(self):
        """中等级 AI：防守优先——主要拦截玩家，兼顾补全自己的连线"""
        candidates = self._get_candidates()
        center = BOARD_SIZE // 2
        if not candidates:
            return (center, center)

        # 1) AI 能立即赢 → 直接落子
        win_move = self._find_winning_move(self.ai_color)
        if win_move:
            return win_move

        # 2) 玩家即将赢 → 必须堵
        block_move = self._find_winning_move(self.player_color)
        if block_move:
            return block_move

        # 3) 防守为主，兼顾进攻 — 对每个候选点评估防御价值和进攻价值
        best_score = -1
        best_move = (center, center)
        for r, c in candidates:
            def_score = self._score_cell_full(r, c, self.player_color)   # 玩家在此点的威胁
            off_score = self._score_cell_full(r, c, self.ai_color)   # AI 在此点的收益
            # 防守权重远高于进攻
            score = def_score * 3 + off_score
            if score > best_score:
                best_score = score
                best_move = (r, c)
        return best_move

    # ---- AI 策略 ---- 困难 ----

    def _get_ai_move_hard(self):
        """困难级 AI：兼顾攻防，进攻与防守并重，抢占关键点位"""
        candidates = self._get_candidates()
        center = BOARD_SIZE // 2
        if not candidates:
            return (center, center)

        # 1) AI 能立即赢 → 直接落子
        win_move = self._find_winning_move(self.ai_color)
        if win_move:
            return win_move

        # 2) 玩家即将赢 → 必须堵
        block_move = self._find_winning_move(self.player_color)
        if block_move:
            return block_move

        # 3) 多条件综合评分
        best_score = -1
        best_move = (center, center)
        for r, c in candidates:
            off_score = self._score_cell_full(r, c, self.ai_color)   # 进攻价值
            def_score = self._score_cell_full(r, c, self.player_color)   # 防守价值

            # 中心位置加成（靠近天元/星位有额外分）
            center_bonus = 0
            d = abs(r - center) + abs(c - center)
            if d <= 2:
                center_bonus = 30 - d * 10  # 越靠近中心分越高

            # 双重威胁加分：同一个点同时有好进攻和好防守
            dual_bonus = 0
            if off_score >= 200 and def_score >= 200:
                dual_bonus = min(off_score, def_score) // 2

            # 综合：进攻与防守均衡，略微偏防守
            score = off_score + int(def_score * 1.3) + center_bonus + dual_bonus

            if score > best_score:
                best_score = score
                best_move = (r, c)

        return best_move

    # ---- AI 决策分发 ----

    def _get_ai_move(self):
        """AI 入口：根据难度等级分发到对应策略"""
        if self.ai_difficulty == AI_EASY:
            return self._get_ai_move_easy()
        elif self.ai_difficulty == AI_MEDIUM:
            return self._get_ai_move_medium()
        else:  # AI_HARD
            return self._get_ai_move_hard()

    # ============================================================
    #  绘制 — 主入口
    # ============================================================

    def update(self):
        """更新游戏状态（倒计时、AI决策等，与渲染分离）"""
        if self.toast_timer > 0:
            self.toast_timer -= 1

        # 胜利动画帧递增
        if self.game_over:
            self.victory_frame += 1

        # AI 思考延迟
        if self.ai_thinking and not self.game_over and self.current_player == self.ai_color:
            self.ai_move_timer -= 1
            if self.ai_move_timer <= 0:
                move = self._get_ai_move()
                if move is not None:
                    self.place_piece(*move)
                self.ai_thinking = False

    def draw(self, screen):
        """绘制整个游戏画面"""
        mx, my = pygame.mouse.get_pos()

        self._draw_background(screen)
        self._draw_grid(screen)
        self._draw_star_points(screen)
        self._draw_coordinate_labels(screen)
        self._draw_pieces(screen)
        self._draw_panel(screen, mx, my)
        self._draw_toast(screen)
        if self.game_over:
            self._draw_result_overlay(screen)
            self._draw_win_highlight(screen)  # 高亮绘制在遮罩之上

        if self.selecting_color:
            self._draw_color_selection(screen, mx, my)

    # ============================================================
    #  绘制 — 背景与棋盘
    # ============================================================

    def _draw_background(self, screen):
        """填充全局背景"""
        screen.fill(COLOR_BG)

    def _draw_grid(self, screen):
        """绘制棋盘木质底板 + 网格线"""
        # ---- 阴影底板（软阴影） ----
        shadow_rect = pygame.Rect(
            BOARD_OFFSET_X + 2, BOARD_OFFSET_Y + 3,
            BOARD_AREA_W, BOARD_AREA_H
        )
        pygame.draw.rect(screen, (30, 22, 15), shadow_rect, border_radius=8)

        # ---- 底板外缘 ----
        board_outer = pygame.Rect(
            BOARD_OFFSET_X - 1, BOARD_OFFSET_Y - 1,
            BOARD_AREA_W + 2, BOARD_AREA_H + 2
        )
        pygame.draw.rect(screen, COLOR_BOARD_FRAME_BOT, board_outer,
                         border_radius=7)

        # ---- 底板主体 ----
        board_inner = pygame.Rect(
            BOARD_OFFSET_X, BOARD_OFFSET_Y,
            BOARD_AREA_W, BOARD_AREA_H
        )
        pygame.draw.rect(screen, COLOR_BOARD_FILL, board_inner,
                         border_radius=6)

        # ---- 棋盘面微纹理（棋盘面内部略深的四角） ----
        # 四个角做微妙的渐变（可选省略）

        # ---- 木质边框立体感 ----
        # 外边框
        frame_outer = pygame.Rect(
            BOARD_OFFSET_X, BOARD_OFFSET_Y,
            BOARD_AREA_W, BOARD_AREA_H
        )
        pygame.draw.rect(screen, COLOR_BOARD_FRAME, frame_outer,
                         width=2, border_radius=6)

        # 内边框顶部高光线
        for i in range(2):
            fi_rect = pygame.Rect(
                BOARD_OFFSET_X + FRAME_THICKNESS - 5 + i,
                BOARD_OFFSET_Y + FRAME_THICKNESS - 5 + i,
                BOARD_GRID_PX + 10 - 2 * i,
                BOARD_GRID_PX + 10 - 2 * i
            )
            color = COLOR_BOARD_FRAME_TOP if i == 0 else \
                    (160, 115, 65)
            pygame.draw.rect(screen, color, fi_rect, width=1)

        # ---- 网格线 ----
        grid_left = BOARD_OFFSET_X + FRAME_THICKNESS
        grid_top  = BOARD_OFFSET_Y + FRAME_THICKNESS

        for i in range(BOARD_SIZE):
            line_pos = i * CELL_SIZE
            # 横线
            pygame.draw.line(
                screen, COLOR_LINE,
                (grid_left, grid_top + line_pos),
                (grid_left + BOARD_GRID_PX, grid_top + line_pos),
                1
            )
            # 竖线
            pygame.draw.line(
                screen, COLOR_LINE,
                (grid_left + line_pos, grid_top),
                (grid_left + line_pos, grid_top + BOARD_GRID_PX),
                1
            )

    def _draw_star_points(self, screen):
        """绘制星位标记点"""
        star_positions = [
            (3, 3), (3, 7), (3, 11),
            (7, 3), (7, 7), (7, 11),
            (11, 3), (11, 7), (11, 11)
        ]
        for row, col in star_positions:
            cx, cy = board_to_screen(row, col)
            # 外层小圆
            pygame.draw.circle(screen, COLOR_STAR, (cx, cy), 5)
            # 内层填充
            pygame.draw.circle(screen, (78, 62, 45), (cx, cy), 3)

    def _draw_coordinate_labels(self, screen):
        """绘制棋盘坐标标签"""
        global FONT_LABEL
        grid_left = BOARD_OFFSET_X + FRAME_THICKNESS
        grid_top  = BOARD_OFFSET_Y + FRAME_THICKNESS

        for i in range(BOARD_SIZE):
            letter = chr(ord('A') + i)
            label  = FONT_LABEL.render(letter, True, COLOR_LABEL)
            lx = grid_left + i * CELL_SIZE - label.get_width() // 2
            ly = BOARD_OFFSET_Y + 5
            screen.blit(label, (lx, ly))

            number = str(i + 1)
            label  = FONT_LABEL.render(number, True, COLOR_LABEL)
            lx = BOARD_OFFSET_X + FRAME_THICKNESS - label.get_width() - 12
            ly = grid_top + i * CELL_SIZE - label.get_height() // 2
            screen.blit(label, (lx, ly))

    # ============================================================
    #  绘制 — 棋子（多层径向渐变）
    # ============================================================

    def _draw_pieces(self, screen):
        """绘制所有棋子，带多层立体渐变效果"""
        piece_r = CELL_SIZE // 2 - 2

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                player = self.board[row][col]
                if player == 0:
                    continue

                cx, cy = board_to_screen(row, col)

                if player == 1:
                    # ===== 黑子（多层径向渐变） =====
                    # 阴影偏移
                    pygame.draw.circle(screen, (6, 6, 6),
                                       (cx + 2, cy + 3), piece_r)
                    # 外层
                    pygame.draw.circle(screen, PC_BLACK_OUTER,
                                       (cx, cy), piece_r)
                    # 中层
                    pygame.draw.circle(screen, PC_BLACK_MID,
                                       (cx, cy), piece_r - 1)
                    # 内层
                    pygame.draw.circle(screen, PC_BLACK_INNER,
                                       (cx, cy), piece_r - 4)
                    # 高光（左上角）
                    hl_x = cx - piece_r // 3
                    hl_y = cy - piece_r // 3
                    pygame.draw.circle(screen, PC_BLACK_HL,
                                       (hl_x, hl_y), piece_r // 3)
                else:
                    # ===== 白子（多层径向渐变） =====
                    # 阴影偏移
                    pygame.draw.circle(screen, PC_WHITE_SHADOW,
                                       (cx + 2, cy + 3), piece_r)
                    # 外描边
                    pygame.draw.circle(screen, PC_WHITE_OUTLINE,
                                       (cx, cy), piece_r)
                    # 外层
                    pygame.draw.circle(screen, PC_WHITE_OUTER,
                                       (cx, cy), piece_r - 1)
                    # 中层
                    pygame.draw.circle(screen, PC_WHITE_MID,
                                       (cx, cy), piece_r - 3)
                    # 内层（几乎纯白）
                    pygame.draw.circle(screen, PC_WHITE_INNER,
                                       (cx, cy), piece_r - 5)
                    # 高光（左上角小圆斑点）
                    hl_x = cx - piece_r // 3
                    hl_y = cy - piece_r // 3
                    pygame.draw.circle(screen, PC_WHITE_HL,
                                       (hl_x, hl_y), piece_r // 4)

        # 末子标记：小红点 + 外环
        if self.last_move is not None:
            lr, lc = self.last_move
            lx, ly = board_to_screen(lr, lc)
            # 外环
            pygame.draw.circle(screen, (255, 80, 60), (lx, ly), 7, 1)
            # 中心点
            pygame.draw.circle(screen, (215, 40, 35), (lx, ly), 4)

    # ============================================================
    #  绘制 — 右侧控制面板
    # ============================================================

    def _draw_panel(self, screen, mx, my):
        """绘制右侧控制面板"""
        global FONT_PANEL_TITLE, FONT_PANEL_TEXT, FONT_TURN_LARGE
        px = PANEL_X
        pw = PANEL_WIDTH
        cx = px + pw // 2
        self.panel_buttons = []

        # ---- 面板背景 ----
        panel_rect = pygame.Rect(px, BOARD_OFFSET_Y, pw, BOARD_AREA_H)
        # 面板阴影
        shadow_rect = panel_rect.copy()
        shadow_rect.x += 2; shadow_rect.y += 2
        pygame.draw.rect(screen, (40, 30, 20), shadow_rect, border_radius=12)
        # 面板主体
        pygame.draw.rect(screen, COLOR_PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, panel_rect,
                         width=1, border_radius=10)

        # ---- 顶部装饰条 ----
        bar_rect = pygame.Rect(px, BOARD_OFFSET_Y, pw, 44)
        pygame.draw.rect(screen, COLOR_PANEL_ACCENT, bar_rect,
                         border_top_left_radius=10, border_top_right_radius=10)
        title = FONT_PANEL_TITLE.render("控制面板", True, (95, 60, 28))
        screen.blit(title, (cx - title.get_width() // 2, BOARD_OFFSET_Y + 10))

        # ---- 分隔线 ----
        sep_y0 = BOARD_OFFSET_Y + 45
        pygame.draw.line(screen, (185, 155, 115),
                         (px + 15, sep_y0), (px + pw - 15, sep_y0), 1)

        # ================================================
        #  第1区块：对战模式 — 分段式切换开关
        # ================================================
        mode_y = sep_y0 + 18
        seg_w  = (pw - 30) // 2
        seg_h  = 44

        # 凹陷槽背景
        seg_bg = pygame.Rect(px + 15, mode_y, pw - 30, seg_h)
        pygame.draw.rect(screen, (210, 195, 170), seg_bg, border_radius=10)
        pygame.draw.rect(screen, (185, 165, 138), seg_bg,
                         width=1, border_radius=10)

        # ---- 左分段：双人对战（图标左 · 文字右，紧凑排列） ----
        seg_left_rect = pygame.Rect(px + 17, mode_y + 3, seg_w - 4, seg_h - 6)
        seg_left_hover = seg_left_rect.collidepoint(mx, my)
        self.panel_buttons.append((seg_left_rect, "mode_dual"))

        is_dual = not self.ai_mode

        if is_dual:
            # 激活态
            pygame.draw.rect(screen, (255, 252, 246),
                             seg_left_rect, border_radius=8)
            pygame.draw.rect(screen, (190, 160, 115),
                             seg_left_rect, width=1, border_radius=8)
        elif seg_left_hover:
            pygame.draw.rect(screen, (235, 222, 200),
                             seg_left_rect, border_radius=8)

        # 双人图标 — 左对齐
        icon_left_x = seg_left_rect.left + 8
        icon_cy     = seg_left_rect.centery
        left_color  = (100, 135, 180) if is_dual else (155, 145, 125)
        hl_c        = (255, 255, 255) if is_dual else (235, 225, 210)
        for ox in (-5, 5):
            pygame.draw.circle(screen, left_color,
                               (icon_left_x + 7 + ox, icon_cy - 6), 7)
            pygame.draw.circle(screen, hl_c,
                               (icon_left_x + 7 + ox, icon_cy - 9), 2)

        # 文字 — 图标右侧，垂直居中
        text_left_x = icon_left_x + 22
        dual_text = FONT_PANEL_TEXT.render("双人对战", True,
                         (40, 95, 150) if is_dual else (125, 108, 88))
        # 确保文字不超出右边界
        text_x = min(text_left_x, seg_left_rect.right - dual_text.get_width() - 4)
        screen.blit(dual_text, (text_x,
                     seg_left_rect.centery - dual_text.get_height() // 2))

        # ---- 右分段：人机对战（图标左 · 文字右，紧凑排列） ----
        seg_right_rect = pygame.Rect(px + 15 + seg_w, mode_y + 3,
                                     seg_w - 4, seg_h - 6)
        seg_right_hover = seg_right_rect.collidepoint(mx, my)
        self.panel_buttons.append((seg_right_rect, "mode_ai"))

        if self.ai_mode:
            pygame.draw.rect(screen, (255, 252, 246),
                             seg_right_rect, border_radius=8)
            pygame.draw.rect(screen, (190, 160, 115),
                             seg_right_rect, width=1, border_radius=8)
        elif seg_right_hover:
            pygame.draw.rect(screen, (235, 222, 200),
                             seg_right_rect, border_radius=8)

        # AI 图标 — 左对齐
        icon_left_x2 = seg_right_rect.left + 8
        ai_color     = (85, 125, 165) if self.ai_mode else (155, 145, 125)
        face_fill    = (248, 246, 240) if self.ai_mode else (235, 225, 210)
        # 机器人脸轮廓
        ai_rect = pygame.Rect(icon_left_x2 + 4, icon_cy - 9, 16, 16)
        pygame.draw.rect(screen, ai_color, ai_rect, border_radius=4)
        # 脸部填充
        pygame.draw.rect(screen, face_fill,
                         (icon_left_x2 + 6, icon_cy - 7, 12, 12), border_radius=3)
        # 眼睛
        for ex in (-3, 3):
            pygame.draw.circle(screen, ai_color,
                               (icon_left_x2 + 12 + ex, icon_cy - 2), 2)
        # 天线
        pygame.draw.line(screen, ai_color,
                         (icon_left_x2 + 10, icon_cy - 9),
                         (icon_left_x2 + 8, icon_cy - 16), 2)
        pygame.draw.circle(screen, ai_color,
                           (icon_left_x2 + 8, icon_cy - 16), 2)

        # 文字 — 图标右侧，垂直居中
        text_left_x2 = icon_left_x2 + 22
        ai_text = FONT_PANEL_TEXT.render("人机对战", True,
                        (160, 110, 40) if self.ai_mode else (125, 108, 88))
        text_x2 = min(text_left_x2, seg_right_rect.right - ai_text.get_width() - 4)
        screen.blit(ai_text, (text_x2,
                     seg_right_rect.centery - ai_text.get_height() // 2))

        # 分段标题
        mode_title = FONT_PANEL_TEXT.render("对战模式", True, (125, 105, 72))
        screen.blit(mode_title, (px + 20, mode_y - 20))

        # ================================================
        #  第1.5区块：AI 难度选择（仅人机模式显示）
        # ================================================
        diff_offset = 0
        if self.ai_mode:
            diff_label_y = mode_y + 52
            diff_bar_y   = diff_label_y + 18
            diff_bar_h   = 36
            diff_offset  = 54  # 下移后续区块

            # 难度标签
            diff_label = FONT_PANEL_TEXT.render("AI 难度", True, (125, 105, 72))
            screen.blit(diff_label, (px + 20, diff_label_y))

            # 三选一凹陷槽背景
            seg_bg2 = pygame.Rect(px + 15, diff_bar_y, pw - 30, diff_bar_h)
            pygame.draw.rect(screen, (210, 195, 170), seg_bg2, border_radius=9)
            pygame.draw.rect(screen, (185, 165, 138), seg_bg2,
                             width=1, border_radius=9)

            diff_w = (pw - 36) // 3
            diff_labels = [(AI_EASY, "简单"), (AI_MEDIUM, "中等"), (AI_HARD, "困难")]
            diff_colors = [
                (100, 155, 100),   # 简单 — 绿色系
                (200, 150, 50),    # 中等 — 橙色系
                (170, 60, 60),     # 困难 — 红色系
            ]

            for idx, (d_val, d_name) in enumerate(diff_labels):
                dr_rect = pygame.Rect(px + 18 + idx * diff_w, diff_bar_y + 3,
                                      diff_w - 3, diff_bar_h - 6)
                dr_hover = dr_rect.collidepoint(mx, my)
                self.panel_buttons.append((dr_rect, f"diff_{d_val}"))
                is_active = (self.ai_difficulty == d_val)

                if is_active:
                    pygame.draw.rect(screen, (255, 252, 246),
                                     dr_rect, border_radius=7)
                    pygame.draw.rect(screen, diff_colors[idx],
                                     dr_rect, width=2, border_radius=7)
                    text_color = diff_colors[idx]
                elif dr_hover:
                    pygame.draw.rect(screen, (235, 222, 200),
                                     dr_rect, border_radius=7)
                    text_color = (diff_colors[idx][0] - 30,
                                  diff_colors[idx][1] - 30,
                                  diff_colors[idx][2] - 30)
                else:
                    text_color = (125, 108, 88)

                d_text = FONT_PANEL_TEXT.render(d_name, True, text_color)
                screen.blit(d_text,
                            (dr_rect.centerx - d_text.get_width() // 2,
                             dr_rect.centery - d_text.get_height() // 2))

        # ================================================
        #  第2区块：当前回合
        # ================================================
        turn_y = mode_y + 68 + diff_offset

        # 回合卡片背景
        turn_card = pygame.Rect(px + 12, turn_y - 4, pw - 24, 100)
        pygame.draw.rect(screen, (252, 247, 236), turn_card, border_radius=8)
        pygame.draw.rect(screen, (215, 198, 168), turn_card,
                         width=1, border_radius=8)

        # 状态标签
        if self.game_over:
            if self.is_draw:
                tag_text  = "握手言和"
                tag_color = (120, 125, 140)
            else:
                tag_text  = "游戏结束"
                tag_color = (190, 55, 55)
        elif self.ai_thinking:
            ai_col_name = "黑棋" if self.ai_color == 1 else "白棋"
            tag_text  = f"AI 思考中…（{ai_col_name}）"
            tag_color = (105, 135, 185)
        else:
            tag_text  = "当前回合"
            tag_color = (125, 105, 72)
        tag = FONT_PANEL_TEXT.render(tag_text, True, tag_color)
        screen.blit(tag, (cx - tag.get_width() // 2, turn_y + 4))

        # 大号棋子 + 回合文字
        piece_cx = cx
        piece_cy = turn_y + 42

        display_player = self.winner if self.game_over else self.current_player

        if self.is_draw and self.game_over:
            # 平局：黑白双棋并排显示
            # 黑子（左）
            left_cx = piece_cx - 12
            pygame.draw.circle(screen, (12, 12, 12), (left_cx + 1, piece_cy + 1), 16)
            pygame.draw.circle(screen, PC_BLACK_OUTER, (left_cx, piece_cy), 16)
            pygame.draw.circle(screen, PC_BLACK_MID, (left_cx, piece_cy), 15)
            pygame.draw.circle(screen, PC_BLACK_INNER, (left_cx, piece_cy), 12)
            pygame.draw.circle(screen, PC_BLACK_HL, (left_cx - 5, piece_cy - 5), 5)
            # 白子（右）
            right_cx = piece_cx + 12
            pygame.draw.circle(screen, PC_WHITE_SHADOW, (right_cx + 1, piece_cy + 1), 16)
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (right_cx, piece_cy), 16)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (right_cx, piece_cy), 15)
            pygame.draw.circle(screen, PC_WHITE_MID, (right_cx, piece_cy), 13)
            pygame.draw.circle(screen, PC_WHITE_HL, (right_cx - 5, piece_cy - 5), 4)
            turn_text = "握手言和"
        elif self.ai_thinking and not self.game_over:
            # AI 思考中 — 显示 AI 执子颜色
            if self.ai_color == 1:
                pygame.draw.circle(screen, (12, 12, 12),
                                   (piece_cx + 1, piece_cy + 1), 18)
                pygame.draw.circle(screen, PC_BLACK_OUTER,
                                   (piece_cx, piece_cy), 18)
                pygame.draw.circle(screen, PC_BLACK_MID,
                                   (piece_cx, piece_cy), 17)
                pygame.draw.circle(screen, PC_BLACK_INNER,
                                   (piece_cx, piece_cy), 14)
                pygame.draw.circle(screen, PC_BLACK_HL,
                                   (piece_cx - 6, piece_cy - 6), 6)
            else:
                pygame.draw.circle(screen, PC_WHITE_SHADOW,
                                   (piece_cx + 1, piece_cy + 1), 18)
                pygame.draw.circle(screen, PC_WHITE_OUTLINE,
                                   (piece_cx, piece_cy), 18)
                pygame.draw.circle(screen, PC_WHITE_OUTER,
                                   (piece_cx, piece_cy), 17)
                pygame.draw.circle(screen, PC_WHITE_MID,
                                   (piece_cx, piece_cy), 15)
                pygame.draw.circle(screen, PC_WHITE_HL,
                                   (piece_cx - 6, piece_cy - 6), 5)
            # 脉冲环
            pulse_r = (self.ai_move_timer % 20) + 22
            alpha_val = max(20, 180 - self.ai_move_timer * 3)
            pulse_surf = pygame.Surface((pulse_r * 2 + 4, pulse_r * 2 + 4),
                                        pygame.SRCALPHA)
            pygame.draw.circle(pulse_surf, (100, 135, 185, alpha_val),
                               (pulse_r + 2, pulse_r + 2), pulse_r, 2)
            screen.blit(pulse_surf,
                        (piece_cx - pulse_r - 2, piece_cy - pulse_r - 2))
            ai_col = "黑棋" if self.ai_color == 1 else "白棋"
            turn_text = f"等待 AI（{ai_col}）..."
        elif display_player == 1:
            pygame.draw.circle(screen, (12, 12, 12),
                               (piece_cx + 1, piece_cy + 1), 18)
            pygame.draw.circle(screen, PC_BLACK_OUTER,
                               (piece_cx, piece_cy), 18)
            pygame.draw.circle(screen, PC_BLACK_MID,
                               (piece_cx, piece_cy), 17)
            pygame.draw.circle(screen, PC_BLACK_INNER,
                               (piece_cx, piece_cy), 14)
            pygame.draw.circle(screen, PC_BLACK_HL,
                               (piece_cx - 6, piece_cy - 6), 6)
            turn_text = "你的回合（黑棋）" if self.ai_mode else "黑棋回合"
        else:
            pygame.draw.circle(screen, PC_WHITE_SHADOW,
                               (piece_cx + 1, piece_cy + 1), 18)
            pygame.draw.circle(screen, PC_WHITE_OUTLINE,
                               (piece_cx, piece_cy), 18)
            pygame.draw.circle(screen, PC_WHITE_OUTER,
                               (piece_cx, piece_cy), 17)
            pygame.draw.circle(screen, PC_WHITE_MID,
                               (piece_cx, piece_cy), 15)
            pygame.draw.circle(screen, PC_WHITE_HL,
                               (piece_cx - 6, piece_cy - 6), 5)
            turn_text = "你的回合（白棋）" if self.ai_mode else "白棋回合"

        turn_label = FONT_TURN_LARGE.render(turn_text, True, (75, 50, 25))
        screen.blit(turn_label, (cx - turn_label.get_width() // 2,
                                 turn_y + 70))

        # ================================================
        #  第3区块：步数统计
        # ================================================
        stat_y = turn_y + 105
        stat_card_w = pw - 24
        stat_card_h = 80
        stat_card = pygame.Rect(px + 12, stat_y - 2, stat_card_w, stat_card_h)
        pygame.draw.rect(screen, (252, 247, 236), stat_card, border_radius=8)
        pygame.draw.rect(screen, (215, 198, 168), stat_card,
                         width=1, border_radius=8)

        # 统计标签
        stat_title = FONT_PANEL_TEXT.render("步数统计", True, (125, 105, 72))
        screen.blit(stat_title, (cx - stat_title.get_width() // 2, stat_y + 4))

        # 计算黑棋/白棋步数
        total_moves = len(self.move_history)
        black_moves = sum(1 for _, _, p in self.move_history if p == 1)
        white_moves = sum(1 for _, _, p in self.move_history if p == 2)

        # 三列布局：总步数 | 黑棋 | 白棋
        col_w = stat_card_w // 3
        columns = [
            (None,     "总步数", str(total_moves),  (135, 110, 75)),
            ("black",  "黑棋",   str(black_moves),  (55, 55, 55)),
            ("white",  "白棋",   str(white_moves),  (170, 150, 120)),
        ]

        global FONT_STAT_NUM
        for idx, (icon_type, label, value, color) in enumerate(columns):
            col_cx = stat_card.left + col_w // 2 + idx * col_w
            num_y = stat_y + 28
            lbl_y = stat_y + 56

            # 数值大字
            num_surf = FONT_STAT_NUM.render(value, True, color)
            screen.blit(num_surf, (col_cx - num_surf.get_width() // 2, num_y))

            # 标签 — 带棋子图标
            lbl_surf = FONT_LABEL.render(label, True, (140, 120, 95))
            icon_r = 5
            gap = 4
            total_w = (icon_r * 2 + gap + lbl_surf.get_width()) if icon_type else lbl_surf.get_width()
            start_x = col_cx - total_w // 2

            if icon_type == "black":
                icon_cx = start_x + icon_r
                icon_cy = lbl_y + FONT_LABEL.get_height() // 2
                pygame.draw.circle(screen, (30, 30, 30), (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(screen, (75, 75, 75), (icon_cx - 1, icon_cy - 2), icon_r // 2)
                screen.blit(lbl_surf, (start_x + icon_r * 2 + gap, lbl_y))
            elif icon_type == "white":
                icon_cx = start_x + icon_r
                icon_cy = lbl_y + FONT_LABEL.get_height() // 2
                pygame.draw.circle(screen, (210, 205, 200), (icon_cx, icon_cy), icon_r)
                pygame.draw.circle(screen, (155, 150, 145), (icon_cx, icon_cy), icon_r, 1)
                pygame.draw.circle(screen, (255, 255, 254), (icon_cx - 1, icon_cy - 2), icon_r // 3)
                screen.blit(lbl_surf, (start_x + icon_r * 2 + gap, lbl_y))
            else:
                screen.blit(lbl_surf, (start_x, lbl_y))

        # ================================================
        #  第4区块：操作按钮
        # ================================================
        btn_y  = BOARD_OFFSET_Y + BOARD_AREA_H - 170
        btn_w  = pw - 40
        btn_h  = 44
        btn_gap = 10

        button_defs = [
            ("再来一局", (205, 95, 58),  "restart"),
            ("悔棋",     (95, 132, 100), "undo"),
            ("退出游戏",  (165, 70, 68),  "quit"),
        ]

        for i, (text, base_color, action) in enumerate(button_defs):
            bx = px + 20
            by = btn_y + i * (btn_h + btn_gap)
            btn_rect = pygame.Rect(bx, by, btn_w, btn_h)
            self.panel_buttons.append((btn_rect, action))

            is_hovered = btn_rect.collidepoint(mx, my)

            if is_hovered:
                # 悬浮：发光 + 放大
                hover_rect = btn_rect.inflate(4, 4)
                hover_rect.center = btn_rect.center
                # 柔光外圈
                glow_surf = pygame.Surface(
                    (hover_rect.width + 10, hover_rect.height + 10),
                    pygame.SRCALPHA)
                glow_color = tuple(min(255, c + 70)
                                   for c in base_color) + (70,)
                pygame.draw.rect(glow_surf, glow_color,
                                 pygame.Rect(5, 5,
                                 hover_rect.width, hover_rect.height),
                                 border_radius=10)
                screen.blit(glow_surf,
                            (hover_rect.x - 5, hover_rect.y - 5))
                # 提亮主体
                hover_fill = tuple(min(255, c + 50) for c in base_color)
                pygame.draw.rect(screen, hover_fill,
                                 hover_rect, border_radius=10)
                # 亮边框
                hover_border = tuple(min(255, c + 90) for c in base_color)
                pygame.draw.rect(screen, hover_border,
                                 hover_rect, width=2, border_radius=10)
                use_rect = hover_rect
            else:
                # 正常状态
                # 阴影
                shadow_rect = btn_rect.copy()
                shadow_rect.y += 3
                pygame.draw.rect(screen, (55, 40, 28),
                                 shadow_rect, border_radius=9)
                # 主体
                pygame.draw.rect(screen, base_color,
                                 btn_rect, border_radius=9)
                # 顶部高光线
                hl_color = tuple(min(255, c + 55) for c in base_color)
                pygame.draw.rect(screen, hl_color,
                                 btn_rect, width=1, border_radius=9)
                # 底部阴影线
                sd_color = tuple(max(0, c - 55) for c in base_color)
                pygame.draw.line(screen, sd_color,
                                 (bx + 5, by + btn_h - 2),
                                 (bx + btn_w - 5, by + btn_h - 2), 3)
                use_rect = btn_rect

            # 按钮文字
            global FONT_BTN
            btn_label = FONT_BTN.render(text, True, (255, 255, 255))
            screen.blit(btn_label,
                        (use_rect.centerx - btn_label.get_width() // 2,
                         use_rect.centery - btn_label.get_height() // 2))

        # ---- 底部版本信息 ----
        ver_y = BOARD_OFFSET_Y + BOARD_AREA_H - 24
        ver_label = FONT_PANEL_TEXT.render("优雅五子棋  v2.0", True,
                                           (175, 155, 130))
        screen.blit(ver_label, (cx - ver_label.get_width() // 2, ver_y))

    # ============================================================
    #  绘制 — 提示消息
    # ============================================================

    def _draw_toast(self, screen):
        """绘制浮动提示消息（带淡入淡出动画）"""
        if self.toast_timer <= 0 or not self.toast_message:
            return

        total       = 90
        fade_frames = 20
        alpha       = 255

        if self.toast_timer < fade_frames:
            alpha = int(255 * self.toast_timer / fade_frames)
        elif self.toast_timer > total - fade_frames:
            alpha = int(255 * (total - self.toast_timer) / fade_frames)

        alpha = max(0, min(255, alpha))

        global FONT_TOAST
        text_surf  = FONT_TOAST.render(self.toast_message, True, (255, 255, 255))

        pad_x, pad_y = 30, 14
        bubble_w = text_surf.get_width() + pad_x * 2
        bubble_h = text_surf.get_height() + pad_y * 2

        bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (50, 38, 25, 215),
                         bubble.get_rect(), border_radius=12)
        pygame.draw.rect(bubble, (190, 155, 100, 190),
                         bubble.get_rect(), width=1, border_radius=12)

        bubble.set_alpha(alpha)
        text_surf.set_alpha(alpha)

        bubble_x = (WIN_WIDTH - bubble_w) // 2
        bubble_y = WIN_HEIGHT - bubble_h - 32
        screen.blit(bubble, (bubble_x, bubble_y))
        screen.blit(text_surf, (bubble_x + pad_x, bubble_y + pad_y))

    # ============================================================
    #  绘制 — 先后手选择界面
    # ============================================================

    def _draw_color_selection(self, screen, mx, my):
        """绘制先后手选择界面，玩家可选择执黑、执白或随机"""
        if not self.selecting_color:
            return

        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 8, 5, 195))
        screen.blit(overlay, (0, 0))

        title_text = FONT_WINNER.render("选择先后手", True, (240, 210, 160))
        screen.blit(title_text,
                    (WIN_WIDTH // 2 - title_text.get_width() // 2, 75))

        sub_text = FONT_TURN_LARGE.render("请选择你的执子颜色", True,
                                          (200, 175, 140))
        screen.blit(sub_text,
                    (WIN_WIDTH // 2 - sub_text.get_width() // 2, 130))

        card_w, card_h = 155, 215
        card_gap = 24
        total_w = card_w * 3 + card_gap * 2
        start_x = (WIN_WIDTH - total_w) // 2
        card_y = 185

        cards = [
            {"label": "执黑先行", "sub": "先手优势",
             "color": (35, 28, 22), "accent": (75, 75, 80),
             "piece": "black", "action": "choose_black"},
            {"label": "执白后手", "sub": "后手应对",
             "color": (238, 230, 218), "accent": (195, 185, 168),
             "piece": "white", "action": "choose_white"},
            {"label": "随机分配", "sub": "公平对决",
             "color": (48, 38, 25), "accent": (220, 180, 60),
             "piece": "random", "action": "choose_random"},
        ]

        self._selection_buttons.clear()

        for i, card in enumerate(cards):
            cx = start_x + i * (card_w + card_gap)
            card_rect = pygame.Rect(cx, card_y, card_w, card_h)
            is_hovered = card_rect.collidepoint(mx, my)
            self._selection_buttons.append((card_rect, card["action"]))

            sh = card_rect.copy(); sh.x += 3; sh.y += 5
            pygame.draw.rect(screen, (14, 10, 6), sh, border_radius=18)
            pygame.draw.rect(screen, card["color"], card_rect, border_radius=16)
            bw = 3 if is_hovered else 1
            bc = (240, 195, 55) if is_hovered else card["accent"]
            pygame.draw.rect(screen, bc, card_rect, width=bw, border_radius=16)

            if is_hovered:
                hl = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 30))
                screen.blit(hl, (cx, card_y))

            icon_cx = cx + card_w // 2
            icon_cy = card_y + 55

            if card["piece"] == "black":
                pygame.draw.circle(screen, (14, 14, 14), (icon_cx + 2, icon_cy + 3), 30)
                pygame.draw.circle(screen, PC_BLACK_OUTER, (icon_cx, icon_cy), 30)
                pygame.draw.circle(screen, PC_BLACK_MID, (icon_cx, icon_cy), 28)
                pygame.draw.circle(screen, PC_BLACK_INNER, (icon_cx, icon_cy), 22)
                pygame.draw.circle(screen, PC_BLACK_HL, (icon_cx - 9, icon_cy - 9), 10)
            elif card["piece"] == "white":
                pygame.draw.circle(screen, PC_WHITE_SHADOW, (icon_cx + 2, icon_cy + 3), 30)
                pygame.draw.circle(screen, PC_WHITE_OUTLINE, (icon_cx, icon_cy), 30)
                pygame.draw.circle(screen, PC_WHITE_OUTER, (icon_cx, icon_cy), 28)
                pygame.draw.circle(screen, PC_WHITE_MID, (icon_cx, icon_cy), 24)
                pygame.draw.circle(screen, PC_WHITE_HL, (icon_cx - 9, icon_cy - 9), 8)
            else:
                pygame.draw.circle(screen, (18, 18, 18), (icon_cx - 11, icon_cy), 26)
                pygame.draw.circle(screen, (35, 35, 35), (icon_cx - 11, icon_cy), 24)
                pygame.draw.circle(screen, PC_WHITE_SHADOW, (icon_cx + 12, icon_cy + 1), 26)
                pygame.draw.circle(screen, PC_WHITE_OUTLINE, (icon_cx + 11, icon_cy), 26)
                pygame.draw.circle(screen, PC_WHITE_OUTER, (icon_cx + 11, icon_cy), 24)
                pygame.draw.circle(screen, PC_WHITE_MID, (icon_cx + 11, icon_cy), 21)
                q_s = FONT_STAT_NUM.render("?", True, (240, 195, 55))
                screen.blit(q_s, (icon_cx - q_s.get_width() // 2,
                            icon_cy - q_s.get_height() // 2 - 2))

            if card["piece"] == "white":
                lc = (65, 48, 28); sc = (110, 85, 55)
            else:
                lc = (240, 215, 175); sc = (180, 155, 115)

            label = FONT_TURN_LARGE.render(card["label"], True, lc)
            screen.blit(label, (cx + card_w // 2 - label.get_width() // 2, card_y + 110))
            sub = FONT_PANEL_TEXT.render(card["sub"], True, sc)
            screen.blit(sub, (cx + card_w // 2 - sub.get_width() // 2, card_y + 142))

        hint = FONT_WINNER_HINT.render("选择后将开始对局", True, (160, 140, 110))
        screen.blit(hint, (WIN_WIDTH // 2 - hint.get_width() // 2, card_y + card_h + 28))

    # ============================================================
    #  绘制 — 胜利动画
    # ============================================================

    def _draw_result_overlay(self, screen):
        """
        游戏胜利动画：
        - 全屏半透明遮罩渐入
        - 中央卡片平台
        - 文字脉冲呼吸效果
        - 金色粒子爆发
        """
        vf = self.victory_frame

        # ---- 阶段1: 全屏暗色遮罩渐入 ----
        overlay_alpha = min(175, vf * 4)
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((18, 12, 8, overlay_alpha))
        screen.blit(overlay, (0, 0))

        is_draw = self.is_draw

        # ---- 阶段2: 中央卡片 ----
        card_w, card_h = 420, 190
        card_x = (WIN_WIDTH - card_w) // 2
        card_y = (WIN_HEIGHT - card_h) // 2 - 10
        card_alpha = min(235, vf * 6)

        # 卡片滑入效果
        slide_offset = max(0, 30 - vf * 1.5)
        card_y += int(slide_offset)

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)

        # 卡片底色
        if is_draw:
            # 平局 — 反差双色底（左侧深黑、右侧浅白渐变感）
            pygame.draw.rect(card, (45, 42, 48, card_alpha),
                             card.get_rect(), border_radius=18)
        elif self.winner == 1:
            pygame.draw.rect(card, (28, 24, 22, card_alpha),
                             card.get_rect(), border_radius=18)
        else:
            pygame.draw.rect(card, (248, 242, 232, card_alpha),
                             card.get_rect(), border_radius=18)

        # 金色装饰边框
        border_alpha = min(200, vf * 4)
        pygame.draw.rect(card, (240, 195, 55, border_alpha),
                         card.get_rect(), width=2, border_radius=18)
        # 内边框（细金线）
        inner_rect = pygame.Rect(4, 4, card_w - 8, card_h - 8)
        pygame.draw.rect(card, (240, 195, 55, border_alpha // 2),
                         inner_rect, width=1, border_radius=15)

        screen.blit(card, (card_x, card_y))

        # ---- 阶段3: 奖杯/平局图标 ----
        trophy_y = card_y + 28
        trophy_cx = card_x + card_w // 2
        trophy_alpha = min(255, vf * 5)

        # 杯身
        cup_w, cup_h = 26, 24
        cup_color = (240, 195, 55, trophy_alpha)

        if is_draw:
            # ---- 平局图标：黑白双圆交叠 ----
            draw_icon_surf = pygame.Surface((40, 28), pygame.SRCALPHA)
            icon_alpha = trophy_alpha
            # 黑子（左侧）
            black_c = (50, 50, 55, icon_alpha)
            pygame.draw.circle(draw_icon_surf, black_c, (13, 14), 10)
            pygame.draw.circle(draw_icon_surf, (85, 85, 90, icon_alpha),
                               (12, 13), 3)
            # 白子（右侧，与黑子交叠）
            white_c = (235, 228, 215, icon_alpha)
            pygame.draw.circle(draw_icon_surf, white_c, (27, 14), 10)
            pygame.draw.circle(draw_icon_surf, (185, 178, 168, icon_alpha),
                               (27, 14), 10, 1)
            pygame.draw.circle(draw_icon_surf, (255, 255, 254, icon_alpha),
                               (26, 13), 3)
            screen.blit(draw_icon_surf, (trophy_cx - 20, trophy_y))
        else:
            cup_surf = pygame.Surface((cup_w + 4, cup_h + 4), pygame.SRCALPHA)
            pygame.draw.rect(cup_surf, cup_color,
                             pygame.Rect(2, 2, cup_w, cup_h), border_radius=4)
            # 杯耳
            for dx in (-6, cup_w + 2):
                pygame.draw.arc(cup_surf, cup_color,
                                (dx, 4, 8, cup_h), 0, math.pi, 2)
            # 杯座
            base_w = cup_w + 10
            pygame.draw.rect(cup_surf, cup_color,
                             pygame.Rect(cup_w // 2 - base_w // 2 + 2,
                                         2 + cup_h - 4, base_w, 6),
                             border_radius=2)
            screen.blit(cup_surf, (trophy_cx - cup_w // 2 - 2, trophy_y - 2))

        # ---- 阶段4: 胜利/平局文字（脉冲呼吸） ----
        pulse = 1.0 + 0.04 * math.sin(vf * 0.07)
        global FONT_WINNER

        if is_draw:
            w_text = "握手言和"
            w_color = (180, 190, 210)
            glow_color = (140, 150, 175)
        else:
            w_text = "黑棋 胜利！" if self.winner == 1 else "白棋 胜利！"
            w_color = (255, 220, 50) if self.winner == 1 else (190, 55, 35)
            glow_color = (255, 180, 30) if self.winner == 1 else (220, 100, 60)
        text_alpha = min(255, vf * 6)

        base_surf = FONT_WINNER.render(w_text, True, w_color)
        new_w = max(1, int(base_surf.get_width() * pulse))
        new_h = max(1, int(base_surf.get_height() * pulse))
        w_surf = pygame.transform.smoothscale(base_surf, (new_w, new_h))
        w_surf.set_alpha(text_alpha)

        # 文字发光层
        base_glow = FONT_WINNER.render(w_text, True, glow_color)
        g_surf = pygame.transform.smoothscale(base_glow, (new_w, new_h))
        g_surf.set_alpha(min(100, text_alpha // 2))
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            screen.blit(g_surf,
                        (WIN_WIDTH // 2 - g_surf.get_width() // 2 + dx,
                         card_y + 58 + dy))

        screen.blit(w_surf,
                    (WIN_WIDTH // 2 - w_surf.get_width() // 2,
                     card_y + 58))

        # ---- 阶段5: 副提示文字 ----
        global FONT_WINNER_HINT
        hint_text = "点击「再来一局」重新开局"
        if is_draw:
            hint_color = (185, 180, 195)
        else:
            hint_color = (220, 210, 190) if self.winner == 1 \
                         else (145, 105, 82)
        hint_surf = FONT_WINNER_HINT.render(hint_text, True, hint_color)
        hint_surf.set_alpha(min(200, vf * 4))
        screen.blit(hint_surf,
                    (WIN_WIDTH // 2 - hint_surf.get_width() // 2,
                     card_y + 115))

        # 右下小棋子装饰
        deco_r = 8
        deco_cx, deco_cy = card_x + card_w - 26, card_y + card_h - 18
        if is_draw:
            # 平局：黑白各一半小棋子在角落
            pygame.draw.circle(screen, PC_BLACK_OUTER, (deco_cx - 6, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_BLACK_MID, (deco_cx - 6, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_BLACK_HL,
                               (deco_cx - 8, deco_cy - 2), 3)
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (deco_cx + 6, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (deco_cx + 6, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_WHITE_HL,
                               (deco_cx + 5, deco_cy - 2), 2)
        elif self.winner == 1:
            pygame.draw.circle(screen, PC_BLACK_OUTER, (deco_cx, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_BLACK_MID, (deco_cx, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_BLACK_HL,
                               (deco_cx - 2, deco_cy - 2), 3)
        else:
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (deco_cx, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (deco_cx, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_WHITE_HL,
                               (deco_cx - 2, deco_cy - 2), 2)

        # ---- 阶段6: 金色粒子爆发 ----
        if self._victory_sparks:
            for spark in self._victory_sparks:
                spark['distance'] += spark['speed']
                spark['life'] -= 1
                if spark['life'] <= 0:
                    continue

                dist = spark['distance']
                if dist > spark['max_dist']:
                    dist = spark['max_dist']

                sx = spark['cx'] + math.cos(spark['angle']) * dist
                sy = spark['cy'] + math.sin(spark['angle']) * dist

                life_ratio = spark['life'] / spark['max_life']
                alpha = int(255 * life_ratio)
                size  = max(1, int(spark['size'] * life_ratio))

                spark_color = spark['hue'] + (alpha,)
                spark_surf = pygame.Surface((size * 4, size * 4),
                                            pygame.SRCALPHA)
                pygame.draw.circle(spark_surf, spark_color,
                                   (size * 2, size * 2), size)
                screen.blit(spark_surf,
                            (int(sx) - size * 2, int(sy) - size * 2))
    # ============================================================
    #  绘制 — 胜利连子高亮（遮罩之上）
    # ============================================================

    def _draw_win_highlight(self, screen):
        """在结算遮罩之上绘制获胜五连棋子金色脉冲高亮"""
        if not (self.game_over and not self.is_draw and self.win_line):
            return

        vf = self.victory_frame
        piece_r = CELL_SIZE // 2 - 2

        for row, col in self.win_line:
            cx, cy = board_to_screen(row, col)

            # 外发光环 — 金色柔光
            glow_r = piece_r + 4
            glow_alpha = int(100 + 60 * math.sin(vf * 0.06 + row * 0.7))
            glow_surf = pygame.Surface((glow_r * 2 + 6, glow_r * 2 + 6),
                                       pygame.SRCALPHA)
            glow_color = (255, 200, 50, max(30, glow_alpha // 2))
            pygame.draw.circle(glow_surf, glow_color,
                               (glow_r + 3, glow_r + 3), glow_r)
            screen.blit(glow_surf,
                        (cx - glow_r - 3, cy - glow_r - 3))

            # 中层高亮圆环 — 亮金色
            ring_r = piece_r + 1
            ring_alpha = int(140 + 80 * math.sin(vf * 0.07 + col * 0.7))
            ring_color = (255, 215, 0, max(60, ring_alpha))
            ring_surf = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4),
                                       pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, ring_color,
                               (ring_r + 2, ring_r + 2), ring_r, 2)
            screen.blit(ring_surf,
                        (cx - ring_r - 2, cy - ring_r - 2))

            # 内层细环 — 白色高亮
            inner_r = piece_r - 2
            inner_alpha = int(120 + 100 * math.sin(vf * 0.09 + (row + col) * 0.5))
            inner_color = (255, 255, 240, max(40, inner_alpha))
            inner_surf = pygame.Surface((inner_r * 2 + 4, inner_r * 2 + 4),
                                        pygame.SRCALPHA)
            pygame.draw.circle(inner_surf, inner_color,
                               (inner_r + 2, inner_r + 2), inner_r, 1)
            screen.blit(inner_surf,
                        (cx - inner_r - 2, cy - inner_r - 2))


# ============================================================
# 主函数
# ============================================================

def main():
    """程序入口"""
    global FONT_LABEL, FONT_PANEL_TITLE, FONT_PANEL_TEXT, FONT_TURN_LARGE
    global FONT_BTN, FONT_TOAST, FONT_WINNER, FONT_WINNER_HINT, FONT_STAT_NUM

    # 修复 Pygame 在 Windows 上扫描系统字体时的类型错误 bug
    _orig_sf = pygame.sysfont.initsysfonts_win32
    def _safe_sf(*a, **kw):
        try: return _orig_sf(*a, **kw)
        except TypeError: return {}
    pygame.sysfont.initsysfonts_win32 = _safe_sf

    pygame.init()

    # 用字体文件路径加载，绕过 SysFont 系统枚举
    _FR = "C:/Windows/Fonts/msyh.ttc"
    _FB = "C:/Windows/Fonts/msyhbd.ttc"
    _fl = lambda p, s: pygame.font.Font(p, s) if __import__("os").path.exists(p) else pygame.font.Font(None, s)

    FONT_LABEL        = _fl(_FR, 13)
    FONT_PANEL_TITLE  = _fl(_FB, 22)
    FONT_PANEL_TEXT   = _fl(_FR, 16)
    FONT_TURN_LARGE   = _fl(_FB, 18)
    FONT_BTN          = _fl(_FB, 17)
    FONT_TOAST        = _fl(_FB, 18)
    FONT_WINNER       = _fl(_FB, 46)
    FONT_WINNER_HINT  = _fl(_FR, 14)
    FONT_STAT_NUM     = _fl(_FB, 22)

    screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
    pygame.display.set_caption("优雅五子棋")

    clock = pygame.time.Clock()
    game  = GomokuGame()

    running = True
    while running:
        # ---- 事件处理 ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # 键盘快捷键
            if event.type == pygame.KEYDOWN:
                if (event.key == pygame.K_z
                      and pygame.key.get_mods() & pygame.KMOD_CTRL):
                    game.undo()
                continue  # 键盘事件已处理，跳过鼠标逻辑

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = pygame.mouse.get_pos()

                if game.selecting_color:
                    for sel_rect, action in game._selection_buttons:
                        if sel_rect.collidepoint(mx, my):
                            if action == "choose_black":
                                game.player_color = 1
                            elif action == "choose_white":
                                game.player_color = 2
                            elif action == "choose_random":
                                game.player_color = random.choice([1, 2])
                            game.selecting_color = False
                            color_name = "黑棋（先手）" if game.player_color == 1 else "白棋（后手）"
                            game.toast_message = f"你选择执{color_name}"
                            game.toast_timer = 120
                            if game.ai_mode and game.current_player == game.ai_color:
                                game.ai_thinking = True
                                ai_timers = {AI_EASY: 5, AI_MEDIUM: 22, AI_HARD: 35}
                                game.ai_move_timer = ai_timers.get(
                                    game.ai_difficulty, 22)
                            break
                    continue

                button_clicked = False
                for btn_rect, action in game.panel_buttons:
                    if btn_rect.collidepoint(mx, my):
                        if action == "restart":
                            game.reset()
                        elif action == "undo":
                            game.undo()
                        elif action == "quit":
                            running = False
                        elif action == "mode_dual":
                            if game.ai_mode:
                                game.toggle_mode()
                        elif action == "mode_ai":
                            if not game.ai_mode:
                                game.toggle_mode()
                        elif action.startswith("diff_"):
                            diff_val = int(action.split("_")[1])
                            if game.ai_mode and game.ai_difficulty != diff_val:
                                game.ai_difficulty = diff_val
                                diff_name = AI_DIFF_NAMES[diff_val]
                                game.toast_message = f"AI 难度已切换为「{diff_name}」"
                                game.toast_timer = 90
                        button_clicked = True
                        break

                if (not button_clicked and not game.game_over
                        and not game.ai_thinking):
                    pos = screen_to_board(mx, my)
                    if pos is not None:
                        if game.place_piece(*pos):
                            if game.ai_mode and game.current_player == game.ai_color:
                                game.ai_thinking   = True
                                # 不同难度思考延迟不同
                                ai_timers = {AI_EASY: 5, AI_MEDIUM: 22, AI_HARD: 35}
                                game.ai_move_timer = ai_timers.get(
                                    game.ai_difficulty, 22)

        # ---- 游戏逻辑更新 ----
        game.update()

        # ---- 绘制 ----
        game.draw(screen)

        # ---- 鼠标悬停落子预览 ----
        if not game.game_over and not game.ai_thinking and not game.selecting_color:
            mx, my = pygame.mouse.get_pos()
            pos = screen_to_board(mx, my)
            if pos is not None and game.board[pos[0]][pos[1]] == 0:
                cx, cy = board_to_screen(*pos)
                hint_surf = pygame.Surface((CELL_SIZE, CELL_SIZE),
                                           pygame.SRCALPHA)
                if game.current_player == 1:
                    hint_color = (20, 20, 20, 55)
                else:
                    hint_color = (210, 208, 200, 70)
                pygame.draw.circle(hint_surf, hint_color,
                                   (CELL_SIZE // 2, CELL_SIZE // 2),
                                   CELL_SIZE // 2 - 3)
                screen.blit(hint_surf,
                            (cx - CELL_SIZE // 2, cy - CELL_SIZE // 2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
