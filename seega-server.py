import Pyro4
import random
import threading
import traceback

# Configuração do Pyro para utilizar o serializer 'pickle'
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = {'pickle'}


# Expondo a classe para acesso remoto via Pyro
@Pyro4.expose
class SeegaPyroServer:
    def __init__(self):
        # Inicialização das variáveis do servidor
        self.nicknames = []  # Lista de apelidos dos jogadores conectados
        self.clients_ready = []  # Lista de status de prontidão de cada jogador
        self.lock = threading.Lock()  # Lock para controle de concorrência
        self.forced_piece = None  # Peça que o jogador deve mover novamente após captura
        self.chat_messages = []  # Histórico de mensagens do chat
        self.placement_counter = 0  # Contador de quantas peças foram colocadas no turno

        # Estado inicial do jogo
        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],  # Tabuleiro 5x5 vazio
            'phase': 'placement',  # Começa na fase de colocação
            'current_turn': 0,  # Jogador 0 inicia por padrão
            'pieces_placed': [0, 0],  # Quantidade de peças colocadas por cada jogador
            'captured': [0, 0],  # Peças capturadas por cada jogador
            'game_over': False,
            'winner': None
        }

        # Marca o centro como bloqueado inicialmente
        self.game_state['board'][2][2] = -1
        print("Servidor Seega inicializado")

    # Registra um novo cliente no servidor
    def register_client(self, nickname):
        with self.lock:
            if len(self.nicknames) >= 2:
                print(f"Tentativa de registro rejeitada - servidor cheio. Nickname: {nickname}")
                return -1

            player_id = len(self.nicknames)
            self.nicknames.append(nickname)
            self.clients_ready.append(False)
            print(f"Cliente registrado: {nickname} (ID: {player_id})")
            return player_id

    # Marca o cliente como pronto para jogar
    def set_ready(self, player_id):
        with self.lock:
            if player_id < len(self.clients_ready):
                self.clients_ready[player_id] = True
                print(f"Jogador {player_id} ({self.nicknames[player_id]}) está pronto")

                # Inicia o jogo se ambos estiverem prontos
                if all(self.clients_ready) and len(self.clients_ready) == 2:
                    self.game_state['current_turn'] = random.randint(0, 1)
                    print(
                        f"Jogo iniciado! Jogador {self.game_state['current_turn']} ({self.nicknames[self.game_state['current_turn']]}) começa")
            return True

    # Recebe e processa comandos enviados pelos clientes
    def send_command(self, player_id, command):
        with self.lock:
            if self.game_state['game_over']:
                return self.game_state

            if self.game_state['current_turn'] != player_id:
                print(f"Comando rejeitado: não é o turno do jogador {player_id}")
                return self.game_state

            try:
                # Identifica o tipo de comando recebido
                if command['type'] == 'place':
                    return self._handle_place(player_id, command['row'], command['col'])
                elif command['type'] == 'move':
                    return self._handle_move(player_id, command['from_row'], command['from_col'], command['to_row'],
                                             command['to_col'])
                elif command['type'] == 'pass':
                    return self._handle_pass(player_id)
                elif command['type'] == 'surrender':
                    return self._handle_surrender(player_id)
            except Exception as erro:
                print(f"Erro ao processar comando: {erro}")
                traceback.print_exc()

            return self.game_state

    # Fornece o estado atual do jogo para o cliente
    def get_game_state(self):
        with self.lock:
            return self.game_state.copy()

    # Adiciona mensagens ao chat
    def send_chat_message(self, sender, message):
        with self.lock:
            self.chat_messages.append({"sender": sender, "message": message})
            print(f"Chat - {sender}: {message}")
            return True

    # Retorna o histórico de mensagens do chat
    def get_chat_messages(self):
        with self.lock:
            return self.chat_messages.copy()

    # Trata a colocação de peças na fase inicial
    def _handle_place(self, player_id, row, col):
        if self.game_state['phase'] != 'placement':
            print("Comando de colocação rejeitado: não está na fase de colocação")
            return self.game_state

        if not (0 <= row < 5 and 0 <= col < 5):
            print(f"Posição inválida: ({row}, {col})")
            return self.game_state

        if self.game_state['board'][row][col] != 0:
            print(f"Posição ocupada: ({row}, {col})")
            return self.game_state

        if row == 2 and col == 2:
            print("Não é possível colocar no centro durante a fase de colocação")
            return self.game_state

        if self.game_state['pieces_placed'][player_id] >= 12:
            print(f"Jogador {player_id} já colocou todas as peças")
            return self.game_state

        self.game_state['board'][row][col] = player_id + 1
        self.game_state['pieces_placed'][player_id] += 1
        self.placement_counter += 1
        print(
            f"Jogador {player_id} colocou peça em ({row}, {col}) - Total: {self.game_state['pieces_placed'][player_id]}/12")

        # Quando todos colocaram as 24 peças, inicia a fase de movimento
        if sum(self.game_state['pieces_placed']) == 24:
            self.game_state['phase'] = 'movement'
            self.game_state['board'][2][2] = 0  # Libera o centro
            self.placement_counter = 0
            print("Fase de colocação concluída! Iniciando fase de movimento")
            return self.game_state

        # Alterna o turno após 2 peças no mesmo turno
        if self.placement_counter == 2:
            self.placement_counter = 0
            self.game_state['current_turn'] = 1 - player_id
            print(f"Turno passou para jogador {self.game_state['current_turn']}")

        return self.game_state

    # Trata o movimento de peças na fase de movimento
    def _handle_move(self, player_id, from_row, from_col, to_row, to_col):
        if self.game_state['phase'] != 'movement':
            print("Comando de movimento rejeitado: não está na fase de movimento")
            return self.game_state

        if not self._is_valid_move(from_row, from_col, to_row, to_col, player_id + 1):
            print(f"Movimento inválido: ({from_row},{from_col}) -> ({to_row},{to_col})")
            return self.game_state

        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            print(f"Deve continuar com a peça em {self.forced_piece}")
            return self.game_state

        # Executa o movimento
        self.game_state['board'][from_row][from_col] = 0
        self.game_state['board'][to_row][to_col] = player_id + 1
        print(f"Jogador {player_id} moveu de ({from_row},{from_col}) para ({to_row},{to_col})")

        captures = self._check_captures(to_row, to_col, player_id + 1)

        if captures > 0:
            self.game_state['captured'][player_id] += captures
            self.forced_piece = (to_row, to_col)
            print(f"Jogador {player_id} capturou {captures} peça(s) e deve continuar jogando")
        else:
            self.forced_piece = None
            self.game_state['current_turn'] = 1 - player_id
            print(f"Sem capturas. Turno passa para jogador {self.game_state['current_turn']}")

        self._check_victory()
        return self.game_state

    # Permite que o jogador passe a vez (só na fase de movimento)
    def _handle_pass(self, player_id):
        if self.game_state['phase'] != 'movement':
            return self.game_state

        if player_id != self.game_state['current_turn']:
            return self.game_state

        self.forced_piece = None
        self.game_state['current_turn'] = 1 - player_id
        print(f"Jogador {player_id} passou o turno")
        return self.game_state

    # Trata a desistência do jogador
    def _handle_surrender(self, player_id):
        self.game_state['game_over'] = True
        self.game_state['winner'] = 1 - player_id
        print(f"Jogador {player_id} desistiu. Jogador {1 - player_id} venceu!")
        return self.game_state

    # Valida se o movimento é permitido
    def _is_valid_move(self, fr, fc, tr, tc, piece):
        if not (0 <= fr < 5 and 0 <= fc < 5 and 0 <= tr < 5 and 0 <= tc < 5):
            return False

        if self.game_state['board'][fr][fc] != piece:
            return False

        if self.game_state['board'][tr][tc] != 0:
            return False

        if (fr == tr and abs(fc - tc) == 1) or (fc == tc and abs(fr - tr) == 1):
            return True

        return False

    # Verifica e executa capturas após movimento
    def _check_captures(self, r, c, piece):
        opponent = 1 if piece == 2 else 2
        captures = 0

        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        for dr, dc in directions:
            ar, ac = r + dr, c + dc
            nr, nc = ar + dr, ac + dc

            if 0 <= ar < 5 and 0 <= ac < 5 and self.game_state['board'][ar][ac] == opponent:
                if (ar, ac) == (2, 2):
                    continue
                if 0 <= nr < 5 and 0 <= nc < 5 and self.game_state['board'][nr][nc] == piece:
                    self.game_state['board'][ar][ac] = 0
                    captures += 1
                    print(f"Capturada peça em ({ar},{ac})")

        return captures

    # Verifica se o jogo acabou
    def _check_victory(self):
        player1_pieces = sum(row.count(1) for row in self.game_state['board'])
        player2_pieces = sum(row.count(2) for row in self.game_state['board'])

        if player1_pieces == 0:
            self.game_state['game_over'] = True
            self.game_state['winner'] = 1
            print("Jogador 1 venceu por eliminação!")
        elif player2_pieces == 0:
            self.game_state['game_over'] = True
            self.game_state['winner'] = 0
            print("Jogador 0 venceu por eliminação!")
        else:
            current_piece = self.game_state['current_turn'] + 1
            if not self._has_valid_moves(current_piece):
                self.game_state['game_over'] = True
                self.game_state['winner'] = 1 - self.game_state['current_turn']
                print(f"Jogador {self.game_state['winner']} venceu por bloqueio!")

    # Verifica se há movimentos válidos para o jogador atual
    def _has_valid_moves(self, piece):
        for r in range(5):
            for c in range(5):
                if self.game_state['board'][r][c] == piece:
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        if 5 > nr >= 0 == self.game_state['board'][nr][nc] and 0 <= nc < 5:
                            return True
        return False


# Inicialização do servidor
if __name__ == "__main__":
    print("=== Iniciando Servidor Seega Pyro4 ===")

    daemon = Pyro4.Daemon(host="localhost", port=9091)

    server = SeegaPyroServer()
    uri = daemon.register(server)

    print(f"✓ Servidor criado com URI: {uri}")
    print(f"✓ Servidor rodando em: localhost:9091")

    try:
        ns = Pyro4.locateNS(host="localhost", port=9090)
        ns.remove("seega.server")
        ns.register("seega.server", uri)
        print("✓ Servidor registrado no name server como 'seega.server'")
    except Exception as e:
        print(f"⚠ Erro ao registrar no name server: {e}")
        traceback.print_exc()

    print("\n=== Instruções ===")
    print("1. Para usar com name server:")
    print("   - Inicie o name server: python -m Pyro4.naming")
    print("   - Execute este servidor")
    print("   - Execute os clientes")

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n✓ Servidor interrompido pelo usuário")
    finally:
        print("✓ Servidor finalizado")
