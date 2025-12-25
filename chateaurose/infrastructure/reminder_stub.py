class ReminderGatewayStub:
    def __init__(self):
        self.reminders = []

    def schedule(self, recipient, send_at, subject, body):
        self.reminders.append(
            {
                "recipient": recipient,
                "send_at": send_at,
                "subject": subject,
                "body": body,
            }
        )
