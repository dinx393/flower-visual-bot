# Flower Visual Bot

Production foundation for a Telegram-based assistant that turns a flower-shop photo into a reviewed Story.

## Product flow

`Telegram → job queue → agent plan → image provider → quality control → employee approval → Google Drive`

The agent never publishes automatically. A result that fails any hard check is returned for a new attempt or manual review. Only an employee approval triggers Drive upload and an approval-history record.

Positive feedback is stored separately from approval: it creates a calibration candidate in `database/case-history/`, while only explicit approval creates a publishable test reference in `tests/fixtures/approved/`.

## Agent memory

The core uses two complementary forms of memory:

- semantic memory: every rule document in `knowledge/` is included in full;
- episodic memory: approved case cards and revision histories are indexed separately, then the most relevant complete records and up to three approved reference images are attached to a generation plan.

Case retrieval uses the employee instruction plus a structured visual description of the current source image. This keeps all rules active while preventing a growing case library from being copied wholesale into every request. Retrieved cases are evidence and failure history, not templates.

Every generation plan also contains a decision passport: the exact rules, approved case records, anti-lessons and employee directions used when the plan was assembled. Any future chat or interface must show this stored passport when asked what informed a design; it must not reconstruct an explanation from its temporary conversation context.

## Boundaries

- `knowledge/` is versioned, read-only knowledge for decisions. Every Markdown document in this folder is included in the agent's complete knowledge snapshot.
- `database/` contains schemas and migrations, not production secrets or image files.
- `app/` contains application code; integration credentials belong in environment variables.
- `tests/` will contain fixed source images, expected plans, and regression checks.

## Local start (after provider integrations are implemented)

1. Copy `.env.example` to `.env` and fill in credentials.
2. Start the stack with `docker compose -f infra/docker-compose.yml up --build`.

The current foundation deliberately has no default model or Telegram token. Those are deployment choices, not knowledge embedded in the agent.

## Latency policy

- Every finished Story is made by the image generator. There is no local-compositor fallback and no lower-quality “fast mode”.
- One standard production profile is used for every intervention: `gpt-image-2.5-flare` at medium quality, one generation attempt and a 120-second generation deadline. The intervention level changes the prompt, not the visual-quality tier.
- At startup the service reads every knowledge document once and builds one complete in-memory snapshot. Each job only compares filenames, timestamps and sizes; if nothing changed, it reuses the snapshot without rereading documents. When one document changes, only that document is reread; the complete prompt context is then assembled from the changed fragment plus the other fragments already in memory. Added files are read once and removed files are simply excluded. The exact snapshot version is recorded with the job for later audit. The full snapshot is placed at the stable beginning of every model prompt because the model itself is stateless between image-generation calls.
- Automatic retries are disabled. A failed quality check is shown as a failure or sent to manual review instead of silently adding several minutes.
- Every job records planning, rendering, quality-control and upload timings separately.
