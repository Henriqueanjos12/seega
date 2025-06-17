import subprocess
import sys
import Pyro4
import os

# Configurações corretas
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')

def start_nameserver():
    try:
        print("=== Iniciando Pyro4 Name Server com pickle ===")
        env = os.environ.copy()
        env["PYRO_SERIALIZER"] = "pickle"
        env["PYRO_SERIALIZERS_ACCEPTED"] = "pickle"
        subprocess.run([sys.executable, '-m', 'Pyro4.naming'], env=env)
    except KeyboardInterrupt:
        print("\n✓ Name Server interrompido.")
    except Exception as e:
        print(f"✗ Erro ao iniciar name server: {e}")

if __name__ == "__main__":
    start_nameserver()
