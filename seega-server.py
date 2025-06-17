import Pyro4
import random
import threading
import traceback

# Configurar serialização
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = {'pickle'}


@Pyro4.expose
class SeegaPyroServer:
    def __init__(self):
        self.nicknames = []
        self.clients_ready = []
        self.lock = threading.Lock()
        self.forced_piece = None
        self.chat_messages = []
        self.placement_counter = 0

        # Estado inicial do jogo
        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],
            'phase': 'placement',
            'current_turn': 0,
            'pieces_placed': [0, 0],
            'captured': [0, 0],
            'game_over': False,
            'winner': None
        }

        # Centro inicialmente bloqueado
        self.game_state['board'][2][2] = -1
        print("Servidor Seega inicializado")

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

    def set_ready(self, player_id):
        with self.lock:
            if player_id < len(self.clients_ready):
                self.clients_ready[player_id] = True
                print(f"Jogador {player_id} ({self.nicknames[player_id]}) está pronto")

                # Iniciar jogo quando ambos estiverem prontos
                if all(self.clients_ready) and len(self.clients_ready) == 2:
                    self.game_state['current_turn'] = random.randint(0, 1)
                    print(
                        f"Jogo iniciado! Jogador {self.game_state['current_turn']} ({self.nicknames[self.game_state['current_turn']]}) começa")
            return True

    def send_command(self, player_id, command):
        with self.lock:
            if self.game_state['game_over']:
                return self.game_state

            # Verificar se é o turno do jogador
            if self.game_state['current_turn'] != player_id:
                print(f"Comando rejeitado: não é o turno do jogador {player_id}")
                return self.game_state

            try:
                if command['type'] == 'place':
                    return self._handle_place(player_id, command['row'], command['col'])
                elif command['type'] == 'move':
                    return self._handle_move(player_id, command['from_row'], command['from_col'],
                                             command['to_row'], command['to_col'])
                elif command['type'] == 'pass':
                    return self._handle_pass(player_id)
                elif command['type'] == 'surrender':
                    return self._handle_surrender(player_id)
            except Exception as erro:
                print(f"Erro ao processar comando: {erro}")
                traceback.print_exc()

            return self.game_state

    def get_game_state(self):
        with self.lock:
            return self.game_state.copy()

    def send_chat_message(self, sender, message):
        with self.lock:
            self.chat_messages.append({"sender": sender, "message": message})
            print(f"Chat - {sender}: {message}")
            return True

    def get_chat_messages(self):
        with self.lock:
            return self.chat_messages.copy()

    def _handle_place(self, player_id, row, col):
        """Gerencia a colocação de peças na fase inicial com 2 peças por turno"""

        if self.game_state['phase'] != 'placement':
            print(f"Comando de colocação rejeitado: não está na fase de colocação")
            return self.game_state

        # Verificar se a posição é válida
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

        # Coloca a peça
        self.game_state['board'][row][col] = player_id + 1
        self.game_state['pieces_placed'][player_id] += 1
        self.placement_counter += 1

        print(
            f"Jogador {player_id} colocou peça em ({row}, {col}) - Total: {self.game_state['pieces_placed'][player_id]}/12")

        # Verifica se acabou a fase de colocação
        if sum(self.game_state['pieces_placed']) == 24:
            self.game_state['phase'] = 'movement'
            self.game_state['board'][2][2] = 0  # Libera o centro
            self.placement_counter = 0
            print("Fase de colocação concluída! Iniciando fase de movimento")
            return self.game_state

        # Se colocou 2 peças no turno, passa o turno
        if self.placement_counter == 2:
            self.placement_counter = 0
            self.game_state['current_turn'] = 1 - player_id
            print(f"Turno passou para jogador {self.game_state['current_turn']}")

        return self.game_state

    def _handle_move(self, player_id, from_row, from_col, to_row, to_col):
        """Gerencia o movimento de peças na fase de movimento"""
        if self.game_state['phase'] != 'movement':
            print("Comando de movimento rejeitado: não está na fase de movimento")
            return self.game_state

        # Verificar se o movimento é válido
        if not self._is_valid_move(from_row, from_col, to_row, to_col, player_id + 1):
            print(f"Movimento inválido: ({from_row},{from_col}) -> ({to_row},{to_col})")
            return self.game_state

        # Verificar se há peça forçada (após captura)
        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            print(f"Deve continuar com a peça em {self.forced_piece}")
            return self.game_state

        # Executar o movimento
        self.game_state['board'][from_row][from_col] = 0
        self.game_state['board'][to_row][to_col] = player_id + 1
        print(f"Jogador {player_id} moveu de ({from_row},{from_col}) para ({to_row},{to_col})")

        # Verificar capturas
        captures = self._check_captures(to_row, to_col, player_id + 1)

        if captures > 0:
            self.game_state['captured'][player_id] += captures
            self.forced_piece = (to_row, to_col)  # Jogador deve continuar com esta peça
            print(f"Jogador {player_id} capturou {captures} peça(s) e deve continuar jogando")
        else:
            self.forced_piece = None
            self.game_state['current_turn'] = 1 - player_id  # Alternar turno
            print(f"Sem capturas. Turno passa para jogador {self.game_state['current_turn']}")

        # Verificar condições de vitória
        self._check_victory()

        return self.game_state

    def _handle_pass(self, player_id):
        """Permite que o jogador passe o turno (apenas na fase de movimento)"""
        if self.game_state['phase'] != 'movement':
            return self.game_state

        if player_id != self.game_state['current_turn']:
            return self.game_state

        self.forced_piece = None
        self.game_state['current_turn'] = 1 - player_id
        print(f"Jogador {player_id} passou o turno")
        return self.game_state

    def _handle_surrender(self, player_id):
        """Gerencia a desistência de um jogador"""
        self.game_state['game_over'] = True
        self.game_state['winner'] = 1 - player_id
        print(f"Jogador {player_id} desistiu. Jogador {1 - player_id} venceu!")
        return self.game_state

    def _is_valid_move(self, fr, fc, tr, tc, piece):
        """Verifica se um movimento é válido"""
        # Verificar limites do tabuleiro
        if not (0 <= fr < 5 and 0 <= fc < 5 and 0 <= tr < 5 and 0 <= tc < 5):
            return False

        # Verificar se a peça de origem pertence ao jogador
        if self.game_state['board'][fr][fc] != piece:
            return False

        # Verificar se o destino está vazio
        if self.game_state['board'][tr][tc] != 0:
            return False

        # Verificar se é um movimento ortogonal de 1 casa
        if (fr == tr and abs(fc - tc) == 1) or (fc == tc and abs(fr - tr) == 1):
            return True

        return False

    def _check_captures(self, r, c, piece):
        """Verifica e executa capturas após um movimento"""
        opponent = 1 if piece == 2 else 2
        captures = 0

        # Verificar nas 4 direções
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        for dr, dc in directions:
            # Posição da peça adversária
            ar, ac = r + dr, c + dc
            # Posição da peça aliada (do outro lado)
            nr, nc = ar + dr, ac + dc

            # Verificar se há uma peça adversária adjacente
            if (0 <= ar < 5 and 0 <= ac < 5 and
                    self.game_state['board'][ar][ac] == opponent):

                # Não pode capturar no centro
                if (ar, ac) == (2, 2):
                    continue

                # Verificar se há uma peça aliada do outro lado
                if (0 <= nr < 5 and 0 <= nc < 5 and
                        self.game_state['board'][nr][nc] == piece):
                    # Capturar a peça
                    self.game_state['board'][ar][ac] = 0
                    captures += 1
                    print(f"Capturada peça em ({ar},{ac})")

        return captures

    def _check_victory(self):
        """Verifica condições de vitória"""
        player1_pieces = sum(row.count(1) for row in self.game_state['board'])
        player2_pieces = sum(row.count(2) for row in self.game_state['board'])

        # Vitória por eliminação
        if player1_pieces == 0:
            self.game_state['game_over'] = True
            self.game_state['winner'] = 1
            print("Jogador 1 venceu por eliminação!")
        elif player2_pieces == 0:
            self.game_state['game_over'] = True
            self.game_state['winner'] = 0
            print("Jogador 0 venceu por eliminação!")
        else:
            # Verificar se o jogador atual pode se mover
            current_piece = self.game_state['current_turn'] + 1
            if not self._has_valid_moves(current_piece):
                self.game_state['game_over'] = True
                self.game_state['winner'] = 1 - self.game_state['current_turn']
                print(f"Jogador {self.game_state['winner']} venceu por bloqueio!")

    def _has_valid_moves(self, piece):
        """Verifica se um jogador tem movimentos válidos"""
        for r in range(5):
            for c in range(5):
                if self.game_state['board'][r][c] == piece:
                    # Verificar as 4 direções
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        if 5 > nr >= 0 == self.game_state['board'][nr][nc] and 0 <= nc < 5:
                            return True
        return False


