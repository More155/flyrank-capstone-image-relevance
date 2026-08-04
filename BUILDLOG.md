# Build Log — AI usage

Honest record of where AI (Claude Code) helped, where it was wrong, and what
got changed as a result. This project has been built with heavy AI
assistance from the start — that's disclosed here, not hidden.

---

## 2026-08-03 — Wrong vision-model stack, corrected

**Where AI was wrong:** `BRIEF.md` (my own planning doc, written earlier in
this project) specified the `anthropic` SDK for vision tagging, with
structured output via forced tool use. That's a paid API. I built Step 1
(`guard.py`) and Step 2 (the data model, `db.py`) against that plan without
flagging the cost implication.

**What caught it:** the user shared the actual official capstone brief (a
PDF from the FlyRank internship program) and pointed out its explicit,
non-negotiable constraint: **$0, no credit card, ever** — Gemini Flash free
tier (or fully local Ollama) for vision, Gemini embeddings free tier (or
Ollama `all-minilm`) for embeddings.

**What changed:**
- `BRIEF.md`'s stack table and Flow A pseudocode updated: Gemini Flash
  (`google-genai`, `response_schema` JSON mode) replaces the `anthropic` SDK
  and forced tool use; Gemini embeddings (`text-embedding-004`) replace the
  unspecified "one embedding model."
- Nothing built in Steps 1–2 needed to change — `guard.py` operates on
  provider-agnostic `Candidate` objects, and the data model's `vector(N)`
  columns were already flagged as a placeholder pending the real embedding
  model's dimension, so no rework there either. The cost was caught before
  it compounded, not after.
- Added the required submission-pack files this project was missing
  (`README.md`, `LICENSE`, `capstone.yaml`, `EVIDENCE.md`, this file) — they
  should have been present from the first commit per the source brief's
  GitHub rules; added now, kept honest going forward.

**Lesson for the rest of the build:** don't assume a stack choice from an
earlier, self-authored planning doc is still ground truth — check it against
the actual source requirements when they're available, especially anywhere
cost or credentials are involved.

---

## 2026-08-03 — Step 3: Gemini structured output, first attempt failed

**Where AI helped:** wrote `vision.py` and `jobs/classify.py`, but didn't
just assume the Gemini structured-output API would work as documented from
training-data knowledge — ran a live smoke test against the real API before
building the batch job around it, since the model in use
(`gemini-3.6-flash`, resolved via the `gemini-flash-latest` alias) postdates
this assistant's January 2026 training cutoff.

