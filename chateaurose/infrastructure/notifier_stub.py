class NotifierStub:
    def __init__(self):
        self.sent = []

    def notify(self, recipient, subject, body):
        self.sent.append({"recipient": recipient, "subject": subject, "body": body})
