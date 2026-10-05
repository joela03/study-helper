# Architecture

How this application is put together, why each piece is the way it is, and
where the sharp edges are.

---

## 1. What it does

You give it a lecture — slides as a PDF, plus a transcript. It:

1. Extracts text from both and merges them
2. Splits the merged text into **semantic chunks** at topic boundaries
3. Embeds each chunk as a 384-dimension vector and stores it in Postgres
4. Walks the lecture window by window, condensing each into a **concept** —
   a definition, an intuition, how it works, its limitation, and where it
   fits in the module
5. Turns each concept's questions into **flashcards**
6. Schedules those cards with **SM-2 spaced repetition**

The unit of ownership is a **subject** (`SubjectProfile`). Everything else
hangs off one.

---

## 2. The shape of the system

```
                            ┌─────────────┐
   browser ────── 443 ────▶ │    Caddy    │  TLS, single origin
                            └──────┬──────┘
                        /api/*     │     everything else
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
            ┌─────────────┐                 ┌─────────────┐
            │   FastAPI   │                 │   Next.js   │
            │   :8000     │                 │   :3000     │
            └──┬───────┬──┘                 └─────────────┘
               │       │
     ┌─────────┘       └────────┐
     ▼                          ▼
┌──────────┐              ┌──────────┐      ┌──────────────┐
│ Postgres │◀─────────────│  Redis   │◀─────│    Celery    │
│ pgvector │              │  broker  │      │    worker    │
└──────────┘              └──────────┘      └──────┬───────┘
     ▲                                             │
     └─────────────────────────────────────────────┘
                                                   │
                                            ┌──────▼───────┐
                                            │  Groq / LLM  │
                                            └──────────────┘
```

Five services. The API never does slow work: anything involving an LLM or an
embedding model is handed to the worker over Redis. Caddy puts the browser
and the API on one origin, so normal use involves no CORS preflight at all.

---

## 3. Data model

Ten tables. The spine is `users → subject_profiles → transcripts → chunks`,
with `concepts` and `cards` hanging off a transcript.

```
users
  └── subject_profiles (user_id)          ← ownership is enforced here
        ├── course_materials               outline, past papers, notes
        ├── transcripts
        │     ├── transcript_chunks        content + vector(384)
        │     └── concepts                 the condensed explainers
        │           └── cards              SM-2 state
        └── sample_questions
invite_codes
```

**Why ownership lives on the subject and nowhere else.** Transcripts, cards,
concepts and materials all carry a `profile_id`. Rather than adding a
`user_id` to five tables and checking it in twenty places, every route
resolves the subject and checks that once:

```python
# backend/app/core/deps.py
async def get_owned_profile(profile_id: int, user: User, db: AsyncSession):
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    # 404 rather than 403: don't confirm an id exists to someone
    # who isn't allowed to see it
    if not profile or (profile.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile
```

The 404-not-403 choice matters. A 403 tells an attacker "this id is real,
you just can't have it", which turns the endpoint into an enumeration oracle.

---

## 4. The ingestion pipeline

### 4.1 Getting text in

Three ways to supply the spoken half of a lecture, all landing in the same
column (`transcripts.audio_text`) so nothing downstream has to care:

- `transcript_text` — pasted in
- `transcript_file` — a `.txt` / `.md` / `.docx` export
- `audio` — a recording for Whisper (**off by default**, see §9)

The upload endpoint sniffs the file rather than trusting the field it arrived
in, because people reasonably drop a transcript into the audio box:

```python
# backend/app/api/routes/transcripts.py
# A transcript sent in the audio field is still a transcript.
# Re-route it instead of sending a text file to Whisper.
if audio and is_transcript_file(audio.filename) and not transcript_file:
    transcript_file = audio
    audio = None
```

### 4.2 Merging

Slides give structure, speech gives the explanation. They're concatenated
under markers:

```python
# backend/app/services/merging.py
parts.append("=== DOCUMENT CONTENT ===\n")
parts.append(document_text.strip())
parts.append("=== AUDIO TRANSCRIPTION ===\n")
parts.append(audio_text.strip())
```

**This is the weakest part of the design** and it has a measurable
consequence — see §10.

### 4.3 Semantic chunking

Not fixed-size splitting. Sentences are embedded, and a new chunk starts when
consecutive sentences stop being about the same thing:

```python
# backend/app/services/chunking.py
embeddings = model.encode(sentences, convert_to_numpy=True)

for i in range(1, len(sentences)):
    similarity = compute_similarity(embeddings[i-1], embeddings[i])

    should_split = (
        similarity < similarity_threshold      # topic changed
        and current_length >= min_chunk_size   # but don't make slivers
    )
    would_exceed_max = current_length + sentence_length > max_chunk_size

    if should_split or would_exceed_max:
        chunks.append(" ".join(current_chunk))
        current_chunk = [sentences[i]]
```

