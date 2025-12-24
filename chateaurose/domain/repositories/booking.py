from typing import Protocol


class BookingRepositoryPort(Protocol):
    def add(self, booking):
        ...

    def get(self, booking_id: str):
        ...

    def update(self, booking):
        ...
