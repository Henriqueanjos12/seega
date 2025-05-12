import socket
import threading
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import time


class SeegaClient:
    def __init__(self, host='localhost', port=5556):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.nickname = None
        self.current_turn = 0
        self.selected_piece = None
        self.game_state = None
        
        # Configurações visuais
        self.CELL_SIZE = 80
        self.BOARD_SIZE = 5
        self.CANVAS_SIZE = self.CELL_SIZE * self.BOARD_SIZE
        self.COLORS = {
            'board_bg': '#E8D0AA',
            'cell_light': '#F5DEB3',
            'cell_dark': '#D2B48C',
            'player1': '#000000',  # Preto
            'player2': '#FFFFFF',  # Branco
            'highlight': '#90EE90',  # Verde claro para destacar
            'center': '#A0522D',  # Marrom para o centro
        }
        
        # Iniciar interface
        self.root = tk.Tk()
        self.root.title("Seega - Aguardando conexão")
        self.root.resizable(False, False)
        self.setup_ui()
        
        # Conectar ao servidor
        self.connect()
        
    def connect(self):
        try:
            self.socket.connect((self.host, self.port))
            
            # Iniciar thread para receber mensagens
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor: {e}")
            self.root.destroy()
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)
        
        # Área do jogo (esquerda)
        game_frame = tk.Frame(main_frame)
        game_frame.pack(side=tk.LEFT, padx=10)
        
        # Status do jogo
        self.status_label = tk.Label(game_frame, text="Aguardando outro jogador...", font=("Arial", 12))
        self.status_label.pack(pady=5)
        
        # Tabuleiro
        board_frame = tk.Frame(game_frame)
        board_frame.pack()
        
        self.canvas = tk.Canvas(board_frame, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE, bg=self.COLORS['board_bg'])
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Botão de desistência
        self.surrender_button = tk.Button(game_frame, text="Desistir", command=self.surrender, state=tk.DISABLED)
        self.surrender_button.pack(pady=10)

        # Botão de passar turno
        self.pass_button = tk.Button(game_frame, text="Passar Turno", command=self.pass_turn, state=tk.DISABLED)
        self.pass_button.pack(pady=5)

        # Chat e informações (direita)
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side=tk.RIGHT, padx=10, fill=tk.BOTH)
        
        # Área de chat
        chat_label = tk.Label(chat_frame, text="Chat", font=("Arial", 12, "bold"))
        chat_label.pack(pady=5)
        
        self.chat_area = scrolledtext.ScrolledText(chat_frame, width=30, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_area.pack(pady=5)
        
        # Entrada de mensagem
        msg_frame = tk.Frame(chat_frame)
        msg_frame.pack(fill=tk.X, pady=5)
        
        self.msg_entry = tk.Entry(msg_frame, width=25)
        self.msg_entry.pack(side=tk.LEFT, padx=2)
        self.msg_entry.bind("<Return>", lambda event: self.send_chat_message())
        
        send_button = tk.Button(msg_frame, text="Enviar", command=self.send_chat_message)
        send_button.pack(side=tk.RIGHT, padx=2)
        
        # Informações do jogo
        info_frame = tk.LabelFrame(chat_frame, text="Informações", padx=5, pady=5)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.player_info_label = tk.Label(info_frame, text="Aguardando...", anchor="w")
        self.player_info_label.pack(fill=tk.X)
        
        self.opponent_info_label = tk.Label(info_frame, text="Aguardando oponente...", anchor="w")
        self.opponent_info_label.pack(fill=tk.X)
        
        self.phase_label = tk.Label(info_frame, text="Fase: Preparação", anchor="w")
        self.phase_label.pack(fill=tk.X)
        
        # Desenhar tabuleiro inicial
        self.draw_board()
    
    def draw_board(self):
        self.canvas.delete("all")
        
        # Desenhar células do tabuleiro
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                x1 = col * self.CELL_SIZE
                y1 = row * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                
                # Alternar cores das células
                color = self.COLORS['cell_light'] if (row + col) % 2 == 0 else self.COLORS['cell_dark']
                
                # Destacar o centro
                if row == 2 and col == 2:
                    color = self.COLORS['center']
                
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")
        
        # Se temos estado do jogo, desenhar as peças
        if self.game_state:
            board = self.game_state['board']
            for row in range(self.BOARD_SIZE):
                for col in range(self.BOARD_SIZE):
                    cell_value = board[row][col]
                    x = col * self.CELL_SIZE + self.CELL_SIZE // 2
                    y = row * self.CELL_SIZE + self.CELL_SIZE // 2
                    
                    if cell_value == 1:  # Jogador 1
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, 
                                              fill=self.COLORS['player1'], outline="gray", width=2)
                    elif cell_value == 2:  # Jogador 2
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, 
                                              fill=self.COLORS['player2'], outline="black", width=2)
                    elif cell_value == -1:  # Centro bloqueado na fase inicial
                        self.canvas.create_line(x - 20, y - 20, x + 20, y + 20, fill="red", width=3)
                        self.canvas.create_line(x + 20, y - 20, x - 20, y + 20, fill="red", width=3)
            
            # Destacar peça selecionada
            if self.selected_piece:
                row, col = self.selected_piece
                x1 = col * self.CELL_SIZE
                y1 = row * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.COLORS['highlight'], width=3)
    
    def update_game_state(self, state):
        self.game_state = state
        self.current_turn = state['current_turn']
        
        # Atualizar informações na interface
        if state['phase'] == 'placement':
            self.phase_label.config(text=f"Fase: Colocação de peças")
        else:
            self.phase_label.config(text=f"Fase: Movimentação")
            
        # Atualizar status do turno
        if self.player_id is not None:
            if state['game_over']:
                if state['winner'] == self.player_id:
                    self.status_label.config(text="Você venceu! 🎉")
                else:
                    self.status_label.config(text="Você perdeu! 😢")
                self.surrender_button.config(state=tk.DISABLED)
            else:
                if state['current_turn'] == self.player_id:
                    self.status_label.config(text="Seu turno!")
                    self.surrender_button.config(state=tk.NORMAL)
                else:
                    self.status_label.config(text="Turno do oponente...")
                    self.surrender_button.config(state=tk.DISABLED)
        
        # Atualizar informações dos jogadores
        if self.player_id == 0:
            self.player_info_label.config(text=f"Você: {self.nickname} (Preto) - Capturadas: {state['captured'][0]}")
            self.opponent_info_label.config(text=f"Oponente (Branco) - Capturadas: {state['captured'][1]}")
        else:
            self.player_info_label.config(text=f"Você: {self.nickname} (Branco) - Capturadas: {state['captured'][1]}")
            self.opponent_info_label.config(text=f"Oponente (Preto) - Capturadas: {state['captured'][0]}")
        
        # Redesenhar o tabuleiro
        self.draw_board()

        # Habilitar botão "Passar Turno" apenas na fase de movimentação e no seu turno
        if self.player_id == self.current_turn and self.game_state['phase'] == 'movement' and not self.game_state[
            'game_over']:
            self.pass_button.config(state=tk.NORMAL)
        else:
            self.pass_button.config(state=tk.DISABLED)

    def pass_turn(self):
        command = {
            'type': 'pass'
        }
        self.socket.send(json.dumps(command).encode('utf-8'))
        self.pass_button.config(state=tk.DISABLED)

    def on_canvas_click(self, event):
        if not self.game_state or self.game_state['game_over']:
            return
            
        if self.current_turn != self.player_id:
            return  # Não é o turno do jogador
        
        # Converter coordenadas do clique para linha/coluna do tabuleiro
        col = event.x // self.CELL_SIZE
        row = event.y // self.CELL_SIZE
        
        if not (0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE):
            return  # Clique fora do tabuleiro
        
        # Na fase de colocação
        if self.game_state['phase'] == 'placement':
            # Não pode colocar no centro durante a fase de colocação
            if row == 2 and col == 2:
                return
                
            # Verifica se a célula está vazia
            if self.game_state['board'][row][col] == 0:
                # Enviar comando de colocação
                self.send_place_command(row, col)
        
        # Na fase de movimento
        else:
            player_piece = self.player_id + 1  # 1 para jogador 0, 2 para jogador 1
            
            # Se nenhuma peça está selecionada e clicou em uma peça própria
            if not self.selected_piece and self.game_state['board'][row][col] == player_piece:
                self.selected_piece = (row, col)
                self.draw_board()  # Redesenhar para mostrar seleção
            
            # Se já tem uma peça selecionada
            elif self.selected_piece:
                from_row, from_col = self.selected_piece
                
                # Clicou na mesma peça, desseleciona
                if from_row == row and from_col == col:
                    self.selected_piece = None
                    self.draw_board()
                
                # Clicou em outra célula, tenta mover
                elif self.game_state['board'][row][col] == 0:
                    # Verifica se é um movimento válido (apenas uma casa ortogonalmente)
                    if (abs(from_row - row) == 1 and from_col == col) or (abs(from_col - col) == 1 and from_row == row):
                        self.send_move_command(from_row, from_col, row, col)
                        self.selected_piece = None
                
                # Clicou em outra peça própria, muda seleção
                elif self.game_state['board'][row][col] == player_piece:
                    self.selected_piece = (row, col)
                    self.draw_board()
    
    def send_place_command(self, row, col):
        command = {
            'type': 'place',
            'row': row,
            'col': col
        }
        self.socket.send(json.dumps(command).encode('utf-8'))
    
    def send_move_command(self, from_row, from_col, to_row, to_col):
        command = {
            'type': 'move',
            'from_row': from_row,
            'from_col': from_col,
            'to_row': to_row,
            'to_col': to_col
        }
        self.socket.send(json.dumps(command).encode('utf-8'))
    
    def send_chat_message(self):
        message = self.msg_entry.get().strip()
        if message:
            command = {
                'type': 'chat',
                'message': message
            }
            self.socket.send(json.dumps(command).encode('utf-8'))
            self.msg_entry.delete(0, tk.END)
    
    def add_chat_message(self, sender, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{sender}: {message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def add_system_message(self, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"SISTEMA: {message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
    
    def surrender(self):
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            command = {
                'type': 'surrender'
            }
            self.socket.send(json.dumps(command).encode('utf-8'))
    
    def receive_messages(self):
        while True:
            try:
                message = self.socket.recv(1024).decode('utf-8')

                if message == 'NICK':
                    try:
                        # Força a exibição da janela de nickname na thread principal
                        def ask_nick():
                            nickname = simpledialog.askstring("Nickname", "Digite seu nickname:", parent=self.root)
                            if not nickname:
                                nickname = f"Jogador{round(time.time())}"
                            self.nickname = nickname
                            self.socket.send(nickname.encode('utf-8'))

                        # Executa na thread principal do Tkinter
                        self.root.after(0, ask_nick)

                    except Exception as e:
                        print(f"[Erro ao enviar nickname]: {e}")
                        try:
                            self.socket.close()
                        except:
                            pass
                        self.root.quit()
                        return



                else:
                    try:
                        data = json.loads(message)
                        
                        if data['type'] == 'player_info':
                            self.player_id = data['player_id']
                            self.root.title(f"Seega - {self.nickname}")
                            piece_color = "Preto" if self.player_id == 0 else "Branco"
                            self.add_system_message(f"Você é o jogador {self.player_id + 1} ({piece_color})")
                        
                        elif data['type'] == 'chat':
                            self.add_chat_message(data['sender'], data['message'])
                        
                        elif data['type'] == 'system_message':
                            self.add_system_message(data['message'])
                        
                        elif data['type'] == 'game_state':
                            self.update_game_state(data['state'])
                    
                    except json.JSONDecodeError:
                        self.add_system_message(f"Mensagem inválida recebida: {message}")
            
            except Exception as e:
                print(f"Erro: {e}")
                messagebox.showerror("Erro de Conexão", "Conexão com o servidor perdida!")
                self.root.destroy()
                break
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    client = SeegaClient()
    client.run()
