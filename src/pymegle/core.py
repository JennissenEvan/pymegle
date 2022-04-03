import aiohttp
import random

_URL_TEMPLATE = "https://{server}.omegle.com/{path}"

_STATUS_URL = _URL_TEMPLATE.format(server="www", path="status")


def __format_method(p):
    return _URL_TEMPLATE.format(server="{server}", path=p)


_START_TEMPLATE = __format_method("start")
_EVENTS_TEMPLATE = __format_method("events")
_TYPING_TEMPLATE = __format_method("typing")
_SEND_TEMPLATE = __format_method("send")
_DISCONNECT_TEMPLATE = __format_method("disconnect")
_STOPPEDTYPING_TEMPLATE = __format_method("stoppedtyping")

_status_cache = None

flagged_phrases = []


async def _update_cache(client: aiohttp.ClientSession = None):
    global _status_cache

    if client is None:
        client = aiohttp.ClientSession()
        close_client = True
    else:
        close_client = False

    async with client.get(_STATUS_URL) as resp:
        _status_cache = await resp.json()

    if close_client:
        await client.close()


async def get_servers(client: aiohttp.ClientSession = None):
    if _status_cache is None:
        await _update_cache(client)

    return _status_cache["servers"]


async def get_online_count(client: aiohttp.ClientSession = None):
    await _update_cache(client)

    return _status_cache["count"]


# Carbon copy of the JavaScript function Omegle uses to generate randids
def generate_randid():
    randid = ""
    for _ in range(8):
        randid += random.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ")
    return randid
