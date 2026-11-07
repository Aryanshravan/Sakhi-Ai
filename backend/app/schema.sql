-- Sakhi AI schema. Idempotent: safe to run repeatedly (python -m app.migrate).
-- Row Level Security is enabled with no policies: only the backend (database
-- owner connection) can read or write. The public API keys get no access.

create table if not exists profiles (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null unique,
  pin_hash        text not null,
  parent_name     text not null,
  child_name      text not null,
  grade           smallint not null check (grade between 1 and 5),
  report_language text not null check (report_language in ('en', 'te', 'hi')),
  created_at      timestamptz not null default now()
);

create table if not exists login_sessions (
  token_hash text primary key,
  profile_id uuid not null references profiles(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

-- Keyed by the typed user ID so unknown IDs are rate limited identically.
create table if not exists login_attempts (
  user_id      text primary key,
  failures     integer not null default 0,
  locked_until timestamptz
);

create table if not exists lesson_sessions (
  id           uuid primary key default gen_random_uuid(),
  profile_id   uuid not null references profiles(id) on delete cascade,
  lesson_id    text not null,
  status       text not null default 'in_progress' check (status in ('in_progress', 'completed')),
  current_step integer not null default 0,
  summary      text,
  started_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  completed_at timestamptz
);

-- A child has at most one unfinished lesson, which is what makes resume work.
create unique index if not exists one_open_lesson_per_child
  on lesson_sessions (profile_id) where status = 'in_progress';

create table if not exists session_events (
  id         bigint generated always as identity primary key,
  session_id uuid not null references lesson_sessions(id) on delete cascade,
  profile_id uuid not null references profiles(id) on delete cascade,
  step       integer not null,
  skill      text not null,
  question   text not null,
  answer     text not null,
  is_correct boolean not null,
  created_at timestamptz not null default now()
);
create index if not exists session_events_profile_idx on session_events (profile_id, created_at desc);

create table if not exists skill_mastery (
  profile_id uuid not null references profiles(id) on delete cascade,
  skill      text not null,
  score      real not null,
  attempts   integer not null default 0,
  correct    integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (profile_id, skill)
);

alter table profiles        enable row level security;
alter table login_sessions  enable row level security;
alter table login_attempts  enable row level security;
alter table lesson_sessions enable row level security;
alter table session_events  enable row level security;
alter table skill_mastery   enable row level security;

-- Learning evidence: one row per question, updated as the child retries it (the backend is the source of truth).
alter table session_events add column if not exists topic        text;
alter table session_events add column if not exists expected     text;
alter table session_events add column if not exists first_answer text;
alter table session_events add column if not exists attempts     integer not null default 1;
alter table session_events add column if not exists answers      jsonb not null default '[]';
alter table session_events add column if not exists hint         text;
alter table session_events add column if not exists needed_help  boolean not null default false;
alter table session_events add column if not exists outcome      text not null default 'open';
alter table session_events add column if not exists updated_at   timestamptz not null default now();
do $$ begin
  alter table session_events add constraint session_events_outcome_check
    check (outcome in ('open', 'correct', 'correct_after_help', 'needs_practice'));
exception when duplicate_object then null; end $$;

-- Parent report for a finished session, with where it got to: generation -> speech -> Telegram delivery.
create table if not exists session_reports (
  session_id          uuid primary key references lesson_sessions(id) on delete cascade,
  profile_id          uuid not null references profiles(id) on delete cascade,
  language            text not null check (language in ('en', 'te', 'hi')),
  status              text not null default 'pending' check (status in (
    'pending', 'generating', 'ready', 'sending', 'sent',
    'generation_failed', 'tts_failed', 'delivery_failed', 'telegram_not_connected')),
  report_text         text,
  audio_seconds       real,
  attempts            integer not null default 0,
  telegram_message_id bigint,
  error               text,
  claimed_at          timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  sent_at             timestamptz
);

-- The parent's Telegram chat, and short-lived one-time tokens used to link it.
alter table profiles add column if not exists telegram_chat_id   bigint;
alter table profiles add column if not exists telegram_linked_at timestamptz;

create table if not exists telegram_link_tokens (
  token_hash text primary key,
  profile_id uuid not null references profiles(id) on delete cascade,
  expires_at timestamptz not null,
  used_at    timestamptz,
  created_at timestamptz not null default now()
);

alter table session_reports      enable row level security;
alter table telegram_link_tokens enable row level security;
