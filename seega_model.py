import random

class SeegaGame:
    """Modelo principal do jogo Seega."""

    BOARD_SIZE = 5
    TOTAL_PIECES = 24
    FORBIDDEN_CENTER = (2, 2)
    DIRECTIONS = [(0, 1), (1, 0), (0, -1), (-1, 0)]

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
        self.board[2][2] = -1  # Centro bloqueado
        self.phase = 'placement'
        self.current_turn = 0
        self.pieces_placed = [0, 0]
        self.turn_piece_count = 0
        self.captured = [0, 0]
        self.forced_piece = None
        self.game_over = False
        self.winner = None
        self.chat_messages = []

    def start_game(self):
        self.current_turn = random.randint(0, 1)
        self.turn_piece_count = 0

    def get_state(self):
        return {
            'board': [row[:] for row in self.board],
            'phase': self.phase,
            'current_turn': self.current_turn,
            'pieces_placed': self.pieces_placed[:],
            'captured': self.captured[:],
            'game_over': self.game_over,
            'winner': self.winner,
            'forced_piece': self.forced_piece,
            'turn_piece_count': self.turn_piece_count
        }

    def place_piece(self, player_id, row, col):
        if self.phase != 'placement' or player_id != self.current_turn:
            return False
        if not (0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE):
            return False
        if self.board[row][col] != 0 or (row, col) == self.FORBIDDEN_CENTER:
            return False

        self.board[row][col] = player_id + 1
        self.pieces_placed[player_id] += 1
        self.turn_piece_count += 1

        if sum(self.pieces_placed) == self.TOTAL_PIECES:
            self.phase = 'movement'
            self.board[2][2] = 0
            self.turn_piece_count = 0
        elif self.turn_piece_count == 2:
            self.turn_piece_count = 0
            self.current_turn = 1 - player_id

        return True

    def move_piece(self, player_id, from_row, from_col, to_row, to_col):
        if self.phase != 'movement' or self.game_over or player_id != self.current_turn:
            return False
        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            return False
        if not self.valid_move(player_id, from_row, from_col, to_row, to_col):
            return False

        self.board[from_row][from_col] = 0
        self.board[to_row][to_col] = player_id + 1

        captured = self.check_captures(to_row, to_col, player_id)
        if captured:
            self.captured[player_id] += captured
            self.forced_piece = (to_row, to_col)
        else:
            self.forced_piece = None
            self.current_turn = 1 - player_id

        self.check_end_conditions(player_id)
        return True

    def valid_move(self, player_id, from_row, from_col, to_row, to_col):
        if not (0 <= from_row < self.BOARD_SIZE and 0 <= from_col < self.BOARD_SIZE):
            return False
        if not (0 <= to_row < self.BOARD_SIZE and 0 <= to_col < self.BOARD_SIZE):
            return False
        if self.board[from_row][from_col] != player_id + 1 or self.board[to_row][to_col] != 0:
            return False
        if from_row != to_row and from_col != to_col:
            return False
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False
        return True

    def check_captures(self, row, col, player_id):
        opponent = 2 if player_id == 0 else 1
        captured_positions = []
        for dr, dc in self.DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.BOARD_SIZE and 0 <= nc < self.BOARD_SIZE:
                if self.board[nr][nc] == opponent and (nr, nc) != self.FORBIDDEN_CENTER:
                    nnr, nnc = nr + dr, nc + dc
                    if 0 <= nnr < self.BOARD_SIZE and 0 <= nnc < self.BOARD_SIZE:
                        if self.board[nnr][nnc] == player_id + 1:
                            captured_positions.append((nr, nc))
        for r, c in captured_positions:
            self.board[r][c] = 0
        return len(captured_positions)

    def pass_turn(self, player_id):
        if self.phase == 'movement' and player_id == self.current_turn:
            self.forced_piece = None
            self.current_turn = 1 - player_id
            return True
        return False

    def surrender(self, player_id):
        self.game_over = True
        self.winner = 1 - player_id
        return True

    def check_end_conditions(self, player_id):
        opponent = 1 - player_id
        opponent_piece = opponent + 1
        if not any(opponent_piece in row for row in self.board):
            self.game_over = True
            self.winner = player_id
            return
        if not self.has_valid_moves(opponent):
            self.game_over = True
            self.winner = player_id
            return

    def has_valid_moves(self, player_id):
        piece = player_id + 1
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                if self.board[row][col] == piece:
                    for dr, dc in self.DIRECTIONS:
                        nr, nc = row + dr, col + dc
                        if 0 <= nr < self.BOARD_SIZE and 0 <= nc < self.BOARD_SIZE and self.board[nr][nc] == 0:
                            return True
        return False

    def add_chat_message(self, sender, message):
        self.chat_messages.append({'sender': sender, 'message': message})
