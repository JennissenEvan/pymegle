import time
import json
import _io


class LogElement:
    def __init__(self):
        self.logtime = time.localtime()

    def draw(self):
        return f"{self._draw_timestamp()} {self._draw_entry()}"

    def _draw_timestamp(self):
        return time.strftime("[%H:%M:%S]", self.logtime)

    def _draw_entry(self):
        pass


class LogConnected(LogElement):
    def __init__(self, common_topics=None):
        super().__init__()
        self.common_topics = common_topics

    def _draw_entry(self):
        if self.common_topics is None or len(self.common_topics) == 0:
            return "Connected."
        else:
            return f"Connected. Common interests: {json.dumps(list(self.common_topics))}"


class Exchange:
    def _draw_sender(self):
        pass


class ExchangeClient(Exchange):
    def _draw_sender(self):
        return "Client"


class ExchangeStranger(Exchange):
    def _draw_sender(self):
        return "Stranger"


class LogMessage(LogElement, Exchange):
    def __init__(self, message):
        super().__init__()
        self.message = message

    def _draw_entry(self):
        return f"{self._draw_sender()}: {self.message}"


class LogSentMessage(LogMessage, ExchangeClient):
    pass


class LogGotMessage(LogMessage, ExchangeStranger):
    pass


class LogTyping(LogElement, Exchange):
    def _draw_entry(self):
        return f"{self._draw_sender()} is typing..."


class LogSentTyping(LogTyping, ExchangeClient):
    pass


class LogGotTyping(LogTyping, ExchangeStranger):
    pass


class LogStoppedTyping(LogElement, Exchange):
    def _draw_entry(self):
        return f"{self._draw_sender()} stopped typing."


class LogSentStoppedTyping(LogStoppedTyping, ExchangeClient):
    pass


class LogGotStoppedTyping(LogStoppedTyping, ExchangeStranger):
    pass


class LogDisconnected(LogElement, Exchange):
    def _draw_entry(self):
        return f"{self._draw_sender()} disconnected."


class LogSentDisconnected(LogDisconnected, ExchangeClient):
    pass


class LogGotDisconnected(LogDisconnected, ExchangeStranger):
    pass


class LogEnded(LogElement):
    def _draw_entry(self):
        return "Chat ended."


class LogCaptcha(LogElement):
    def _draw_entry(self):
        return "Could not connect due to Captcha requirement."


class LogInitiated(LogElement):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def _draw_entry(self):
        return f"Connecting to Omegle... Request data: {json.dumps(self.data)}"


class LogSearchTimeout(LogElement):
    def _draw_entry(self):
        return "Could not find partner with same interests."


class LogBotDetected(LogElement):
    def _draw_entry(self):
        return "Stranger detected as bot."


class LogConnectionError(LogElement):
    def _draw_entry(self):
        return "Unexpected server disconnect."


class LogMiscError(LogElement):
    def __init__(self, error):
        super().__init__()
        self.error = error

    def _draw_entry(self):
        return f"Encountered error: {self.error}"


class LogBanned(LogElement):
    def _draw_entry(self):
        return "IP is banned."


class LogNoResponse(LogElement):
    def _draw_entry(self):
        return "Empty response from server."


class ChatLog:
    def __init__(self):
        self.entries = []

    def log_entry(self, entry):
        self.entries.append(entry)

    def draw(self):
        log_str = ""
        for entry in self.entries:
            log_str += entry.draw()
            log_str += "\n"
        if len(log_str) > 0:
            log_str = log_str[:-1]
        return log_str

    def write_to_file(self, file: _io.TextIOWrapper):
        if len(self.entries) == 0:
            file.write("")
            return

        not_last_entries = self.entries[:-1]
        for entry in not_last_entries:
            file.write(entry.draw() + "\n")
        file.write(self.entries[-1].draw())

    def get_length(self):
        return len(self.entries)

    def got_convo(self):
        for entry in self.entries:
            if isinstance(entry, LogBotDetected):
                return False
        for entry in self.entries:
            if isinstance(entry, LogGotMessage):
                return True
        return False
