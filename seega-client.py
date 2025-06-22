import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import Pyro5.api
import Pyro5.client
import Pyro5.errors


class SeegaClientPyro:
    """
    Cliente Pyro5 do jogo Seega.
    Gerencia a interface gráfica, a comunicação com o servidor e a lógica local de jogo.
    """

    def __init__(self):
        """Inicializa a interface e conecta ao servidor."""
        self.opponent_score_label = None
        self.chat_area = None
        self.msg_entry = None
        self.your_score_label = None
        self.score_frame = None
        self.pass_button = None
        self.surrender_button = None
        self.status_label = None
        self.canvas = None
        self.server = None
        self.player_id = None
        self.nickname = None
        self.current_turn = 0
        self.selected_piece = None
        self.game_state = None
        self.chat_messages = []
        self.popup_shown = False
        self.last_update_id = 0  # Controle incremental de atualização de estado
        self.last_chat_count = 0  # Controle incremental de atualização do chat

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
            'center': '#A0522D'
        }

        self.root = tk.Tk()
        self.root.title("Seega Pyro5")
        self.root.resizable(False, False)
        self.setup_ui()
        self.connect_to_server()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_loop()

    def connect_to_server(self):
        """Conecta ao servidor Pyro5 e registra o jogador."""
        try:
            ns = Pyro5.api.locate_ns()
            uri = ns.lookup("Seega.Server")
            self.server = Pyro5.api.Proxy(uri)
            nickname = simpledialog.askstring("Nickname", "Digite seu nickname:", parent=self.root)
            if not nickname:
                nickname = f"Jogador{round(time.time())}"
            response = self.server.register_player(nickname)
            if response['status'] == 'full':
                messagebox.showerror("Erro", "Servidor cheio!")
                self.root.destroy()
            else:
                self.player_id = response['player_id']
                self.nickname = nickname
                self.last_update_id = response['update_id']
                color_name = "Preto" if self.player_id == 0 else "Branco"
                self.root.title(f"Seega | {self.nickname} ({color_name})")
                self.add_system_message(f"Você entrou como jogador {self.player_id + 1}")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível localizar o servidor: {e}")
            self.root.destroy()

    def setup_ui(self):
        """Configura a interface gráfica principal do jogo."""
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        # Área do tabuleiro
        game_frame = tk.Frame(main_frame)
        game_frame.pack(side="left", padx=10)

        self.status_label = tk.Label(game_frame, text="Aguardando...", font=("Arial", 12))
        self.status_label.pack(pady=5)

        board_frame = tk.Frame(game_frame)
        board_frame.pack()

        self.canvas = tk.Canvas(board_frame, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE,
                                bg=self.COLORS['board_bg'])
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.surrender_button = tk.Button(game_frame, text="Desistir", command=self.surrender, state="disabled")
        self.surrender_button.pack(pady=10)

        self.pass_button = tk.Button(game_frame, text="Passar Turno", command=self.pass_turn, state="disabled")
        self.pass_button.pack(pady=5)

        # Área de chat e placar
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side="right", padx=10, fill="both")

        chat_label = tk.Label(chat_frame, text="Chat", font=("Arial", 12, "bold"))
        chat_label.pack(pady=5, padx=5)

        chat_bg_color = "#444444"
        self.chat_area = scrolledtext.ScrolledText(chat_frame, width=30, height=15, wrap=tk.WORD, state=tk.DISABLED,
                                                   font=("Arial", 11), bg=chat_bg_color)
        self.chat_area.pack(pady=5)

        msg_frame = tk.Frame(chat_frame)
        msg_frame.pack(fill="x", pady=5)

        self.msg_entry = tk.Entry(msg_frame, width=25)
        self.msg_entry.pack(side="left", padx=2)
        self.msg_entry.bind("<Return>", lambda e: self.send_chat_message())

        send_button = tk.Button(msg_frame, text="Enviar", command=self.send_chat_message)
        send_button.pack(side="right", padx=2)

        score_title = tk.Label(chat_frame, text="Placar", font=("Arial", 12, "bold"))
        score_title.pack(pady=5, padx=5)

        score_bg_color = "#444444"
        self.score_frame = tk.Frame(chat_frame, bg=score_bg_color, relief="groove", bd=2)
        self.score_frame.pack(pady=10, fill="x")

        self.your_score_label = tk.Label(self.score_frame, text="", font=("Arial", 12, "bold"), bg=score_bg_color)
        self.your_score_label.pack(anchor="w", pady=2, padx=5)

        self.opponent_score_label = tk.Label(self.score_frame, text="", font=("Arial", 12, "bold"), bg=score_bg_color)
        self.opponent_score_label.pack(anchor="w", pady=2, padx=5)

        self.draw_board()

    def draw_board(self):
        """Redesenha o tabuleiro completo."""
        self.canvas.delete("all")
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
                x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
                color = self.COLORS['cell_light'] if (row + col) % 2 == 0 else self.COLORS['cell_dark']
                if row == 2 and col == 2:
                    color = self.COLORS['center']
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

        if self.game_state:
            board = self.game_state['board']
            for row in range(self.BOARD_SIZE):
                for col in range(self.BOARD_SIZE):
                    cell = board[row][col]
                    x, y = col * self.CELL_SIZE + self.CELL_SIZE // 2, row * self.CELL_SIZE // 2 + self.CELL_SIZE // 2
                    if cell == 1:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, fill=self.COLORS['player1'],
                                                outline="gray", width=2)
                    elif cell == 2:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, fill=self.COLORS['player2'],
                                                outline="black", width=2)
                    elif cell == -1:
                        self.canvas.create_line(x - 20, y - 20, x + 20, y + 20, fill="red", width=3)
                        self.canvas.create_line(x + 20, y - 20, x - 20, y + 20, fill="red", width=3)

            if self.selected_piece:
                row, col = self.selected_piece
                x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
                x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.COLORS['highlight'], width=3)

    def update_loop(self):
        """Loop de atualização periódica do estado e do chat."""
        try:
            self.check_for_game_updates()
            self.check_for_new_chat()
        except Exception as e:
            print(f"Erro ao atualizar: {e}")
        self.root.after(500, self.update_loop)

    def check_for_game_updates(self):
        """Verifica se houve atualização do estado do jogo."""
        result = self.server.get_game_state_if_updated(self.last_update_id)
        if result['state']:
            self.game_state = result['state']
            self.last_update_id = result['update_id']
            self.update_game_state()

    def check_for_new_chat(self):
        """Busca apenas novas mensagens do chat."""
        new_msgs = self.server.get_chat_messages_if_updated(self.last_chat_count)
        if new_msgs:
            for msg in new_msgs:
                self.add_chat_message(msg['sender'], msg['message'])
            self.last_chat_count += len(new_msgs)

    def update_game_state(self):
        """Atualiza interface com novo estado do jogo."""
        state = self.game_state
        self.current_turn = state['current_turn']

        phase_text = "Colocação de Peças" if state['phase'] == 'placement' else "Movimentação"
        self.status_label.config(text=f"Fase: {phase_text}")

        if state['game_over']:
            if not self.popup_shown:
                if state['winner'] == self.player_id:
                    messagebox.showinfo("Fim de Jogo", "Você venceu! 🎉")
                else:
                    messagebox.showinfo("Fim de Jogo", "Você perdeu! 😢")
                self.popup_shown = True
            self.surrender_button.config(state=tk.DISABLED)
        else:
            if state['current_turn'] == self.player_id:
                self.status_label.config(text="Seu turno!", fg="green")
                self.surrender_button.config(state=tk.NORMAL)
            else:
                self.status_label.config(text="Turno do oponente...", fg="red")
                self.surrender_button.config(state=tk.DISABLED)

        nicknames = self.server.get_nicknames()
        opponent_id = 1 - self.player_id
        opponent_name = nicknames[opponent_id] if len(nicknames) > opponent_id else "Aguardando..."

        your_score = state['captured'][self.player_id]
        opponent_score = state['captured'][opponent_id]

        if self.player_id == 0:
            self.your_score_label.config(text=f"Você: {your_score}", fg="black")
            self.opponent_score_label.config(text=f"{opponent_name}: {opponent_score}", fg="white")
        else:
            self.your_score_label.config(text=f"Você: {your_score}", fg="white")
            self.opponent_score_label.config(text=f"{opponent_name}: {opponent_score}", fg="black")

        if self.player_id == self.current_turn and state['phase'] == 'movement' and not state['game_over']:
            self.pass_button.config(state=tk.NORMAL)
        else:
            self.pass_button.config(state=tk.DISABLED)

        self.draw_board()

    def on_canvas_click(self, event):
        """Lida com cliques do jogador no tabuleiro."""
        if not self.game_state or self.game_state['game_over']:
            return
        if self.current_turn != self.player_id:
            return
        col, row = event.x // self.CELL_SIZE, event.y // self.CELL_SIZE
        if not (0 <= row < 5 and 0 <= col < 5):
            return

        if self.game_state['phase'] == 'placement':
            if row == 2 and col == 2:
                return
            if self.game_state['board'][row][col] == 0:
                self.server.send_command(self.player_id, {'type': 'place', 'row': row, 'col': col})
        else:
            piece = self.player_id + 1
            if not self.selected_piece and self.game_state['board'][row][col] == piece:
                self.selected_piece = (row, col)
                self.draw_board()
            elif self.selected_piece:
                from_row, from_col = self.selected_piece
                if from_row == row and from_col == col:
                    self.selected_piece = None
                    self.draw_board()
                elif self.game_state['board'][row][col] == 0:
                    if (abs(from_row - row) == 1 and from_col == col) or (abs(from_col - col) == 1 and from_row == row):
                        self.server.send_command(self.player_id, {
                            'type': 'move',
                            'from_row': from_row,
                            'from_col': from_col,
                            'to_row': row,
                            'to_col': col
                        })
                        self.selected_piece = None
                elif self.game_state['board'][row][col] == piece:
                    self.selected_piece = (row, col)
                    self.draw_board()

    def send_chat_message(self):
        """Envia mensagem de chat ao servidor."""
        message = self.msg_entry.get().strip()
        if message:
            self.server.send_chat_message(self.player_id, message)
            self.msg_entry.delete(0, tk.END)

    def add_chat_message(self, sender, message):
        """Adiciona mensagem na interface do chat."""
        self.chat_area.config(state=tk.NORMAL)
        nicknames = self.server.get_nicknames()
        color = "yellow"
        if sender == nicknames[0]:
            color = "black"
        elif sender == nicknames[1]:
            color = "white"
        self.chat_area.tag_config(sender, foreground=color)
        self.chat_area.insert(tk.END, f"{sender}: {message}\n", sender)
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def add_system_message(self, message):
        """Adiciona mensagem do sistema no chat."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.tag_config("SISTEMA", foreground="yellow")
        self.chat_area.insert(tk.END, f"SISTEMA: {message}\n", "SISTEMA")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def pass_turn(self):
        """Envia comando de passar turno."""
        self.server.send_command(self.player_id, {'type': 'pass'})

    def surrender(self):
        """Envia comando de desistência."""
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            self.server.send_command(self.player_id, {'type': 'surrender'})

    def on_close(self):
        """Confirmação ao tentar fechar a janela."""
        if messagebox.askokcancel("Sair", "Tem certeza que deseja fechar o jogo?"):
            if not self.game_state or not self.game_state['game_over']:
                try:
                    self.server.send_command(self.player_id, {'type': 'surrender'})
                except Pyro5.errors.CommunicationError:
                    print("Falha ao comunicar com o servidor para desistir.")
            self.root.destroy()

    def run(self):
        """Inicia o loop principal da interface."""
        self.root.mainloop()


if __name__ == "__main__":
    client = SeegaClientPyro()
    client.run()