if __name__ == "__main__":

    print("=== Iniciando Servidor Seega Pyro4 ===")

    # Criar daemon com configuração específica
    daemon = Pyro4.Daemon(host="localhost", port=9091)

    # Criar e registrar o servidor
    server = SeegaPyroServer()
    uri = daemon.register(server)

    print(f"✓ Servidor criado com URI: {uri}")
    print(f"✓ Servidor rodando em: localhost:9091")

    # Tentar registrar no name server
    try:
        ns = Pyro4.locateNS(host="localhost", port=9090)
        ns.remove("seega.server")
        ns.register("seega.server", uri)
        # Agora sim, muda a serialização para pickle
        Pyro4.config.SERIALIZER = 'pickle'
        Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
        print("✓ Servidor registrado no name server como 'seega.server'")
        print("✓ Clientes podem conectar automaticamente via name server")
    except Exception as e:
        print(f"⚠ Erro ao registrar no name server: {e}")
        traceback.print_exc()

    print("\n=== Instruções ===")
    print("1. Para usar com name server:")
    print("   - Inicie o name server: python -m Pyro4.naming")
    print("   - Execute este servidor")
    print("   - Execute os clientes")
    print("")
    print("2. Para usar sem name server:")
    print("   - Execute este servidor")
    print("   - Os clientes conectarão automaticamente na porta 9090")
    print("")
    print("✓ Servidor Seega Pyro4 iniciado e aguardando conexões...")
    print("✓ Pressione Ctrl+C para parar o servidor")

    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n✓ Servidor interrompido pelo usuário")
    except Exception as e:
        print(f"\n✗ Erro no servidor: {e}")
    finally:
        print("✓ Servidor finalizado")
