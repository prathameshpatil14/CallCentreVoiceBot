def run_server() -> None:
    from .main import run_server as _run_server

    _run_server()


__all__ = ["run_server"]
