class FixedClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now
