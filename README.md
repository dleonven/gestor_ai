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
   - `KHIPU_BEARER_TOKEN` (optional, for ENEL debt lookups)
   - `KHIPU_BASE_URL` (optional, defaults to `https://api.khipu.com`)
   - `OPENAI_API_KEY` (optional, for contract Q&A tests)
   - `OPENAI_MODEL` (optional, defaults to `gpt-5`)
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

## Bot orchestration

The bot now follows a grounded orchestration pattern:

```text
WhatsApp message
-> authenticate sender
-> classify structured intent
-> fetch facts from deterministic tools/DB/API
-> compose a grounded Spanish response
-> send WhatsApp reply
```

The LLM is optional for intent classification and final wording when `OPENAI_API_KEY` is configured. Facts still come from deterministic sources such as PostgreSQL, contract documents, and utility lookup adapters. Without `OPENAI_API_KEY`, the bot uses deterministic fallback intent rules and fixed response templates.

The first utility capability is ENEL electricity debt lookup through the Sencillito prototype adapter. For a tenant question such as `quiero saber si mi departamento de navidad tiene deuda en la cuenta de luz`, the bot:

- extracts `UTILITY_DEBT`, `ELECTRICITY`, `ENEL`, and property hint `navidad`
- finds the active ENEL utility account associated with the sender
- consults the Sencillito ENEL balance endpoint
- replies with the grounded amount and document number

## Run tests

```bash
pytest
```

## Contract Q&A experiment

The repo now includes a direct PDF-to-model experiment using the OpenAI Responses API and file inputs.

The test contract is stored at [`data/contracts/contrato_prueba.pdf`](/Users/dleonven/Projects/ia-admin-propiedades/data/contracts/contrato_prueba.pdf).

Example:

```bash
./.venv/bin/python scripts/ask_contract_openai.py "Cuando puede el arrendatario dar aviso?"
```

This sends the PDF directly to the model as an `input_file`, without building retrieval or database extraction first.

## ENEL debt lookup test

The repo includes a direct Khipu ENEL test script using the `debt-status-by-client-identifier` endpoint.

Example:

```bash
./.venv/bin/python scripts/test_khipu_enel.py "1234567-8"
```

It reads `KHIPU_BEARER_TOKEN` from the environment and prints a normalized JSON summary plus the raw Khipu response.

## Sencillito ENEL debt lookup prototype

For prototype testing, the repo also includes a Sencillito-based ENEL lookup that uses the public balance endpoint observed from Sencillito's payment page.

Example:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/test_sencillito_enel.py "312091-0"
```

This is useful to validate the bot flow, but it should be treated as a non-contractual adapter until the integration is approved for production use.

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
