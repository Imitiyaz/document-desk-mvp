"""Run local checks with Python external sockets denied and telemetry opted out.

This is a test-process guard, not an operating-system network sandbox. Real
embedding downloads and remote-model tests must be run separately, explicitly.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import importlib.util
import ipaddress
import os
import sys
from typing import Any


def loopback(host: object) -> bool:
    """Allow local test servers; reject public addresses and external DNS names."""
    if not isinstance(host, str):
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def guard(event: str, arguments: tuple[Any, ...]) -> None:
    """Refuse external Python socket traffic before any payload is transmitted."""
    host = None
    if event in {"socket.connect", "socket.sendto"}:
        address = arguments[-1]
        if isinstance(address, tuple):
            host = address[0]
    elif event in {
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyaddr",
    }:
        host = arguments[0]
    if host is not None and not loopback(host):
        raise PermissionError(
            "Offline verification refused external socket/DNS access: " + str(host)
        )


def main() -> int:
    """Require lightweight runtimes, install the guard, then run unchanged pytest."""
    os.environ.update(
        ANONYMIZED_TELEMETRY="False", OTEL_SDK_DISABLED="true", DO_NOT_TRACK="1"
    )
    sys.addaudithook(guard)
    if any(
        importlib.util.find_spec(name) is not None
        for name in ("onnxruntime", "chromadb", "torch")
    ):
        raise RuntimeError(
            "Use a lightweight test environment without native model/vector runtimes; this guard does not sandbox native telemetry."
        )
    import pytest

    return int(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
