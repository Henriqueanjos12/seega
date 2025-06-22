import Pyro5.api
import Pyro5.server
import threading
import subprocess
import sys
import time
import socket
from seega_model import SeegaGame


@Pyro5.api.expose
class SeegaServer:
    """Servidor Pyro5 responsável por gerenciar o jogo Seega."""

    def __init__(self):
        self.lock = threading.Lock()  # Controle de concorrência
        self.nicknames = []  # Lista de jogadores conectados
        self.game = SeegaGame()  # Instância do modelo (MVC)

    def register_player(self, nickname):
        """Registra um jogador e inicia o jogo se ambos conectados."""
        with self.lock:
            if len(self.nicknames) >= 2:
                return {'status': 'full'}
            self.nicknames.append(nickname)
            player_id = len(self.nicknames) - 1
            print(f">>> Jogador {player_id + 1} conectado: {nickname}")
            if len(self.nicknames) == 2:
                print(">>> Ambos os jogadores conectados. Iniciando o jogo!")
                self.game.start_game()
            return {'status': 'ok', 'player_id': player_id}

    def get_nicknames(self):
        """Retorna a lista de apelidos registrados."""
        return self.nicknames

    def get_game_state(self):
        """Retorna o estado atual do jogo para o cliente."""
        return self.game.get_state()

    def send_command(self, player_id, command):
        """Recebe comandos dos clientes e executa no modelo."""
        with self.lock:
            match command['type']:
                case 'place':
                    self.game.place_piece(player_id, command['row'], command['col'])
                case 'move':
                    self.game.move_piece(player_id, command['from_row'], command['from_col'],
                                         command['to_row'], command['to_col'])
                case 'pass':
                    self.game.pass_turn(player_id)
                case 'surrender':
                    self.game.surrender(player_id)

    def get_chat_messages(self):
        """Retorna as mensagens do chat."""
        return self.game.chat_messages

    def send_chat_message(self, player_id, message):
        """Adiciona uma nova mensagem ao chat."""
        sender = self.nicknames[player_id]
        self.game.chat_messages.append({'sender': sender, 'message': message})

    def restart_game(self):
        """Reinicia o jogo mantendo os mesmos jogadores."""
        with self.lock:
            self.game.reset()
            if len(self.nicknames) == 2:
                self.game.start_game()


def is_port_open(port):
    """Verifica se a porta do NameServer já está ativa."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def main():
    """Inicia o servidor Pyro5 e registra no Name Server."""
    if not is_port_open(9090):
        print("Name Server não encontrado. Iniciando...")
        subprocess.Popen([sys.executable, "-m", "Pyro5.nameserver"])
        time.sleep(2)

    daemon = Pyro5.server.Daemon()
    ns = Pyro5.api.locate_ns()
    server = SeegaServer()
    uri = daemon.register(server)
    ns.register("Seega.Server", uri)
    print("Servidor Seega registrado e aguardando conexões...")
    daemon.requestLoop()


if __name__ == "__main__":
    main()
