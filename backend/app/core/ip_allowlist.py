from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Request


def client_ip_allowed(request: Request, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    client_ip = _client_ip(request)
    if client_ip is None:
        return False
    try:
        parsed_ip = ip_address(client_ip)
    except ValueError:
        return False
    for rule in allowlist:
        try:
            network = ip_network(rule, strict=False)
        except ValueError:
            continue
        if parsed_ip in network:
            return True
    return False


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else None
