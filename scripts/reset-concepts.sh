#!/usr/bin/env bash
# Clear a subject's concepts and cards, then regenerate from the existing
# transcripts. Nothing is re-uploaded — chunks and embeddings are untouched.
#
#   ./scripts/reset-concepts.sh "cv"                 local dev stack
#   ./scripts/reset-concepts.sh "cv" --prod          deployed stack
#   ./scripts/reset-concepts.sh "cv" --prod --yes    skip the confirmation
#
# Destroys SM-2 review history for the affected cards. That is the point of
# the preview and the prompt.
set -euo pipefail

SUBJECT="${1:-}"
shift || true

# Explicit rather than inferred. A stray .env.production on a laptop is not
# evidence that the production stack is the one running.
USE_PROD=0
CONFIRM=""
for arg in "$@"; do
  case "$arg" in
    --prod) USE_PROD=1 ;;
    --yes)  CONFIRM="--yes" ;;
  esac
done

if [ -z "$SUBJECT" ]; then
  echo "usage: $0 \"<subject name>\" [--prod] [--yes]" >&2
  exit 1
fi

if [ "$USE_PROD" = "1" ]; then
  DC=(docker compose -f docker-compose.prod.yml --env-file .env.production)
else
  DC=(docker compose)
fi

psql() { "${DC[@]}" exec -T db psql -U studyhelper -d studyhelper "$@"; }

echo "Subject: $SUBJECT"
echo
psql -c "
select t.id as transcript, t.title, t.status,
       (select count(*) from concepts c where c.transcript_id = t.id) as concepts,
       (select count(*) from cards cd where cd.transcript_id = t.id) as cards,
       (select count(*) from transcript_chunks ch where ch.transcript_id = t.id) as chunks_kept
from transcripts t
join subject_profiles p on p.id = t.profile_id
where lower(p.name) = lower('$SUBJECT')
order by t.id;"

TOTAL=$(psql -tAc "
select coalesce(count(cd.id), 0) from cards cd
join transcripts t on t.id = cd.transcript_id
join subject_profiles p on p.id = t.profile_id
where lower(p.name) = lower('$SUBJECT');" | tr -d '[:space:]')

if [ "$TOTAL" = "0" ]; then
  echo "No cards to clear."
else
  echo "This deletes $TOTAL card(s) and their review history, and all concepts above."
  if [ "$CONFIRM" != "--yes" ]; then
    printf 'Type the subject name again to confirm: '
    read -r TYPED
    if [ "$TYPED" != "$SUBJECT" ]; then
      echo "Not confirmed, nothing changed." >&2
      exit 1
    fi
  fi
fi

# Cards first: cards.concept_id is a plain foreign key with no cascade
psql -v ON_ERROR_STOP=1 <<SQL
begin;
delete from cards where transcript_id in (
  select t.id from transcripts t join subject_profiles p on p.id = t.profile_id
  where lower(p.name) = lower('$SUBJECT'));
delete from concepts where transcript_id in (
  select t.id from transcripts t join subject_profiles p on p.id = t.profile_id
  where lower(p.name) = lower('$SUBJECT'));
commit;
SQL

echo
echo "Cleared. Re-queueing concept generation..."

IDS=$(psql -tAc "
select t.id from transcripts t
join subject_profiles p on p.id = t.profile_id
where lower(p.name) = lower('$SUBJECT') and t.status = 'COMPLETED'
order by t.id;" | tr -d '\r')

if [ -z "$IDS" ]; then
  echo "No processed transcripts to regenerate from." >&2
  exit 0
fi

for ID in $IDS; do
  "${DC[@]}" exec -T backend python -c "
from app.tasks.concepts import generate_concepts_task
r = generate_concepts_task.delay(transcript_id=$ID)
print(f'  queued transcript $ID -> {r.id}')"
done

echo
echo "Running on the worker. Watch with:  ${DC[*]} logs -f celery_worker"
