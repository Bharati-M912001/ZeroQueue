# Connecting the real Intercom Messenger

The webhook code is already live-verified from the earlier build (200 OK,
signature check, dedupe, loop prevention). This is the setup path.

## Before you start: rotate the token

The old Intercom access token was pasted into a chat on Sep 16 - treat it
as leaked. In Intercom: Settings -> Developers -> Authentication -> revoke
and create a new token. Put ONLY the new token in `.env`. Never send it
through WhatsApp again.

## Steps

1. Start the backend (`scripts\run_backend.bat`).
2. In a THIRD terminal, start the tunnel: `ngrok http 8000`
   Copy the https URL it prints (e.g. https://abc123.ngrok-free.app).
   Note: free ngrok URLs change on every restart - when it changes, update
   the webhook URL in Intercom (step 4) again.
3. Fill `.env`: INTERCOM_ACCESS_TOKEN (the ROTATED one), INTERCOM_ADMIN_ID,
   INTERCOM_TEAM_ID, INTERCOM_WEBHOOK_SECRET, MOCK_MODE=false.
4. Intercom -> Settings -> Developers -> Webhooks: add endpoint
   `https://<your-ngrok-url>/api/webhooks/intercom`
   and subscribe to `conversation.user.created` and
   `conversation.user.replied`. Copy the webhook secret into `.env`.
5. Send a message in the Messenger. Watch the backend terminal:
   - `invalid_signature` -> the webhook secret is wrong.
   - nothing at all -> Intercom cannot reach your URL; check ngrok is on.
6. Handoff check: say "talk to a human" in the Messenger. The conversation
   should get an acknowledgement, an internal note, and land with your
   human team in the Intercom Inbox.

## The four gates (go / no-go for keeping Intercom in the demo)

1. Messenger loads on your page. 2. Webhook reaches FastAPI (200 in the
logs). 3. The bot's reply appears in the Messenger. 4. Handoff assigns
the conversation to your team. All four pass -> keep Intercom. Any gate
fails -> demo with the built-in chat; it is the same pipeline, so you
lose nothing on stage.
