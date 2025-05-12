import socket
import threading
import json
import random
import time


class SeegaServer:
    """
    Classe que implementa o servidor do jogo Seega com suporte para dois jogadores.
    Gerencia conexões, estado do jogo, comunicação e lógica do jogo.
    """

    def __init__(self, host='localhost', port=5556):
        """
        Inicializa o servidor socket e o estado do jogo.
        """
        self.host = host
        self.port = port

        # Cria um socket TCP
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Permite reutilizar o mesmo endereço e porta imediatamente após o encerramento do servidor
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Associa o socket ao endereço IP e porta especificados
        self.server.bind((self.host, self.port))

        # Coloca o socket em modo de escuta, aceitando até 2 conexões pendentes
        self.server.listen(2)

        # Listas para armazenar conexões e apelidos dos jogadores
        self.clients = []
        self.nicknames = []

        # Conta quantas peças o jogador atual colocou nesta rodada
        self.placement_counter = 0

        # (row, col) da peça que deve ser usada se o jogador continuar o turno
        self.forced_piece = None

        self.center_protection = {
            'owner': None,  # 0 ou 1
            'turns': 0  # Quantidade de turnos jogados pelo dono
        }

        # Estado do jogo
        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],  # Tabuleiro 5x5
            'phase': 'placement',  # Fases: 'placement' ou 'movement'
            'center_filled': False,
            'current_turn': 0,  # Índice do jogador da vez
            'pieces_placed': [0, 0],  # Peças colocadas por jogador
            'captured': [0, 0],  # Peças capturadas por jogador
            'game_over': False,
            'winner': None
        }

        # Centro do tabuleiro inicialmente bloqueado
        self.game_state['board'][2][2] = -1

        print(f"Servidor inicializado em {host}:{port}")
        print("Aguardando jogadores...")

    def broadcast(self, message):
        """
        Envia uma mensagem para todos os clientes conectados.
        """
        for client in self.clients:
            try:
                client.send(message)
            except:
                index = self.clients.index(client)
                self.clients.remove(client)
                client.close()
                nickname = self.nicknames[index]
                self.nicknames.remove(nickname)

    def handle_client(self, client, nickname, player_id):
        """
        Processa mensagens recebidas de um cliente específico.
        """
        while True:
            try:
                message = client.recv(1024)
                if not message:
                    break

                data = json.loads(message.decode('utf-8'))

                # Mensagem de chat
                if data['type'] == 'chat':
                    chat_msg = {
                        'type': 'chat',
                        'sender': nickname,
                        'message': data['message']
                    }
                    self.broadcast(json.dumps(chat_msg).encode('utf-8'))

                # Jogada de movimento
                elif data['type'] == 'move':
                    if player_id == self.game_state['current_turn']:
                        self.handle_move(data, player_id)

                # Colocação de peça
                elif data['type'] == 'place':
                    if player_id == self.game_state['current_turn']:
                        self.handle_placement(data, player_id)

                # Rendição
                elif data['type'] == 'surrender':
                    self.game_state['game_over'] = True
                    self.game_state['winner'] = 1 if player_id == 0 else 0
                    self.broadcast_game_state()

                # Passar turno
                elif data['type'] == 'pass':
                    if player_id == self.game_state['current_turn'] and self.game_state['phase'] == 'movement':
                        self.forced_piece = None  # limpa peça forçada
                        self.game_state['current_turn'] = 1 - player_id
                        self.broadcast_game_state()

            except Exception as e:
                print(f"Erro: {e}")
                break

        # Remoção do cliente desconectado
        if client in self.clients:
            index = self.clients.index(client)
            self.clients.remove(client)
            client.close()
            nickname = self.nicknames[index]
            self.nicknames.remove(nickname)

            # Encerrar o jogo se um jogador sair
            if len(self.clients) < 2:
                self.game_state['game_over'] = True
                self.game_state['winner'] = 1 if player_id == 0 else 0
                self.broadcast_game_state()

    def handle_placement(self, data, player_id):
        """
        Processa a colocação de uma peça no tabuleiro.
        Agora cada jogador pode colocar 2 peças seguidas antes de passar o turno.
        """
        row, col = data['row'], data['col']

        if self.game_state['phase'] == 'placement':
            if row == 2 and col == 2:
                return  # Centro não pode ser usado nessa fase

            if self.game_state['board'][row][col] == 0 and player_id == self.game_state['current_turn']:
                player_piece = player_id + 1
                self.game_state['board'][row][col] = player_piece
                self.game_state['pieces_placed'][player_id] += 1
                self.placement_counter += 1

                # Verifica se todas as peças foram colocadas
                total_pieces = sum(self.game_state['pieces_placed'])
                if total_pieces == 24:
                    self.game_state['phase'] = 'movement'
                    self.game_state['board'][2][2] = 0  # Libera o centro
                    self.placement_counter = 0  # resetar para segurança
                    self.broadcast_game_state()
                    return

                # Após 2 peças, passa o turno
                if self.placement_counter == 2:
                    self.placement_counter = 0
                    self.game_state['current_turn'] = 1 - self.game_state['current_turn']

                self.broadcast_game_state()

    def handle_move(self, data, player_id):
        """
        Processa o movimento de uma peça no tabuleiro.
        Jogador continua jogando se capturar, mas deve continuar com a mesma peça.
        """
        if self.game_state['phase'] != 'movement':
            return

        from_row = data['from_row']
        from_col = data['from_col']
        to_row = data['to_row']
        to_col = data['to_col']
        player_piece = player_id + 1

        # Se houver peça forçada, só pode mover ela
        if self.forced_piece is not None:
            forced_row, forced_col = self.forced_piece
            if (from_row, from_col) != (forced_row, forced_col):
                return  # Movimento inválido com peça diferente

        if self.is_valid_move(from_row, from_col, to_row, to_col, player_piece):
            self.game_state['board'][from_row][from_col] = 0
            self.game_state['board'][to_row][to_col] = player_piece

            captures = self.check_captures(to_row, to_col, player_piece)
            opponent = 1 - player_id
            opponent_piece = opponent + 1

            # Verifica fim de jogo por peças eliminadas
            if sum(row.count(opponent_piece) for row in self.game_state['board']) == 0:
                self.game_state['game_over'] = True
                self.game_state['winner'] = player_id

            # Verifica bloqueio de movimentos
            if not self.has_valid_moves(opponent_piece):
                self.game_state['game_over'] = True
                self.game_state['winner'] = player_id

            if captures > 0:
                self.game_state['captured'][player_id] += captures
                self.forced_piece = (to_row, to_col)  # Jogador continua com esta peça
            else:
                self.forced_piece = None
                self.game_state['current_turn'] = opponent

            self.broadcast_game_state()

    def is_valid_move(self, from_row, from_col, to_row, to_col, player_piece):
        """
        Verifica se um movimento é válido.
        """
        if self.game_state['board'][from_row][from_col] != player_piece:
            return False
        if self.game_state['board'][to_row][to_col] != 0:
            return False
        if from_row != to_row and from_col != to_col:
            return False
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False
        return True

    def check_captures(self, row, col, player_piece):
        """
        Verifica e executa capturas ao redor da posição (row, col).
        """
        opponent_piece = 1 if player_piece == 2 else 2
        captures = 0
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # direita, baixo, esquerda, cima

        for dr, dc in directions:
            adj_row = row + dr
            adj_col = col + dc

            if 0 <= adj_row < 5 and 0 <= adj_col < 5:
                if self.game_state['board'][adj_row][adj_col] == opponent_piece:
                    # Impede captura se a peça estiver no centro
                    if adj_row == 2 and adj_col == 2:
                        continue

                    next_row = adj_row + dr
                    next_col = adj_col + dc

                    if 0 <= next_row < 5 and 0 <= next_col < 5:
                        if self.game_state['board'][next_row][next_col] == player_piece:
                            self.game_state['board'][adj_row][adj_col] = 0
                            captures += 1

        return captures

    def has_valid_moves(self, player_piece):
        """
        Verifica se o jogador com player_piece tem movimentos válidos disponíveis.
        """
        for row in range(5):
            for col in range(5):
                if self.game_state['board'][row][col] == player_piece:
                    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
                    for dr, dc in directions:
                        new_row = row + dr
                        new_col = col + dc
                        if 0 <= new_row < 5 and 0 <= new_col < 5:
                            if self.game_state['board'][new_row][new_col] == 0:
                                return True
        return False

    def broadcast_game_state(self):
        """
        Envia o estado atual do jogo para todos os clientes.
        """
        state_message = {
            'type': 'game_state',
            'state': self.game_state
        }
        self.broadcast(json.dumps(state_message).encode('utf-8'))

    def start(self):
        """
        Inicia o servidor e aceita conexões dos dois jogadores.
        """
        # Escolhe aleatoriamente quem começa
        self.game_state['current_turn'] = random.randint(0, 1)

        while len(self.clients) < 2:
            client, address = self.server.accept()
            print(f"Conexão estabelecida com {str(address)}")

            client.send('NICK'.encode('utf-8'))

            try:
                nickname = client.recv(1024).decode('utf-8')
            except:
                print("Cliente desconectou antes de enviar nickname.")
                client.close()
                continue

            self.nicknames.append(nickname)
            self.clients.append(client)

            print(f"Nickname do cliente é {nickname}")
            player_id = len(self.clients) - 1

            # Envia ao cliente suas informações
            client.send(json.dumps({
                'type': 'player_info',
                'player_id': player_id,
                'nickname': nickname
            }).encode('utf-8'))

            # Informa todos sobre novo jogador
            self.broadcast(json.dumps({
                'type': 'system_message',
                'message': f"{nickname} entrou no jogo!"
            }).encode('utf-8'))

            # Inicia a thread para o cliente
            thread = threading.Thread(target=self.handle_client,
                                      args=(client, nickname, player_id))
            thread.daemon = True
            thread.start()

            # Quando os dois jogadores estiverem conectados
            if len(self.clients) == 2:
                time.sleep(1)
                starter = self.nicknames[self.game_state['current_turn']]
                self.broadcast(json.dumps({
                    'type': 'system_message',
                    'message': f"O jogo começou! {starter} começa!"
                }).encode('utf-8'))
                self.broadcast_game_state()

        # Mantém o servidor ativo até interrupção manual
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Servidor encerrado")
            self.server.close()


if __name__ == "__main__":
    server = SeegaServer()
    server.start()
