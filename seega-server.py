import threading
import random
import time
import Pyro5.api
import Pyro5.server
import subprocess
import socket
import sys


@Pyro5.api.expose
class SeegaServer:
    """
    Servidor principal do jogo Seega utilizando Pyro5.
    Gerencia o estado completo do jogo, chat e lógica de jogadas.
    """

    def __init__(self):
        """Inicializa o servidor com estado inicial do jogo."""
        self.nicknames = []
        self.lock = threading.Lock()
        self.placement_counter = 0
        self.forced_piece = None
        self.chat_messages = []

        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],
            'phase': 'placement',
            'current_turn': 0,
            'pieces_placed': [0, 0],
            'captured': [0, 0],
            'game_over': False,
            'winner': None,
            'update_id': 0  # Controle incremental para otimização do cliente
        }
        self.game_state['board'][2][2] = -1
        print("Servidor Pyro5 inicializado")

    def get_nicknames(self):
        """Retorna lista de jogadores conectados."""
        return self.nicknames

    def register_player(self, nickname):
        """Registra jogador e inicia jogo se ambos conectados."""
        with self.lock:
            if len(self.nicknames) >= 2:
                return {'status': 'full'}
            self.nicknames.append(nickname)
            player_id = len(self.nicknames) - 1
            print(f"{nickname} conectado como jogador {player_id}")
            if len(self.nicknames) == 2:
                self.start_game()
            return {'status': 'ok', 'player_id': player_id, 'update_id': self.game_state['update_id']}

    def start_game(self):
        """Define aleatoriamente quem inicia."""
        self.game_state['current_turn'] = random.randint(0, 1)
        self.increment_update()
        print("Jogo iniciado!")

    def increment_update(self):
        """Incrementa identificador de atualização do estado."""
        self.game_state['update_id'] += 1

    def get_game_state(self):
        """Retorna estado completo (modo compatibilidade)."""
        return self.game_state

    def get_game_state_if_updated(self, last_update_id):
        """Retorna apenas se houver atualização nova."""
        if last_update_id != self.game_state['update_id']:
            return {'state': self.game_state, 'update_id': self.game_state['update_id']}
        return {'state': None, 'update_id': self.game_state['update_id']}

    def get_chat_messages(self):
        """Retorna todo o histórico do chat."""
        return self.chat_messages

    def get_chat_messages_if_updated(self, last_count):
        """Retorna apenas mensagens novas do chat."""
        if len(self.chat_messages) > last_count:
            return self.chat_messages[last_count:]
        return []

    def send_chat_message(self, player_id, message):
        """Adiciona mensagem ao chat."""
        sender = self.nicknames[player_id]
        self.chat_messages.append({'sender': sender, 'message': message})

    def send_command(self, player_id, command):
        """Processa comandos enviados pelos jogadores."""
        with self.lock:
            if command['type'] == 'place':
                self.handle_placement(player_id, command)
            elif command['type'] == 'move':
                self.handle_move(player_id, command)
            elif command['type'] == 'surrender':
                self.handle_surrender(player_id)
            elif command['type'] == 'pass':
                self.handle_pass(player_id)
            return self.game_state

    def handle_surrender(self, player_id):
        """Processa desistência."""
        self.game_state['game_over'] = True
        self.game_state['winner'] = 1 - player_id
        self.increment_update()

    def handle_pass(self, player_id):
        """Permite passar turno (fase de movimentação)."""
        if self.game_state['phase'] == 'movement' and self.game_state['current_turn'] == player_id:
            self.forced_piece = None
            self.game_state['current_turn'] = 1 - player_id
            self.increment_update()

    def handle_placement(self, player_id, data):
        """Gerencia colocação inicial das peças."""
        row, col = data['row'], data['col']
        if self.game_state['phase'] != 'placement':
            return
        if row == 2 and col == 2:
            return
        if self.game_state['board'][row][col] != 0:
            return
        if player_id != self.game_state['current_turn']:
            return

        piece = player_id + 1
        self.game_state['board'][row][col] = piece
        self.game_state['pieces_placed'][player_id] += 1
        self.placement_counter += 1

        if sum(self.game_state['pieces_placed']) == 24:
            self.game_state['phase'] = 'movement'
            self.game_state['board'][2][2] = 0
            self.placement_counter = 0
            self.increment_update()
            return

        if self.placement_counter == 2:
            self.placement_counter = 0
            self.game_state['current_turn'] = 1 - player_id
        self.increment_update()

    def handle_move(self, player_id, data):
        """Processa movimentação de peças."""
        if self.game_state['phase'] != 'movement':
            return
        from_row, from_col = data['from_row'], data['from_col']
        to_row, to_col = data['to_row'], data['to_col']
        piece = player_id + 1

        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            return
        if not self.is_valid_move(from_row, from_col, to_row, to_col, piece):
            return

        self.game_state['board'][from_row][from_col] = 0
        self.game_state['board'][to_row][to_col] = piece
        captures = self.check_captures(to_row, to_col, piece)

        opponent_id = 1 - player_id
        opponent_piece = opponent_id + 1

        if sum(row.count(opponent_piece) for row in self.game_state['board']) == 0:
            self.game_state['game_over'] = True
            self.game_state['winner'] = player_id
        elif not self.has_valid_moves(opponent_piece):
            self.game_state['game_over'] = True
            self.game_state['winner'] = player_id

        if captures > 0:
            self.game_state['captured'][player_id] += captures
            self.forced_piece = (to_row, to_col)
        else:
            self.forced_piece = None
            self.game_state['current_turn'] = opponent_id
        self.increment_update()

    def is_valid_move(self, from_row, from_col, to_row, to_col, piece):
        """Valida legalidade do movimento."""
        if self.game_state['board'][from_row][from_col] != piece:
            return False
        if self.game_state['board'][to_row][to_col] != 0:
            return False
        if from_row != to_row and from_col != to_col:
            return False
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False
        return True

    def check_captures(self, row, col, piece):
        """Verifica capturas após movimento."""
        opponent_piece = 1 if piece == 2 else 2
        captures = 0
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dr, dc in directions:
            adj_row, adj_col = row + dr, col + dc
            if 0 <= adj_row < 5 and 0 <= adj_col < 5:
                if self.game_state['board'][adj_row][adj_col] == opponent_piece:
                    if (adj_row, adj_col) == (2, 2):
                        continue  # Centro não pode ser capturado
                    next_row, next_col = adj_row + dr, adj_col + dc
                    if 0 <= next_row < 5 and 0 <= next_col < 5:
                        if self.game_state['board'][next_row][next_col] == piece:
                            self.game_state['board'][adj_row][adj_col] = 0
                            captures += 1
        return captures

    def has_valid_moves(self, piece):
        """Verifica se o jogador ainda possui movimentos válidos."""
        for row in range(5):
            for col in range(5):
                if self.game_state['board'][row][col] == piece:
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        new_row, new_col = row + dr, col + dc
                        if 0 <= new_row < 5 and 0 <= new_col < 5:
                            if self.game_state['board'][new_row][new_col] == 0:
                                return True
        return False


def is_port_open(port):
    """Verifica se o Name Server já está ativo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def main():
    """Inicia o servidor Pyro5 com Name Server automático."""
    if not is_port_open(9090):
        print("Name Server não encontrado. Iniciando novo Name Server...")
        subprocess.Popen([sys.executable, "-m", "Pyro5.nameserver"])
        time.sleep(2)

    daemon = Pyro5.server.Daemon()
    ns = Pyro5.api.locate_ns()
    servidor = SeegaServer()
    uri = daemon.register(servidor)
    ns.register("Seega.Server", uri)
    print("Servidor registrado no Name Server com sucesso.")
    daemon.requestLoop()


if __name__ == "__main__":
    main()
