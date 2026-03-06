# WhatsApp Role-Based MVP

FastAPI service that verifies a Meta webhook, looks up the sender in PostgreSQL, and replies based on user role.

## Requirements

- Python 3.11+
- A Meta app with WhatsApp Cloud API enabled
- A public HTTPS URL for webhook delivery in production

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` into `.env` and set real values for:
   - `VERIFY_TOKEN`
   - `WHATSAPP_TOKEN`
   - `PHONE_NUMBER_ID`
   - `DATABASE_URL`
   - `GRAPH_API_VERSION`
   - `PORT`

4. Start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

## Endpoints

- `GET /health`
- `GET /webhook`
- `POST /webhook`

## Role-based replies

When a WhatsApp text message arrives, the app queries `public.users` by `phone_e164` and replies as follows:

- `role = TENANT` and active: `hello arrendatario`
- `role = LANDLORD` and active: `hello arrendador`
- user not found or inactive: `no autorizado`

## Run tests

```bash
pytest
```

## Render deployment

Use this start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set these environment variables in Render:

- `VERIFY_TOKEN`
- `WHATSAPP_TOKEN`
- `PHONE_NUMBER_ID`
- `DATABASE_URL`
- `GRAPH_API_VERSION`
- `PORT`

Use `/health` as the health check path.

## Meta webhook setup

Configure the WhatsApp webhook in Meta with:

- Webhook URL: `https://<your-render-domain>/webhook`
- Verify token: same value as `VERIFY_TOKEN`
- Subscription: `messages`

## Known limitations

- Replies only to inbound text messages
- Ignores unsupported/non-text events
- No deduplication
- Outbound send failures are logged but do not fail the webhook response
# gestor_ai
