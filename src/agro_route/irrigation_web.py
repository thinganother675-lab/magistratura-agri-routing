"""Local-only HTTP entry point for the separate irrigation coursework MVP."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from .irrigation_mvp import InputError, analyse, csv_text, generate_demo


def make_server(port=8094):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, kind="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def local_request(self):
            actual_port = self.server.server_address[1]
            hosts = (f"127.0.0.1:{actual_port}", f"localhost:{actual_port}")
            origins = tuple("http://" + host for host in hosts)
            return self.headers.get("Host") in hosts and self.headers.get("Origin") in (None, *origins)

        def do_GET(self):
            if not self.local_request():
                return self.send(403, {"error": "Доступ только с локального адреса"})
            if self.path == "/":
                return self.send(200, (Path(__file__).parent / "static/irrigation.html").read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/health":
                return self.send(200, {"ok": True, "app": "AgroPlan", "external_calls": 0})
            if self.path == "/api/sample.csv":
                return self.send(200, csv_text(generate_demo()).encode("utf-8-sig"), "text/csv; charset=utf-8")
            if self.path == "/favicon.ico":
                return self.send(204, b"", "image/x-icon")
            return self.send(404, {"error": "Не найдено"})

        def do_POST(self):
            if not self.local_request():
                return self.send(403, {"error": "Доступ только с локального адреса"})
            if self.path != "/api/analyse":
                return self.send(404, {"error": "Не найдено"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send(415, {"error": "Требуется application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 220000:
                    raise InputError("Размер запроса: от 1 до 220000 байт")
                payload = json.loads(self.rfile.read(length))
                return self.send(200, analyse(payload))
            except (InputError, ValueError, TypeError, UnicodeError) as exc:
                return self.send(400, {"error": str(exc) if isinstance(exc, InputError) else "Некорректный JSON-запрос"})

        def log_message(self, fmt, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AgroPlan: local irrigation coursework MVP")
    parser.add_argument("--port", type=int, default=8094)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"AgroPlan: http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
