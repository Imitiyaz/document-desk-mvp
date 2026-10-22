"""Local test servers remain usable while external socket attempts are refused.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import pytest

from tools.offline_pytest import guard, loopback


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_local_servers_are_allowed(host: str) -> None:
    assert loopback(host)
    guard("socket.connect", (None, (host, 8000)))


@pytest.mark.parametrize(
    "event,args",
    [
        ("socket.connect", (None, ("203.0.113.1", 443))),
        ("socket.sendto", (None, b"not sent", ("203.0.113.1", 443))),
        ("socket.getaddrinfo", ("telemetry.example.invalid", 443, 0, 0, 0)),
    ],
)
def test_external_access_is_refused_before_transmission(
    event: str, args: tuple
) -> None:
    with pytest.raises(PermissionError, match="Offline verification refused"):
        guard(event, args)
