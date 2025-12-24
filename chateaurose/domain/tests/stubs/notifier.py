class InMemoryNotifier:
    def __init__(self):
        self.messages = []

    def notify(self, recipient, subject, body):
        self.messages.append({"recipient": recipient, "subject": subject, "body": body})
