import random
import threading
from socketserver import ThreadingMixIn
from xmlrpc.server import SimpleXMLRPCServer


class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

class SeegaRPCServer:
    def __init__(self, host='0.0.0.0', port=8000):
        self.server = ThreadedXMLRPCServer((host, port), allow_none=True, logRequests=False)
        self.server.register_instance(self)

        self.nicknames = []
        self.clients_ready = []
        self.lock = threading.Lock()

        self.forced_piece = None
        self.chat_messages = []

        self.game_state = {
            'board': [[0 for _ in range(5)] for _ in range(5)],
            'phase': 'placement',
            'center_filled': False,
            'current_turn': 0,
            'pieces_placed': [0, 0],
            'captured': [0, 0],
            'game_over': False,
            'winner': None
        }
        self.game_state['board'][2][2] = -1

        self.placement_counter = 0

    def register_client(self, nickname):
        with self.lock:
            if len(self.nicknames) >= 2:
                return -1
            self.nicknames.append(nickname)
            self.clients_ready.append(False)
            return len(self.nicknames) - 1

    def set_ready(self, player_id):
        with self.lock:
            self.clients_ready[player_id] = True
            if all(self.clients_ready):
                self.game_state['current_turn'] = random.randint(0, 1)
            return True

    def send_command(self, player_id, command):
        with self.lock:
            if self.game_state['game_over']:
                return self.game_state
            try:
                if command['type'] == 'place':
                    return self._handle_place(player_id, command['row'], command['col'])
                elif command['type'] == 'move':
                    return self._handle_move(player_id, command['from_row'], command['from_col'], command['to_row'], command['to_col'])
                elif command['type'] == 'pass':
                    return self._handle_pass(player_id)
                elif command['type'] == 'surrender':
                    return self._handle_surrender(player_id)
            except Exception as e:
                print(f"Erro ao processar comando: {e}")
            return self.game_state

    def get_game_state(self, player_id):
        return self.game_state

    def send_chat_message(self, sender, message):
        with self.lock:
            self.chat_messages.append({"sender": sender, "message": message})
            return True

    def get_chat_messages(self):
        with self.lock:
            return self.chat_messages

    def _handle_place(self, player_id, row, col):
        if self.game_state['phase'] != 'placement' or self.game_state['board'][row][col] != 0:
            return self.game_state

        if row == 2 and col == 2:
            return self.game_state

        self.game_state['board'][row][col] = player_id + 1
        self.game_state['pieces_placed'][player_id] += 1
        self.placement_counter += 1

        if sum(self.game_state['pieces_placed']) == 24:
            self.game_state['phase'] = 'movement'
            self.game_state['board'][2][2] = 0
            self.placement_counter = 0
        elif self.placement_counter == 2:
            self.placement_counter = 0
            self.game_state['current_turn'] = 1 - player_id

        return self.game_state

    def _handle_move(self, player_id, from_row, from_col, to_row, to_col):
        if self.game_state['phase'] != 'movement':
            return self.game_state

        if not self._is_valid_move(from_row, from_col, to_row, to_col, player_id + 1):
            return self.game_state

        if self.forced_piece and (from_row, from_col) != self.forced_piece:
            return self.game_state

        self.game_state['board'][from_row][from_col] = 0
        self.game_state['board'][to_row][to_col] = player_id + 1

        captures = self._check_captures(to_row, to_col, player_id + 1)
        opponent_id = 1 - player_id
        opponent_piece = opponent_id + 1

        if sum(row.count(opponent_piece) for row in self.game_state['board']) == 0 or not self._has_valid_moves(opponent_piece):
            self.game_state['game_over'] = True
            self.game_state['winner'] = player_id

        if captures > 0:
            self.game_state['captured'][player_id] += captures
            self.forced_piece = (to_row, to_col)
        else:
            self.forced_piece = None
            self.game_state['current_turn'] = opponent_id

        return self.game_state

    def _handle_pass(self, player_id):
        if self.game_state['phase'] == 'movement' and player_id == self.game_state['current_turn']:
            self.forced_piece = None
            self.game_state['current_turn'] = 1 - player_id
        return self.game_state

    def _handle_surrender(self, player_id):
        self.game_state['game_over'] = True
        self.game_state['winner'] = 1 - player_id
        return self.game_state

    def _is_valid_move(self, fr, fc, tr, tc, piece):
        return (self.game_state['board'][fr][fc] == piece and
                self.game_state['board'][tr][tc] == 0 and
                (fr == tr or fc == tc) and
                abs(fr - tr) + abs(fc - tc) == 1)

    def _check_captures(self, r, c, piece):
        opponent = 1 if piece == 2 else 2
        captures = 0
        for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            ar, ac = r + dr, c + dc
            nr, nc = ar + dr, ac + dc
            if 0 <= ar < 5 and 0 <= ac < 5 and self.game_state['board'][ar][ac] == opponent:
                if (ar, ac) != (2, 2) and 0 <= nr < 5 and 0 <= nc < 5 and self.game_state['board'][nr][nc] == piece:
                    self.game_state['board'][ar][ac] = 0
                    captures += 1
        return captures

    def _has_valid_moves(self, piece):
        for r in range(5):
            for c in range(5):
                if self.game_state['board'][r][c] == piece:
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 5 and 0 <= nc < 5 and self.game_state['board'][nr][nc] == 0:
                            return True
        return False

    def serve(self):
        print("Servidor RPC Seega (threaded) iniciado.")
        self.server.serve_forever()

if __name__ == "__main__":
    server = SeegaRPCServer()
    server.serve()
