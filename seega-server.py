import socket
import threading
import json
import random
import time

class SeegaServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(2)
        
        self.clients = []
        self.nicknames = []
        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],
            'phase': 'placement',  # 'placement', 'movement'
            'center_filled': False,
            'current_turn': 0,  # 0 or 1 for player index
            'pieces_placed': [0, 0],  # Pieces placed by each player
            'captured': [0, 0],  # Number of captured pieces
            'game_over': False,
            'winner': None,
        }
        
        # Inicializa o tabuleiro - 0 vazio, 1 jogador 1, 2 jogador 2
        self.game_state['board'][2][2] = -1  # Centro é bloqueado inicialmente
        
        print(f"Servidor inicializado em {host}:{port}")
        print("Aguardando jogadores...")
        
    def broadcast(self, message):
        for client in self.clients:
            try:
                client.send(message)
            except:
                # Remover cliente com problema
                index = self.clients.index(client)
                self.clients.remove(client)
                client.close()
                nickname = self.nicknames[index]
                self.nicknames.remove(nickname)
                
    def handle_client(self, client, nickname, player_id):
        while True:
            try:
                message = client.recv(1024)
                if not message:
                    break
                
                data = json.loads(message.decode('utf-8'))
                
                if data['type'] == 'chat':
                    # Transmitir mensagem de chat
                    chat_msg = {
                        'type': 'chat',
                        'sender': nickname,
                        'message': data['message']
                    }
                    self.broadcast(json.dumps(chat_msg).encode('utf-8'))
                
                elif data['type'] == 'move':
                    if player_id == self.game_state['current_turn']:
                        self.handle_move(data, player_id)
                
                elif data['type'] == 'place':
                    if player_id == self.game_state['current_turn']:
                        self.handle_placement(data, player_id)
                
                elif data['type'] == 'surrender':
                    self.game_state['game_over'] = True
                    self.game_state['winner'] = 1 if player_id == 0 else 0
                    self.broadcast_game_state()
                    
            except Exception as e:
                print(f"Erro: {e}")
                break
        
        # Cliente desconectou
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
        row, col = data['row'], data['col']
        
        # Verifica se a posição é válida para colocação
        if self.game_state['phase'] == 'placement':
            if row == 2 and col == 2:  # Centro do tabuleiro
                return  # Não pode colocar no centro durante a fase de colocação
                
            if self.game_state['board'][row][col] == 0:  # Posição vazia
                # Coloca a peça do jogador
                player_piece = player_id + 1  # 1 para jogador 0, 2 para jogador 1
                self.game_state['board'][row][col] = player_piece
                self.game_state['pieces_placed'][player_id] += 1
                
                # Verifica se deve mudar de fase
                total_pieces = sum(self.game_state['pieces_placed'])
                if total_pieces == 24:  # Cada jogador colocou 12 peças
                    self.game_state['phase'] = 'movement'
                    self.game_state['board'][2][2] = 0  # Libera o centro
                    self.game_state['center_filled'] = True
                
                # Troca o turno
                self.game_state['current_turn'] = 1 - self.game_state['current_turn']
                self.broadcast_game_state()
    
    def handle_move(self, data, player_id):
        if self.game_state['phase'] != 'movement':
            return
            
        from_row, from_col = data['from_row'], data['from_col']
        to_row, to_col = data['to_row'], data['to_col']
        player_piece = player_id + 1  # 1 para jogador 0, 2 para jogador 1
        
        # Verifica se o movimento é válido
        if self.is_valid_move(from_row, from_col, to_row, to_col, player_piece):
            # Executa o movimento
            self.game_state['board'][from_row][from_col] = 0
            self.game_state['board'][to_row][to_col] = player_piece
            
            # Verifica e realiza capturas
            captures = self.check_captures(to_row, to_col, player_piece)
            
            if captures > 0:
                self.game_state['captured'][player_id] += captures
                
                # Verifica condição de vitória
                opponent = 1 - player_id
                opponent_piece = opponent + 1
                
                # Conta peças do oponente
                opponent_pieces = sum(row.count(opponent_piece) for row in self.game_state['board'])
                
                if opponent_pieces == 0:
                    self.game_state['game_over'] = True
                    self.game_state['winner'] = player_id
            
            # Verifica se o oponente está bloqueado (não pode mover)
            opponent = 1 - player_id
            opponent_piece = opponent + 1
            if not self.has_valid_moves(opponent_piece):
                self.game_state['game_over'] = True
                self.game_state['winner'] = player_id
            
            # Troca o turno
            self.game_state['current_turn'] = 1 - self.game_state['current_turn']
            
            self.broadcast_game_state()
    
    def is_valid_move(self, from_row, from_col, to_row, to_col, player_piece):
        # Verifica se a origem tem uma peça do jogador atual
        if self.game_state['board'][from_row][from_col] != player_piece:
            return False
        
        # Verifica se o destino está vazio
        if self.game_state['board'][to_row][to_col] != 0:
            return False
        
        # Verifica se o movimento é horizontal ou vertical (não diagonal)
        if from_row != to_row and from_col != to_col:
            return False
        
        # Verifica se o movimento é de apenas uma casa
        if abs(from_row - to_row) + abs(from_col - to_col) != 1:
            return False
        
        return True
    
    def check_captures(self, row, col, player_piece):
        opponent_piece = 1 if player_piece == 2 else 2
        captures = 0
        
        # Verifica nas quatro direções
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # direita, baixo, esquerda, cima
        
        for dr, dc in directions:
            # Posição adjacente
            adj_row, adj_col = row + dr, col + dc
            
            # Verificar se está dentro do tabuleiro
            if 0 <= adj_row < 5 and 0 <= adj_col < 5:
                # Verifica se há uma peça do oponente adjacente
                if self.game_state['board'][adj_row][adj_col] == opponent_piece:
                    # Posição após a peça do oponente na mesma direção
                    next_row, next_col = adj_row + dr, adj_col + dc
                    
                    # Verificar se está dentro do tabuleiro
                    if 0 <= next_row < 5 and 0 <= next_col < 5:
                        # Se há uma peça do jogador atual nesta posição, captura a peça do oponente
                        if self.game_state['board'][next_row][next_col] == player_piece:
                            self.game_state['board'][adj_row][adj_col] = 0
                            captures += 1
        
        return captures
    
    def has_valid_moves(self, player_piece):
        for row in range(5):
            for col in range(5):
                if self.game_state['board'][row][col] == player_piece:
                    # Verifica movimento em cada direção
                    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
                    for dr, dc in directions:
                        new_row, new_col = row + dr, col + dc
                        if 0 <= new_row < 5 and 0 <= new_col < 5:
                            if self.game_state['board'][new_row][new_col] == 0:
                                return True
        return False
    
    def broadcast_game_state(self):
        state_message = {
            'type': 'game_state',
            'state': self.game_state
        }
        self.broadcast(json.dumps(state_message).encode('utf-8'))
    
    def start(self):
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
            
            # Notifica o cliente sobre seu ID de jogador
            client.send(json.dumps({
                'type': 'player_info',
                'player_id': player_id,
                'nickname': nickname
            }).encode('utf-8'))
            
            # Informa a todos sobre o novo jogador
            self.broadcast(json.dumps({
                'type': 'system_message',
                'message': f"{nickname} entrou no jogo!"
            }).encode('utf-8'))
            
            # Inicia thread para o cliente
            thread = threading.Thread(target=self.handle_client, args=(client, nickname, player_id))
            thread.daemon = True
            thread.start()
            
            if len(self.clients) == 2:
                time.sleep(1)  # Pequena pausa para garantir que tudo esteja pronto
                # Informa quem começa
                starter = self.nicknames[self.game_state['current_turn']]
                self.broadcast(json.dumps({
                    'type': 'system_message',
                    'message': f"O jogo começou! {starter} começa!"
                }).encode('utf-8'))
                self.broadcast_game_state()
        
        # Manter o servidor rodando
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Servidor encerrado")
            self.server.close()

if __name__ == "__main__":
    server = SeegaServer()
    server.start()
