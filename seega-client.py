import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import Pyro5.api
import Pyro5.errors


class SeegaClientPyro:
    """
    Cliente Pyro5 do jogo Seega.
    Responsável por interface gráfica (Tkinter), comunicação com o servidor e atualizações.
    """

    def __init__(self):
        """Inicializa interface e conecta ao servidor."""
        self.server = None
        self.player_id = None
        self.nickname = None
        self.current_turn = 0
        self.selected_piece = None
        self.game_state = None
        self.popup_shown = False

        # Interface gráfica
        self.root = tk.Tk()
        self.root.title("Seega Pyro5")
        self.root.resizable(False, False)
        self._setup_colors()
        self._setup_board()
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.connect_to_server()
        self.update_loop()

    def _setup_colors(self):
        """Define as cores do tabuleiro e interface."""
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

    def _setup_board(self):
        """Inicia estado visual do tabuleiro."""
        self.canvas = None
        self.status_label = None
        self.pass_button = None
        self.surrender_button = None
        self.chat_area = None
        self.msg_entry = None
        self.your_score_label = None
        self.opponent_score_label = None

    def _setup_ui(self):
        """Monta layout Tkinter."""
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        # Tabuleiro à esquerda
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

        button_frame = tk.Frame(game_frame)
        button_frame.pack(pady=10)

        self.surrender_button = tk.Button(button_frame, text="Desistir", command=self.surrender, state="disabled")
        self.surrender_button.pack(side="left", padx=5)

        self.pass_button = tk.Button(button_frame, text="Passar Turno", command=self.pass_turn, state="disabled")
        self.pass_button.pack(side="left", padx=5)

        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side="right", padx=10, fill="both")

        tk.Label(chat_frame, text="Chat", font=("Arial", 12, "bold")).pack(pady=5, padx=5)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, width=30, height=15, wrap=tk.WORD,
                                                   font=("Arial", 11), bg="#444444", state=tk.DISABLED)
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

        self.your_score_label = tk.Label(score_frame, text="", font=("Arial", 12, "bold"), bg="#444444")
        self.your_score_label.pack(anchor="w", pady=2, padx=5)

        self.opponent_score_label = tk.Label(score_frame, text="", font=("Arial", 12, "bold"), bg="#444444")
        self.opponent_score_label.pack(anchor="w", pady=2, padx=5)

        self.restart_button = tk.Button(chat_frame, text="Novo Jogo", command=self.restart_game, state="disabled")
        self.restart_button.pack(pady=10)

        self.draw_board()

    def connect_to_server(self):
        """Conecta via Pyro5 e registra nickname."""
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
                self.update_title()
                self.add_system_message(f"Você entrou como jogador {self.player_id + 1}.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível conectar: {e}")
            self.root.destroy()

    def update_title(self):
        """Atualiza título da janela com o jogador."""
        color = "Preto" if self.player_id == 0 else "Branco"
        self.root.title(f"Seega | {self.nickname} ({color})")

    def update_loop(self):
        """Loop contínuo de atualização de estado do jogo."""
        try:
            self.game_state = self.server.get_game_state()
            self.update_game_state()
            self.update_chat()
        except Pyro5.errors.CommunicationError:
            print("Falha de comunicação com o servidor.")
        except Exception as e:
            print(f"Erro inesperado: {e}")
        self.root.after(500, self.update_loop)

    def update_game_state(self):
        """Atualiza interface a partir do estado atual do servidor."""
        state = self.game_state
        phase = "Colocação" if state['phase'] == 'placement' else "Movimentação"
        self.status_label.config(text=f"Fase: {phase}")

        if state['game_over']:
            if not self.popup_shown:
                if state['winner'] == self.player_id:
                    messagebox.showinfo("Fim de Jogo", "Você venceu! 🎉")
                else:
                    messagebox.showinfo("Fim de Jogo", "Você perdeu! 😢")
                self.popup_shown = True
                self.restart_button.config(state="normal")
            self.surrender_button.config(state="disabled")
            self.pass_button.config(state="disabled")
        else:
            if state['current_turn'] == self.player_id:
                self.status_label.config(text="Seu turno!", fg="green")
                self.surrender_button.config(state="normal")
                if state['phase'] == 'movement':
                    self.pass_button.config(state="normal")
            else:
                self.status_label.config(text="Turno do oponente...", fg="red")
                self.surrender_button.config(state="disabled")
                self.pass_button.config(state="disabled")

        nicknames = self.server.get_nicknames()
        opponent = 1 - self.player_id
        opponent_name = nicknames[opponent] if len(nicknames) > opponent else "Aguardando..."

        # Agora com cores corretas
        if self.player_id == 0:
            self.your_score_label.config(text=f"Você: {state['captured'][self.player_id]}", fg="black")
            self.opponent_score_label.config(text=f"{opponent_name}: {state['captured'][opponent]}", fg="white")
        else:
            self.your_score_label.config(text=f"Você: {state['captured'][self.player_id]}", fg="white")
            self.opponent_score_label.config(text=f"{opponent_name}: {state['captured'][opponent]}", fg="black")

        self.draw_board()

    def update_chat(self):
        """Atualiza chat com novas mensagens."""
        messages = self.server.get_chat_messages()
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete('1.0', tk.END)
        nicknames = self.server.get_nicknames()
        for msg in messages:
            color = "yellow"
            if msg['sender'] == nicknames[0]:
                color = "black"
            elif len(nicknames) > 1 and msg['sender'] == nicknames[1]:
                color = "white"
            self.chat_area.tag_config(msg['sender'], foreground=color)
            self.chat_area.insert(tk.END, f"{msg['sender']}: {msg['message']}\n", msg['sender'])
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def draw_board(self):
        """Redesenha o tabuleiro com peças e seleções."""
        self.canvas.delete("all")
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
                x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
                color = self.COLORS['cell_light'] if (row + col) % 2 == 0 else self.COLORS['cell_dark']
                if row == 2 and col == 2:
                    color = self.COLORS['center']
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

                piece = self.game_state['board'][row][col] if self.game_state else 0
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
        """Processa clique no tabuleiro."""
        if not self.game_state or self.game_state['game_over']:
            return
        if self.game_state['current_turn'] != self.player_id:
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
                if (row, col) == (from_row, from_col):
                    self.selected_piece = None
                    self.draw_board()
                elif self.valid_move(from_row, from_col, row, col):
                    self.server.send_command(self.player_id, {
                        'type': 'move', 'from_row': from_row, 'from_col': from_col,
                        'to_row': row, 'to_col': col
                    })
                    self.selected_piece = None

    def valid_move(self, from_row, from_col, to_row, to_col):
        """Valida se o movimento é válido (apenas ortogonal e uma casa)."""
        return (abs(from_row - to_row) == 1 and from_col == to_col) or \
            (abs(from_col - to_col) == 1 and from_row == to_row)

    def send_chat_message(self):
        """Envia mensagem de chat."""
        msg = self.msg_entry.get().strip()
        if msg:
            self.server.send_chat_message(self.player_id, msg)
            self.msg_entry.delete(0, tk.END)

    def add_system_message(self, message):
        """Adiciona mensagem de sistema no chat."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"SISTEMA: {message}\n", "system")
        self.chat_area.tag_config("system", foreground="yellow")
        self.chat_area.config(state=tk.DISABLED)

    def pass_turn(self):
        """Solicita passagem de turno."""
        self.server.send_command(self.player_id, {'type': 'pass'})

    def surrender(self):
        """Solicita desistência."""
        if messagebox.askyesno("Desistir", "Deseja desistir?"):
            self.server.send_command(self.player_id, {'type': 'surrender'})

    def restart_game(self):
        """Solicita reinício do jogo no servidor."""
        if messagebox.askyesno("Novo Jogo", "Deseja reiniciar a partida?"):
            self.server.restart_game()
            self.popup_shown = False
            self.selected_piece = None
            self.restart_button.config(state="disabled")

    def on_close(self):
        """Confirmação de saída."""
        if messagebox.askokcancel("Sair", "Deseja sair do jogo?"):
            try:
                self.server.send_command(self.player_id, {'type': 'surrender'})
            except Pyro5.errors.CommunicationError:
                pass
            self.root.destroy()

    def run(self):
        """Inicia interface principal."""
        self.root.mainloop()


if __name__ == "__main__":
    client = SeegaClientPyro()
    client.run()
