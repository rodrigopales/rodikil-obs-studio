"""Serve o Painel Rodikil para o celular na rede de casa (Stream Deck no celular).

Só entrega o painel e o que ele usa (painel/, overlays/shared/, brand/assets/) — nunca o .env nem o resto do repo.
O celular precisa estar no MESMO Wi-Fi do PC. No 1º uso, o Windows pode perguntar sobre o firewall:
permita em "Redes privadas" (para o Python e, se o painel não conectar, para o OBS também).

Uso:
  python scripts/painel_servidor.py            # porta 8787
  python scripts/painel_servidor.py --port 9000
Deixe a janela aberta durante a live; Ctrl+C encerra.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ("painel/", "overlays/shared/", "brand/assets/")


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # não envia nada; só descobre a interface da rede local
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


BLOCKED = ROOT / "__bloqueado__"  # caminho inexistente -> 404


class PanelHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        # Checa o caminho FINAL (depois de decodificar %xx e normalizar ..), não o texto da URL.
        resolved = Path(super().translate_path(path)).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return str(BLOCKED)
        if not any((rel + "/").startswith(a) for a in ALLOWED):
            return str(BLOCKED)
        return str(resolved)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] in ("/", "/painel", "/painel/"):
            self.send_response(302)
            self.send_header("Location", "/painel/index.html")
            self.end_headers()
            return
        super().do_GET()

    def list_directory(self, path):  # nada de listar pastas
        self.send_error(404)
        return None

    def log_message(self, fmt, *args) -> None:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve o Painel Rodikil na rede local.")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()

    handler = functools.partial(PanelHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"Painel no celular:  http://{lan_ip()}:{args.port}/painel/index.html")
    print("Mesmo Wi-Fi do PC. Senha = a do WebSocket do OBS (fica salva só no celular). Ctrl+C encerra.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
