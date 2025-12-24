from typing import Protocol


class NotifierPort(Protocol):
    def notify(self, recipient: str, subject: str, body: str) -> None:
        ...
