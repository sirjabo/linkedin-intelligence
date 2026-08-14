"""Pytest fixtures for mock ATS server used in browser E2E tests.

Starts a real uvicorn server in a background thread so Playwright can
navigate to it via HTTP.  Session-scoped so it's started once per test run.
"""
import socket
import threading
import time

import pytest
import uvicorn


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        self.port = port
        self._config = uvicorn.Config(
            "tests.mock_ats.server:app",
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
        self._server = uvicorn.Server(self._config)
        self._ready = threading.Event()

    def run(self) -> None:
        self._server.run()

    def stop(self) -> None:
        self._server.should_exit = True

    def wait_ready(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"Mock ATS server did not start on port {self.port} within {timeout}s")


@pytest.fixture(scope="session")
def mock_ats_url():
    """Yield the base URL of a live mock ATS server for the whole test session."""
    port = _get_free_port()
    server = _Server(port)
    server.start()
    server.wait_ready()
    yield f"http://127.0.0.1:{port}"
    server.stop()
