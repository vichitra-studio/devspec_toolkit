# Accounts seed (excerpt)

Members who forget their password reset it themselves through a link we email them.
The link works once and stops working 30 minutes after we send it.
We count on a member's email account being under their own control.
Support wants password tickets to stop landing on them.
No reset by SMS for now.
Every change goes through dev, CI and staging before production.
We hash passwords with argon2. Email goes out through MailRelay.
