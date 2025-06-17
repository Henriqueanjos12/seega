import subprocess
import sys
import Pyro4
import os

# Configuração do Pyro para utilizar o serializer 'pickle'
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')


# Função responsável por iniciar o Name Server do Pyro4 com a configuração de serialização

def start_nameserver():
    try:
        print("=== Iniciando Pyro4 Name Server com pickle ===")

        # Copia as variáveis de ambiente existentes
        env = os.environ.copy()

        # Define as variáveis de ambiente específicas para o Pyro aceitar pickle
        env["PYRO_SERIALIZER"] = "pickle"
        env["PYRO_SERIALIZERS_ACCEPTED"] = "pickle"

        # Inicia o processo do name server do Pyro4 usando o interpretador Python atual
        subprocess.run([sys.executable, '-m', 'Pyro4.naming'], env=env)

    except KeyboardInterrupt:
        print("\n✓ Name Server interrompido.")
    except Exception as e:
        print(f"✗ Erro ao iniciar name server: {e}")


# Ponto de entrada principal do script
if __name__ == "__main__":
    start_nameserver()
