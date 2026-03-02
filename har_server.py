#!/usr/bin/env python3
"""
har_server.py — Serveur local pour HAR Feature Report dynamique
---------------------------------------------------------------
Lance ce script dans le dossier contenant tes fichiers JSON et le rapport HTML.
Puis ouvre http://localhost:7331 dans ton navigateur.

Usage :
    python3 har_server.py
    python3 har_server.py --port 7331
    python3 har_server.py --dir /chemin/vers/tes/fichiers
"""

import argparse
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# ── CONFIG ────────────────────────────────────────────────
DEFAULT_PORT = 7331
ALLOWED_ORIGINS = ['http://localhost', 'http://127.0.0.1', 'null', '']


def get_serve_dir(arg_dir=None):
    """Dossier à servir : celui passé en arg, ou celui du script."""
    if arg_dir:
        d = Path(arg_dir).resolve()
        if not d.is_dir():
            print(f"[ERR] Dossier introuvable : {d}")
            sys.exit(1)
        return d
    return Path(__file__).resolve().parent


# ── HTTP HANDLER ──────────────────────────────────────────
class HARHandler(BaseHTTPRequestHandler):

    serve_dir: Path = Path('.')

    def log_message(self, fmt, *args):
        # Quiet mode — only print errors
        if args and str(args[1]) not in ('200', '304'):
            super().log_message(fmt, *args)

    def cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # ── /ping ─────────────────────────────────────────
        if path == '/ping':
            self._json({'status': 'ok', 'version': '1.0'})

        # ── /list — list JSON files in serve_dir ──────────
        elif path == '/list':
            files = sorted(
                f.name for f in self.serve_dir.iterdir()
                if f.suffix.lower() == '.json' and f.is_file()
            )
            self._json({'files': files, 'dir': str(self.serve_dir)})

        # ── /file?name=xxx.json — serve a JSON file ───────
        elif path == '/file':
            name = params.get('name', [None])[0]
            if not name:
                self._error(400, 'Missing ?name= parameter')
                return
            # Security: no path traversal
            name = Path(unquote(name)).name
            target = self.serve_dir / name
            if not target.exists() or not target.is_file():
                self._error(404, f'File not found: {name}')
                return
            if target.suffix.lower() != '.json':
                self._error(403, 'Only .json files are served')
                return
            try:
                with open(target, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.cors_headers()
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._error(500, str(e))

        # ── / or /index.html — serve the report HTML ──────
        elif path in ('/', '/index.html', '/har_report_dynamic.html'):
            html_candidates = [
                self.serve_dir / 'har_report_dynamic.html',
                self.serve_dir / 'index.html',
                Path(__file__).resolve().parent / 'har_report_dynamic.html',
            ]
            html_file = next((f for f in html_candidates if f.exists()), None)
            if not html_file:
                self._error(404, 'har_report_dynamic.html not found in server directory')
                return
            with open(html_file, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.cors_headers()
            self.end_headers()
            self.wfile.write(data)

        # ── 404 ───────────────────────────────────────────
        else:
            self._error(404, f'Unknown route: {path}')

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, msg):
        body = json.dumps({'error': msg}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.cors_headers()
        self.end_headers()
        self.wfile.write(body)


# ── MAIN ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='HAR Feature Report — Serveur local')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Port (défaut: {DEFAULT_PORT})')
    parser.add_argument('--dir', type=str, default=None, help='Dossier contenant les JSON (défaut: dossier du script)')
    parser.add_argument('--no-browser', action='store_true', help='Ne pas ouvrir le navigateur automatiquement')
    args = parser.parse_args()

    serve_dir = get_serve_dir(args.dir)
    HARHandler.serve_dir = serve_dir

    # List available JSON files
    json_files = sorted(f.name for f in serve_dir.iterdir() if f.suffix.lower() == '.json' and f.is_file())

    print()
    print('╔══════════════════════════════════════════════════════╗')
    print('║          HAR Feature Report — Serveur local          ║')
    print('╚══════════════════════════════════════════════════════╝')
    print(f'  Dossier : {serve_dir}')
    print(f'  Port    : {args.port}')
    print(f'  URL     : \033[36mhttp://localhost:{args.port}\033[0m')
    print()
    if json_files:
        print(f'  Fichiers JSON détectés ({len(json_files)}) :')
        for f in json_files:
            size_kb = (serve_dir / f).stat().st_size // 1024
            print(f'    ✓  {f}  ({size_kb} Ko)')
    else:
        print('  \033[33m⚠ Aucun fichier JSON trouvé dans ce dossier.\033[0m')
        print('    Place tes fichiers *.json ici et actualise le rapport.')
    print()
    print('  Ctrl+C pour arrêter le serveur.')
    print()

    server = HTTPServer(('localhost', args.port), HARHandler)

    if not args.no_browser:
        try:
            webbrowser.open(f'http://localhost:{args.port}')
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Serveur arrêté.')
        server.server_close()


if __name__ == '__main__':
    main()
