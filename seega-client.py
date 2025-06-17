import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog

import Pyro4

# Configurar serialização para compatibilidade com pickle
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = {'pickle'}


# Classe principal do cliente Seega usando Pyro para comunicação RPC
class SeegaClientPyro:
    def __init__(self):
        # Inicializa variáveis de estado do cliente
        self.msg_entry = None
        self.chat_area = None
        self.surrender_button = None
        self.pass_button = None
        self.canvas = None
        self.status_label = None
        self.status_label = None
        self.player_info_label = None
        self.player_info_label = None
        self.opponent_info_label = None
        self.phase_label = None
        self.nickname = None
        self.player_id = None
        self.game_state = None
        self.chat_messages = []
        self.selected_piece = None
        self.server = None

        # Parâmetros visuais do tabuleiro
        self.CELL_SIZE = 80
        self.BOARD_SIZE = 5
        self.CANVAS_SIZE = self.CELL_SIZE * self.BOARD_SIZE
        self.COLORS = {
            'board_bg': '#E8D0AA',
            'cell_light': '#F5DEB3',
            'cell_dark': '#D2B48C',
            'player1': '#000000',
            'player2': '#FFFFFF',
            'highlight': '#90EE90',
            'center': '#A0522D',
        }

        # Cria interface gráfica
        self.root = tk.Tk()
        self.root.title("Seega Pyro")
        self.root.resizable(False, False)
        self.setup_ui()

        # Tenta conectar ao servidor
        if not self.connect_to_server():
            messagebox.showerror("Erro", "Não foi possível conectar ao servidor")
            self.root.destroy()
            return

        # Faz o registro e inicia o loop de atualização
        self.setup_connection()
        self.update_loop()

    # Função que localiza o servidor via Name Server do Pyro
    def connect_to_server(self):
        try:
            print("Tentando localizar Name Server em localhost:9090...")
            ns = Pyro4.locateNS(host="localhost", port=9090, broadcast=False)
            print("✓ Name Server encontrado")

            uri = ns.lookup("seega.server")
            print(f"✓ URI obtida: {uri}")

            self.server = Pyro4.Proxy(uri)
            self.server._pyroTimeout = 10

            # Testa conexão com chamada simples
            _ = self.server.get_chat_messages()
            print("✓ Conexão com o servidor OK")
            return True

        except Exception as erro:
            print(f"✗ Erro ao conectar: {erro}")
            return False

    # Realiza o registro do jogador junto ao servidor
    def setup_connection(self):
        try:
            self.nickname = simpledialog.askstring("Nickname", "Digite seu nome:", parent=self.root)
            if not self.nickname:
                self.nickname = f"Jogador{round(time.time())}"

            self.player_id = self.server.register_client(self.nickname)
            if self.player_id == -1:
                messagebox.showerror("Erro", "Servidor cheio")
                self.root.destroy()
                return
            else:
                self.server.set_ready(self.player_id)
                print(f"Cliente registrado com ID: {self.player_id}")
        except Exception as erro:
            messagebox.showerror("Erro", f"Erro de conexão: {erro}")
            self.root.destroy()

    # Monta toda a interface gráfica
    def setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        # Área do jogo
        game_frame = tk.Frame(main_frame)
        game_frame.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(game_frame, text="Aguardando outro jogador...", font=("Arial", 12))
        self.status_label.pack(pady=5)

        board_frame = tk.Frame(game_frame)
        board_frame.pack()

        self.canvas = tk.Canvas(board_frame, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE,
                                bg=self.COLORS['board_bg'])
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Botões de controle
        button_frame = tk.Frame(game_frame)
        button_frame.pack(pady=10)

        self.surrender_button = tk.Button(button_frame, text="Desistir", command=self.surrender, state=tk.DISABLED)
        self.surrender_button.pack(side=tk.LEFT, padx=5)

        self.pass_button = tk.Button(button_frame, text="Passar Turno", command=self.pass_turn, state=tk.DISABLED)
        self.pass_button.pack(side=tk.LEFT, padx=5)

        # Área do chat
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side=tk.RIGHT, padx=10, fill=tk.BOTH)

        chat_label = tk.Label(chat_frame, text="Chat", font=("Arial", 12, "bold"))
        chat_label.pack(pady=5)

        self.chat_area = scrolledtext.ScrolledText(chat_frame, width=30, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_area.pack(pady=5)

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

        self.draw_board()

    # Desenha o tabuleiro visualmente
    def draw_board(self):
        self.canvas.delete("all")

        # Desenha as casas do tabuleiro
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                x1 = col * self.CELL_SIZE
                y1 = row * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE

                color = self.COLORS['cell_light'] if (row + col) % 2 == 0 else self.COLORS['cell_dark']
                if row == 2 and col == 2:
                    color = self.COLORS['center']

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

        # Desenha as peças do jogo com base no estado atual
        if self.game_state:
            board = self.game_state['board']
            for row in range(self.BOARD_SIZE):
                for col in range(self.BOARD_SIZE):
                    cell_value = board[row][col]
                    x = col * self.CELL_SIZE + self.CELL_SIZE // 2
                    y = row * self.CELL_SIZE + self.CELL_SIZE // 2

                    if cell_value == 1:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25,
                                                fill=self.COLORS['player1'], outline="gray", width=2)
                    elif cell_value == 2:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25,
                                                fill=self.COLORS['player2'], outline="black", width=2)
                    elif cell_value == -1:
                        self.canvas.create_line(x - 20, y - 20, x + 20, y + 20, fill="red", width=3)
                        self.canvas.create_line(x + 20, y - 20, x - 20, y + 20, fill="red", width=3)

            if self.selected_piece:
                row, col = self.selected_piece
                x1 = col * self.CELL_SIZE
                y1 = row * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.COLORS['highlight'], width=4)

    # Loop de atualização constante do estado do jogo e chat
    def update_loop(self):
        try:
            if self.server and self.player_id is not None:
                state = self.server.get_game_state()
                if state:
                    self.update_game_state(state)

                # Atualiza chat
                messages = self.server.get_chat_messages()
                new_messages = messages[len(self.chat_messages):]
                for msg in new_messages:
                    self.chat_area.config(state=tk.NORMAL)
                    self.chat_area.insert(tk.END, f"{msg['sender']}: {msg['message']}\n")
                    self.chat_area.see(tk.END)
                    self.chat_area.config(state=tk.DISABLED)
                    self.chat_messages.append(msg)

        except Exception as erro:
            print(f"Erro no update_loop: {erro}")

        self.root.after(500, self.update_loop)

    # Atualiza a interface com o estado recebido do servidor
    def update_game_state(self, state):
        self.game_state = state

        if state['phase'] == 'placement':
            pieces_left_p1 = 12 - state['pieces_placed'][0]
            pieces_left_p2 = 12 - state['pieces_placed'][1]
            self.phase_label.config(text=f"Fase: Colocação (P1:{pieces_left_p1}, P2:{pieces_left_p2})")
        else:
            self.phase_label.config(text="Fase: Movimentação")

        if state['game_over']:
            if state['winner'] == self.player_id:
                self.status_label.config(text="🎉 Você venceu!")
            else:
                self.status_label.config(text="😢 Você perdeu!")
            self.surrender_button.config(state=tk.DISABLED)
            self.pass_button.config(state=tk.DISABLED)
        else:
            if state['current_turn'] == self.player_id:
                self.status_label.config(text="🎯 Seu turno!")
                self.surrender_button.config(state=tk.NORMAL)
            else:
                self.status_label.config(text="⏳ Turno do oponente...")
                self.surrender_button.config(state=tk.DISABLED)

        # Exibe informações dos jogadores
        if self.player_id == 0:
            self.player_info_label.config(text=f"Você: {self.nickname} (●) - Capturadas: {state['captured'][0]}")
            self.opponent_info_label.config(text=f"Oponente (○) - Capturadas: {state['captured'][1]}")
        else:
            self.player_info_label.config(text=f"Você: {self.nickname} (○) - Capturadas: {state['captured'][1]}")
            self.opponent_info_label.config(text=f"Oponente (●) - Capturadas: {state['captured'][0]}")

        if self.player_id == state['current_turn'] and state['phase'] == 'movement' and not state['game_over']:
            self.pass_button.config(state=tk.NORMAL)
        else:
            self.pass_button.config(state=tk.DISABLED)

        self.draw_board()

    # Trata cliques no tabuleiro
    def on_canvas_click(self, event):
        if not self.game_state or self.game_state['game_over']:
            return

        if self.game_state['current_turn'] != self.player_id:
            return

        col = event.x // self.CELL_SIZE
        row = event.y // self.CELL_SIZE

        if not (0 <= row < self.BOARD_SIZE and 0 <= col < self.BOARD_SIZE):
            return

        if self.game_state['phase'] == 'placement':
            if row == 2 and col == 2:
                return
            if self.game_state['board'][row][col] == 0:
                self.send_command({"type": "place", "row": row, "col": col})
        else:
            player_piece = self.player_id + 1

            if not self.selected_piece:
                if self.game_state['board'][row][col] == player_piece:
                    self.selected_piece = (row, col)
                    self.draw_board()
            else:
                from_row, from_col = self.selected_piece
                if from_row == row and from_col == col:
                    self.selected_piece = None
                    self.draw_board()
                elif self.game_state['board'][row][col] == 0 and abs(from_row - row) + abs(from_col - col) == 1:
                    self.send_command({
                        "type": "move",
                        "from_row": from_row, "from_col": from_col,
                        "to_row": row, "to_col": col
                    })
                    self.selected_piece = None
                elif self.game_state['board'][row][col] == player_piece:
                    self.selected_piece = (row, col)
                    self.draw_board()

    # Envia comando de passar turno
    def pass_turn(self):
        if messagebox.askyesno("Passar Turno", "Tem certeza que deseja passar o turno?"):
            self.send_command({"type": "pass"})

    # Envia comando de desistência
    def surrender(self):
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            self.send_command({"type": "surrender"})

    # Envia comandos gerais ao servidor
    def send_command(self, command):
        try:
            if self.server:
                response = self.server.send_command(self.player_id, command)
                if response:
                    self.update_game_state(response)
        except Exception as erro:
            print(f"Erro ao enviar comando: {erro}")
            messagebox.showerror("Erro", f"Erro de comunicação: {erro}")

    # Envia mensagem de chat
    def send_chat_message(self):
        message = self.msg_entry.get().strip()
        if message:
            try:
                if self.server:
                    self.server.send_chat_message(self.nickname, message)
                    self.msg_entry.delete(0, tk.END)
            except Exception as erro:
                print(f"Erro ao enviar chat: {erro}")

    # Inicia o loop principal da interface Tkinter
    def run(self):
        if hasattr(self, 'root') and self.root:
            try:
                self.root.mainloop()
            except Exception as erro:
                print(f"Erro na interface: {erro}")
        else:
            print("Interface não foi inicializada corretamente.")


# Inicialização do cliente
if __name__ == '__main__':
    try:
        client = SeegaClientPyro()
        client.run()
    except Exception as e:
        print(f"Erro fatal: {e}")
        input("Pressione Enter para sair...")
