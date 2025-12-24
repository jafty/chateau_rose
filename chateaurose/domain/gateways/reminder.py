from typing import Protocol


class ReminderGatewayPort(Protocol):
    def schedule(self, recipient: str, send_at, subject: str, body: str) -> None:
        ...
