import asyncio
import random
import aiohttp
import json

from . import core, log, exceptions


class OmegleObject:
    def __init__(self, **kwargs):
        self.http_client = kwargs.get("http_client", None)
        self._cleanup_client = self.http_client is None

        self.interests = set(kwargs.get("interests", ()))

        self.server = kwargs.get("server", None)

        self.lang = kwargs.get("lang", "en")

        self.wpm = kwargs.get("wpm", 40)

        self.randid = kwargs.get("randid", core.generate_randid())

        self.detect_bots = kwargs.get("detect_bots", False)

        self.inactivity_timeout = kwargs.get("inactivity_timeout", None)


class OmegleChat(OmegleObject):
    def __init__(self, **kwargs):
        self.started = False
        self.connected = False
        self.finished = False
        self.cid = None
        self.__event_handler = None
        self.__event_tasks = []
        self.log = log.ChatLog()
        self.waiting = False
        self.can_connect = True
        self.__active_connection = None

        self.__partner_has_typed = False
        self.__inactivity_timer = None
        self.__partner_last_comm = True
        
        super().__init__(**kwargs)

    def __add_event_task(self, task: asyncio.Task):
        self.__event_tasks.append(task)
        newlist = []
        for t in self.__event_tasks:
            if not t.done():
                newlist.append(t)
        self.__event_tasks = newlist

    def start(self):
        asyncio.run(self.connect())

    async def connect(self):
        try:
            self.__active_connection = asyncio.create_task(self.__run())
            await self.__active_connection
        except aiohttp.ServerDisconnectedError:
            self.log.log_entry(log.LogConnectionError())
        except aiohttp.ClientPayloadError:
            self.log.log_entry(log.LogMiscError("aiohttp.ClientPayloadError"))
        except asyncio.CancelledError:
            pass
        except aiohttp.ContentTypeError:
            self.log.log_entry(log.LogMiscError("aiohttp.ContentTypeError"))
        finally:
            await self._end_chat()

    async def __run(self):
        if self.started:
            raise exceptions.AlreadyStarted

        if self.http_client is None:
            self.http_client = aiohttp.ClientSession()

        if self.server is None:
            self.server = random.choice(await core.get_servers(self.http_client))

        connect_params = {
            "lang": self.lang,
            "firstevents": "1",
            "caps": "recaptcha2,t",
            "spid": "",
            "randid": self.randid
        }
        if len(self.interests) > 0:
            connect_params["topics"] = json.dumps(list(self.interests)).replace(", ", ",")

        self.started = True
        self.on_start()
        self.log.log_entry(log.LogInitiated(connect_params))

        start_url = core._START_TEMPLATE.format(server=self.server)
        async with self.http_client.post(start_url, params=connect_params) as resp:
            resp_data = await resp.json()
            if len(resp_data) == 0:
                await self._master_on_no_response()
            else:
                self.cid = resp_data["clientID"]
                if resp_data["events"][0][0] == "connected":
                    await self._master_on_connected()
                elif resp_data["events"][0][0] == "waiting":
                    self.waiting = True
                elif resp_data["events"][0][0] == "recaptchaRequired":
                    await self._master_on_captcha_required(resp_data["events"][0][1])
                elif resp_data["events"][0][0] == "antinudeBanned":
                    await self._master_on_banned()

        while self.can_connect:
            self.__event_handler = asyncio.create_task(self.__handle_event())
            if await self.__event_handler:
                continue
            else:
                break

    async def __handle_event(self):
        payload = {"id": self.cid}
        async with self.http_client.post(core._EVENTS_TEMPLATE.format(server=self.server), data=payload) as resp:
            resp_json = await resp.json()

            if not self.waiting:
                if resp_json is None or len(resp_json) == 0:
                    return True
            elif resp_json is not None and len(resp_json) > 0 and resp_json[0][0] == "connected":
                self.waiting = False
                await self._master_on_connected(set(resp_json[1][1]))
            else:
                self.connected = True
                self.log.log_entry(log.LogSearchTimeout())
                await self.send_disconnect()
                return False

            if resp_json[0][0] == "strangerDisconnected":
                await self._master_on_disconnect()
                return False

            if resp_json[0][0] == "typing":
                await self._master_on_typing()
            elif resp_json[0][0] == "gotMessage":
                await self._master_on_message(resp_json[0][1])
            elif resp_json[0][0] == "stoppedTyping":
                await self._master_on_stopped_typing()

        return True

    async def _end_chat(self):
        self.finished = True
        for task in self.__event_tasks:
            task.cancel()
        self.log.log_entry(log.LogEnded())
        self.on_end()
        if self._cleanup_client:
            await self.http_client.close()

    async def _master_on_connected(self, i=None):
        self.connected = True

        if i is None:
            i = set()
        self.log.log_entry(log.LogConnected(i))

        self.__add_event_task(asyncio.create_task(self.on_connected(i)))

        await self.__reset_inactivity_timer()

    async def on_connected(self, i):
        pass

    async def _master_on_disconnect(self):
        self.finished = True
        self.log.log_entry(log.LogGotDisconnected())
        await self.on_disconnect()

    async def on_disconnect(self):
        pass

    async def _master_on_typing(self):
        await self.__stop_inactivity_timer()

        self.log.log_entry(log.LogGotTyping())
        self.__partner_has_typed = True

        self.__add_event_task(asyncio.create_task(self.on_typing()))

    async def on_typing(self):
        pass

    async def _master_on_message(self, m: str):
        await self.__reset_inactivity_timer()
        self.__partner_last_comm = True

        self.log.log_entry(log.LogGotMessage(m))

        if self.detect_bots:
            for phrase in core.flagged_phrases:
                if phrase in m:
                    self.log.log_entry(log.LogBotDetected())
                    await self.send_disconnect()
                    return
            if not self.__partner_has_typed:
                self.log.log_entry(log.LogBotDetected())
                await self.send_disconnect()
                return

        self.__add_event_task(asyncio.create_task(self.on_message(m)))

    async def on_message(self, m: str):
        pass

    async def _master_on_stopped_typing(self):
        await self.__reset_inactivity_timer()
        self.__partner_last_comm = True

        self.log.log_entry(log.LogGotStoppedTyping())

        self.__add_event_task(asyncio.create_task(self.on_stopped_typing()))

    async def on_stopped_typing(self):
        pass

    async def _master_on_captcha_required(self, url):
        self.log.log_entry(log.LogCaptcha())

        self.can_connect = False

    async def _master_on_banned(self):
        self.log.log_entry(log.LogBanned())

        self.can_connect = False

    async def _master_on_no_response(self):
        self.log.log_entry(log.LogNoResponse)

        self.can_connect = False

    async def _do_request(self, path, **xdata):
        if not self.connected:
            raise exceptions.NotConnected

        if self.finished:
            return

        payload = {"id": self.cid, **xdata}
        await self.http_client.post(core._URL_TEMPLATE.format(server=self.server, path=path), data=payload)

    async def send_typing(self):
        if self.__partner_last_comm:
            await self.__stop_inactivity_timer()

        self.log.log_entry(log.LogSentTyping())

        await self._do_request("typing")

    async def send_message(self, m: str):
        if self.__partner_last_comm:
            await self.__reset_inactivity_timer()
        self.__partner_last_comm = False

        self.log.log_entry(log.LogSentMessage(m))

        await self._do_request("send", msg=m)

    async def send_disconnect(self):
        self.log.log_entry(log.LogSentDisconnected())

        await self._do_request("disconnect")

        self.__active_connection.cancel()

    async def send_stopped_typing(self):
        if self.__partner_last_comm:
            await self.__reset_inactivity_timer()
        self.__partner_last_comm = False

        self.log.log_entry(log.LogSentStoppedTyping())

        await self._do_request("stoppedtyping")

    async def type_message(self, m):
        await self.send_typing()

        cps = (self.wpm * 5) / 60
        await asyncio.sleep(len(m) / cps)

        await self.send_message(m)

    def on_start(self):
        pass

    def on_end(self):
        pass

    async def __run_inactivity_timer(self):
        await asyncio.sleep(self.inactivity_timeout)
        await self.send_disconnect()

    async def __reset_inactivity_timer(self):
        if self.inactivity_timeout is None or self.inactivity_timeout < 0:
            return

        await self.__stop_inactivity_timer()
        self.__inactivity_timer = asyncio.create_task(self.__run_inactivity_timer())

    async def __stop_inactivity_timer(self):
        if self.__inactivity_timer is not None:
            self.__inactivity_timer.cancel()


