"""
Cliente gráfico para o jogo Seega usando Pyro5 e Tkinter.

Este módulo implementa uma interface gráfica para o jogo Seega, conectando-se
a um servidor remoto via Pyro5. O cliente utiliza polling para sincronizar
o estado do jogo e inclui funcionalidades de chat em tempo real.
"""

import time
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import Pyro5.api


class SeegaClientPyro:
    """Cliente gráfico do jogo Seega com polling de estado (sem callback)."""

    def __init__(self):
        """
        Inicializa o cliente Seega.

        Configura a interface gráfica, estabelece conexão com o servidor
        e inicia o sistema de polling para sincronização de estado.
        """
        # Atributos de conexão e estado do jogo
        self.server = None
        self.player_id = None
        self.nickname = None
        self.game_state = None
        self.chat_messages = []
        self.popup_shown = False
        self.selected_piece = None

        # Configurações visuais do tabuleiro
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

        # Configuração da janela principal
        self.root = tk.Tk()
        self.root.title("Seega Pyro5")
        self.root.resizable(False, False)
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Conexão com servidor e início do sistema de polling
        if self.connect_to_server():
            self.start_polling()
        else:
            self.root.destroy()

    def _setup_ui(self):
        """
        Configura toda a interface gráfica do cliente.

        Cria e organiza todos os widgets necessários: tabuleiro, chat,
        botões de controle e área de status.
        """
        # Frame principal que contém todos os elementos
        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        # === SEÇÃO DO JOGO (lado esquerdo) ===
        game_frame = tk.Frame(main_frame)
        game_frame.pack(side="left", padx=10)

        # Label de status do jogo
        self.status_label = tk.Label(game_frame, text="Aguardando...",
                                   font=("Arial", 12))
        self.status_label.pack(pady=5)

        # Canvas para desenhar o tabuleiro
        self.canvas = tk.Canvas(
            game_frame,
            width=self.CELL_SIZE * self.BOARD_SIZE,
            height=self.CELL_SIZE * self.BOARD_SIZE,
            bg=self.COLORS['board_bg']
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Frame para botões de controle do jogo
        button_frame = tk.Frame(game_frame)
        button_frame.pack(pady=10)

        self.surrender_button = tk.Button(button_frame, text="Desistir",
                                        command=self.surrender, state="disabled")
        self.surrender_button.pack(side="left", padx=5)

        self.pass_button = tk.Button(button_frame, text="Passar Turno",
                                   command=self.pass_turn, state="disabled")
        self.pass_button.pack(side="left", padx=5)

        # === SEÇÃO DO CHAT (lado direito) ===
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side="right", padx=10, fill="both")

        # Título da área de chat
        tk.Label(chat_frame, text="Chat",
                font=("Arial", 12, "bold")).pack(pady=5)

        # Área scrollável para mensagens do chat
        self.chat_area = scrolledtext.ScrolledText(
            chat_frame, width=30, height=15, wrap=tk.WORD,
            font=("Arial", 11), bg="#444444", fg="white",
            state=tk.DISABLED
        )
        self.chat_area.pack(pady=5)

        # Frame para entrada de mensagens
        msg_frame = tk.Frame(chat_frame)
        msg_frame.pack(fill="x", pady=5)

        self.msg_entry = tk.Entry(msg_frame, width=25)
        self.msg_entry.pack(side="left", padx=2)
        self.msg_entry.bind("<Return>", lambda e: self.send_chat_message())

        tk.Button(msg_frame, text="Enviar",
                 command=self.send_chat_message).pack(side="right", padx=2)

        # === SEÇÃO DO PLACAR ===
        tk.Label(chat_frame, text="Placar",
                font=("Arial", 12, "bold")).pack(pady=5)

        score_frame = tk.Frame(chat_frame, bg="#444444",
                              relief="groove", bd=2)
        score_frame.pack(pady=5, fill="x")

        # Labels do placar para cada jogador
        self.your_score_label = tk.Label(
            score_frame, text="Você: 0", font=("Arial", 12, "bold"),
            bg="#444444", fg="white"
        )
        self.your_score_label.pack(anchor="w", pady=2, padx=5)

        self.opponent_score_label = tk.Label(
            score_frame, text="Oponente: 0", font=("Arial", 12, "bold"),
            bg="#444444", fg="white"
        )
        self.opponent_score_label.pack(anchor="w", pady=2, padx=5)

        # Botão para reiniciar o jogo
        self.restart_button = tk.Button(
            chat_frame, text="Novo Jogo", command=self.restart_game,
            state="disabled"
        )
        self.restart_button.pack(pady=10)

    def connect_to_server(self):
        """
        Estabelece conexão com o servidor Seega via Pyro5.

        Returns:
            bool: True se a conexão foi estabelecida com sucesso, False caso contrário.
        """
        try:
            # Localiza o servidor através do name server do Pyro5
            ns = Pyro5.api.locate_ns()
            uri = ns.lookup("Seega.Server")
            self.server = Pyro5.api.Proxy(uri)

            # Solicita nickname do jogador
            nickname = simpledialog.askstring(
                "Nickname", "Digite seu nickname:", parent=self.root
            )
            if not nickname:
                nickname = f"Jogador{round(time.time())}"

            # Registra o jogador no servidor
            response = self.server.register_player(nickname)
            if response['status'] == 'full':
                messagebox.showerror("Erro", "Servidor cheio! Máximo 2 jogadores.")
                return False

            # Armazena informações do jogador
            self.player_id = response['player_id']
            self.nickname = nickname
            self.update_title()
            self.add_system_message(f"Conectado como {nickname}!")

            # Verifica quantos jogadores estão conectados
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
        """Atualiza o título da janela com informações do jogador."""
        color = "Preto" if self.player_id == 0 else "Branco"
        self.root.title(f"Seega | {self.nickname} ({color})")

    def start_polling(self):
        """Inicia o sistema de polling para sincronização com o servidor."""
        self.poll_server()

    def poll_server(self):
        """
        Consulta periodicamente o servidor para obter atualizações.

        Este método é chamado recursivamente a cada 500ms para manter
        o cliente sincronizado com o estado do servidor.
        """
        try:
            # Verifica se ainda há conexão com o servidor
            if not self.server:
                return

            # Obtém estado completo do jogo e mensagens do chat
            full_state = self.server.get_full_state()
            self.update_all(full_state['state'], full_state['messages'])
        except Exception as e:
            print(f"Erro ao consultar servidor: {e}")
            import traceback
            traceback.print_exc()

        # Agenda próxima consulta
        self.root.after(500, self.poll_server)

    def update_all(self, state, messages):
        """
        Atualiza todos os componentes da interface com novos dados.

        Args:
            state (dict): Estado atual do jogo.
            messages (list): Lista de mensagens do chat.
        """
        self.game_state = state
        self.chat_messages = messages
        self.update_game_state()
        self.update_chat()

    def update_game_state(self):
        """
        Atualiza a interface com base no estado atual do jogo.

        Controla a exibição de status, habilitação de botões e
        exibição de mensagens de fim de jogo.
        """
        if not self.game_state:
            return

        state = self.game_state
        phase_text = "Colocação" if state['phase'] == 'placement' else "Movimentação"

        # Verifica se o jogo terminou
        if state['game_over']:
            if not self.popup_shown:
                winner_msg = ("Você venceu! 🎉" if state['winner'] == self.player_id
                            else "Você perdeu! 😢")
                self.popup_shown = True
                self.root.after(100, lambda: messagebox.showinfo("Fim de Jogo", winner_msg))
                self.restart_button.config(state="normal")

            # Atualiza interface para estado de jogo finalizado
            self.status_label.config(text=f"Jogo Finalizado - {phase_text}", fg="blue")
            self.surrender_button.config(state="disabled")
            self.pass_button.config(state="disabled")
        else:
            # Atualiza interface baseada no turno atual
            if state['current_turn'] == self.player_id:
                self.status_label.config(text=f"Seu turno! - {phase_text}", fg="green")
                self.surrender_button.config(state="normal")

                # Botão de passar turno só é habilitado na fase de movimento
                if state['phase'] == 'movement':
                    self.pass_button.config(state="normal")
                else:
                    self.pass_button.config(state="disabled")
            else:
                self.status_label.config(text=f"Turno do oponente - {phase_text}", fg="red")
                self.surrender_button.config(state="disabled")
                self.pass_button.config(state="disabled")

        # Atualiza placar dos jogadores
        try:
            nicknames = self.server.get_nicknames()
            opponent_id = 1 - self.player_id

            # Verifica se existe oponente antes de acessar a lista
            if len(nicknames) > opponent_id:
                opponent_name = nicknames[opponent_id]
            else:
                opponent_name = "Aguardando..."

            # Define cores baseadas no ID do jogador
            your_color = "black" if self.player_id == 0 else "white"
            opponent_color = "white" if self.player_id == 0 else "black"

            # Atualiza labels do placar
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
            import traceback
            traceback.print_exc()

        # Redesenha o tabuleiro
        self.draw_board()

    def update_chat(self):
        """
        Atualiza a área de chat com as mensagens mais recentes.

        Aplica formatação diferente para mensagens próprias, do oponente
        e do sistema, com alinhamento e cores apropriadas.
        """
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete('1.0', tk.END)

        for msg in self.chat_messages:
            sender = msg['sender']
            message = msg['message']

            if sender == self.nickname:
                # Mensagem própria -> alinhada à direita
                color = (self.COLORS['player1'] if self.player_id == 0
                        else self.COLORS['player2'])
                self.chat_area.tag_config('right', justify='right', foreground=color)
                self.chat_area.insert(tk.END, f"{message}\n", 'right')

            elif sender.startswith("[SISTEMA]"):
                # Mensagem de sistema -> centralizada em laranja
                self.chat_area.tag_config('center', justify='center', foreground="orange")
                self.chat_area.insert(tk.END, f"{sender}\n", 'center')

            else:
                # Mensagem do oponente -> alinhada à esquerda
                opponent_id = 1 - self.player_id
                color = (self.COLORS['player1'] if opponent_id == 0
                        else self.COLORS['player2'])
                self.chat_area.tag_config('left', justify='left', foreground=color)
                self.chat_area.insert(tk.END, f"{message}\n", 'left')

        # Desabilita edição e rola para o final
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def draw_board(self):
        """
        Desenha o tabuleiro de jogo no canvas.

        Renderiza o tabuleiro 5x5, peças dos jogadores, célula central
        especial e destaque da peça selecionada.
        """
        if not self.game_state:
            return

        # Limpa o canvas
        self.canvas.delete("all")

        # Desenha cada célula do tabuleiro
        for row in range(self.BOARD_SIZE):
            for col in range(self.BOARD_SIZE):
                # Calcula coordenadas da célula
                x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
                x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE

                # Define cor da célula (padrão xadrez)
                color = (self.COLORS['cell_light'] if (row + col) % 2 == 0
                        else self.COLORS['cell_dark'])

                # Célula central tem cor especial
                if row == 2 and col == 2:
                    color = self.COLORS['center']

                # Desenha a célula
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

                # Desenha peças se houver
                piece = self.game_state['board'][row][col]
                cx, cy = x1 + self.CELL_SIZE // 2, y1 + self.CELL_SIZE // 2

                if piece == 1:
                    # Peça do jogador 1 (preta)
                    self.canvas.create_oval(
                        cx - 25, cy - 25, cx + 25, cy + 25,
                        fill=self.COLORS['player1'], outline="gray", width=2
                    )
                elif piece == 2:
                    # Peça do jogador 2 (branca)
                    self.canvas.create_oval(
                        cx - 25, cy - 25, cx + 25, cy + 25,
                        fill=self.COLORS['player2'], outline="black", width=2
                    )
                elif piece == -1:
                    # Peça capturada (X vermelho)
                    self.canvas.create_line(
                        cx - 20, cy - 20, cx + 20, cy + 20, fill="red", width=3
                    )
                    self.canvas.create_line(
                        cx + 20, cy - 20, cx - 20, cy + 20, fill="red", width=3
                    )

        # Destaca peça selecionada
        if self.selected_piece:
            row, col = self.selected_piece
            x1, y1 = col * self.CELL_SIZE, row * self.CELL_SIZE
            x2, y2 = x1 + self.CELL_SIZE, y1 + self.CELL_SIZE
            self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=self.COLORS['highlight'], width=3
            )

    def on_canvas_click(self, event):
        """
        Processa cliques no tabuleiro para jogadas.

        Args:
            event: Evento de clique do mouse contendo coordenadas.

        Gerencia tanto a fase de colocação quanto a de movimento das peças,
        incluindo seleção e movimentação.
        """
        # Verifica se é possível fazer jogadas
        if not self.game_state or self.game_state['game_over']:
            return
        if self.game_state['current_turn'] != self.player_id:
            return

        # Verifica se o player_id é válido
        if self.player_id is None or self.player_id not in [0, 1]:
            print(f"Player ID inválido: {self.player_id}")
            return

        # Converte coordenadas do clique para posição no tabuleiro
        col, row = event.x // self.CELL_SIZE, event.y // self.CELL_SIZE
        if not (0 <= row < 5 and 0 <= col < 5):
            return

        # Verifica se há servidor conectado
        if not self.server:
            return

        try:
            # Log para debug
            print(f"Clique processado: row={row}, col={col}, player_id={self.player_id}")
            print(f"Fase do jogo: {self.game_state['phase']}")
            print(f"Estado do tabuleiro na posição [{row}][{col}]: {self.game_state['board'][row][col]}")

            if self.game_state['phase'] == 'placement':
                # Fase de colocação: coloca peça em célula vazia (exceto centro)
                if (row == 2 and col == 2) or self.game_state['board'][row][col] != 0:
                    print(f"Posição inválida para colocação: centro={row==2 and col==2}, ocupada={self.game_state['board'][row][col] != 0}")
                    return  # Posição inválida para colocação

                command = {'type': 'place', 'row': row, 'col': col}
                print(f"Enviando comando de colocação: {command}")
                self.server.send_command(self.player_id, command)

            else:
                # Fase de movimento: seleciona peça própria ou move peça selecionada
                piece = self.player_id + 1
                print(f"Procurando peça do tipo: {piece}")

                if not self.selected_piece and self.game_state['board'][row][col] == piece:
                    # Seleciona uma peça própria
                    print(f"Selecionando peça em ({row}, {col})")
                    self.selected_piece = (row, col)
                    self.draw_board()

                elif self.selected_piece:
                    from_row, from_col = self.selected_piece
                    print(f"Peça selecionada: ({from_row}, {from_col})")

                    if (row, col) == (from_row, from_col):
                        # Clique na mesma peça: deseleciona
                        print("Deselecionando peça")
                        self.selected_piece = None
                        self.draw_board()

                    elif (abs(from_row - row) + abs(from_col - col) == 1 and
                          self.game_state['board'][row][col] == 0):
                        # Movimento válido: adjacente e célula vazia
                        command = {
                            'type': 'move',
                            'from_row': from_row, 'from_col': from_col,
                            'to_row': row, 'to_col': col
                        }
                        print(f"Enviando comando de movimento: {command}")
                        self.server.send_command(self.player_id, command)
                        self.selected_piece = None
                    else:
                        print(f"Movimento inválido: distância={abs(from_row - row) + abs(from_col - col)}, destino_ocupado={self.game_state['board'][row][col] != 0}")

        except Exception as e:
            print(f"Erro ao processar clique: {e}")
            print(f"Estado atual do jogo: {self.game_state}")
            print(f"Player ID: {self.player_id}")
            import traceback
            traceback.print_exc()

    def send_chat_message(self):
        """
        Envia mensagem de chat para o servidor.

        Obtém o texto do campo de entrada, envia para o servidor
        e limpa o campo após o envio.
        """
        msg = self.msg_entry.get().strip()
        if msg and self.server:
            try:
                self.server.send_chat_message(self.player_id, msg)
                self.msg_entry.delete(0, tk.END)
            except Exception as e:
                print(f"Erro ao enviar mensagem: {e}")

    def add_system_message(self, message):
        """
        Adiciona mensagem do sistema ao chat.

        Args:
            message (str): Mensagem a ser exibida.

        Mensagens do sistema são centralizadas e exibidas em laranja.
        """
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.tag_config('center', justify='center', foreground="orange")
        self.chat_area.insert(tk.END, f"[SISTEMA] {message}\n", 'center')
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)

    def pass_turn(self):
        """
        Envia comando para passar o turno.

        Funcionalidade disponível apenas na fase de movimento
        quando o jogador não pode ou não quer fazer um movimento.
        """
        try:
            self.server.send_command(self.player_id, {'type': 'pass'})
        except Exception as e:
            print(f"Erro ao passar turno: {e}")

    def surrender(self):
        """
        Processa desistência do jogador.

        Exibe confirmação antes de enviar comando de desistência
        para o servidor.
        """
        if messagebox.askyesno("Desistir", "Tem certeza que deseja desistir?"):
            try:
                self.server.send_command(self.player_id, {'type': 'surrender'})
            except Exception as e:
                print(f"Erro ao desistir: {e}")

    def restart_game(self):
        """
        Reinicia uma nova partida.

        Solicita confirmação do usuário e envia comando de reinício
        para o servidor, resetando o estado local.
        """
        if messagebox.askyesno("Novo Jogo", "Deseja reiniciar a partida?"):
            try:
                self.server.restart_game()
                # Reset do estado local
                self.popup_shown = False
                self.selected_piece = None
                self.restart_button.config(state="disabled")
            except Exception as e:
                print(f"Erro ao reiniciar jogo: {e}")

    def on_close(self):
        """
        Processa fechamento da janela.

        Exibe confirmação antes de fechar a aplicação.
        """
        if messagebox.askokcancel("Sair", "Deseja sair do jogo?"):
            self.root.destroy()

    def run(self):
        """
        Inicia o loop principal da interface gráfica.

        Este método deve ser chamado após a inicialização para
        começar a execução da aplicação.
        """
        self.root.mainloop()


if __name__ == "__main__":
    # Cria e executa o cliente Seega
    client = SeegaClientPyro()
    client.run()