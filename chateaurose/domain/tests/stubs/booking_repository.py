class InMemoryBookingRepository:
    def __init__(self):
        self.saved = {}

    def add(self, booking):
        self.saved[booking.id] = booking
        return booking

    def get(self, booking_id):
        return self.saved[booking_id]

    def update(self, booking):
        self.saved[booking.id] = booking
        return booking
