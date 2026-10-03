"""Inicio con doble clic: busca un puerto libre, levanta el servidor y abre
el navegador cuando /health responde."""
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402


def free_port(start=8765, attempts=50, host="127.0.0.1"):
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError("No hay puertos libres entre %d y %d" % (start, start + attempts))


def wait_health(url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    no_browser = "--no-browser" in sys.argv
    host = "127.0.0.1"
    port = free_port(int(os.environ.get("PORT", 8765)))
    httpd = app.create_server(host, port)
    url = "http://%s:%d" % (host, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print("=" * 60)
    print(" Eventos Región del Biobío")
    print(" Abierto en: " + url)
    print(" Semilla cargada: %s" % httpd.ctx.seed_result)
    print(" Rastreo (data/crawled_events.json): %s" % httpd.ctx.crawled_result)
    print(" Cierra esta ventana o presiona Ctrl+C para detener.")
    print("=" * 60)
    if wait_health(url) and not no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Deteniendo...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
