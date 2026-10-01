"""Resolve throttle identity only across explicitly trusted proxy hops."""

from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import Settings


def login_client_key(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client is not None else "unknown"
    try:
        address = ip_address(peer)
    except ValueError:
        return peer
    networks = [ip_network(value) for value in settings.trusted_proxy_networks]

    def trusted(value: str) -> bool:
        candidate = ip_address(value)
        return any(candidate in network for network in networks)

    if not trusted(str(address)):
        return str(address)
    forwarded = request.headers.getlist("x-forwarded-for")
    if len(forwarded) != 1 or len(forwarded[0]) > 1024:
        return str(address)
    hops = forwarded[0].split(",")
    if len(hops) > 16:
        return str(address)
    try:
        chain = [str(ip_address(value.strip())) for value in hops] + [str(address)]
    except ValueError:
        return str(address)
    # Walk from the real connection peer; an untrusted hop ends authority.
    while len(chain) > 1 and trusted(chain[-1]):
        chain.pop()
    return chain[-1]
