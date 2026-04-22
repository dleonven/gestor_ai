create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists public.properties (
  id uuid primary key default gen_random_uuid(),
  code text unique,
  name text not null,
  street_address text,
  commune text,
  city text,
  country_code text not null default 'CL',
  property_type text not null default 'RESIDENTIAL',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_properties_updated_at on public.properties;
create trigger trg_properties_updated_at
before update on public.properties
for each row execute function public.set_updated_at();

create table if not exists public.property_participants (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references public.properties(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  participant_role text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint property_participants_role_check check (
    participant_role in ('LANDLORD', 'TENANT', 'MANAGER')
  ),
  constraint property_participants_unique unique (property_id, user_id, participant_role)
);

drop trigger if exists trg_property_participants_updated_at on public.property_participants;
create trigger trg_property_participants_updated_at
before update on public.property_participants
for each row execute function public.set_updated_at();

create table if not exists public.tenancies (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references public.properties(id) on delete restrict,
  landlord_user_id uuid not null references public.users(id) on delete restrict,
  tenant_user_id uuid not null references public.users(id) on delete restrict,
  contract_status text not null default 'ACTIVE',
  contract_start_date date not null,
  contract_end_date date,
  notice_days integer,
  billing_day smallint not null default 1,
  monthly_rent_amount numeric(12,2) not null,
  rent_currency text not null default 'CLP',
  deposit_amount numeric(12,2),
  rent_adjustment_frequency_months smallint,
  rent_adjustment_index text,
  next_adjustment_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint tenancies_status_check check (
    contract_status in ('DRAFT', 'ACTIVE', 'ENDED', 'CANCELLED')
  )
);

drop trigger if exists trg_tenancies_updated_at on public.tenancies;
create trigger trg_tenancies_updated_at
before update on public.tenancies
for each row execute function public.set_updated_at();

create table if not exists public.rent_charges (
  id uuid primary key default gen_random_uuid(),
  tenancy_id uuid not null references public.tenancies(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  due_date date not null,
  amount_due numeric(12,2) not null,
  amount_paid numeric(12,2) not null default 0,
  charge_status text not null default 'PENDING',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rent_charges_status_check check (
    charge_status in ('PENDING', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'CANCELLED')
  ),
  constraint rent_charges_unique unique (tenancy_id, period_start, period_end)
);

drop trigger if exists trg_rent_charges_updated_at on public.rent_charges;
create trigger trg_rent_charges_updated_at
before update on public.rent_charges
for each row execute function public.set_updated_at();

create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  tenancy_id uuid not null references public.tenancies(id) on delete cascade,
  rent_charge_id uuid references public.rent_charges(id) on delete set null,
  payment_type text not null default 'RENT',
  payment_status text not null default 'CONFIRMED',
  paid_at timestamptz not null,
  amount numeric(12,2) not null,
  currency text not null default 'CLP',
  external_reference text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint payments_type_check check (
    payment_type in ('RENT', 'UTILITY', 'DEPOSIT', 'OTHER')
  ),
  constraint payments_status_check check (
    payment_status in ('PENDING', 'CONFIRMED', 'REJECTED', 'REFUNDED')
  )
);

drop trigger if exists trg_payments_updated_at on public.payments;
create trigger trg_payments_updated_at
before update on public.payments
for each row execute function public.set_updated_at();

create table if not exists public.utility_accounts (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references public.properties(id) on delete cascade,
  provider_name text not null,
  utility_type text not null,
  service_account_number text,
  payment_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint utility_accounts_type_check check (
    utility_type in ('ELECTRICITY', 'WATER', 'GAS', 'INTERNET', 'COMMUNITY_EXPENSE', 'OTHER')
  )
);

drop trigger if exists trg_utility_accounts_updated_at on public.utility_accounts;
create trigger trg_utility_accounts_updated_at
before update on public.utility_accounts
for each row execute function public.set_updated_at();

create table if not exists public.utility_bills (
  id uuid primary key default gen_random_uuid(),
  utility_account_id uuid not null references public.utility_accounts(id) on delete cascade,
  billing_period_start date,
  billing_period_end date,
  due_date date not null,
  amount_due numeric(12,2) not null,
  amount_paid numeric(12,2) not null default 0,
  bill_status text not null default 'PENDING',
  external_reference text,
  source_document_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint utility_bills_status_check check (
    bill_status in ('PENDING', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'CANCELLED')
  )
);

drop trigger if exists trg_utility_bills_updated_at on public.utility_bills;
create trigger trg_utility_bills_updated_at
before update on public.utility_bills
for each row execute function public.set_updated_at();

create table if not exists public.owner_expenses (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references public.properties(id) on delete cascade,
  expense_type text not null,
  expense_status text not null default 'RECORDED',
  incurred_on date not null,
  amount numeric(12,2) not null,
  currency text not null default 'CLP',
  notes text,
  source_document_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint owner_expenses_status_check check (
    expense_status in ('RECORDED', 'ESTIMATED', 'PAID', 'VOID')
  )
);

drop trigger if exists trg_owner_expenses_updated_at on public.owner_expenses;
create trigger trg_owner_expenses_updated_at
before update on public.owner_expenses
for each row execute function public.set_updated_at();

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references public.properties(id) on delete cascade,
  tenancy_id uuid references public.tenancies(id) on delete cascade,
  uploaded_by_user_id uuid references public.users(id) on delete set null,
  document_type text not null,
  storage_bucket text not null,
  storage_path text not null,
  original_filename text,
  mime_type text,
  file_size_bytes bigint,
  capture_source text not null default 'ADMIN',
  inspection_stage text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint documents_type_check check (
    document_type in (
      'CONTRACT',
      'UTILITY_BILL',
      'PAYMENT_RECEIPT',
      'PROPERTY_PHOTO',
      'INVENTORY_REPORT',
      'OTHER'
    )
  ),
  constraint documents_source_check check (
    capture_source in ('ADMIN', 'WHATSAPP', 'IMPORT')
  ),
  constraint documents_inspection_stage_check check (
    inspection_stage is null or inspection_stage in ('MOVE_IN', 'MOVE_OUT')
  ),
  constraint documents_storage_unique unique (storage_bucket, storage_path)
);

drop trigger if exists trg_documents_updated_at on public.documents;
create trigger trg_documents_updated_at
before update on public.documents
for each row execute function public.set_updated_at();

alter table public.utility_bills
  add constraint utility_bills_source_document_fk
  foreign key (source_document_id) references public.documents(id) on delete set null;

alter table public.owner_expenses
  add constraint owner_expenses_source_document_fk
  foreign key (source_document_id) references public.documents(id) on delete set null;

create index if not exists idx_property_participants_user_id
  on public.property_participants(user_id);

create index if not exists idx_tenancies_landlord_user_id
  on public.tenancies(landlord_user_id);

create index if not exists idx_tenancies_tenant_user_id
  on public.tenancies(tenant_user_id);

create index if not exists idx_rent_charges_tenancy_due_date
  on public.rent_charges(tenancy_id, due_date);

create index if not exists idx_payments_tenancy_paid_at
  on public.payments(tenancy_id, paid_at desc);

create index if not exists idx_utility_accounts_property_id
  on public.utility_accounts(property_id);

create index if not exists idx_utility_bills_due_date
  on public.utility_bills(due_date);

create index if not exists idx_owner_expenses_property_incurred_on
  on public.owner_expenses(property_id, incurred_on desc);

create index if not exists idx_documents_property_id
  on public.documents(property_id);

create index if not exists idx_documents_tenancy_id
  on public.documents(tenancy_id);
