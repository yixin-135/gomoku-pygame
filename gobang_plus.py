"""
五子棋（Gomoku）Plus — 基于 Pygame
升级版 · Elegant Gomoku Plus

核心升级：
  1. Minimax + Alpha-Beta 剪枝搜索 AI（替代简单打分）
  2. 多线程 AI 计算（界面永不卡顿）
  3. 程序化音效系统（无需外部音频文件）
  4. 棋谱回放（逐步查看历史落子）
  5. 会话胜率统计
  6. 开局库（常见定式）
  7. 改进的评估函数（双威胁检测、位置权重）
"""

import sys
import math
import random
import struct
import threading
import copy
import pygame

# ============================================================
# 常量定义
# ============================================================

BOARD_SIZE   = 15
CELL_SIZE    = 34

AI_EASY      = 0
AI_MEDIUM    = 1
AI_HARD      = 2
AI_DIFF_NAMES = {AI_EASY: "简单", AI_MEDIUM: "中等", AI_HARD: "困难"}

BOARD_GRID_PX   = (BOARD_SIZE - 1) * CELL_SIZE  # 476
BOARD_OFFSET_X  = 46
BOARD_OFFSET_Y  = 58
FRAME_THICKNESS = 28
BOARD_AREA_W    = BOARD_GRID_PX + FRAME_THICKNESS * 2
BOARD_AREA_H    = BOARD_GRID_PX + FRAME_THICKNESS * 2

PANEL_X      = BOARD_OFFSET_X + BOARD_AREA_W + 24
PANEL_WIDTH  = 240
WIN_WIDTH    = PANEL_X + PANEL_WIDTH + 20
WIN_HEIGHT   = BOARD_OFFSET_Y + BOARD_AREA_H + 40 + 20

# 各难度 AI 搜索深度
AI_DEPTH = {AI_EASY: 1, AI_MEDIUM: 3, AI_HARD: 5}

# ============================================================
# 颜色定义
# ============================================================

COLOR_BG               = (58, 45, 35)
COLOR_BOARD_FILL       = (238, 218, 176)
COLOR_BOARD_FRAME      = (130, 85, 45)
COLOR_BOARD_FRAME_TOP  = (170, 120, 65)
COLOR_BOARD_FRAME_BOT  = (80, 48, 22)
COLOR_LINE             = (108, 92, 72)
COLOR_STAR             = (88, 72, 55)

PC_BLACK_OUTER   = (18, 18, 18)
PC_BLACK_MID     = (32, 32, 32)
PC_BLACK_INNER   = (48, 48, 48)
PC_BLACK_HL      = (72, 72, 72)

PC_WHITE_OUTLINE = (148, 142, 135)
PC_WHITE_SHADOW  = (118, 112, 105)
PC_WHITE_OUTER   = (228, 224, 216)
PC_WHITE_MID     = (240, 237, 230)
PC_WHITE_INNER   = (250, 248, 244)
PC_WHITE_HL      = (255, 255, 254)

COLOR_PANEL_BG     = (250, 243, 230)
COLOR_PANEL_BORDER = (160, 130, 90)
COLOR_PANEL_ACCENT = (225, 208, 178)
COLOR_LABEL        = (125, 100, 70)

REPLAY_HIGHLIGHT   = (255, 80, 60)

# 全局字体引用
FONT_LABEL = FONT_PANEL_TITLE = FONT_PANEL_TEXT = None
FONT_TURN_LARGE = FONT_BTN = FONT_TOAST = None
FONT_WINNER = FONT_WINNER_HINT = FONT_STAT_NUM = FONT_SMALL = None

# ============================================================
# 坐标转换
# ============================================================

def board_to_screen(row, col):
    x = BOARD_OFFSET_X + FRAME_THICKNESS + col * CELL_SIZE
    y = BOARD_OFFSET_Y + FRAME_THICKNESS + row * CELL_SIZE
    return x, y

def screen_to_board(mx, my):
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
# 音效引擎 — 程序化生成，无需外部文件
# ============================================================

class SoundEngine:
    """用数学合成简单音效，无需外部音频文件"""

    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._available = True
            self._generate_all()
        except Exception:
            self._available = False

    def _generate_all(self):
        self.sounds["place"]  = self._gen_tone(800, 0.06, "square", 0.15)
        self.sounds["win"]    = self._gen_arpeggio([523, 659, 784, 1047], 0.12, 0.35)
        self.sounds["undo"]   = self._gen_tone(300, 0.08, "sine", 0.12)
        self.sounds["click"]  = self._gen_tone(1200, 0.03, "square", 0.08)
        self.sounds["draw"]   = self._gen_arpeggio([392, 330, 262], 0.15, 0.3)
        self.sounds["start"]  = self._gen_arpeggio([262, 330, 392, 523], 0.1, 0.25)

    def _gen_tone(self, freq, duration, waveform="sine", volume=0.3):
        sample_rate = 22050
        n_samples   = int(sample_rate * duration)
        buf = []
        for i in range(n_samples):
            t = i / sample_rate
            envelope = max(0, 1.0 - (i / n_samples) ** 2)
            if waveform == "square":
                sample = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            else:
                sample = math.sin(2 * math.pi * freq * t)
            sample *= envelope * volume * 32767
            buf.append(int(sample))
        raw = struct.pack(f"<{len(buf)}h", *buf)
        try:
            return pygame.mixer.Sound(buffer=raw)
        except Exception:
            return None

    def _gen_arpeggio(self, freqs, note_dur, volume=0.3):
        sample_rate = 22050
        total_samples = int(sample_rate * note_dur * len(freqs))
        buf = []
        for i in range(total_samples):
            t = i / sample_rate
            note_idx = min(int(t / note_dur), len(freqs) - 1)
            freq = freqs[note_idx]
            local_t = t - note_idx * note_dur
            envelope = max(0, 1.0 - (local_t / note_dur))
            sample = math.sin(2 * math.pi * freq * t) * envelope * volume * 32767
            buf.append(int(sample))
        raw = struct.pack(f"<{len(buf)}h", *buf)
        try:
            return pygame.mixer.Sound(buffer=raw)
        except Exception:
            return None

    def play(self, name):
        if not self._available or not self.enabled:
            return
        s = self.sounds.get(name)
        if s:
            s.play()

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

# ============================================================
# 开局库
# ============================================================

OPENING_BOOK = [
    # (row, col) 序列 — 常见的五子棋开局定式
    # 斜月开局
    [(7, 7), (7, 8), (8, 6), (8, 8), (6, 9)],
    # 浦月开局
    [(7, 7), (7, 8), (8, 7), (6, 8), (8, 6)],
    # 岚月开局
    [(7, 7), (6, 8), (8, 7), (6, 6), (8, 8)],
    # 花月开局
    [(7, 7), (7, 8), (8, 7), (8, 8), (9, 7)],
    # 雨月开局
    [(7, 7), (6, 7), (8, 7), (7, 6), (7, 8)],
    # 恒星开局
    [(7, 7), (8, 7), (7, 8), (9, 7), (6, 7)],
    # 云月开局
    [(7, 7), (8, 7), (6, 8), (7, 6), (9, 7)],
]

# ============================================================
# AI 引擎 — Minimax + Alpha-Beta 剪枝
# ============================================================

# 四个方向
DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]

# 位置权重表：越靠近中心权重越高
POSITION_WEIGHT = [
    [max(0, 7 - max(abs(r - 7), abs(c - 7))) for c in range(BOARD_SIZE)]
    for r in range(BOARD_SIZE)
]


