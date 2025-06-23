import threading
import time
import subprocess
import sys
import Pyro5.api
import Pyro5.server
import Pyro5.errors
from seega_model import SeegaGame


@Pyro5.api.expose
@Pyro5.api.behavior(instance_mode="single")
class SeegaServer:
    """Servidor Pyro5 do jogo Seega sem callbacks."""

    def __init__(self):
        self.lock = threading.Lock()
        self.nicknames = []
        self.game = SeegaGame()

    def register_player(self, nickname):
        """Registra novo jogador."""
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
        return self.nicknames

    def send_command(self, player_id, command):
        """Executa o comando do cliente."""
        with self.lock:
            match command['type']:
                case 'place':
                    self.game.place_piece(player_id, command['row'], command['col'])
                case 'move':
                    self.game.move_piece(
                        player_id,
                        command['from_row'], command['from_col'],
                        command['to_row'], command['to_col']
                    )
                case 'pass':
                    self.game.pass_turn(player_id)
                case 'surrender':
                    self.game.surrender(player_id)

    def restart_game(self):
        """Reinicia o jogo mantendo jogadores conectados."""
        with self.lock:
            self.game.reset()
            if len(self.nicknames) == 2:
                self.game.start_game()

    def send_chat_message(self, player_id, message):
        """Adiciona nova mensagem de chat."""
        with self.lock:
            sender = self.nicknames[player_id]
            self.game.add_chat_message(sender, message)

    def get_full_state(self):
        """Retorna estado completo do jogo e chat."""
        with self.lock:
            return {
                'state': self.game.get_state(),
                'messages': self.game.chat_messages
            }


def start_nameserver():
    print(">>> Name Server não encontrado. Tentando iniciar...")
    try:
        subprocess.Popen([sys.executable, "-m", "Pyro5.nameserver"])
        time.sleep(2)
    except Exception as e:
        print(f">>> Erro ao iniciar Name Server: {e}")


def main():
    print(">>> Iniciando servidor Seega...")

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            ns = Pyro5.api.locate_ns()
            break
        except Pyro5.errors.NamingError:
            if attempt == 0:
                start_nameserver()
            print(f">>> Tentativa {attempt + 1} de conectar ao Name Server...")
            time.sleep(1)
    else:
        print(">>> Erro: Não foi possível conectar ao Name Server.")
        return

    try:
        daemon = Pyro5.server.Daemon()
        server = SeegaServer()
        uri = daemon.register(server)
        ns.register("Seega.Server", uri)
        print(">>> Servidor Seega registrado. Aguardando conexões...")
        print(f">>> URI do servidor: {uri}")
        daemon.requestLoop()
    except Exception as e:
        print(f">>> Erro fatal no servidor: {e}")


if __name__ == "__main__":
    main()
