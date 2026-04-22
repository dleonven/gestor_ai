# WhatsApp Bot MVP – Domain v0.2 (Properties, Contracts, Bills, Documents)

## Why this iteration exists

The current bot already proves the transport layer:

- WhatsApp webhook works
- PostgreSQL lookup works
- role-based replies work

The next bottleneck is not infrastructure. It is missing business data.

To answer useful landlord and tenant questions, the system needs a domain model for:

- properties
- contracts / tenancies
- rent collection
- utility bills
- owner costs
- uploaded documents and photos

This iteration defines the minimum structure needed to support the stage 1 product goals from the project brief.

## Stage 1 goals supported by this model

### Tenant-facing

- Ask for pending utility bills
- Ask contract questions on demand
- Upload and retrieve contract files
- Upload and retrieve move-in / move-out property photos

### Landlord-facing

- Ask whether rent was paid
- Ask when rent should be adjusted
- See property costs
- Estimate how much to provision monthly

## Design principles

- Keep `users` as the WhatsApp identity table
- Model business relationships separately from user identity
- Use raw SQL and direct Postgres access
- Store binary files in Supabase Storage, but keep metadata in Postgres
- Prefer append-only financial/event records over overwriting business history

## Core entities

### `users`

Already exists.

Purpose:
- WhatsApp identity
- role (`TENANT` or `LANDLORD`)

### `properties`

One physical rental property.

Examples:
- apartment
- house
- office

### `property_participants`

Links users to properties.

Purpose:
- one landlord can own many properties
- one tenant can be related to one or more properties across time

This table is not the legal contract. It is the user/property relationship.

### `tenancies`

Represents the actual rental contract period for a property.

Purpose:
- contract dates
- rent amount
- adjustment policy
- deposit
- contract status

This is the main table the bot should use for contractual answers.

### `rent_charges`

Expected monthly rent obligations.

Purpose:
- determine whether rent is due, overdue, or paid
- avoid deriving payment status only from free text

### `payments`

Actual money movements received.

Purpose:
- register rent payments
- later support utility or other payment types if needed

### `utility_accounts`

Service account per property.

Examples:
- electricity
- water
- gas
- internet
- community expenses

### `utility_bills`

Periodic bill records associated with a utility account.

Purpose:
- amount due
- due date
- billing period
- paid/unpaid status
- payment link

### `owner_expenses`

Non-rent costs that affect landlord cash flow.

Examples:
- maintenance
- insurance
- admin fee
- taxes
- repairs

### `documents`

Metadata for files stored in Supabase Storage.

Purpose:
- contracts
- utility bill PDFs
- payment receipts
- move-in photos
- move-out photos

The database stores metadata and relations. The actual file bytes should live in Storage.

## Upload architecture

### Storage decision

Use Supabase Storage for the files themselves.

Use Postgres only for:
- document metadata
- ownership and access relations
- extracted business references

### Upload entry points

Two upload modes should exist eventually:

1. Admin upload
   - upload contract PDFs, invoices, photos from an internal interface or script
2. WhatsApp-driven upload
   - user sends a media message
   - backend downloads the media from Meta
   - backend stores it in Supabase Storage
   - backend creates a `documents` row

### First upload flow to implement

Start with contract and inspection-photo uploads, not every file type at once.

Reason:
- they unlock the most valuable tenant and landlord questions
- they create the base pattern for all later uploads

## Recommended first question flows

### Tenant asks: "Tengo cuentas pendientes?"

Query:
- active tenancy for user
- property utility accounts
- unpaid utility bills ordered by due date

### Landlord asks: "Pagaron el arriendo?"

Query:
- active tenancy for landlord-owned property
- current month `rent_charges`
- linked payments
- derived status: paid / partially paid / overdue

### Tenant asks: "Cuando puedo dar aviso?"

Query:
- active tenancy
- notice period fields
- contract dates

### Tenant asks: "Como estaba el inmueble al recibirlo?"

Query:
- latest move-in inspection
- linked document/photo records

## Delivery order

### Iteration A

- add domain schema
- keep current webhook behavior
- start seeding properties, tenancies, bills, and documents manually

### Iteration B

- create admin-side ingestion scripts/endpoints
- allow contract and inspection-photo uploads

### Iteration C

- replace static role greetings with intent-aware responses powered by the new data model

## What should not be built yet

- full admin UI
- OCR pipeline for every document type
- background job orchestration
- embeddings / RAG layer
- payment processor integration

These can come later, after the base domain model is populated and queried successfully.