class AIEngine:
    """Minimax + Alpha-Beta 剪枝搜索 + 迭代加深"""

    # 棋型分数（攻防共用）
    PATTERN_SCORES = {
        # (连子数, 开放端数): 分数
        (5, 0): 1000000,  (5, 1): 1000000,  (5, 2): 1000000,
        (4, 2): 50000,    # 活四
        (4, 1): 8000,     # 冲四
        (3, 2): 3000,     # 活三
        (3, 1): 500,      # 眠三
        (2, 2): 200,      # 活二
        (2, 1): 40,       # 眠二
        (1, 2): 10,
        (1, 1): 2,
    }

    def __init__(self):
        self.nodes_searched = 0
        self.transposition_table = {}
        self.killer_moves = {}   # killer heuristic: depth -> [(r,c), (r,c)]

    # ---- 方向计数 ----

    @staticmethod
    def _count_line(board, row, col, dr, dc, player):
        """计算 (row,col) 处沿 (dr,dc) 的 (连子数, 开放端数)"""
        count = 1
        opens = 0
        # 正方向
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1; r += dr; c += dc
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == 0:
            opens += 1
        # 反方向
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1; r -= dr; c -= dc
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == 0:
            opens += 1
        return count, opens

    @staticmethod
    def _pattern_score(count, opens):
        if count >= 5:
            return 100000
        return AIEngine.PATTERN_SCORES.get((count, opens), 0)

    # ---- 单点评估 ----

    def _eval_point(self, board, row, col, player):
        """评估在 (row,col) 落子对 player 的价值（不要求该点为空）"""
        total = 0
        for dr, dc in DIRECTIONS:
            cnt, ends = self._count_line(board, row, col, dr, dc, player)
            total += self._pattern_score(cnt, ends)
        return total

    # ---- 全盘评估 ----

    def evaluate_board(self, board, ai_player, human_player):
        """
        全盘静态评估：遍历所有棋子，累计威胁分。
        ai_player 和 human_player 分别是 1 或 2。
        返回正 = AI 优，负 = 人类优。
        """
        score = 0
        # 检查所有已落子位置的连线
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = board[r][c]
                if p == ai_player:
                    score += self._eval_point(board, r, c, p)
                elif p == human_player:
                    score -= self._eval_point(board, r, c, p)
        # 位置权重修正
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board[r][c] == ai_player:
                    score += POSITION_WEIGHT[r][c] * 3
                elif board[r][c] == human_player:
                    score -= POSITION_WEIGHT[r][c] * 3
        return score

    # ---- 候选点生成 ----

    @staticmethod
    def get_candidates(board, radius=2):
        """返回所有候选落子点（已有棋子周围 radius 格内的空位）"""
        candidates = set()
        has_stone = False
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board[r][c] != 0:
                    has_stone = True
                    for dr in range(-radius, radius + 1):
                        for dc in range(-radius, radius + 1):
                            nr, nc = r + dr, c + dc
                            if (0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE
                                    and board[nr][nc] == 0):
                                candidates.add((nr, nc))
        if not has_stone:
            return [(BOARD_SIZE // 2, BOARD_SIZE // 2)]
        return list(candidates)

    # ---- 着法排序（提高剪枝效率） ----

    def _order_moves(self, board, moves, player, depth):
        """按启发式评分排序候选着法，高分优先"""
        scored = []
        for move in moves:
            r, c = move
            # 临时放置
            board[r][c] = player
            # 自己的收益
            atk = self._eval_point(board, r, c, player)
            # 对手在此下的收益（防守价值）
            board[r][c] = 3 - player
            defense = self._eval_point(board, r, c, 3 - player)
            board[r][c] = 0
            # killer move 加成
            killer_bonus = 0
            if depth in self.killer_moves and move in self.killer_moves[depth]:
                killer_bonus = 5000
            priority = atk + int(defense * 1.2) + POSITION_WEIGHT[r][c] * 5 + killer_bonus
            scored.append((priority, move))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored]

    # ---- 终局检测 ----

    @staticmethod
    def _is_terminal(board):
        """检测是否有五连（用于剪枝）"""
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                p = board[r][c]
                if p == 0:
                    continue
                for dr, dc in DIRECTIONS:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and \
                          board[nr][nc] == p:
                        count += 1; nr += dr; nc += dc
                    if count >= 5:
                        return p
        return 0

    # ---- Alpha-Beta 搜索 ----

    def _alpha_beta(self, board, depth, alpha, beta, maximizing, ai_player, human_player):
        """
        Minimax with Alpha-Beta pruning.
        maximizing=True 表示 AI 方走棋。
        """
        self.nodes_searched += 1

        # 终局检测
        winner = self._is_terminal(board)
        if winner == ai_player:
            return 1000000 + depth  # 越早赢越好
        if winner == human_player:
            return -1000000 - depth
        if depth == 0:
            return self.evaluate_board(board, ai_player, human_player)

        candidates = self.get_candidates(board, radius=1)
        if not candidates:
            return 0  # 平局

        current_player = ai_player if maximizing else human_player

        if maximizing:
            moves = self._order_moves(board, candidates, current_player, depth)
            best = -float('inf')
            for move in moves:
                r, c = move
                board[r][c] = current_player
                val = self._alpha_beta(board, depth - 1, alpha, beta, False,
                                       ai_player, human_player)
                board[r][c] = 0
                if val > best:
                    best = val
                alpha = max(alpha, val)
                if alpha >= beta:
                    # 更新 killer moves
                    if depth not in self.killer_moves:
                        self.killer_moves[depth] = []
                    if move not in self.killer_moves[depth]:
                        self.killer_moves[depth].insert(0, move)
                        if len(self.killer_moves[depth]) > 3:
                            self.killer_moves[depth].pop()
                    break
            return best
        else:
            moves = self._order_moves(board, candidates, current_player, depth)
            best = float('inf')
            for move in moves:
                r, c = move
                board[r][c] = current_player
                val = self._alpha_beta(board, depth - 1, alpha, beta, True,
                                       ai_player, human_player)
                board[r][c] = 0
                if val < best:
                    best = val
                beta = min(beta, val)
                if alpha >= beta:
                    if depth not in self.killer_moves:
                        self.killer_moves[depth] = []
                    if move not in self.killer_moves[depth]:
                        self.killer_moves[depth].insert(0, move)
                        if len(self.killer_moves[depth]) > 3:
                            self.killer_moves[depth].pop()
                    break
            return best

    # ---- 公开接口 ----

    def find_best_move(self, board, ai_player, depth):
        """返回最佳落子坐标 (row, col)"""
        self.nodes_searched = 0
        human_player = 3 - ai_player

        candidates = self.get_candidates(board, radius=2)

        if not candidates:
            return (BOARD_SIZE // 2, BOARD_SIZE // 2)

        # 第一步下天元
        if len([1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)
                if board[r][c] != 0]) == 0:
            return (BOARD_SIZE // 2, BOARD_SIZE // 2)

        best_move = candidates[0]
        best_score = -float('inf')

        moves = self._order_moves(board, candidates, ai_player, depth)

        for move in moves:
            r, c = move
            board[r][c] = ai_player
            score = self._alpha_beta(board, depth - 1, -float('inf'), float('inf'),
                                     False, ai_player, human_player)
            board[r][c] = 0

            if score > best_score:
                best_score = score
                best_move = move

        return best_move


# ============================================================
# AI 工作线程
# ============================================================

class AIWorker:
    """在独立线程中运行 AI 搜索，避免阻塞 UI"""

    def __init__(self):
        self.engine   = AIEngine()
        self._running = False
        self._result  = None
        self._thread  = None

    @property
    def is_running(self):
        return self._running

    @property
    def result(self):
        return self._result

    def start(self, board, ai_player, depth):
        """启动 AI 计算线程"""
        if self._running:
            return
        self._running = True
        self._result  = None
        # 深拷贝棋盘，避免线程间数据竞争
        board_copy = [row[:] for row in board]
        self._thread = threading.Thread(
            target=self._compute,
            args=(board_copy, ai_player, depth),
            daemon=True
        )
        self._thread.start()

    def _compute(self, board, ai_player, depth):
        self._result = self.engine.find_best_move(board, ai_player, depth)
        self._running = False

    def reset(self):
        self._running = False
        self._result  = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.1)


# ============================================================
# 游戏主类
# ============================================================

class GomokuGame:
    """五子棋游戏主类"""

    def __init__(self, sound_engine):
        self.sound = sound_engine

        # 棋盘状态
        self.board          = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.current_player = 1
        self.game_over      = False
        self.winner         = 0
        self.is_draw        = False
        self.win_line       = []
        self.move_history   = []
        self.last_move      = None

        # UI
        self.panel_buttons   = []
        self.toast_message   = ""
        self.toast_timer     = 0
        self.selecting_color = True
        self.player_color    = 1
        self._selection_buttons = []

        # 模式
        self.ai_mode       = False
        self.ai_difficulty = AI_MEDIUM
        self.ai_thinking   = False
        self.ai_move_timer = 0
        self.ai_worker     = AIWorker()

        # 动画
        self.victory_frame   = 0
        self._victory_sparks = []

        # ---- 新增功能 ----
        # 音效
        self.sound_enabled = True

        # 回放模式
        self.replay_mode     = False
        self.replay_index    = 0
        self.replay_board    = None
        self.replay_last     = None

        # 会话统计
        self.stats = {"wins": 0, "losses": 0, "draws": 0, "total": 0}

        # 开局库索引
        self._opening = None
        self._opening_step = 0

    # ================================================================
    #  游戏逻辑
    # ================================================================

    def reset(self):
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
        self.replay_mode    = False
        self.replay_index   = 0
        self.replay_board   = None
        self.replay_last    = None
        self._opening       = None
        self._opening_step  = 0
        self.ai_worker.reset()
        self.selecting_color = True

    def undo(self):
        """悔棋：人机模式连撤两步，双人模式撤销一步"""
        if self.replay_mode:
            self._exit_replay()
            return True

        if not self.move_history:
            self.toast_message = "没有棋子可以悔棋"
            self.toast_timer   = 90
            return False

        # 取消 AI 思考
        self.ai_thinking   = False
        self.ai_move_timer = 0
        self.ai_worker.reset()

        # 清除游戏结束状态（先保存用于回退统计）
        was_game_over = self.game_over
        was_draw      = self.is_draw
        was_winner    = self.winner
        if self.game_over:
            self.game_over    = False
            self.winner       = 0
            self.is_draw      = False
            self.win_line.clear()
            self.victory_frame = 0
            self._victory_sparks.clear()
            # 撤销战绩统计
            if self.stats["total"] > 0:
                self.stats["total"] -= 1
                if was_draw:
                    self.stats["draws"] = max(0, self.stats["draws"] - 1)
                elif was_winner == self.player_color:
                    self.stats["wins"] = max(0, self.stats["wins"] - 1)
                else:
                    self.stats["losses"] = max(0, self.stats["losses"] - 1)

        undo_count = 0

        if self.ai_mode:
            # 人机模式：撤销末尾一手
            row, col, player = self.move_history.pop()
            self.board[row][col] = 0
            undo_count += 1
            # 如果撤销的是 AI 的棋，继续撤销玩家的棋
            if player == self.ai_color and self.move_history:
                r2, c2, _ = self.move_history.pop()
                self.board[r2][c2] = 0
                undo_count += 1
            self.current_player = self.player_color
            if self.move_history:
                self.last_move = (self.move_history[-1][0],
                                  self.move_history[-1][1])
            else:
                self.last_move = None
            if was_game_over:
                self.toast_message = f"已撤销 {undo_count} 手，请重新落子"
            elif undo_count >= 2:
                self.toast_message = "已撤回你与AI的棋子"
            else:
                self.toast_message = "已撤回棋子"
        else:
            # 双人模式：撤销一步
            row, col, player = self.move_history.pop()
            self.board[row][col] = 0
            self.current_player = player
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
        self.sound.play("undo")
        return True

    def place_piece(self, row, col):
        if self.game_over or self.board[row][col] != 0:
            return False

        self.board[row][col] = self.current_player
        self.move_history.append((row, col, self.current_player))
        self.last_move = (row, col)

        if self._check_win(row, col):
            self.game_over = True
            self.winner = self.current_player
            self.victory_frame = 0
            self._init_victory_sparks()
            self._update_stats()
            self.sound.play("win")
        elif len(self.move_history) >= BOARD_SIZE * BOARD_SIZE:
            self.game_over = True
            self.is_draw = True
            self.victory_frame = 0
            self._init_draw_sparks()
            self._update_stats()
            self.sound.play("draw")
        else:
            self.current_player = 3 - self.current_player
            self.sound.play("place")

        return True

    def _check_win(self, row, col):
        player = self.board[row][col]
        for dr, dc in DIRECTIONS:
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

    def _update_stats(self):
        self.stats["total"] += 1
        if self.is_draw:
            self.stats["draws"] += 1
        elif self.winner == self.player_color:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1

    @property
    def ai_color(self):
        return 3 - self.player_color

    def toggle_mode(self):
        self.reset()
        self.ai_mode = not self.ai_mode
        mode_name = "人机对战" if self.ai_mode else "双人对战"
        self.toast_message = f"已切换为「{mode_name}」模式"
        self.toast_timer = 90
        self.sound.play("click")

    # ================================================================
    #  回放功能
    # ================================================================

    def enter_replay(self):
        """进入回放模式"""
        if len(self.move_history) < 1:
            self.toast_message = "暂无棋谱可回放"
            self.toast_timer = 90
            return
        self.replay_mode  = True
        self.replay_index = 0
        self.replay_board = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.replay_last  = None
        self.toast_message = "回放模式：点击面板按钮逐步查看"
        self.toast_timer = 150

    def _exit_replay(self):
        self.replay_mode  = False
        self.replay_index = 0
        self.replay_board = None
        self.replay_last  = None
        self.toast_message = "已退出回放模式"
        self.toast_timer  = 90

    def replay_step_forward(self):
        """回放前进一步"""
        if not self.replay_mode:
            return
        if self.replay_index < len(self.move_history):
            r, c, p = self.move_history[self.replay_index]
            self.replay_board[r][c] = p
            self.replay_last = (r, c)
            self.replay_index += 1
            self.toast_message = f"回放第 {self.replay_index}/{len(self.move_history)} 手"
            self.toast_timer = 120
        else:
            self.toast_message = "已是最后一步"
            self.toast_timer = 90

    def replay_step_back(self):
        """回放后退一步"""
        if not self.replay_mode:
            return
        if self.replay_index > 0:
            self.replay_index -= 1
            r, c, p = self.move_history[self.replay_index]
            self.replay_board[r][c] = 0
            self.replay_last = (self.move_history[self.replay_index - 1][0],
                                self.move_history[self.replay_index - 1][1]) \
                                if self.replay_index > 0 else None
            self.toast_message = f"回放第 {self.replay_index}/{len(self.move_history)} 手"
            self.toast_timer = 120
        else:
            self.toast_message = "已是第一步"
            self.toast_timer = 90

    # ================================================================
    #  开局库
    # ================================================================

    def get_opening_move(self):
        """获取开局库下一步"""
        if self._opening is None:
            # 随机选择一个开局
            self._opening = random.choice(OPENING_BOOK)
            self._opening_step = 0
        if self._opening_step < len(self._opening):
            move = self._opening[self._opening_step]
            self._opening_step += 1
            return move
        return None

    # ================================================================
    #  胜利粒子
    # ================================================================

    def _init_victory_sparks(self):
        self._victory_sparks = []
        cx, cy = WIN_WIDTH // 2, WIN_HEIGHT // 2 - 20
        for _ in range(40):
            life = random.randint(25, 70)
            self._victory_sparks.append({
                'angle': random.uniform(0, 2 * math.pi),
                'speed': random.uniform(1.5, 5.0),
                'distance': 0,
                'max_dist': random.uniform(60, 220),
                'life': life,
                'max_life': life,
                'size': random.randint(2, 5),
                'hue': random.choice([
                    (255, 215, 0), (255, 180, 40), (255, 240, 150),
                    (255, 160, 60), (255, 255, 200),
                ]),
                'cx': cx, 'cy': cy,
            })

    def _init_draw_sparks(self):
        self._victory_sparks = []
        cx, cy = WIN_WIDTH // 2, WIN_HEIGHT // 2 - 20
        for _ in range(35):
            life = random.randint(20, 55)
            self._victory_sparks.append({
                'angle': random.uniform(0, 2 * math.pi),
                'speed': random.uniform(1.0, 3.5),
                'distance': 0,
                'max_dist': random.uniform(50, 180),
                'life': life,
                'max_life': life,
                'size': random.randint(2, 4),
                'hue': random.choice([
                    (160, 180, 200), (140, 155, 175), (180, 190, 210),
                    (200, 200, 210), (150, 140, 160),
                ]),
                'cx': cx, 'cy': cy,
            })

    # ================================================================
    #  更新
    # ================================================================

    def update(self):
        if self.toast_timer > 0:
            self.toast_timer -= 1
        if self.game_over:
            self.victory_frame += 1

        # AI 线程结果回收
        if self.ai_mode and not self.game_over and self.current_player == self.ai_color:
            if self.ai_worker.is_running:
                # 显示思考动画
                self.ai_thinking = True
            elif self.ai_thinking and not self.ai_worker.is_running:
                # AI 计算完成
                self.ai_thinking = False
                move = self.ai_worker.result
                if move is not None:
                    self.place_piece(*move)

        # 触发 AI 思考
        if (self.ai_mode and not self.game_over
                and self.current_player == self.ai_color
                and not self.ai_worker.is_running
                and not self.ai_thinking):
            # 小延迟再启动
            if self.ai_move_timer > 0:
                self.ai_move_timer -= 1
            else:
                self._trigger_ai()

    def _trigger_ai(self):
        """启动 AI 计算线程"""
        # 开局库优先
        opening = self.get_opening_move()
        if opening is not None and self.board[opening[0]][opening[1]] == 0:
            self.ai_thinking = True
            self.ai_worker._result = opening
            self.ai_worker._running = False
            self.ai_move_timer = 8
            return

        depth = AI_DEPTH[self.ai_difficulty]
        self.ai_worker.start(self.board, self.ai_color, depth)
        self.ai_thinking = True

    # ================================================================
    #  绘制 — 主入口
    # ================================================================

    def draw(self, screen):
        mx, my = pygame.mouse.get_pos()

        # 回放模式用回放棋盘
        display_board = self.replay_board if self.replay_mode else self.board
        display_last  = self.replay_last  if self.replay_mode else self.last_move

        self._draw_background(screen)
        self._draw_grid(screen)
        self._draw_star_points(screen)
        self._draw_coordinate_labels(screen)

        # 绘制棋子
        if self.replay_mode:
            self._draw_pieces_on(screen, display_board, display_last)
        else:
            self._draw_pieces(screen)

        self._draw_panel(screen, mx, my)
        self._draw_toast(screen)

        if self.game_over and not self.replay_mode:
            self._draw_result_overlay(screen)
            self._draw_win_highlight(screen)

        if self.selecting_color and not self.replay_mode:
            self._draw_color_selection(screen, mx, my)

    # ================================================================
    #  绘制 — 背景与棋盘
    # ================================================================

    def _draw_background(self, screen):
        screen.fill(COLOR_BG)

    def _draw_grid(self, screen):
        # 阴影
        shadow_rect = pygame.Rect(BOARD_OFFSET_X + 2, BOARD_OFFSET_Y + 3,
                                   BOARD_AREA_W, BOARD_AREA_H)
        pygame.draw.rect(screen, (30, 22, 15), shadow_rect, border_radius=8)
        # 底板外缘
        board_outer = pygame.Rect(BOARD_OFFSET_X - 1, BOARD_OFFSET_Y - 1,
                                   BOARD_AREA_W + 2, BOARD_AREA_H + 2)
        pygame.draw.rect(screen, COLOR_BOARD_FRAME_BOT, board_outer, border_radius=7)
        # 底板主体
        board_inner = pygame.Rect(BOARD_OFFSET_X, BOARD_OFFSET_Y,
                                   BOARD_AREA_W, BOARD_AREA_H)
        pygame.draw.rect(screen, COLOR_BOARD_FILL, board_inner, border_radius=6)
        # 外边框
        frame_outer = pygame.Rect(BOARD_OFFSET_X, BOARD_OFFSET_Y,
                                   BOARD_AREA_W, BOARD_AREA_H)
        pygame.draw.rect(screen, COLOR_BOARD_FRAME, frame_outer, width=2, border_radius=6)
        # 内边框高光线
        for i in range(2):
            fi_rect = pygame.Rect(
                BOARD_OFFSET_X + FRAME_THICKNESS - 5 + i,
                BOARD_OFFSET_Y + FRAME_THICKNESS - 5 + i,
                BOARD_GRID_PX + 10 - 2 * i,
                BOARD_GRID_PX + 10 - 2 * i
            )
            color = COLOR_BOARD_FRAME_TOP if i == 0 else (160, 115, 65)
            pygame.draw.rect(screen, color, fi_rect, width=1)
        # 网格线
        grid_left = BOARD_OFFSET_X + FRAME_THICKNESS
        grid_top  = BOARD_OFFSET_Y + FRAME_THICKNESS
        for i in range(BOARD_SIZE):
            line_pos = i * CELL_SIZE
            pygame.draw.line(screen, COLOR_LINE,
                             (grid_left, grid_top + line_pos),
                             (grid_left + BOARD_GRID_PX, grid_top + line_pos), 1)
            pygame.draw.line(screen, COLOR_LINE,
                             (grid_left + line_pos, grid_top),
                             (grid_left + line_pos, grid_top + BOARD_GRID_PX), 1)

    def _draw_star_points(self, screen):
        for row, col in [(3,3),(3,7),(3,11),(7,3),(7,7),(7,11),(11,3),(11,7),(11,11)]:
            cx, cy = board_to_screen(row, col)
            pygame.draw.circle(screen, COLOR_STAR, (cx, cy), 5)
            pygame.draw.circle(screen, (78, 62, 45), (cx, cy), 3)

    def _draw_coordinate_labels(self, screen):
        global FONT_LABEL
        grid_left = BOARD_OFFSET_X + FRAME_THICKNESS
        grid_top  = BOARD_OFFSET_Y + FRAME_THICKNESS
        for i in range(BOARD_SIZE):
            letter = FONT_LABEL.render(chr(ord('A') + i), True, COLOR_LABEL)
            lx = grid_left + i * CELL_SIZE - letter.get_width() // 2
            screen.blit(letter, (lx, BOARD_OFFSET_Y + 5))
            num = FONT_LABEL.render(str(i + 1), True, COLOR_LABEL)
            lx = BOARD_OFFSET_X + FRAME_THICKNESS - num.get_width() - 12
            screen.blit(num, (lx, grid_top + i * CELL_SIZE - num.get_height() // 2))

    # ================================================================
    #  绘制 — 棋子
    # ================================================================

    def _draw_pieces(self, screen):
        self._draw_pieces_on(screen, self.board, self.last_move)

    def _draw_pieces_on(self, screen, board, last_move):
        piece_r = CELL_SIZE // 2 - 2
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                player = board[row][col]
                if player == 0:
                    continue
                cx, cy = board_to_screen(row, col)
                if player == 1:
                    pygame.draw.circle(screen, (6, 6, 6), (cx + 2, cy + 3), piece_r)
                    pygame.draw.circle(screen, PC_BLACK_OUTER, (cx, cy), piece_r)
                    pygame.draw.circle(screen, PC_BLACK_MID, (cx, cy), piece_r - 1)
                    pygame.draw.circle(screen, PC_BLACK_INNER, (cx, cy), piece_r - 4)
                    hl_x, hl_y = cx - piece_r // 3, cy - piece_r // 3
                    pygame.draw.circle(screen, PC_BLACK_HL, (hl_x, hl_y), piece_r // 3)
                else:
                    pygame.draw.circle(screen, PC_WHITE_SHADOW, (cx + 2, cy + 3), piece_r)
                    pygame.draw.circle(screen, PC_WHITE_OUTLINE, (cx, cy), piece_r)
                    pygame.draw.circle(screen, PC_WHITE_OUTER, (cx, cy), piece_r - 1)
                    pygame.draw.circle(screen, PC_WHITE_MID, (cx, cy), piece_r - 3)
                    pygame.draw.circle(screen, PC_WHITE_INNER, (cx, cy), piece_r - 5)
                    hl_x, hl_y = cx - piece_r // 3, cy - piece_r // 3
                    pygame.draw.circle(screen, PC_WHITE_HL, (hl_x, hl_y), piece_r // 4)

        # 末子标记
        if last_move is not None:
            lr, lc = last_move
            lx, ly = board_to_screen(lr, lc)
            mark_color = REPLAY_HIGHLIGHT if self.replay_mode else (255, 80, 60)
            pygame.draw.circle(screen, mark_color, (lx, ly), 7, 1)
            pygame.draw.circle(screen, (215, 40, 35), (lx, ly), 4)

    # ================================================================
    #  绘制 — 控制面板
    # ================================================================

    def _draw_panel(self, screen, mx, my):
        global FONT_PANEL_TITLE, FONT_PANEL_TEXT, FONT_TURN_LARGE, FONT_STAT_NUM
        px, pw = PANEL_X, PANEL_WIDTH
        cx = px + pw // 2
        self.panel_buttons = []

        # 面板背景
        panel_rect = pygame.Rect(px, BOARD_OFFSET_Y, pw, BOARD_AREA_H)
        shadow_rect = panel_rect.copy(); shadow_rect.x += 2; shadow_rect.y += 2
        pygame.draw.rect(screen, (40, 30, 20), shadow_rect, border_radius=12)
        pygame.draw.rect(screen, COLOR_PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, panel_rect, width=1, border_radius=10)

        # 装饰条
        bar_rect = pygame.Rect(px, BOARD_OFFSET_Y, pw, 44)
        pygame.draw.rect(screen, COLOR_PANEL_ACCENT, bar_rect,
                         border_top_left_radius=10, border_top_right_radius=10)
        title = FONT_PANEL_TITLE.render("控制面板", True, (95, 60, 28))
        screen.blit(title, (cx - title.get_width() // 2, BOARD_OFFSET_Y + 10))

        sep_y0 = BOARD_OFFSET_Y + 45
        pygame.draw.line(screen, (185, 155, 115), (px + 15, sep_y0), (px + pw - 15, sep_y0), 1)

        # ---- 模式切换（带图标） ----
        mode_y = sep_y0 + 18
        seg_w, seg_h = (pw - 30) // 2, 44
        seg_bg = pygame.Rect(px + 15, mode_y, pw - 30, seg_h)
        pygame.draw.rect(screen, (210, 195, 170), seg_bg, border_radius=10)
        pygame.draw.rect(screen, (185, 165, 138), seg_bg, width=1, border_radius=10)

        # 左分段：双人对战（带双人图标）
        seg_left_rect = pygame.Rect(px + 17, mode_y + 3, seg_w - 4, seg_h - 6)
        seg_left_hover = seg_left_rect.collidepoint(mx, my)
        self.panel_buttons.append((seg_left_rect, "mode_dual"))
        is_dual = not self.ai_mode
        if is_dual:
            pygame.draw.rect(screen, (255, 252, 246), seg_left_rect, border_radius=8)
            pygame.draw.rect(screen, (190, 160, 115), seg_left_rect, width=1, border_radius=8)
        elif seg_left_hover:
            pygame.draw.rect(screen, (235, 222, 200), seg_left_rect, border_radius=8)
        # 双人图标
        icon_left_x = seg_left_rect.left + 8
        icon_cy = seg_left_rect.centery
        left_color = (100, 135, 180) if is_dual else (155, 145, 125)
        hl_c = (255, 255, 255) if is_dual else (235, 225, 210)
        for ox in (-5, 5):
            pygame.draw.circle(screen, left_color,
                               (icon_left_x + 7 + ox, icon_cy - 6), 7)
            pygame.draw.circle(screen, hl_c,
                               (icon_left_x + 7 + ox, icon_cy - 9), 2)
        # 双人文字
        text_left_x = icon_left_x + 22
        dual_text = FONT_PANEL_TEXT.render("双人对战", True,
                         (40, 95, 150) if is_dual else (125, 108, 88))
        tx = min(text_left_x, seg_left_rect.right - dual_text.get_width() - 4)
        screen.blit(dual_text, (tx, seg_left_rect.centery - dual_text.get_height() // 2))

        # 右分段：人机对战（带机器人图标）
        seg_right_rect = pygame.Rect(px + 15 + seg_w, mode_y + 3, seg_w - 4, seg_h - 6)
        seg_right_hover = seg_right_rect.collidepoint(mx, my)
        self.panel_buttons.append((seg_right_rect, "mode_ai"))
        if self.ai_mode:
            pygame.draw.rect(screen, (255, 252, 246), seg_right_rect, border_radius=8)
            pygame.draw.rect(screen, (190, 160, 115), seg_right_rect, width=1, border_radius=8)
        elif seg_right_hover:
            pygame.draw.rect(screen, (235, 222, 200), seg_right_rect, border_radius=8)
        # 机器人图标
        icon_left_x2 = seg_right_rect.left + 8
        ai_color = (85, 125, 165) if self.ai_mode else (155, 145, 125)
        face_fill = (248, 246, 240) if self.ai_mode else (235, 225, 210)
        ai_rect = pygame.Rect(icon_left_x2 + 4, icon_cy - 9, 16, 16)
        pygame.draw.rect(screen, ai_color, ai_rect, border_radius=4)
        pygame.draw.rect(screen, face_fill, (icon_left_x2 + 6, icon_cy - 7, 12, 12), border_radius=3)
        for ex in (-3, 3):
            pygame.draw.circle(screen, ai_color, (icon_left_x2 + 12 + ex, icon_cy - 2), 2)
        pygame.draw.line(screen, ai_color, (icon_left_x2 + 10, icon_cy - 9),
                         (icon_left_x2 + 8, icon_cy - 16), 2)
        pygame.draw.circle(screen, ai_color, (icon_left_x2 + 8, icon_cy - 16), 2)
        # 人机文字
        text_left_x2 = icon_left_x2 + 22
        ai_text = FONT_PANEL_TEXT.render("人机对战", True,
                        (160, 110, 40) if self.ai_mode else (125, 108, 88))
        tx2 = min(text_left_x2, seg_right_rect.right - ai_text.get_width() - 4)
        screen.blit(ai_text, (tx2, seg_right_rect.centery - ai_text.get_height() // 2))

        mode_title = FONT_PANEL_TEXT.render("对战模式", True, (125, 105, 72))
        screen.blit(mode_title, (px + 20, mode_y - 20))

        # ---- AI 难度（人机模式） ----
        diff_offset = 0
        if self.ai_mode:
            diff_label_y = mode_y + 52; diff_bar_y = diff_label_y + 18
            diff_bar_h = 36; diff_offset = 54
            diff_label = FONT_PANEL_TEXT.render("AI 难度", True, (125, 105, 72))
            screen.blit(diff_label, (px + 20, diff_label_y))
            seg_bg2 = pygame.Rect(px + 15, diff_bar_y, pw - 30, diff_bar_h)
            pygame.draw.rect(screen, (210, 195, 170), seg_bg2, border_radius=9)
            pygame.draw.rect(screen, (185, 165, 138), seg_bg2, width=1, border_radius=9)
            diff_w = (pw - 36) // 3
            diff_colors = [(100, 155, 100), (200, 150, 50), (170, 60, 60)]
            for idx, (d_val, d_name) in enumerate([(AI_EASY, "简单"), (AI_MEDIUM, "中等"), (AI_HARD, "困难")]):
                dr_rect = pygame.Rect(px + 18 + idx * diff_w, diff_bar_y + 3,
                                       diff_w - 3, diff_bar_h - 6)
                dr_hover = dr_rect.collidepoint(mx, my)
                self.panel_buttons.append((dr_rect, f"diff_{d_val}"))
                is_active = (self.ai_difficulty == d_val)
                if is_active:
                    pygame.draw.rect(screen, (255, 252, 246), dr_rect, border_radius=7)
                    pygame.draw.rect(screen, diff_colors[idx], dr_rect, width=2, border_radius=7)
                    text_color = diff_colors[idx]
                elif dr_hover:
                    pygame.draw.rect(screen, (235, 222, 200), dr_rect, border_radius=7)
                    text_color = tuple(max(0, c - 30) for c in diff_colors[idx])
                else:
                    text_color = (125, 108, 88)
                d_text = FONT_PANEL_TEXT.render(d_name, True, text_color)
                screen.blit(d_text, (dr_rect.centerx - d_text.get_width() // 2,
                                      dr_rect.centery - d_text.get_height() // 2))

        # ---- 当前回合 ----
        turn_y = mode_y + 68 + diff_offset
        turn_card = pygame.Rect(px + 12, turn_y - 4, pw - 24, 100)
        pygame.draw.rect(screen, (252, 247, 236), turn_card, border_radius=8)
        pygame.draw.rect(screen, (215, 198, 168), turn_card, width=1, border_radius=8)

        if self.replay_mode:
            tag_text, tag_color = "棋谱回放中", (180, 130, 40)
        elif self.game_over:
            if self.is_draw:
                tag_text, tag_color = "握手言和", (120, 125, 140)
            else:
                tag_text, tag_color = "游戏结束", (190, 55, 55)
        elif self.ai_thinking:
            tag_text = f"AI 思考中…（{'黑棋' if self.ai_color == 1 else '白棋'}）"
            tag_color = (105, 135, 185)
        else:
            tag_text, tag_color = "当前回合", (125, 105, 72)
        tag = FONT_PANEL_TEXT.render(tag_text, True, tag_color)
        screen.blit(tag, (cx - tag.get_width() // 2, turn_y + 4))

        piece_cx, piece_cy = cx, turn_y + 42
        display_player = self.winner if self.game_over else self.current_player
        self._draw_turn_piece(screen, piece_cx, piece_cy, display_player, turn_y)

        turn_label = FONT_TURN_LARGE.render(
            self._turn_text(), True, (75, 50, 25))
        screen.blit(turn_label, (cx - turn_label.get_width() // 2, turn_y + 70))

        # ---- 步数统计 ----
        stat_y = turn_y + 105
        stat_card = pygame.Rect(px + 12, stat_y - 2, pw - 24, 80)
        pygame.draw.rect(screen, (252, 247, 236), stat_card, border_radius=8)
        pygame.draw.rect(screen, (215, 198, 168), stat_card, width=1, border_radius=8)
        stat_title = FONT_PANEL_TEXT.render("步数统计", True, (125, 105, 72))
        screen.blit(stat_title, (cx - stat_title.get_width() // 2, stat_y + 4))

        total_moves = len(self.move_history)
        black_moves = sum(1 for _, _, p in self.move_history if p == 1)
        white_moves = sum(1 for _, _, p in self.move_history if p == 2)
        col_w = (pw - 24) // 3
        for idx, (icon_type, label, value, color) in enumerate([
            (None, "总步数", str(total_moves), (135, 110, 75)),
            ("black", "黑棋", str(black_moves), (55, 55, 55)),
            ("white", "白棋", str(white_moves), (170, 150, 120)),
        ]):
            col_cx = stat_card.left + col_w // 2 + idx * col_w
            num_surf = FONT_STAT_NUM.render(value, True, color)
            screen.blit(num_surf, (col_cx - num_surf.get_width() // 2, stat_y + 28))
            lbl_surf = FONT_LABEL.render(label, True, (140, 120, 95))
            if icon_type == "black":
                icon_cx = col_cx - lbl_surf.get_width() // 2 - 8
                icon_cy = stat_y + 56 + FONT_LABEL.get_height() // 2
                pygame.draw.circle(screen, (30, 30, 30), (icon_cx, icon_cy), 5)
                pygame.draw.circle(screen, (75, 75, 75), (icon_cx - 1, icon_cy - 2), 2)
                screen.blit(lbl_surf, (icon_cx + 7, stat_y + 56))
            elif icon_type == "white":
                icon_cx = col_cx - lbl_surf.get_width() // 2 - 8
                icon_cy = stat_y + 56 + FONT_LABEL.get_height() // 2
                pygame.draw.circle(screen, (210, 205, 200), (icon_cx, icon_cy), 5)
                pygame.draw.circle(screen, (155, 150, 145), (icon_cx, icon_cy), 5, 1)
                screen.blit(lbl_surf, (icon_cx + 7, stat_y + 56))
            else:
                screen.blit(lbl_surf, (col_cx - lbl_surf.get_width() // 2, stat_y + 56))

        # ---- 胜率统计 ----
        stats_y = stat_y + 82
        stats_card = pygame.Rect(px + 12, stats_y - 2, pw - 24, 65)
        pygame.draw.rect(screen, (252, 247, 236), stats_card, border_radius=8)
        pygame.draw.rect(screen, (215, 198, 168), stats_card, width=1, border_radius=8)
        stats_title = FONT_PANEL_TEXT.render("本局战绩", True, (125, 105, 72))
        screen.blit(stats_title, (cx - stats_title.get_width() // 2, stats_y + 2))
        w, l, d, t = self.stats["wins"], self.stats["losses"], self.stats["draws"], self.stats["total"]
        win_rate = f"{w / t * 100:.0f}%" if t > 0 else "-"
        stats_line = f"胜 {w}  |  负 {l}  |  平 {d}  |  胜率 {win_rate}"
        stats_surf = FONT_LABEL.render(stats_line, True, (100, 85, 65))
        screen.blit(stats_surf, (cx - stats_surf.get_width() // 2, stats_y + 26))
        if t > 0:
            bar_w = pw - 40; bar_h = 6; bar_x = px + 20; bar_y = stats_y + 46
            pygame.draw.rect(screen, (200, 185, 160), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            win_bar = int(bar_w * w / t) if t > 0 else 0
            draw_bar = int(bar_w * d / t) if t > 0 else 0
            if win_bar > 0:
                pygame.draw.rect(screen, (90, 160, 90), (bar_x, bar_y, win_bar, bar_h),
                                 border_radius=3)
            if draw_bar > 0:
                pygame.draw.rect(screen, (160, 155, 145),
                                 (bar_x + win_bar, bar_y, draw_bar, bar_h), border_radius=3)

        # ---- 按钮 ----
        btn_y  = stats_y + 70
        btn_w  = pw - 40; btn_h = 38; btn_gap = 8

        if self.replay_mode:
            button_defs = [
                ("上一步", (95, 132, 100), "replay_back"),
                ("下一步", (95, 132, 100), "replay_fwd"),
                ("退出回放", (165, 70, 68), "replay_exit"),
            ]
        else:
            button_defs = [
                ("再来一局", (205, 95, 58), "restart"),
                ("悔棋", (95, 132, 100), "undo"),
                ("棋谱回放", (100, 125, 160), "replay"),
                ("退出游戏", (165, 70, 68), "quit"),
            ]

        for i, (text, base_color, action) in enumerate(button_defs):
            bx = px + 20; by = btn_y + i * (btn_h + btn_gap)
            btn_rect = pygame.Rect(bx, by, btn_w, btn_h)
            self.panel_buttons.append((btn_rect, action))
            is_hovered = btn_rect.collidepoint(mx, my)
            if is_hovered:
                # 悬浮：发光 + 放大
                hover_rect = btn_rect.inflate(4, 4)
                hover_rect.center = btn_rect.center
                glow_surf = pygame.Surface((hover_rect.width + 10, hover_rect.height + 10),
                                           pygame.SRCALPHA)
                glow_color = tuple(min(255, c + 70) for c in base_color) + (70,)
                pygame.draw.rect(glow_surf, glow_color,
                                 pygame.Rect(5, 5, hover_rect.width, hover_rect.height),
                                 border_radius=10)
                screen.blit(glow_surf, (hover_rect.x - 5, hover_rect.y - 5))
                hover_fill = tuple(min(255, c + 50) for c in base_color)
                pygame.draw.rect(screen, hover_fill, hover_rect, border_radius=10)
                hover_border = tuple(min(255, c + 90) for c in base_color)
                pygame.draw.rect(screen, hover_border, hover_rect, width=2, border_radius=10)
                use_rect = hover_rect
            else:
                shadow_rect2 = btn_rect.copy(); shadow_rect2.y += 3
                pygame.draw.rect(screen, (55, 40, 28), shadow_rect2, border_radius=9)
                pygame.draw.rect(screen, base_color, btn_rect, border_radius=9)
                hl_color = tuple(min(255, c + 55) for c in base_color)
                pygame.draw.rect(screen, hl_color, btn_rect, width=1, border_radius=9)
                sd_color = tuple(max(0, c - 55) for c in base_color)
                pygame.draw.line(screen, sd_color,
                                 (bx + 5, by + btn_h - 2),
                                 (bx + btn_w - 5, by + btn_h - 2), 3)
                use_rect = btn_rect
            btn_label = FONT_BTN.render(text, True, (255, 255, 255))
            screen.blit(btn_label, (use_rect.centerx - btn_label.get_width() // 2,
                                     use_rect.centery - btn_label.get_height() // 2))

        # 版本信息
        ver_y = BOARD_OFFSET_Y + BOARD_AREA_H - 24
        ver_label = FONT_PANEL_TEXT.render("五子棋 Plus  v3.0", True, (175, 155, 130))
        screen.blit(ver_label, (cx - ver_label.get_width() // 2, ver_y))

    def _draw_turn_piece(self, screen, cx, cy, player, turn_y):
        """绘制当前回合棋子图标"""
        if self.is_draw and self.game_over:
            for offset, p in [(-12, 1), (12, 2)]:
                px_cx = cx + offset
                if p == 1:
                    pygame.draw.circle(screen, (12, 12, 12), (px_cx + 1, cy + 1), 16)
                    pygame.draw.circle(screen, PC_BLACK_OUTER, (px_cx, cy), 16)
                    pygame.draw.circle(screen, PC_BLACK_MID, (px_cx, cy), 15)
                    pygame.draw.circle(screen, PC_BLACK_INNER, (px_cx, cy), 12)
                    pygame.draw.circle(screen, PC_BLACK_HL, (px_cx - 5, cy - 5), 5)
                else:
                    pygame.draw.circle(screen, PC_WHITE_SHADOW, (px_cx + 1, cy + 1), 16)
                    pygame.draw.circle(screen, PC_WHITE_OUTLINE, (px_cx, cy), 16)
                    pygame.draw.circle(screen, PC_WHITE_OUTER, (px_cx, cy), 15)
                    pygame.draw.circle(screen, PC_WHITE_MID, (px_cx, cy), 13)
                    pygame.draw.circle(screen, PC_WHITE_HL, (px_cx - 5, cy - 5), 4)
        elif self.ai_thinking and not self.game_over:
            ai_p = self.ai_color
            if ai_p == 1:
                pygame.draw.circle(screen, (12, 12, 12), (cx + 1, cy + 1), 18)
                pygame.draw.circle(screen, PC_BLACK_OUTER, (cx, cy), 18)
                pygame.draw.circle(screen, PC_BLACK_MID, (cx, cy), 17)
                pygame.draw.circle(screen, PC_BLACK_INNER, (cx, cy), 14)
                pygame.draw.circle(screen, PC_BLACK_HL, (cx - 6, cy - 6), 6)
            else:
                pygame.draw.circle(screen, PC_WHITE_SHADOW, (cx + 1, cy + 1), 18)
                pygame.draw.circle(screen, PC_WHITE_OUTLINE, (cx, cy), 18)
                pygame.draw.circle(screen, PC_WHITE_OUTER, (cx, cy), 17)
                pygame.draw.circle(screen, PC_WHITE_MID, (cx, cy), 15)
                pygame.draw.circle(screen, PC_WHITE_HL, (cx - 6, cy - 6), 5)
            # AI 思考脉冲环
            pulse_r = ((pygame.time.get_ticks() // 50) % 20) + 22
            pulse_alpha = max(20, 180 - (pygame.time.get_ticks() // 10) % 200)
            pulse_surf = pygame.Surface((pulse_r * 2 + 4, pulse_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(pulse_surf, (100, 135, 185, pulse_alpha),
                               (pulse_r + 2, pulse_r + 2), pulse_r, 2)
            screen.blit(pulse_surf, (cx - pulse_r - 2, cy - pulse_r - 2))
        elif player == 1:
            pygame.draw.circle(screen, (12, 12, 12), (cx + 1, cy + 1), 18)
            pygame.draw.circle(screen, PC_BLACK_OUTER, (cx, cy), 18)
            pygame.draw.circle(screen, PC_BLACK_MID, (cx, cy), 17)
            pygame.draw.circle(screen, PC_BLACK_INNER, (cx, cy), 14)
            pygame.draw.circle(screen, PC_BLACK_HL, (cx - 6, cy - 6), 6)
        else:
            pygame.draw.circle(screen, PC_WHITE_SHADOW, (cx + 1, cy + 1), 18)
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (cx, cy), 18)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (cx, cy), 17)
            pygame.draw.circle(screen, PC_WHITE_MID, (cx, cy), 15)
            pygame.draw.circle(screen, PC_WHITE_HL, (cx - 6, cy - 6), 5)

    def _turn_text(self):
        if self.replay_mode:
            return f"回放第{self.replay_index}/{len(self.move_history)}手"
        if self.game_over:
            return "对局结束"
        if self.ai_thinking:
            return f"AI 思考中..."
        if self.current_player == 1:
            return "你的回合（黑棋）" if self.ai_mode else "黑棋回合"
        return "你的回合（白棋）" if self.ai_mode else "白棋回合"

    # ================================================================
    #  绘制 — 提示消息
    # ================================================================

    def _draw_toast(self, screen):
        if self.toast_timer <= 0 or not self.toast_message:
            return
        total, fade_frames = 90, 20
        if self.toast_timer < fade_frames:
            alpha = int(255 * self.toast_timer / fade_frames)
        elif self.toast_timer > total - fade_frames:
            alpha = int(255 * (total - self.toast_timer) / fade_frames)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))
        text_surf = FONT_TOAST.render(self.toast_message, True, (255, 255, 255))
        pad_x, pad_y = 30, 14
        bubble_w = text_surf.get_width() + pad_x * 2
        bubble_h = text_surf.get_height() + pad_y * 2
        bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (50, 38, 25, 215), bubble.get_rect(), border_radius=12)
        pygame.draw.rect(bubble, (190, 155, 100, 190), bubble.get_rect(), width=1, border_radius=12)
        bubble.set_alpha(alpha); text_surf.set_alpha(alpha)
        bx, by = (WIN_WIDTH - bubble_w) // 2, WIN_HEIGHT - bubble_h - 32
        screen.blit(bubble, (bx, by))
        screen.blit(text_surf, (bx + pad_x, by + pad_y))

    # ================================================================
    #  绘制 — 先后手选择
    # ================================================================

    def _draw_color_selection(self, screen, mx, my):
        if not self.selecting_color:
            return
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 8, 5, 195))
        screen.blit(overlay, (0, 0))

        title_text = FONT_WINNER.render("选择先后手", True, (240, 210, 160))
        screen.blit(title_text, (WIN_WIDTH // 2 - title_text.get_width() // 2, 75))
        sub_text = FONT_TURN_LARGE.render("请选择你的执子颜色", True, (200, 175, 140))
        screen.blit(sub_text, (WIN_WIDTH // 2 - sub_text.get_width() // 2, 130))

        card_w, card_h, card_gap = 155, 215, 24
        total_w = card_w * 3 + card_gap * 2
        start_x = (WIN_WIDTH - total_w) // 2
        card_y = 185
        cards = [
            ("执黑先行", "先手优势", (35, 28, 22), (75, 75, 80), "black", "choose_black"),
            ("执白后手", "后手应对", (238, 230, 218), (195, 185, 168), "white", "choose_white"),
            ("随机分配", "公平对决", (48, 38, 25), (220, 180, 60), "random", "choose_random"),
        ]
        self._selection_buttons.clear()

        for i, (label, sub, color, accent, piece, action) in enumerate(cards):
            cx_card = start_x + i * (card_w + card_gap)
            card_rect = pygame.Rect(cx_card, card_y, card_w, card_h)
            is_hovered = card_rect.collidepoint(mx, my)
            self._selection_buttons.append((card_rect, action))

            sh = card_rect.copy(); sh.x += 3; sh.y += 5
            pygame.draw.rect(screen, (14, 10, 6), sh, border_radius=18)
            pygame.draw.rect(screen, color, card_rect, border_radius=16)
            bw = 3 if is_hovered else 1
            bc = (240, 195, 55) if is_hovered else accent
            pygame.draw.rect(screen, bc, card_rect, width=bw, border_radius=16)
            if is_hovered:
                hl = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 30))
                screen.blit(hl, (cx_card, card_y))

            icon_cx = cx_card + card_w // 2
            icon_cy = card_y + 55
            if piece == "black":
                pygame.draw.circle(screen, (14, 14, 14), (icon_cx + 2, icon_cy + 3), 30)
                pygame.draw.circle(screen, PC_BLACK_OUTER, (icon_cx, icon_cy), 30)
                pygame.draw.circle(screen, PC_BLACK_MID, (icon_cx, icon_cy), 28)
                pygame.draw.circle(screen, PC_BLACK_INNER, (icon_cx, icon_cy), 22)
                pygame.draw.circle(screen, PC_BLACK_HL, (icon_cx - 9, icon_cy - 9), 10)
            elif piece == "white":
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
                screen.blit(q_s, (icon_cx - q_s.get_width() // 2, icon_cy - q_s.get_height() // 2 - 2))

            if piece == "white":
                lc, sc = (65, 48, 28), (110, 85, 55)
            else:
                lc, sc = (240, 215, 175), (180, 155, 115)

            label_surf = FONT_TURN_LARGE.render(label, True, lc)
            screen.blit(label_surf, (cx_card + card_w // 2 - label_surf.get_width() // 2,
                                      card_y + 110))
            sub_surf = FONT_PANEL_TEXT.render(sub, True, sc)
            screen.blit(sub_surf, (cx_card + card_w // 2 - sub_surf.get_width() // 2,
                                    card_y + 142))

        hint = FONT_WINNER_HINT.render("选择后将开始对局", True, (160, 140, 110))
        screen.blit(hint, (WIN_WIDTH // 2 - hint.get_width() // 2, card_y + card_h + 28))

    # ================================================================
    #  绘制 — 胜利动画
    # ================================================================

    def _draw_result_overlay(self, screen):
        vf = self.victory_frame
        overlay_alpha = min(175, vf * 4)
        overlay = pygame.Surface((WIN_WIDTH, WIN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((18, 12, 8, overlay_alpha))
        screen.blit(overlay, (0, 0))

        card_w, card_h = 420, 190
        card_x = (WIN_WIDTH - card_w) // 2
        card_y = (WIN_HEIGHT - card_h) // 2 - 10
        slide_offset = max(0, 30 - vf * 1.5)
        card_y += int(slide_offset)

        card_alpha = min(235, vf * 6)
        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        if self.is_draw:
            pygame.draw.rect(card, (45, 42, 48, card_alpha), card.get_rect(), border_radius=18)
        elif self.winner == 1:
            pygame.draw.rect(card, (28, 24, 22, card_alpha), card.get_rect(), border_radius=18)
        else:
            pygame.draw.rect(card, (248, 242, 232, card_alpha), card.get_rect(), border_radius=18)

        border_alpha = min(200, vf * 4)
        pygame.draw.rect(card, (240, 195, 55, border_alpha),
                         card.get_rect(), width=2, border_radius=18)
        inner_rect = pygame.Rect(4, 4, card_w - 8, card_h - 8)
        pygame.draw.rect(card, (240, 195, 55, border_alpha // 2),
                         inner_rect, width=1, border_radius=15)
        screen.blit(card, (card_x, card_y))

        # 奖杯图标
        trophy_y, trophy_cx = card_y + 28, card_x + card_w // 2
        trophy_alpha = min(255, vf * 5)
        cup_w, cup_h = 26, 24
        cup_color = (240, 195, 55, trophy_alpha)
        if self.is_draw:
            draw_icon_surf = pygame.Surface((40, 28), pygame.SRCALPHA)
            pygame.draw.circle(draw_icon_surf, (50, 50, 55, trophy_alpha), (13, 14), 10)
            pygame.draw.circle(draw_icon_surf, (85, 85, 90, trophy_alpha), (12, 13), 3)
            pygame.draw.circle(draw_icon_surf, (235, 228, 215, trophy_alpha), (27, 14), 10)
            pygame.draw.circle(draw_icon_surf, (185, 178, 168, trophy_alpha), (27, 14), 10, 1)
            pygame.draw.circle(draw_icon_surf, (255, 255, 254, trophy_alpha), (26, 13), 3)
            screen.blit(draw_icon_surf, (trophy_cx - 20, trophy_y))
        else:
            cup_surf = pygame.Surface((cup_w + 4, cup_h + 4), pygame.SRCALPHA)
            pygame.draw.rect(cup_surf, cup_color,
                             pygame.Rect(2, 2, cup_w, cup_h), border_radius=4)
            for dx in (-6, cup_w + 2):
                pygame.draw.arc(cup_surf, cup_color, (dx, 4, 8, cup_h), 0, math.pi, 2)
            base_w = cup_w + 10
            pygame.draw.rect(cup_surf, cup_color,
                             pygame.Rect(cup_w // 2 - base_w // 2 + 2, 2 + cup_h - 4, base_w, 6),
                             border_radius=2)
            screen.blit(cup_surf, (trophy_cx - cup_w // 2 - 2, trophy_y - 2))

        # 文字（脉冲呼吸）
        pulse = 1.0 + 0.04 * math.sin(vf * 0.07)
        if self.is_draw:
            w_text, w_color, glow_color = "握手言和", (180, 190, 210), (140, 150, 175)
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
        base_glow = FONT_WINNER.render(w_text, True, glow_color)
        g_surf = pygame.transform.smoothscale(base_glow, (new_w, new_h))
        g_surf.set_alpha(min(100, text_alpha // 2))
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            screen.blit(g_surf, (WIN_WIDTH // 2 - g_surf.get_width() // 2 + dx,
                                  card_y + 58 + dy))
        screen.blit(w_surf, (WIN_WIDTH // 2 - w_surf.get_width() // 2, card_y + 58))

        # ---- 副提示文字 ----
        hint_text = "点击「再来一局」重新开局"
        if self.is_draw:
            hint_color = (185, 180, 195)
        else:
            hint_color = (220, 210, 190) if self.winner == 1 else (145, 105, 82)
        hint_surf = FONT_WINNER_HINT.render(hint_text, True, hint_color)
        hint_surf.set_alpha(min(200, vf * 4))
        screen.blit(hint_surf, (WIN_WIDTH // 2 - hint_surf.get_width() // 2, card_y + 115))

        # ---- 右下小棋子装饰 ----
        deco_r = 8
        deco_cx, deco_cy = card_x + card_w - 26, card_y + card_h - 18
        if self.is_draw:
            pygame.draw.circle(screen, PC_BLACK_OUTER, (deco_cx - 6, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_BLACK_MID, (deco_cx - 6, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_BLACK_HL, (deco_cx - 8, deco_cy - 2), 3)
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (deco_cx + 6, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (deco_cx + 6, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_WHITE_HL, (deco_cx + 5, deco_cy - 2), 2)
        elif self.winner == 1:
            pygame.draw.circle(screen, PC_BLACK_OUTER, (deco_cx, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_BLACK_MID, (deco_cx, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_BLACK_HL, (deco_cx - 2, deco_cy - 2), 3)
        else:
            pygame.draw.circle(screen, PC_WHITE_OUTLINE, (deco_cx, deco_cy), deco_r)
            pygame.draw.circle(screen, PC_WHITE_OUTER, (deco_cx, deco_cy), deco_r - 1)
            pygame.draw.circle(screen, PC_WHITE_HL, (deco_cx - 2, deco_cy - 2), 2)

        # 粒子
        if self._victory_sparks:
            for spark in self._victory_sparks:
                spark['distance'] += spark['speed']
                spark['life'] -= 1
                if spark['life'] <= 0:
                    continue
                dist = min(spark['distance'], spark['max_dist'])
                sx = spark['cx'] + math.cos(spark['angle']) * dist
                sy = spark['cy'] + math.sin(spark['angle']) * dist
                life_ratio = spark['life'] / spark['max_life']
                alpha = int(255 * life_ratio)
                size = max(1, int(spark['size'] * life_ratio))
                spark_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                pygame.draw.circle(spark_surf, spark['hue'] + (alpha,),
                                   (size * 2, size * 2), size)
                screen.blit(spark_surf, (int(sx) - size * 2, int(sy) - size * 2))

    # ================================================================
    #  绘制 — 胜利连子高亮
    # ================================================================

    def _draw_win_highlight(self, screen):
        if not (self.game_over and not self.is_draw and self.win_line):
            return
        vf = self.victory_frame
        piece_r = CELL_SIZE // 2 - 2
        for row, col in self.win_line:
            cx, cy = board_to_screen(row, col)
            glow_r = piece_r + 4
            glow_alpha = int(100 + 60 * math.sin(vf * 0.06 + row * 0.7))
            glow_surf = pygame.Surface((glow_r * 2 + 6, glow_r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 200, 50, max(30, glow_alpha // 2)),
                               (glow_r + 3, glow_r + 3), glow_r)
            screen.blit(glow_surf, (cx - glow_r - 3, cy - glow_r - 3))
            ring_r = piece_r + 1
            ring_alpha = int(140 + 80 * math.sin(vf * 0.07 + col * 0.7))
            ring_surf = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (255, 215, 0, max(60, ring_alpha)),
                               (ring_r + 2, ring_r + 2), ring_r, 2)
            screen.blit(ring_surf, (cx - ring_r - 2, cy - ring_r - 2))


# ============================================================
# 主函数
# ============================================================

def main():
    global FONT_LABEL, FONT_PANEL_TITLE, FONT_PANEL_TEXT, FONT_TURN_LARGE
    global FONT_BTN, FONT_TOAST, FONT_WINNER, FONT_WINNER_HINT, FONT_STAT_NUM, FONT_SMALL

    pygame.init()

    # 字体初始化
    FONT_LABEL       = pygame.font.SysFont("microsoftyahei", 13)
    FONT_PANEL_TITLE = pygame.font.SysFont("microsoftyahei", 22, bold=True)
    FONT_PANEL_TEXT  = pygame.font.SysFont("microsoftyahei", 16)
    FONT_TURN_LARGE  = pygame.font.SysFont("microsoftyahei", 18, bold=True)
    FONT_BTN         = pygame.font.SysFont("microsoftyahei", 17, bold=True)
    FONT_TOAST       = pygame.font.SysFont("microsoftyahei", 18, bold=True)
    FONT_WINNER      = pygame.font.SysFont("microsoftyahei", 46, bold=True)
    FONT_WINNER_HINT = pygame.font.SysFont("microsoftyahei", 14)
    FONT_STAT_NUM    = pygame.font.SysFont("microsoftyahei", 22, bold=True)
    FONT_SMALL       = pygame.font.SysFont("microsoftyahei", 11)

    # 音效引擎
    sound = SoundEngine()
    sound.play("start")

    screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
    pygame.display.set_caption("五子棋 Plus — Alpha-Beta AI")
    clock = pygame.time.Clock()

    game = GomokuGame(sound)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # 键盘快捷键
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_z and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    game.undo()
                elif event.key == pygame.K_r and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    game.reset()
                elif event.key == pygame.K_LEFT and game.replay_mode:
                    game.replay_step_back()
                elif event.key == pygame.K_RIGHT and game.replay_mode:
                    game.replay_step_forward()
                elif event.key == pygame.K_m:
                    enabled = sound.toggle()
                    game.toast_message = "音效已开启" if enabled else "音效已关闭"
                    game.toast_timer = 90
                continue

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = pygame.mouse.get_pos()

                # 先后手选择
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
                            sound.play("click")
                            if game.ai_mode and game.current_player == game.ai_color:
                                game.ai_move_timer = 15
                            break
                    continue

                # 控制面板按钮
                button_clicked = False
                for btn_rect, action in game.panel_buttons:
                    if btn_rect.collidepoint(mx, my):
                        if action == "restart":
                            game.reset()
                            sound.play("click")
                        elif action == "undo":
                            game.undo()
                        elif action == "quit":
                            running = False
                        elif action == "replay":
                            game.enter_replay()
                            sound.play("click")
                        elif action == "replay_fwd":
                            game.replay_step_forward()
                        elif action == "replay_back":
                            game.replay_step_back()
                        elif action == "replay_exit":
                            game._exit_replay()
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
                                game.toast_message = f"AI 难度已切换为「{AI_DIFF_NAMES[diff_val]}」"
                                game.toast_timer = 90
                                sound.play("click")
                        button_clicked = True
                        break

                # 棋盘落子
                if (not button_clicked and not game.game_over
                        and not game.ai_thinking and not game.replay_mode):
                    pos = screen_to_board(mx, my)
                    if pos is not None:
                        if game.place_piece(*pos):
                            if game.ai_mode and (not game.game_over) and \
                               game.current_player == game.ai_color:
                                game.ai_move_timer = random.randint(5, 15)

        # 更新
        game.update()

        # 绘制
        game.draw(screen)

        # 悬停预览
        if (not game.game_over and not game.ai_thinking
                and not game.selecting_color and not game.replay_mode):
            mx, my = pygame.mouse.get_pos()
            pos = screen_to_board(mx, my)
            if pos is not None and game.board[pos[0]][pos[1]] == 0:
                cx, cy = board_to_screen(*pos)
                hint_surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                if game.current_player == 1:
                    pygame.draw.circle(hint_surf, (20, 20, 20, 55),
                                       (CELL_SIZE // 2, CELL_SIZE // 2),
                                       CELL_SIZE // 2 - 3)
                else:
                    pygame.draw.circle(hint_surf, (210, 208, 200, 70),
                                       (CELL_SIZE // 2, CELL_SIZE // 2),
                                       CELL_SIZE // 2 - 3)
                screen.blit(hint_surf, (cx - CELL_SIZE // 2, cy - CELL_SIZE // 2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
