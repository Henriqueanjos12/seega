import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import Pyro5.api


class SeegaClientPyro:
    """Cliente gráfico do jogo Seega com polling de estado (sem callback)."""

    def __init__(self):
        self.server = None
        self.player_id = None
        self.nickname = None
        self.game_state = None
        self.chat_messages = []
        self.popup_shown = False
        self.selected_piece = None

        self.CELL_SIZE = 80
        self.BOARD_SIZE = 5
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
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.connect_to_server():
            self.start_polling()
        else:
            self.root.destroy()

    def _setup_ui(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        game_frame = tk.Frame(main_frame)
        game_frame.pack(side="left", padx=10)

        self.status_label = tk.Label(game_frame, text="Aguardando...", font=("Arial", 12))
        self.status_label.pack(pady=5)

        self.canvas = tk.Canvas(
            game_frame, width=self.CELL_SIZE * self.BOARD_SIZE, height=self.CELL_SIZE * self.BOARD_SIZE,
            bg=self.COLORS['board_bg']
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        button_frame = tk.Frame(game_frame)
        button_frame.pack(pady=10)
        self.surrender_button = tk.Button(button_frame, text="Desistir", command=self.surrender, state="disabled")
        self.surrender_button.pack(side="left", padx=5)
        self.pass_button = tk.Button(button_frame, text="Passar Turno", command=self.pass_turn, state="disabled")
        self.pass_button.pack(side="left", padx=5)

        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side="right", padx=10, fill="both")

        tk.Label(chat_frame, text="Chat", font=("Arial", 12, "bold")).pack(pady=5)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, width=30, height=15, wrap=tk.WORD, font=("Arial", 11),
                                                   bg="#444444", fg="white", state=tk.DISABLED)
        self.chat_area.pack(pady=5)

        msg_frame = tk.Frame(chat_frame)
        msg_frame.pack(fill="x", pady=5)
        self.msg_entry = tk.Entry(msg_frame, width=25)
        self.msg_entry.pack(side="left", padx=2)
        self.msg_entry.bind("<Return>", lambda e: self.send_chat_message())
        tk.Button(msg_frame, text="Enviar", command=self.send_chat_message).pack(side="right", padx=2)

        tk.Label(chat_frame, text="Placar", font=("Arial", 12, "bold")).pack(pady=5)
        score_frame = tk.Frame(chat_frame, bg="#444444", relief="groove", bd=2)
        score_frame.pack(pady=5, fill="x")

        self.your_score_label = tk.Label(score_frame, text="Você: 0", font=("Arial", 12, "bold"), bg="#444444",
                                         fg="white")
        self.your_score_label.pack(anchor="w", pady=2, padx=5)
        self.opponent_score_label = tk.Label(score_frame, text="Oponente: 0", font=("Arial", 12, "bold"), bg="#444444",
                                             fg="white")
        self.opponent_score_label.pack(anchor="w", pady=2, padx=5)

        self.restart_button = tk.Button(chat_frame, text="Novo Jogo", command=self.restart_game, state="disabled")
        self.restart_button.pack(pady=10)

    def connect_to_server(self):
        try:
            ns = Pyro5.api.locate_ns()
            uri = ns.lookup("Seega.Server")
            self.server = Pyro5.api.Proxy(uri)

            nickname = simpledialog.askstring("Nickname", "Digite seu nickname:", parent=self.root)
            if not nickname:
                nickname = f"Jogador{round(time.time())}"

            response = self.server.register_player(nickname)
            if response['status'] == 'full':
                messagebox.showerror("Erro", "Servidor cheio! Máximo 2 jogadores.")
                return False

            self.player_id = response['player_id']
            self.nickname = nickname
            self.update_title()
            self.add_system_message(f"Conectado como {nickname}!")

            nicknames = self.server.get_nicknames()
            if len(nicknames) == 1:
                self.add_system_message("Aguardando segundo jogador...")
            else:
                self.add_system_message("Jogo iniciado!")
            return True
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível conectar:\n{e}")
            return False

    def update_title(self):
        color = "Preto" if self.player_id == 0 else "Branco"
        self.root.title(f"Seega | {self.nickname} ({color})")

    def start_polling(self):
        self.poll_server()

    def poll_server(self):
        try:
            full_state = self.server.get_full_state()
            self.update_all(full_state['state'], full_state['messages'])
        except Exception as e:
            print(f"Erro ao consultar servidor: {e}")
        self.root.after(500, self.poll_server)

    def update_all(self, state, messages):
        self.game_state = state
        self.chat_messages = messages
        self.update_game_state()
        self.update_chat()

    def update_game_state(self):
        if not self.game_state:
            return

        state = self.game_state
        phase_text = "Colocação" if state['phase'] == 'placement' else "Movimentação"

        if state['game_over']:
            if not self.popup_shown:
                winner_msg = "Você venceu! 🎉" if state['winner'] == self.player_id else "Você perdeu! 😢"
                self.popup_shown = True
                self.root.after(100, lambda: messagebox.showinfo("Fim de Jogo", winner_msg))
                self.restart_button.config(state="normal")

            self.status_label.config(text=f"Jogo Finalizado - {phase_text}", fg="blue")
            self.surrender_button.config(state="disabled")
            self.pass_button.config(state="disabled")
        else:
            if state['current_turn'] == self.player_id:
                self.status_label.config(text=f"Seu turno! - {phase_text}", fg="green")
                self.surrender_button.config(state="normal")
                if state['phase'] == 'movement':
                    self.pass_button.config(state="normal")
                else:
                    self.pass_button.config(state="disabled")
            else:
                self.status_label.config(text=f"Turno do oponente - {phase_text}", fg="red")
                self.surrender_button.config(state="disabled")
                self.pass_button.config(state="disabled")

        try:
            nicknames = self.server.get_nicknames()
            opponent_id = 1 - self.player_id
            opponent_name = nicknames[opponent_id] if len(nicknames) > opponent_id else "Aguardando..."

            your_color = "black" if self.player_id == 0 else "white"
            opponent_color = "white" if self.player_id == 0 else "black"

            self.your_score_label.config(
                text=f"Você: {state['captured'][self.player_id]}",
                fg=your_color
            )
            self.opponent_score_label.config(
                text=f"{opponent_name}: {state['captured'][opponent_id]}",
                fg=opponent_color
            )
        except Exception as e:
            print(f"Erro ao atualizar placar: {e}")

        self.draw_board()

    def update_chat(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete('1.0', tk.END)

        for msg in self.chat_messages:
            sender = msg['sender']
            message = msg['message']

            if sender == self.nickname:
                # Mensagem minha -> direita
                color = self.COLORS['player1'] if self.player_id == 0 else self.COLORS['player2']
                self.chat_area.tag_config('right', justify='right', foreground=color)
                self.chat_area.insert(tk.END, f"{message}\n", 'right')
            elif sender.startswith("[SISTEMA]"):
                # Mensagem de sistema
                self.chat_area.tag_config('center', justify='center', foreground="orange")
                self.chat_area.insert(tk.END, f"{sender}\n", 'center')
            else:
                # Mensagem do oponente -> esquerda
                opponent_id = 1 - self.player_id
                color = self.COLORS['player1'] if opponent_id == 0 else self.COLORS['player2']
                self.chat_area.tag_config('left', justify='left', foreground=color)
                self.chat_area.insert(tk.END, f"{message}\n", 'left')

        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def draw_board(self):
        if not self.game_state:
            return

        self.canvas.delete("all")

        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
                x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
                color = self.COLORS['cell_light'] if (row + col) % 2 == 0 else self.COLORS['cell_dark']
                if row == 2 and col == 2:
                    color = self.COLORS['center']
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

                piece = self.game_state['board'][row][col]
                cx, cy = x1 + self.CELL_SIZE // 2, y1 + self.CELL_SIZE // 2

                if piece == 1:
                    self.canvas.create_oval(cx - 25, cy - 25, cx + 25, cy + 25, fill=self.COLORS['player1'],
                                            outline="gray", width=2)
                elif piece == 2:
                    self.canvas.create_oval(cx - 25, cy - 25, cx + 25, cy + 25, fill=self.COLORS['player2'],
                                            outline="black", width=2)
                elif piece == -1:
                    self.canvas.create_line(cx - 20, cy - 20, cx + 20, cy + 20, fill="red", width=3)
                    self.canvas.create_line(cx + 20, cy - 20, cx - 20, cy + 20, fill="red", width=3)

        if self.selected_piece:
            row, col = self.selected_piece
            x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
            x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.COLORS['highlight'], width=3)

    def on_canvas_click(self, event):
        if not self.game_state or self.game_state['game_over']:
            return
        if self.game_state['current_turn'] != self.player_id:
            return

        col, row = event.x // self.CELL_SIZE, event.y // self.CELL_SIZE
        if not (0 <= row < 5 and 0 <= col < 5):
            return

        try:
            if self.game_state['phase'] == 'placement':
                if (row == 2 and col == 2) or self.game_state['board'][row][col] != 0:
                    return
                self.server.send_command(self.player_id, {'type': 'place', 'row': row, 'col': col})
            else:
                piece = self.player_id + 1
                if not self.selected_piece and self.game_state['board'][row][col] == piece:
                    self.selected_piece = (row, col)
                    self.draw_board()
                elif self.selected_piece:
                    from_row, from_col = self.selected_piece
                    if (row, col) == (from_row, from_col):
                        self.selected_piece = None
                        self.draw_board()
                    elif abs(from_row - row) + abs(from_col - col) == 1 and self.game_state['board'][row][col] == 0:
                        self.server.send_command(self.player_id, {
                            'type': 'move',
                            'from_row': from_row, 'from_col': from_col,
                            'to_row': row, 'to_col': col
                        })
                        self.selected_piece = None
        except Exception as e:
            print(f"Erro ao processar clique: {e}")

    def send_chat_message(self):
        msg = self.msg_entry.get().strip()
        if msg and self.server:
            try:
                self.server.send_chat_message(self.player_id, msg)
                self.msg_entry.delete(0, tk.END)
            except Exception as e:
                print(f"Erro ao enviar mensagem: {e}")

    def add_system_message(self, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.tag_config('center', justify='center', foreground="orange")
        self.chat_area.insert(tk.END, f"[SISTEMA] {message}\n", 'center')
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def pass_turn(self):
        try:
            self.server.send_command(self.player_id, {'type': 'pass'})
        except Exception as e:
            print(f"Erro ao passar turno: {e}")

    def surrender(self):
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            try:
                self.server.send_command(self.player_id, {'type': 'surrender'})
            except Exception as e:
                print(f"Erro ao desistir: {e}")

    def restart_game(self):
        if messagebox.askyesno("Novo Jogo", "Deseja reiniciar a partida?"):
            try:
                self.server.restart_game()
                self.popup_shown = False
                self.selected_piece = None
                self.restart_button.config(state="disabled")
            except Exception as e:
                print(f"Erro ao reiniciar jogo: {e}")

    def on_close(self):
        if messagebox.askokcancel("Sair", "Deseja sair do jogo?"):
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    client = SeegaClientPyro()
    client.run()