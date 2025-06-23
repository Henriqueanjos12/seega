"""
Modelo principal do jogo Seega.

Este módulo implementa a lógica de negócio completa do jogo Seega,
incluindo regras de movimentação, captura e condições de vitória.
"""

import random


class SeegaGame:
    """
    Modelo principal do jogo Seega.

    Implementa todas as regras e lógica do jogo tradicional africano Seega,
    incluindo duas fases (colocação e movimentação), sistema de capturas
    por flanqueamento e condições de vitória.

    Attributes:
        BOARD_SIZE (int): Tamanho do tabuleiro (5x5)
        TOTAL_PIECES (int): Total de peças no jogo (24)
        FORBIDDEN_CENTER (tuple): Posição central bloqueada (2,2)
        DIRECTIONS (list): Direções possíveis para movimento (N,S,L,O)
    """

    # Constantes do jogo
    BOARD_SIZE = 5
    TOTAL_PIECES = 24
    FORBIDDEN_CENTER = (2, 2)
    DIRECTIONS = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # Direita, Baixo, Esquerda, Cima

    def __init__(self):
        """Inicializa uma nova instância do jogo."""
        self.reset()

    def reset(self):
        """
        Reseta o jogo para o estado inicial.

        Limpa o tabuleiro, reinicia contadores e prepara para uma nova partida.
        O centro do tabuleiro é marcado como bloqueado (-1).
        """
        # Inicializa tabuleiro vazio (0 = vazio, -1 = bloqueado, 1/2 = jogador)
        self.board = [[0 for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE)]
        self.board[2][2] = -1  # Centro bloqueado durante fase de colocação

        # Estado do jogo
        self.phase = 'placement'  # Fase atual: 'placement' ou 'movement'
        self.current_turn = 0  # Jogador atual (0 ou 1)
        self.pieces_placed = [0, 0]  # Peças colocadas por cada jogador
        self.turn_piece_count = 0  # Contador de peças colocadas no turno atual
        self.captured = [0, 0]  # Peças capturadas por cada jogador
        self.forced_piece = None  # Peça forçada a continuar jogando após captura

        # Controle de fim de jogo
        self.game_over = False
        self.winner = None

        # Sistema de chat
        self.chat_messages = []

    def start_game(self):
        """
        Inicia o jogo escolhendo aleatoriamente quem começa.

        Define o jogador inicial de forma aleatória e reseta o contador
        de peças do turno.
        """
        self.current_turn = random.randint(0, 1)
        self.turn_piece_count = 0

    def get_state(self):
        """
        Retorna uma cópia do estado atual do jogo.

        Returns:
            dict: Dicionário contendo todo o estado do jogo, incluindo
                  tabuleiro, fase, turno atual, peças capturadas, etc.
        """
        return {
            'board': [row[:] for row in self.board],  # Cópia profunda do tabuleiro
            'phase': self.phase,
            'current_turn': self.current_turn,
            'pieces_placed': self.pieces_placed[:],  # Cópia da lista
            'captured': self.captured[:],  # Cópia da lista
            'game_over': self.game_over,
            'winner': self.winner,
            'forced_piece': self.forced_piece,
            'turn_piece_count': self.turn_piece_count
        }

    def place_piece(self, player_id, row, col):
        """
        Coloca uma peça no tabuleiro durante a fase de colocação.

        Args:
            player_id (int): ID do jogador (0 ou 1)
            row (int): Linha do tabuleiro (0-4)
            col (int): Coluna do tabuleiro (0-4)

        Returns:
            bool: True se a peça foi colocada com sucesso, False caso contrário
        """
        # Validações básicas
        if self.phase != 'placement' or player_id != self.current_turn:
            return False
        if not (0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE):
            return False
        if self.board[row][col] != 0 or (row, col) == self.FORBIDDEN_CENTER:
            return False

        # Coloca a peça (jogador 0 = peça 1, jogador 1 = peça 2)
        self.board[row][col] = player_id + 1
        self.pieces_placed[player_id] += 1
        self.turn_piece_count += 1

        # Verifica se todas as peças foram colocadas
        if sum(self.pieces_placed) == self.TOTAL_PIECES:
            self.phase = 'movement'
            self.board[2][2] = 0  # Libera o centro para a fase de movimento
            self.turn_piece_count = 0
        # Cada jogador coloca 2 peças por turno
        elif self.turn_piece_count == 2:
            self.turn_piece_count = 0
            self.current_turn = 1 - player_id  # Alterna turno

        return True

    def move_piece(self, player_id, from_row, from_col, to_row, to_col):
        """
        Move uma peça durante a fase de movimentação.

        Args:
            player_id (int): ID do jogador
            from_row (int): Linha de origem
            from_col (int): Coluna de origem  
            to_row (int): Linha de destino
            to_col (int): Coluna de destino

        Returns:
            bool: True se o movimento foi realizado, False caso contrário
        """
        # Validações
        if self.phase != 'movement' or self.game_over or player_id != self.current_turn:
            return False

        # Se há peça forçada (após captura), só ela pode se mover
        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            return False

        if not self.valid_move(player_id, from_row, from_col, to_row, to_col):
            return False

        # Executa o movimento
        self.board[from_row][from_col] = 0
        self.board[to_row][to_col] = player_id + 1

        # Verifica capturas
        captured = self.check_captures(to_row, to_col, player_id)
        if captured:
            # Se capturou, pode jogar novamente com a mesma peça
            self.captured[player_id] += captured
            self.forced_piece = (to_row, to_col)
        else:
            # Se não capturou, passa o turno
            self.forced_piece = None
            self.current_turn = 1 - player_id

        # Verifica condições de fim de jogo
        self.check_end_conditions(player_id)
        return True

    def valid_move(self, player_id, from_row, from_col, to_row, to_col):
        """
        Verifica se um movimento é válido.

        Args:
            player_id (int): ID do jogador
            from_row, from_col (int): Posição de origem
            to_row, to_col (int): Posição de destino

        Returns:
            bool: True se o movimento é válido
        """
        # Verifica limites do tabuleiro
        if not (0 <= from_row < self.BOARD_SIZE and 0 <= from_col < self.BOARD_SIZE):
            return False
        if not (0 <= to_row < self.BOARD_SIZE and 0 <= to_col < self.BOARD_SIZE):
            return False

        # Verifica se há peça do jogador na origem e destino está vazio
        if self.board[from_row][from_col] != player_id + 1 or self.board[to_row][to_col] != 0:
            return False

        # Movimento deve ser horizontal ou vertical (não diagonal)
        if from_row != to_row and from_col != to_col:
            return False

        # Movimento deve ser de apenas 1 casa
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False

        return True

    def check_captures(self, row, col, player_id):
        """
        Verifica e executa capturas por flanqueamento.

        O flanqueamento ocorre quando uma peça adversária fica entre
        duas peças do jogador atual em linha reta.

        Args:
            row, col (int): Posição da peça que se moveu
            player_id (int): ID do jogador que se moveu

        Returns:
            int: Número de peças capturadas
        """
        opponent = 2 if player_id == 0 else 1  # Peça do oponente
        captured_positions = []

        # Verifica cada direção
        for dr, dc in self.DIRECTIONS:
            nr, nc = row + dr, col + dc

            # Se há uma peça oponente adjacente
            if (0 <= nr < self.BOARD_SIZE and 0 <= nc < self.BOARD_SIZE and
                    self.board[nr][nc] == opponent and (nr, nc) != self.FORBIDDEN_CENTER):

                # Verifica se há nossa peça do outro lado (flanqueamento)
                nnr, nnc = nr + dr, nc + dc
                if (0 <= nnr < self.BOARD_SIZE and 0 <= nnc < self.BOARD_SIZE and
                        self.board[nnr][nnc] == player_id + 1):
                    captured_positions.append((nr, nc))

        # Remove as peças capturadas do tabuleiro
        for r, c in captured_positions:
            self.board[r][c] = 0

        return len(captured_positions)

    def pass_turn(self, player_id):
        """
        Permite ao jogador passar seu turno durante a fase de movimento.

        Args:
            player_id (int): ID do jogador

        Returns:
            bool: True se conseguiu passar o turno
        """
        if self.phase == 'movement' and player_id == self.current_turn:
            self.forced_piece = None
            self.current_turn = 1 - player_id
            return True
        return False

    def surrender(self, player_id):
        """
        Jogador desiste da partida.

        Args:
            player_id (int): ID do jogador que desiste

        Returns:
            bool: Sempre True (desistência sempre é aceita)
        """
        self.game_over = True
        self.winner = 1 - player_id  # O oponente vence
        return True

    def check_end_conditions(self, player_id):
        """
        Verifica se o jogo terminou por vitória.

        Condições de vitória:
        1. Capturar todas as peças do oponente
        2. Bloquear todos os movimentos do oponente

        Args:
            player_id (int): ID do jogador que acabou de jogar
        """
        opponent = 1 - player_id
        opponent_piece = opponent + 1

        # Verifica se o oponente ainda tem peças no tabuleiro
        if not any(opponent_piece in row for row in self.board):
            self.game_over = True
            self.winner = player_id
            return

        # Verifica se o oponente tem movimentos válidos
        if not self.has_valid_moves(opponent):
            self.game_over = True
            self.winner = player_id
            return

    def has_valid_moves(self, player_id):
        """
        Verifica se um jogador tem movimentos válidos disponíveis.

        Args:
            player_id (int): ID do jogador

        Returns:
            bool: True se o jogador tem pelo menos um movimento válido
        """
        piece = player_id + 1

        # Percorre todas as posições do tabuleiro
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                if self.board[row][col] == piece:
                    # Para cada peça do jogador, verifica se pode se mover
                    for dr, dc in self.DIRECTIONS:
                        nr, nc = row + dr, col + dc
                        if 0 <= nr < self.BOARD_SIZE and 0 <= nc < self.BOARD_SIZE and self.board[nr][nc] == 0:
                            return True
        return False

    def add_chat_message(self, sender, message):
        """
        Adiciona uma mensagem ao chat do jogo.

        Args:
            sender (str): Nome do remetente
            message (str): Conteúdo da mensagem
        """
        self.chat_messages.append({'sender': sender, 'message': message})