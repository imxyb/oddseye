from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Request


def client_ip_allowed(request: Request, allowlist: list[str], trusted_proxy_cidrs: list[str] | None = None) -> bool:
    if not allowlist:
        return True
    parsed_ip = _client_ip(request, trusted_proxy_cidrs or [])
    if parsed_ip is None:
        return False
    for rule in allowlist:
        if _ip_in_network(parsed_ip, rule):
            return True
    return False


def _client_ip(request: Request, trusted_proxy_cidrs: list[str]):
    peer_ip = _parse_ip(request.client.host if request.client else None)
    if peer_ip is None:
        return None
    if _ip_in_any_network(peer_ip, trusted_proxy_cidrs):
        forwarded_ip = _parse_ip(_first_forwarded_for(request.headers.get("x-forwarded-for")))
        if forwarded_ip is not None:
            return forwarded_ip
        real_ip = _parse_ip(request.headers.get("x-real-ip"))
        if real_ip is not None:
            return real_ip
    return peer_ip


def _first_forwarded_for(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(",", maxsplit=1)[0].strip()


def _parse_ip(value: str | None):
    if not value:
        return None
    try:
        return ip_address(value)
    except ValueError:
        return None


def _ip_in_any_network(parsed_ip, rules: list[str]) -> bool:
    return any(_ip_in_network(parsed_ip, rule) for rule in rules)


def _ip_in_network(parsed_ip, rule: str) -> bool:
    try:
        network = ip_network(rule, strict=False)
    except ValueError:
        return False
    return parsed_ip in network
