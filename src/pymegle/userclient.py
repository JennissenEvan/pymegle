import asyncio
from pynput import keyboard
from .chat import OmegleChat, OmegleClient
import aioconsole


# Due to the way standard input works, we can not exit the input state of the console programmatically.
# Instead, in the event that the program no longer needs to accept input from the user, (when the partner disconnects)
# we must prompt the user to enter before continuing.
# Additionally, because console input can not be gathered until after the user returns, a separate process is used to
# detect key presses.
class InputListener:
    def __init__(self, chat_object):
        self.chat: OmegleChat = chat_object

        self.user_input = None
        self.input_updated = False
        self.halted = False

        self.key_pressed = False
        self.sent_typing = False
        self.key_listener = keyboard.Listener(on_press=self.key_press)
        self.typing_timeout: asyncio.Task = None

    def key_press(self, key):
        try:
            char = key.char
        except AttributeError:
            char = None

        if char is not None and char in "/d":
            return

        if key == keyboard.Key.enter:
            return

        self.key_pressed = True

    def halt(self):
        self.halted = True
        self.key_listener.stop()

    async def run(self):
        self.key_listener.start()
        while not self.halted:
            console_input = await aioconsole.ainput()

            if console_input == "/d":
                await self.chat.send_disconnect()
                input("You disconnected. Press Enter to continue.")
                return

            self.user_input = console_input
            self.input_updated = True
            await self.stop_typing()

    async def capture_input(self):
        while True:
            if self.input_updated:
                self.input_updated = False
                return self.user_input

            if self.key_pressed:
                if not self.sent_typing:
                    await self.chat.send_typing()
                    self.sent_typing = True
                await self.typing_timeout_reset()
                self.key_pressed = False

            await asyncio.sleep(0.01)

    async def stop_typing(self):
        if self.sent_typing:
            self.sent_typing = False
            await self.chat.send_stopped_typing()

    async def typing_timeout_reset(self):
        if self.typing_timeout is not None:
            self.typing_timeout.cancel()
        self.typing_timeout = asyncio.create_task(self.typing_timeout_run())

    async def typing_timeout_run(self):
        await asyncio.sleep(5)
        await self.stop_typing()


class UserChat(OmegleChat):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.input_listener = InputListener(self)

        self.user_input_handler = None

    def on_start(self):
        if self.interests:
            print("Looking for a stranger with similar interests...")
        else:
            print("Looking for a stranger you can chat with...")

    async def handle_user_input(self):
        asyncio.create_task(self.input_listener.run())
        while self.connected and not self.finished:
            user_input = await self.input_listener.capture_input()

            print(f"You: {user_input}")
            await self.send_message(user_input)

    async def on_connected(self, i):
        print("You are now chatting with a random stranger! Type /d at any time to disconnect.")

        if len(i) > 0:
            i = tuple(i)
            if len(i) == 1:
                print(f"You both like {i[0]}.")
            else:
                print(f"You both like {', '.join(i[:-1])} and {i[-1]}.")

        self.user_input_handler = asyncio.create_task(self.handle_user_input())

    async def on_message(self, m: str):
        print(f"Stranger: {m}")

    async def on_typing(self):
        print("Stranger is typing...")

    async def on_stopped_typing(self):
        print("Stranger stopped typing.")

    async def on_disconnect(self):
        self.user_input_handler.cancel()
        self.input_listener.halt()
        print("Stranger disconnected. (Enter to continue)")
        await self.input_listener.capture_input()

    def on_end(self):
        print("Chat ended.")


class UserClient(OmegleClient):
    def __init__(self, **kwargs):
        super().__init__(UserChat, **kwargs)

    def on_new_chat(self):
        if not self.interests and self.chats == 0:
            new_interests = input('Enter interests separated by "," or press Enter: ')

            if new_interests != "":
                self.interests = set(new_interests.split(","))

        return True

    def on_chat_end(self, log):
        return input("Start new chat? (Y/n): ").lower() == "y"


def run_user_client(**kwrags):
    client = UserClient(**kwrags)
    client.start()