**Where AI was wrong:** first attempt passed
`response_schema=VisionTagOutput` (the Pydantic class directly) per the
SDK's documented pattern. Gemini rejected it: `400 INVALID_ARGUMENT —
Unknown name "additional_properties"`. Root cause: `VisionTagOutput` sets
`extra="forbid"`, which Pydantic serializes into `additionalProperties:
false` in its JSON Schema — a field Gemini's constrained `response_schema`
subset doesn't accept, even though the SDK is supposed to convert Pydantic
models automatically.

**What changed:** switched to `response_json_schema=VisionTagOutput.model_json_schema()`
— a separate, less-constrained parameter that accepts the raw Pydantic JSON
Schema directly. Verified against both a text-only prompt and a real image
before writing it into `vision.py`.

**Also caught mid-test:** a live `503 UNAVAILABLE` from Gemini during manual
testing — not a bug, but the exact transient-failure case `jobs/classify.py`
needs to retry. Used it as a natural confirmation that treating 5xx as
retryable (not a validation failure) was the right call, rather than
inventing a hypothetical test case.

---

## 2026-08-03 — First real corpus run: three infrastructure bugs and one
design bug, all found by actually running it

**Context:** built the corpus (`corpus.py`, 48 real Unsplash photos) and
ran `jobs/classify.py` against the live Supabase project for real, instead
of stopping at "unit tests pass." That decision is what surfaced all four
of the following — none of them would have shown up otherwise.

**Where AI was wrong, #1 — DATABASE_URL didn't work as given.** The user
pasted a direct-connection string
(`db.<ref>.supabase.co:5432`); it failed DNS resolution. Root cause:
that host is IPv6-only (confirmed with `dig`), and this network has no
IPv6 route. Told the user precisely what was wrong and where to find the
alternative (Supabase's connection pooler) rather than guessing at fixes.

**Where AI was wrong, #2 — the pooler fix broke a different way.**
Switching to the pooler connection surfaced
`psycopg.errors.DuplicatePreparedStatement`. This is a known
PgBouncer-transaction-mode incompatibility with psycopg3's automatic
server-side prepared statements — not something guessed at, but recognized
from the specific error shape and fixed with `prepare_threshold=None`.

**Where AI was wrong, #3 — macOS SSL.** `urllib.request.urlopen()` failed
every HTTPS image fetch with `CERTIFICATE_VERIFY_FAILED` — the python.org
macOS build doesn't use the system CA store. Fixed with an explicit
`certifi`-backed SSL context instead of telling the user to run a
one-off terminal command.

**Where AI was wrong, #4 — a real design bug, not infrastructure.**
`gemini-flash-latest` turned out to have a 20-request/day free-tier quota,
which a 48-image batch blew through immediately. That by itself was just a
model-choice problem (fixed by switching to `gemini-3.1-flash-lite`), but
it exposed something worse: the original code treated *any* failure to get
a model response — including "we simply ran out of quota for the day" — as
`invalid_output`, and idempotency ("skip images already tagged") meant
those 29 images would never be retried again, ever, even after the quota
reset. Quota exhaustion isn't the image's fault and isn't a validation
failure; conflating the two was a real bug, not just bad luck. Fixed by
only writing `invalid_output` for an actual failed schema validation, and
leaving API-failure cases untagged (and thus eligible for the next run).
Had to manually delete 29 wrongly-invalidated rows before re-running.

**Not a bug, but worth recording:** one "gray wolf" corpus photo was
actually a coyote (bad Unsplash alt-text). The model correctly said
`unknown` at 0.95 confidence rather than guessing — the system did exactly
what it's supposed to. Fixed the corpus entry anyway, since it doubles as
eval ground truth and a wrong label there would silently understate a
future precision number.

**Result:** 48/48 images tagged, 48/48 (100%) matching the corpus's
ground-truth label, `pytest` still 24/24. None of the four fixes above
were predictable from documentation or training data — all four came from
actually executing the code against real infrastructure and reading the
actual error.

---

## 2026-08-03 — Step 4: guessed at an API field that doesn't exist

**Where AI was wrong:** first draft of `embeddings.py`'s cost tracking
assumed `embed_content`'s response would carry a `usage_metadata`-style
field the way `generate_content` does — specifically guessed at
`resp.metadata[0].billable_character_count`, invented rather than looked
up, because it looked plausible by analogy to the vision-call cost code
written moments earlier.

**What caught it:** printed the actual response object
(`resp.model_dump(exclude={'embeddings'})`) before trusting the guess,
since this SDK version and this specific model postdate this assistant's
training data. `resp.metadata` was `None` — the field doesn't exist at
all for embeddings in this SDK version.

**What changed:** switched to estimating input tokens from
`len(text) // 4`, Gemini's own documented character-to-token rule of
thumb, applied to the actual input text rather than a response field.
Cost numbers are now honestly approximate (labeled as such in
`embeddings.py`'s comment) instead of silently wrong from a field that
would have just returned `None`/0 forever.

**Also cleaned up while building this step, not a functional bug but
worth naming:** first draft of `extraction.py` imported private
underscore-prefixed constants directly from `vision.py`
(`from vision import _PRICING_PER_TOKEN_USD`) to avoid duplicating the
Gemini pricing table. That's exactly the kind of cross-module reach the
underscore convention exists to flag. Moved the table into `config.py` as
a properly public, shared constant instead of leaving the private import
in place because it "worked."

---

## 2026-08-03 — Step 5: a framework API break, and a misplaced file

**Where AI was wrong, #1:** wrote `api.py`'s review page using
`templates.TemplateResponse("review.html", {"request": request, ...})` —
the pattern every FastAPI/Starlette tutorial in training data uses. It
raised `TypeError: unhashable type: 'dict'` the moment it was actually
loaded in a browser. Starlette changed the calling convention at some
point after this assistant's training cutoff: `request` is now a
required positional argument (`TemplateResponse(request, "name.html",
context)`), not a key inside the context dict. Caught immediately because
this was tested in an actual browser before being called done, not just
assumed to work because the code "looked right" — the same reason Step 3
tested Gemini calls live before building the batch job around them.

**Where AI was wrong, #2:** to preview the app in a browser, needed the
harness's dev-server config (`.claude/launch.json`) in the *primary*
working directory — but that's `be-01-api`, an entirely unrelated project
of the user's, not this one. Created the file there anyway to get the
preview tool working, without stopping to flag that this meant writing
AutoTagging-specific configuration into someone else's unrelated repo.
The user caught it immediately ("the folder shouldn't be BE-01-API, that
is a different one"). Removed the file right away, left the rest of that
directory's `.claude/` contents untouched. Lesson: a tool's technical
requirement (config must live *here*) doesn't make it okay to write into
a directory that isn't the one being worked on — should have surfaced
that tradeoff before acting, not after being told.

**Result:** review page confirmed working end-to-end in a real browser
(suggest → approve, force-wolf → refused-with-no-image-to-approve), API
error handling confirmed live (404/422/400), formal eval run: top-1
precision 100% (7/7).

---

## Ongoing

Each subsequent phase gets an entry here noting anything AI got wrong or had
to be corrected on, alongside what it helped with. See
[IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) for the technical
step-by-step build record — this file is specifically about AI-assistance
honesty, not a duplicate of that log.