Two guards stop it degenerating: `min_chunk_size` prevents one-sentence
chunks when a lecturer's style swings around, and `max_chunk_size` forces a
split even if the topic never changes.

### 4.4 Embeddings and retrieval

`all-MiniLM-L6-v2`, 384 dimensions, stored in a `vector(384)` column.
Retrieval uses pgvector's cosine-distance operator with the index doing the
ordering:

```sql
SELECT tc.content, 1 - (tc.embedding <=> cast(:embedding as vector)) AS similarity
FROM transcript_chunks tc
JOIN transcripts t ON tc.transcript_id = t.id
WHERE t.profile_id = ANY(:profile_ids)
ORDER BY tc.embedding <=> cast(:embedding as vector)
LIMIT :limit
```

`<=>` is cosine distance (lower is closer); `1 - distance` converts to a
similarity score for display. Note the `profile_ids` filter — an unscoped
semantic search would happily return another user's lecture.

---

## 5. Generation

This is where most of the engineering went, because the constraints are
unusual.

### 5.1 Windowing

A whole lecture is far too big for one request — 100k characters against a
free-tier limit. The lecture is cut into consecutive windows, and each window
becomes one LLM call:

```python
# backend/app/services/generation.py
CONCEPT_WINDOW_CHARS = 4_000

def window_chunk_indices(chunks, window_chars=CONCEPT_WINDOW_CHARS):
    windows, current, used = [], [], 0
    for i, chunk in enumerate(chunks):
        if current and used + len(chunk) > window_chars:
            windows.append(current)
            current, used = [], 0
        current.append(i)
        used += len(chunk)
    if current:
        windows.append(current)
    return windows
```

**Window size is the single most consequential number here.** At 12,000
characters one window spanned noise reduction, convolution, edge detection,
Fourier *and* the Convolution Theorem, and a pass yields one concept — so
four of six lecture sections got no coverage at all. Dropping it to 4,000
took coverage from 2/6 sections to 6/6.

### 5.2 Carrying context forward

Each pass is told what's already been written, so the set reads as a sequence
rather than a bag:

```python
recent = list(seen)[-PRIOR_QUESTION_CONTEXT:]

raw_concepts = _concepts_from_provider(
    content="\n\n".join(chunks[i] for i in window),
    provider=provider,
    prior_titles=recent,       # "don't repeat these; build on them"
    course_context=course_context,
)
```

### 5.3 Provenance, and why re-runs are safe

Every concept records the chunks it came from:

```python
source_chunks: Mapped[Optional[list]] = mapped_column(JSON, default=list)
```

That turns "did it cover everything?" from a judgement into arithmetic, and
makes regeneration **additive**:

```python
covered = skip_chunks or set()
pending = [w for w in index_windows if any(i not in covered for i in w)]
```

Re-running a fully covered lecture does nothing — 0 passes, 0 created, 0
destroyed. Re-running one with a gap processes only the gap. This matters
because cards carry SM-2 review history: a regenerate that wiped and rebuilt
would silently throw away weeks of scheduling.

### 5.4 Streaming results

Concepts are persisted the moment each one exists, not batched at the end:

```python
def persist(data: dict, window: list[int]) -> None:
    concept = Concept(..., source_chunks=window)
    db.add(concept)
    db.flush()
    # ... create cards from its questions ...
    db.commit()            # committed immediately
```

A 25-pass lecture takes 10+ minutes. Batching would mean staring at a spinner
and losing everything to one failure; this way the first concept is readable
within seconds and a crash keeps what was done.

### 5.5 Living inside a rate limit

Groq's free tier allows **1,000 output tokens per minute** and rejects a
single request whose *expected* output exceeds that. Two non-obvious findings
shaped the code:

**`max_tokens` doesn't control the estimate.** It reported `Requested 1587`
whether `max_tokens` was 8000 or 900, because the model reserves for its own
reasoning. You can't negotiate below that floor — you can only ask for less
content. That's why the prompt requests *one* concept per pass.

**Lowering `max_tokens` creates a worse failure.** The response truncates
mid-array and `json.loads` throws, discarding concepts that were already
complete. So parsing salvages what finished:

```python
def _parse_json_array(response_text: str) -> list:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Decode object by object; a truncated array still yields the
    # ones that completed
    decoder = json.JSONDecoder()
    objects, index = [], text.find("{")
    while index != -1:
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        objects.append(obj)
        index = text.find("{", end)
    return objects
```

