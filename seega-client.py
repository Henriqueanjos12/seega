import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from xmlrpc.client import ServerProxy


class SeegaClientRPC:
    def __init__(self, server_url='http://localhost:8000/'):
        self.server = ServerProxy(server_url, allow_none=True)
        self.nickname = None
        self.player_id = None
        self.game_state = None
        self.chat_messages = []
        self.selected_piece = None

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

        self.root = tk.Tk()
        self.root.title("Seega RPC")
        self.root.resizable(False, False)
        self.setup_ui()

        self.setup_connection()
        self.update_loop()

    def setup_connection(self):
        self.nickname = simpledialog.askstring("Nickname", "Digite seu nome:", parent=self.root)
        if not self.nickname:
            self.nickname = f"Jogador{round(time.time())}"
        self.player_id = self.server.register_client(self.nickname)
        if self.player_id == -1:
            messagebox.showerror("Erro", "Servidor cheio")
            self.root.destroy()
        else:
            self.server.set_ready(self.player_id)

    def setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        game_frame = tk.Frame(main_frame)
        game_frame.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(game_frame, text="Aguardando outro jogador...", font=("Arial", 12))
        self.status_label.pack(pady=5)

        board_frame = tk.Frame(game_frame)
        board_frame.pack()

        self.canvas = tk.Canvas(board_frame, width=self.CANVAS_SIZE, height=self.CANVAS_SIZE, bg=self.COLORS['board_bg'])
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.surrender_button = tk.Button(game_frame, text="Desistir", command=self.surrender, state=tk.DISABLED)
        self.surrender_button.pack(pady=10)

        self.pass_button = tk.Button(game_frame, text="Passar Turno", command=self.pass_turn, state=tk.DISABLED)
        self.pass_button.pack(pady=5)

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

        info_frame = tk.LabelFrame(chat_frame, text="Informações", padx=5, pady=5)
        info_frame.pack(fill=tk.X, pady=10)

        self.player_info_label = tk.Label(info_frame, text="Aguardando...", anchor="w")
        self.player_info_label.pack(fill=tk.X)

        self.opponent_info_label = tk.Label(info_frame, text="Aguardando oponente...", anchor="w")
        self.opponent_info_label.pack(fill=tk.X)

        self.phase_label = tk.Label(info_frame, text="Fase: Preparação", anchor="w")
        self.phase_label.pack(fill=tk.X)

        self.draw_board()

    def draw_board(self):
        self.canvas.delete("all")
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

        if self.game_state:
            board = self.game_state['board']
            for row in range(self.BOARD_SIZE):
                for col in range(self.BOARD_SIZE):
                    cell_value = board[row][col]
                    x = col * self.CELL_SIZE + self.CELL_SIZE // 2
                    y = row * self.CELL_SIZE + self.CELL_SIZE // 2
                    if cell_value == 1:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, fill=self.COLORS['player1'], outline="gray", width=2)
                    elif cell_value == 2:
                        self.canvas.create_oval(x - 25, y - 25, x + 25, y + 25, fill=self.COLORS['player2'], outline="black", width=2)
                    elif cell_value == -1:
                        self.canvas.create_line(x - 20, y - 20, x + 20, y + 20, fill="red", width=3)
                        self.canvas.create_line(x + 20, y - 20, x - 20, y + 20, fill="red", width=3)

            if self.selected_piece:
                row, col = self.selected_piece
                x1 = col * self.CELL_SIZE
                y1 = row * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.COLORS['highlight'], width=3)

    def update_loop(self):
        try:
            state = self.server.get_game_state(self.player_id)
            if state:
                self.update_game_state(state)
            messages = self.server.get_chat_messages()
            for msg in messages[len(self.chat_messages):]:
                self.chat_area.config(state=tk.NORMAL)
                self.chat_area.insert(tk.END, f"{msg['sender']}: {msg['message']}\n")
                self.chat_area.see(tk.END)
                self.chat_area.config(state=tk.DISABLED)
                self.chat_messages.append(msg)
        except Exception as e:
            print("Erro RPC:", e)
        self.root.after(500, self.update_loop)

    def update_game_state(self, state):
        self.game_state = state
        self.current_turn = state['current_turn']

        if state['phase'] == 'placement':
            self.phase_label.config(text=f"Fase: Colocação de peças")
        else:
            self.phase_label.config(text=f"Fase: Movimentação")

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

        if self.player_id == 0:
            self.player_info_label.config(text=f"Você: {self.nickname} (Preto) - Capturadas: {state['captured'][0]}")
            self.opponent_info_label.config(text=f"Oponente (Branco) - Capturadas: {state['captured'][1]}")
        else:
            self.player_info_label.config(text=f"Você: {self.nickname} (Branco) - Capturadas: {state['captured'][1]}")
            self.opponent_info_label.config(text=f"Oponente (Preto) - Capturadas: {state['captured'][0]}")

        self.draw_board()

        if self.player_id == self.current_turn and self.game_state['phase'] == 'movement' and not self.game_state['game_over']:
            self.pass_button.config(state=tk.NORMAL)
        else:
            self.pass_button.config(state=tk.DISABLED)

    def on_canvas_click(self, event):
        if not self.game_state or self.game_state['game_over']:
            return

        if self.current_turn != self.player_id:
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
            if not self.selected_piece and self.game_state['board'][row][col] == player_piece:
                self.selected_piece = (row, col)
                self.draw_board()
            elif self.selected_piece:
                from_row, from_col = self.selected_piece
                if from_row == row and from_col == col:
                    self.selected_piece = None
                    self.draw_board()
                elif self.game_state['board'][row][col] == 0 and (abs(from_row - row) + abs(from_col - col) == 1):
                    self.send_command({"type": "move", "from_row": from_row, "from_col": from_col, "to_row": row, "to_col": col})
                    self.selected_piece = None
                elif self.game_state['board'][row][col] == player_piece:
                    self.selected_piece = (row, col)
                    self.draw_board()

    def pass_turn(self):
        self.send_command({"type": "pass"})

    def surrender(self):
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            self.send_command({"type": "surrender"})

    def send_command(self, command):
        try:
            self.server.send_command(self.player_id, command)
        except Exception as e:
            print("Erro ao enviar comando:", e)

    def send_chat_message(self):
        message = self.msg_entry.get().strip()
        if message:
            try:
                self.server.send_chat_message(self.nickname, message)
                self.msg_entry.delete(0, tk.END)
            except Exception as e:
                print("Erro ao enviar chat:", e)

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    client = SeegaClientRPC()
    client.run()
