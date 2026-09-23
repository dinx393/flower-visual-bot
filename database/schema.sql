CREATE TABLE jobs (
  id UUID PRIMARY KEY,
  telegram_chat_id TEXT NOT NULL,
  source_file_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE versions (
  id UUID PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES jobs(id),
  generation_attempt INTEGER NOT NULL,
  plan JSONB NOT NULL,
  result_file_id TEXT,
  quality_report JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
  id UUID PRIMARY KEY,
  version_id UUID NOT NULL REFERENCES versions(id),
  decision TEXT NOT NULL CHECK (decision IN ('approved', 'positive_feedback', 'revision_requested', 'rejected')),
  reason TEXT,
  annotations JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