Plus a retry that waits for the per-minute allowance to refill rather than
losing the window's work:

```python
def _call_with_retry(fn, attempts=3, base_delay=20.0):
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            if getattr(e, "status_code", None) != 429 and "rate_limit" not in str(e).lower():
                raise
            if attempt < attempts - 1:
                time.sleep(base_delay * (attempt + 1))
    raise last_error
```

### 5.6 Course materials as standing context

Each subject can hold an outline, past papers and problem sheets. They're
condensed into a bounded brief that rides along in every prompt:

```python
COURSE_CONTEXT_CHARS = 1_800   # shares the request with ~4k of lecture

def build_course_context(materials):
    order = {"outline": 0, "problem_sheet": 1, "past_paper": 2, "notes": 3}
    ranked = sorted(materials, key=lambda m: order.get(m[0], 4))
    ...
```

The budget is the point. A past paper is 9,000 characters; pasting it whole
would blow the same limit §5.5 is working around.

---

## 6. Background processing

Celery over Redis. Two tasks: `process_transcript` and
`generate_concepts_task`.

**Tasks are declared explicitly**, which is not cosmetic:

```python
# backend/app/tasks/__init__.py
celery_app = Celery(
    "study_helper",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # autodiscover_tasks(["app.tasks"]) looks for a submodule *named*
    # tasks — app.tasks.tasks — which doesn't exist. The worker started
    # with an empty registry and discarded every message it received.
    include=["app.tasks.transcription", "app.tasks.concepts"],
)
```

That bug meant no transcript had ever been chunked. The worker logged
`Received unregistered task ... The message has been ignored and discarded`
and carried on looking healthy.

**Progress is reported per pass**, so the UI can show something true:

```python
self.update_state(state="PROGRESS", meta={
    "stage": "condensing",
    "current": current, "total": total,
    "concepts": counters["concepts"],
})
```

**Errors are returned, not raised.** A raised exception gives Celery's
`FAILURE` state with a stringified traceback; returning `{"error": ...}`
lets the status endpoint show a sentence a person can act on.

---

## 7. Spaced repetition

Standard SM-2 with one deliberate deviation:

```python
# backend/app/models/card.py
if quality >= 3:                                  # passed
    if self.repetitions == 0:   self.interval = 1
    elif self.repetitions == 1: self.interval = 6
    else:                       self.interval = round(self.interval * self.ease_factor)
    self.repetitions += 1
    self.next_review = date.today() + timedelta(days=self.interval)
else:                                             # failed
    self.repetitions = 0
    self.interval = 0
    self.next_review = date.today()               # stays in today's queue
    failed = True

self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
return failed
```

Textbook SM-2 sends a failed card to tomorrow. Here it keeps
`next_review = today` and returns `failed`, so the session re-queues it to the
back and you see it again before finishing. The ease factor floor of 1.3 stops
a repeatedly-failed card collapsing to a permanent daily nag.

---

## 8. Authentication

JWT bearer tokens, bcrypt hashes, used directly rather than via passlib
(which has long-running bcrypt 4.x compatibility problems).

```python
# backend/app/core/security.py
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Malformed hash in the database shouldn't look like a valid login
        return False
```

That `except ValueError` is load-bearing: the ownership migration seeds the
admin account with `"!"` as its hash, which bcrypt rejects as malformed. The
catch turns "unparseable hash" into "no password matches" rather than a 500.

Sign-ups are closed by default (`REQUIRE_INVITE=true`) because an open
registration endpoint on a public URL is an invitation to spend your LLM
quota. Every rejection returns the same message so the endpoint can't be used
to probe which codes exist.

---

## 9. Optional Whisper

Audio transcription is **installed-but-not-default**. Lectures normally come
with a transcript already, and `faster-whisper` plus `ffmpeg` was the largest
thing the worker loaded for a path rarely taken.

```python
# backend/app/services/transcription.py
def _load_whisper():
    if not settings.ENABLE_AUDIO_TRANSCRIPTION:
        raise AudioTranscriptionUnavailable(
            "Audio transcription is turned off. Paste the lecture transcript "
            "instead, or set ENABLE_AUDIO_TRANSCRIPTION=true after installing "
            "faster-whisper."
        )
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise AudioTranscriptionUnavailable(...) from e
    return WhisperModel
```

The import is deferred so the rest of the pipeline runs without the package
present, and the API rejects audio uploads up front rather than queueing work
the worker can't finish.

---

## 10. Frontend

Next.js App Router, Tailwind v4, deliberately not a SaaS dashboard — the
visual language is paper, folders and index cards.

