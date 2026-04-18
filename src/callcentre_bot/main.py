from .api import create_http_server
from .config import settings


def run_server() -> None:
    server = create_http_server(settings.server_host, settings.server_port)
    print(f"CallCentreVoiceBot listening on http://{settings.server_host}:{settings.server_port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
