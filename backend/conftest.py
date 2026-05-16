import os
import time
import urllib.request
from pathlib import Path

# Docker Desktop on Mac puts its socket at ~/.docker/run/docker.sock rather than
# /var/run/docker.sock. Testcontainers falls back to the default path, so set
# DOCKER_HOST automatically when the standard socket is missing.
_desktop_sock = Path.home() / ".docker" / "run" / "docker.sock"
if not Path("/var/run/docker.sock").exists() and _desktop_sock.exists():
    os.environ.setdefault("DOCKER_HOST", f"unix://{_desktop_sock}")


def wait_for_chroma(host: str, port: str | int, timeout: int = 90) -> None:
    """Poll the ChromaDB heartbeat endpoint until the server responds (any HTTP response counts)."""
    import urllib.error

    url = f"http://{host}:{port}/api/v1/heartbeat"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return  # 2xx — server is ready
        except urllib.error.HTTPError:
            return  # Server is up but returned an HTTP error code — still ready
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"ChromaDB did not become ready at {url} within {timeout}s")
