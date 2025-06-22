import random
import threading


class SeegaGame:
    """
    Classe principal com a lógica completa do jogo Seega.
    Gerencia o estado do tabuleiro, regras de jogo, capturas, e mensagens de chat.
    """

    BOARD_SIZE = 5

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()
        self.chat_messages = []

    def reset(self):
        """Reinicializa o estado do jogo."""
        self.board = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
        self.board[2][2] = -1  # Centro bloqueado na fase de colocação
        self.phase = 'placement'
        self.current_turn = random.randint(0, 1)
        self.pieces_placed = [0, 0]
        self.captured = [0, 0]
        self.game_over = False
        self.winner = None
        self.forced_piece = None
        self.placement_counter = 0

    def start_game(self):
        """Inicia o jogo definindo o jogador inicial aleatoriamente."""
        self.current_turn = random.randint(0, 1)

    def place_piece(self, player_id, row, col):
        """Lógica de colocação de peças na fase inicial."""
        if self.phase != 'placement' or self.board[row][col] != 0 or (row == 2 and col == 2):
            return
        if player_id != self.current_turn:
            return

        self.board[row][col] = player_id + 1
        self.pieces_placed[player_id] += 1
        self.placement_counter += 1

        if sum(self.pieces_placed) == 24:
            self.phase = 'movement'
            self.board[2][2] = 0  # Libera centro
            self.placement_counter = 0
            return

        if self.placement_counter == 2:
            self.placement_counter = 0
            self.current_turn = 1 - player_id

    def move_piece(self, player_id, from_row, from_col, to_row, to_col):
        """Realiza movimentação e captura de peças."""
        if self.phase != 'movement' or self.game_over:
            return

        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            return

        if not self.valid_move(player_id, from_row, from_col, to_row, to_col):
            return

        self.board[from_row][from_col] = 0
        self.board[to_row][to_col] = player_id + 1
        captures = self.check_captures(to_row, to_col, player_id)

        if captures > 0:
            self.captured[player_id] += captures
            self.forced_piece = (to_row, to_col)
        else:
            self.forced_piece = None
            self.current_turn = 1 - player_id

        self.check_end_game(player_id)

    def valid_move(self, player_id, from_row, from_col, to_row, to_col):
        """Valida se o movimento solicitado é válido."""
        if self.board[from_row][from_col] != player_id + 1 or self.board[to_row][to_col] != 0:
            return False
        if from_row != to_row and from_col != to_col:
            return False
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False
        return True

    def check_captures(self, row, col, player_id):
        """Verifica capturas ao redor da nova posição."""
        opponent = 1 if player_id == 0 else 0
        captures = 0
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        for dr, dc in directions:
            adj_row, adj_col = row + dr, col + dc
            if 0 <= adj_row < self.BOARD_SIZE and 0 <= adj_col < self.BOARD_SIZE:
                if self.board[adj_row][adj_col] == opponent + 1:
                    if (adj_row, adj_col) == (2, 2):
                        continue  # Centro não captura
                    next_row, next_col = adj_row + dr, adj_col + dc
                    if 0 <= next_row < self.BOARD_SIZE and 0 <= next_col < self.BOARD_SIZE:
                        if self.board[next_row][next_col] == player_id + 1:
                            self.board[adj_row][adj_col] = 0
                            captures += 1
        return captures

    def check_end_game(self, player_id):
        """Verifica se o jogo terminou."""
        opponent = 1 - player_id
        remaining_opponent = sum(row.count(opponent + 1) for row in self.board)

        if remaining_opponent == 0 or not self.has_valid_moves(opponent + 1):
            self.game_over = True
            self.winner = player_id

    def has_valid_moves(self, piece):
        """Verifica se ainda há movimentos válidos para o jogador."""
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                if self.board[row][col] == piece:
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = row + dr, col + dc
                        if 0 <= nr < self.BOARD_SIZE and 0 <= nc < self.BOARD_SIZE and self.board[nr][nc] == 0:
                            return True
        return False

    def pass_turn(self, player_id):
        """Permite passar a vez na fase de movimentação."""
        if self.phase == 'movement' and self.current_turn == player_id:
            self.forced_piece = None
            self.current_turn = 1 - player_id

    def surrender(self, player_id):
        """Permite o jogador desistir da partida."""
        self.game_over = True
        self.winner = 1 - player_id

    def send_chat_message(self, nickname, message):
        """Adiciona uma nova mensagem no chat."""
        self.chat_messages.append({'sender': nickname, 'message': message})

    def get_state(self):
        """Retorna o estado atual do jogo como dicionário."""
        return {
            'board': self.board,
            'phase': self.phase,
            'current_turn': self.current_turn,
            'pieces_placed': self.pieces_placed,
            'captured': self.captured,
            'game_over': self.game_over,
            'winner': self.winner,
            'forced_piece': self.forced_piece
        }
