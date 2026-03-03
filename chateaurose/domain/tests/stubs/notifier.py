class InMemoryNotifier:
    def __init__(self):
        self.messages = []

    def notify(self, recipient, subject, body, reply_to=None):
        payload = {"recipient": recipient, "subject": subject, "body": body}
        if reply_to is not None:
            payload["reply_to"] = reply_to
        self.messages.append(payload)
