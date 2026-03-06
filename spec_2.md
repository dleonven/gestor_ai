
# WhatsApp Bot MVP – DB v0.1 (Users + Role-based Hello)

## Overview

This specification defines the **first database-enabled iteration** of the WhatsApp bot.

The system already supports:

- WhatsApp → Webhook → Backend → Reply ("hello world")

This iteration introduces:

- A **PostgreSQL database**
- A **users table**
- Role-based responses

The bot will respond differently depending on whether the sender is:

- a **tenant (arrendatario)**
- a **landlord (arrendador)**
- an **unknown user**

---

# Goal

When a WhatsApp message arrives:

1. Extract the sender phone number
2. Look up the sender in the `users` table
3. Respond based on the user's role

### Responses

| Condition | Response |
|-----------|----------|
| role = TENANT | `hello arrendatario` |
| role = LANDLORD | `hello arrendador` |
| user not found | `no autorizado` |
| user inactive | `no autorizado` |

---

# Stack

Recommended database stack:

**Database**
- PostgreSQL (Supabase managed Postgres)

**Access**
- Direct Postgres connection from backend

**ORM**
- None required for this iteration
- Raw SQL is sufficient

---

# Database Schema

## Table: `users`

Purpose: store WhatsApp users and their roles.

### Fields

| Field | Type | Notes |
|------|------|------|
| id | UUID | Primary key |
| phone_e164 | TEXT | WhatsApp phone number |
| role | TEXT | TENANT or LANDLORD |
| display_name | TEXT | Optional |
| is_active | BOOLEAN | Default true |
| created_at | TIMESTAMPTZ | Default now() |
| updated_at | TIMESTAMPTZ | Auto-updated |

### Constraints

- `phone_e164` must be unique
- role must be one of:
  - TENANT
  - LANDLORD

---

# SQL Schema

Run this in the Supabase SQL editor.

```sql
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  phone_e164 text not null unique,
  role text not null,
  display_name text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint users_role_check check (role in ('TENANT', 'LANDLORD'))
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_users_updated_at on public.users;

create trigger trg_users_updated_at
before update on public.users
for each row execute function public.set_updated_at();
```
