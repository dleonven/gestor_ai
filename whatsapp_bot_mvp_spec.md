
# WhatsApp Bot – Mini MVP (Hello World)

## Overview

This project implements the **smallest possible MVP** for a WhatsApp bot.

The goal is to verify that the system can:

1. Receive messages from WhatsApp.
2. Process the webhook event.
3. Reply automatically with **"hello world"**.

At this stage there is:

- No database
- No user roles
- No contract logic
- No admin panel

This MVP only validates the **end-to-end integration** between WhatsApp and the backend.

---

# Goal

Allow two users:

- Tenant **X**
- Landlord **Y**

to send a message to a WhatsApp number and receive an automatic response:

```
hello world
```

The system should respond to **any message received**.

---

# Architecture

```
User (X/Y)
    |
    | WhatsApp message
    |
WhatsApp Cloud API
    |
    | Webhook (POST)
    |
Backend Server
    |
    | Send message API
    |
WhatsApp Cloud API
    |
    | Message delivered
    |
User receives "hello world"
```

---

# Tech Stack (suggested)

Backend options:

- Node.js + Express
- Python + FastAPI

Requirements:

- Public HTTPS endpoint
- Access to WhatsApp Cloud API

---

# Project Requirements

## Functional Requirements

### 1. Webhook Verification

Endpoint:

GET /webhook

Purpose:

Allow Meta to verify the webhook during configuration.

Behavior:

1. Read query parameters:
   - hub.mode
   - hub.verify_token
   - hub.challenge

2. Compare hub.verify_token with the server environment variable VERIFY_TOKEN.

3. If valid:
   - Return hub.challenge
   - HTTP status 200

4. If invalid:
   - Return 403

---

### 2. Receive WhatsApp Messages

Endpoint:

POST /webhook

Responsibilities:

- Receive incoming webhook events from WhatsApp
- Extract the sender phone number
- Detect message events
- Trigger a response

Data to extract:

- from (phone number)
- message_id
- text.body (if present)

The endpoint must always return:

HTTP 200

---

### 3. Send Reply Message

After receiving a message, the server must send a reply using the WhatsApp Cloud API.

Response:

hello world

Send request:

POST https://graph.facebook.com/vXX.X/{PHONE_NUMBER_ID}/messages

Payload:

{
  "messaging_product": "whatsapp",
  "to": "<sender phone>",
  "type": "text",
  "text": {
    "body": "hello world"
  }
}

---

# Environment Variables

The application requires the following environment variables:

VERIFY_TOKEN=your_verify_token
WHATSAPP_TOKEN=meta_access_token
PHONE_NUMBER_ID=your_phone_number_id
PORT=3000
GRAPH_API_VERSION=v19.0

---

# Endpoints

## Health Check

GET /health

Response:

200 OK
ok

---

## Webhook Verification

GET /webhook

Used by Meta to verify the webhook.

---

## Webhook Receiver

POST /webhook

Receives incoming WhatsApp messages.

---

# Logging

Minimum logs should include:

- timestamp
- sender phone
- message id
- message content
- send message status (success/error)

Example:

[2026-01-10 12:30:10]
from: +56912345678
message: hola
reply: hello world
status: success

---

# Setup Instructions

## 1. Create Meta App

Create an app in:

https://developers.facebook.com/

Add product:

WhatsApp

---

## 2. Configure WhatsApp Cloud API

Retrieve:

- Access Token
- Phone Number ID
- Business Account

---

## 3. Configure Webhook

Webhook URL:

https://your-domain.com/webhook

Verify Token:

same value as VERIFY_TOKEN

Subscribe to event:

messages

---

## 4. Deploy Backend

Deploy the server with a **public HTTPS URL**.

Possible platforms:

- Render
- Railway
- Fly.io
- AWS
- GCP

---

# Manual Test

1. Deploy the server.
2. Configure the webhook in Meta.
3. Send a message from phone **X**.
4. Verify logs show the incoming message.
5. Confirm phone **X** receives:

hello world

6. Repeat with phone **Y**.

---

# Definition of Done

The MVP is complete when:

- Webhook verification succeeds
- The server receives incoming messages
- The system replies hello world
- Both X and Y receive the response

---

# Next Iteration (Future Work)

Next steps after this MVP:

1. Restrict responses to authorized users only
2. Add database for users
3. Add properties
4. Support document uploads
5. Implement contract knowledge

This MVP only validates WhatsApp connectivity.