class OmegleClient(OmegleObject):
    def __init__(self, chat_handler, **kwargs):
        self.chats = 0

        self.chat_handler = chat_handler
        self.active_handler = None
        self.connection = None

        self.halted = False

        super().__init__()

    def on_new_chat(self):
        return True

    def on_chat_end(self, log):
        return False

    async def connect(self):
        if self.is_connected():
            raise exceptions.AlreadyStarted

        self.halted = False

        try:
            self.connection = asyncio.create_task(self.__run())
            await self.connection
        except asyncio.CancelledError:
            pass
        finally:
            self.connection = None

    async def __run(self):
        if self.http_client is None:
            self.http_client = aiohttp.ClientSession()

        if self.server is None:
            self.server = random.choice(await core.get_servers(self.http_client))

        while self.on_new_chat():
            chat_params = {
                "http_client": self.http_client,
                "server": self.server,
                "interests": self.interests.copy(),
                "lang": self.lang,
                "wpm": self.wpm,
                "randid": self.randid,
                "detect_bots": self.detect_bots,
                "inactivity_timeout": self.inactivity_timeout
            }

            self.active_handler = self.chat_handler(**chat_params)
            await self.active_handler.connect()

            self.chats += 1

            if (not self.on_chat_end(self.active_handler.log)) or self.halted:
                break

        if self._cleanup_client:
            await self.http_client.close()
            self.http_client = None

    def start(self):
        asyncio.run(self.connect())

    async def skip(self):
        if self.active_handler is not None:
            await self.active_handler.send_disconnect()

    def halt(self):
        self.halted = True

    async def terminate(self):
        self.halt()
        if self.active_handler is not None:
            await self.skip()
        elif self.is_connected():
            self.connection.cancel()

    def is_connected(self):
        return self.connection is not None