**Per-subject colour is derived, not stored:**

```typescript
// frontend/src/lib/accents.ts
export function accentFor(id: number): Accent {
  const i = ((id % ACCENTS.length) + ACCENTS.length) % ACCENTS.length;
  return ACCENTS[i];
}

// Stable rotation so a row of folders never snaps into a grid,
// and doesn't jump between renders
export function rotationFor(id: number, spread = 1.6): number {
  const h = Math.sin(id * 12.9898) * 43758.5453;
  return Math.round(((h - Math.floor(h)) * 2 - 1) * spread * 100) / 100;
}
```

**Shadows use `filter: drop-shadow`, not `box-shadow`,** so they follow the
folded-corner `clip-path` rather than outlining a rectangle:

```css
.lift {
  transform: rotate(var(--rot, 0deg));
  filter: drop-shadow(0 1px 0.5px rgb(35 48 58 / 0.14))
          drop-shadow(var(--lx, 0px) 7px 9px rgb(35 48 58 / 0.13));
}
```

**`clip-path` overrides `border-radius`**, so the fold and the corner radii
live on separate elements — the radii on a wrapper with `overflow: hidden`,
the fold on the child.

**The paper surface is set before first paint** by an inline script, rather
than after hydration, so the saved choice doesn't flash in:

```html
<script>(function(){try{var p=localStorage.getItem("study-helper:paper");
  if(["blank","dot","grid"].indexOf(p)>-1)
    document.documentElement.setAttribute("data-paper",p)}catch(e){}})()</script>
```

**`NEXT_PUBLIC_API_URL` is a build argument, not a runtime variable** — Next
inlines it into the client bundle, so setting it at runtime silently does
nothing and the browser calls localhost.

---

## 11. Deployment

One VPS, `docker-compose.prod.yml`, Caddy for automatic TLS. Only Caddy
publishes ports. Required secrets use `${VAR:?}` so a missing value fails at
startup instead of falling back to something insecure.

A guard refuses to boot with production settings that are only safe locally:

```python
def _check_production_config() -> None:
    if settings.ENVIRONMENT != "production":
        return
    problems = []
    if settings.SECRET_KEY == INSECURE_SECRET:
        problems.append("SECRET_KEY is still the development default")
    if any("localhost" in o for o in settings.cors_origins):
        problems.append(f"CORS_ORIGINS still points at localhost")
    if "studyhelper:studyhelper@" in settings.DATABASE_URL:
        problems.append("DATABASE_URL still uses the default password")
    if problems:
        raise RuntimeError("Refusing to start in production:\n  - " + "\n  - ".join(problems))
```

A default signing key lets anyone mint a token for any account, and it fails
*silently* — the app works perfectly until someone notices.

**Image size:** 10.5GB → 2.75GB by installing CPU-only torch. `sentence-
transformers` pulls torch, and pip's default wheel bundles the CUDA runtime —
`nvidia/*` was 3.3GB and `triton` another 818MB of GPU libraries a CPU host
never loads.

Schema is owned by Alembic. `create_all` was removed because it creates
missing *tables* but never alters existing ones, so column changes silently
didn't apply.

---

## 12. Known gaps

Honest list, roughly by importance.

**Slides and speech aren't interleaved.** `merge_document_and_audio`
concatenates the whole deck then the whole transcript. Windows late in the
sequence are therefore the transcript restarting the lecture from the
beginning, which produces concepts duplicating ground the early windows
already covered — measured at 4 of 11 on one lecture. The fix is aligning
transcript segments to slides by embedding similarity (the vectors already
exist). `merging.py` has a `merge_with_alignment` stub noting exactly this.

**Coverage means "every chunk was looked at", not "every idea became a
concept".** A pass yields one concept, so a dense window can still drop
detail. Making coverage mean the stronger thing needs concepts to declare
which slide *pages* they explain.

**No evaluation framework.** There is no way to tell whether a prompt change
improved anything. When coverage went from 2/6 sections to 6/6, the only
measurement was counting by hand.

**Multi-provider is really single-provider.** `get_available_provider()`
returns the first provider with a configured key. There's no failover on
error and no cost-based routing.

**Rate limits are per-organisation, not per-user.** Two people generating
concepts at once will starve each other, and the backoff makes both slow
rather than failing one cleanly.

**Tests cover almost nothing.** One file, `test_health.py`. The pure
functions — SM-2 scheduling, window budgeting, truncated-JSON salvage,
coverage arithmetic — are all easily testable and all untested.

**No backups.** The database is a Docker volume. The embeddings are the
expensive part to regenerate.
