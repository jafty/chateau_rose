from typing import Protocol


class ClockPort(Protocol):
    def now(self):
        ...
