"""
Servidor Pyro5 do jogo Seega.

Este módulo implementa o servidor distribuído do jogo Seega usando Pyro5,
gerenciando conexões de jogadores, estado do jogo e comunicação via RPC.
"""

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
    """
    Servidor Pyro5 do jogo Seega.

    Gerencia até 2 jogadores simultâneos, coordena o estado do jogo
    e processa comandos dos clientes via RPC sem uso de callbacks.

    Attributes:
        lock (threading.Lock): Mutex para thread safety
        nicknames (list): Lista de nicknames dos jogadores conectados
        game (SeegaGame): Instância do modelo do jogo
    """

    def __init__(self):
        """Inicializa o servidor com estado limpo."""
        self.lock = threading.Lock()  # Protege acesso concorrente
        self.nicknames = []  # Lista de nicknames (máximo 2)
        self.game = SeegaGame()  # Instância única do jogo

    def register_player(self, nickname):
        """
        Registra um novo jogador no servidor.

        Args:
            nickname (str): Nome escolhido pelo jogador

        Returns:
            dict: Dicionário com status da conexão e ID do jogador
                  {'status': 'ok'|'full', 'player_id': int}
        """
        with self.lock:
            # Verifica se já há 2 jogadores conectados
            if len(self.nicknames) >= 2:
                return {'status': 'full'}

            # Registra o novo jogador
            self.nicknames.append(nickname)
            player_id = len(self.nicknames) - 1

            print(f">>> Jogador {player_id + 1} conectado: {nickname}")

            # Se ambos os jogadores estão conectados, inicia o jogo
            if len(self.nicknames) == 2:
                print(">>> Ambos os jogadores conectados. Iniciando o jogo!")
                self.game.start_game()

            return {'status': 'ok', 'player_id': player_id}

    def get_nicknames(self):
        """
        Retorna a lista de nicknames dos jogadores conectados.

        Returns:
            list: Lista de nicknames (máximo 2 elementos)
        """
        return self.nicknames

    def send_command(self, player_id, command):
        """
        Executa um comando enviado pelo cliente.

        Processa diferentes tipos de comandos: place, move, pass, surrender
        de forma thread-safe usando pattern matching.

        Args:
            player_id (int): ID do jogador que enviou o comando
            command (dict): Dicionário com tipo e parâmetros do comando
        """
        with self.lock:
            # Usa pattern matching (Python 3.10+) para processar comandos
            match command['type']:
                case 'place':
                    # Comando de colocação de peça
                    self.game.place_piece(player_id, command['row'], command['col'])

                case 'move':
                    # Comando de movimento de peça
                    self.game.move_piece(
                        player_id,
                        command['from_row'], command['from_col'],
                        command['to_row'], command['to_col']
                    )

                case 'pass':
                    # Comando para passar o turno
                    self.game.pass_turn(player_id)

                case 'surrender':
                    # Comando de desistência
                    self.game.surrender(player_id)

    def restart_game(self):
        """
        Reinicia o jogo mantendo os jogadores conectados.

        Reseta o estado do jogo para o inicial e, se há 2 jogadores,
        inicia uma nova partida automaticamente.
        """
        with self.lock:
            self.game.reset()

            # Se há 2 jogadores, inicia automaticamente
            if len(self.nicknames) == 2:
                self.game.start_game()

    def send_chat_message(self, player_id, message):
        """
        Adiciona uma nova mensagem ao chat do jogo.

        Args:
            player_id (int): ID do jogador que enviou a mensagem
            message (str): Conteúdo da mensagem
        """
        with self.lock:
            # Obtém o nickname do jogador e adiciona a mensagem
            sender = self.nicknames[player_id]
            self.game.add_chat_message(sender, message)

    def get_full_state(self):
        """
        Retorna o estado completo do jogo e mensagens de chat.

        Método usado pelos clientes para polling do estado atual.

        Returns:
            dict: Dicionário contendo 'state' (estado do jogo) e 
                  'messages' (lista de mensagens do chat)
        """
        with self.lock:
            return {
                'state': self.game.get_state(),
                'messages': self.game.chat_messages
            }


def start_nameserver():
    """
    Tenta iniciar o Pyro5 Name Server automaticamente.

    O Name Server é necessário para que clientes encontrem o servidor.
    Esta função tenta iniciá-lo como um subprocesso separado.
    """
    print(">>> Name Server não encontrado. Tentando iniciar...")
    try:
        # Inicia o nameserver como subprocesso
        subprocess.Popen([sys.executable, "-m", "Pyro5.nameserver"])
        time.sleep(2)  # Aguarda inicialização
    except Exception as e:
        print(f">>> Erro ao iniciar Name Server: {e}")


def main():
    """
    Função principal do servidor.

    Configura e inicia o servidor Pyro5, registra no Name Server
    e entra no loop de atendimento de requisições.
    """
    print(">>> Iniciando servidor Seega...")

    # Tenta conectar ao Name Server com múltiplas tentativas
    max_attempts = 3
    ns = None

    for attempt in range(max_attempts):
        try:
            ns = Pyro5.api.locate_ns()
            break
        except Pyro5.errors.NamingError:
            # Na primeira tentativa, tenta iniciar o Name Server
            if attempt == 0:
                start_nameserver()
            print(f">>> Tentativa {attempt + 1} de conectar ao Name Server...")
            time.sleep(1)
    else:
        # Se não conseguiu conectar após todas as tentativas
        print(">>> Erro: Não foi possível conectar ao Name Server.")
        return

    try:
        # Cria o daemon Pyro5 e registra o servidor
        daemon = Pyro5.server.Daemon()
        server = SeegaServer()
        uri = daemon.register(server)

        # Registra no Name Server com nome conhecido
        ns.register("Seega.Server", uri)

        print(">>> Servidor Seega registrado. Aguardando conexões...")
        print(f">>> URI do servidor: {uri}")

        # Entra no loop principal de atendimento
        daemon.requestLoop()

    except Exception as e:
        print(f">>> Erro fatal no servidor: {e}")


if __name__ == "__main__":
    main()