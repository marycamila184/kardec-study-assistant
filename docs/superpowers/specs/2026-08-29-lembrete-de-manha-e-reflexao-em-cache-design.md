# One reminder a day, in the morning, opening a reflection already written

**Date:** 2026-08-29
**Status:** approved, pending implementation

Refines [2026-08-27-lembrete-push-design](2026-08-27-lembrete-push-design.md),
which is merged but not yet provisioned — no Firestore, no VAPID keys, no
scheduler exist in the project yet. Nothing here has to be undone first.

## What this is

Five changes that are one story. The reminder was built to serve any hour in
any timezone; the product it actually serves is **one notification a day, in
the morning, for readers in Brazil**. Narrowing to that removes both defects
the previous spec had to accept, makes the notification carry something worth
reading, and makes the passage it opens appear instantly.

## 1. Hourly, not every fifteen minutes

The 15-minute cadence existed for one reason: 16 of the world's timezones are
offset by a broken quarter of an hour, and an hourly job would inspect their
local clocks only ever at `:30` or `:45`. Someone in Kathmandu who chose 08:00
would **never** be served — not late, never.

Measured: **every Brazilian timezone is a whole hour** (UTC−2, −3, −4, −5), and
so is every Portuguese-speaking country — Portugal +1, Azores 0, Angola +1,
Mozambique +2, Cape Verde −1, Guinea-Bissau 0, East Timor +9. The broken-offset
zones contain no Lusophone country.

So: the scheduler runs **hourly**, `push_window_minutes` becomes **60**, and
the hour picker offers **whole hours only**.

Setting the window equal to the cadence is what keeps this safe. With hourly
runs and a 15-minute window, a reader in a broken-offset zone would silently
never be served — the failure this project refuses. With a 60-minute window,
every device is served exactly once a day whatever its offset; only punctuality
varies.

| | Before | After |
|---|---|---|
| Punctuality in Brazil | up to ~14 min late | **exact, to the minute** |
| Job executions per day | 96 | **24** |
| DST fall-back double-fire | accepted, documented | **gone** for Brazil (no DST since 2019) |
| Broken-offset zones | ≤14 min late | ≤59 min late, still never silent |

**This retires two accepted defects.** The previous spec documented both — the
~14-minute lateness and the once-a-year duplicate — as costs refused because
fixing them needed a sixth field on the record. Neither needed a sixth field.
They needed a narrower product.

**The picker changes because it was promising what it could not keep.** It
accepts 08:07 today and delivers 08:15 without saying so. Whole hours stop the
promise from outrunning the delivery — the same rule that keeps the toggle off
an iPhone that cannot use it.

## 2. The notification carries the day's theme

Today it reads *"É a hora do seu estudo. Que tal começar pelo trecho de hoje?"*
— a prod. It should carry something a reader gets value from on the lock
screen, without opening anything:

```
Dialogando com a Doutrina
Reflexão de hoje — BEM-AVENTURADOS OS QUE TÊM PURO O CORAÇÃO
```

The body is the **chapter title** of the day's passage. Three candidates were
weighed against the real data:

| Candidate | Size | Verdict |
|---|---|---|
| The passage text | 517 chars | **No.** Truncating it reproduces daily the error [2026-08-05](2026-08-05-curadoria-trecho-e-trilhas-design.md) fixed: 23 passages cut before their ending, which in the Evangelho is usually the merciful part |
| The chapter summary | ~700 chars | No. Too long, summarises the chapter rather than the passage, and every one opens with the same formula ("Este capítulo trata de…"), which wears out by the third day |
| **The chapter title** | ~41 chars | **Yes.** A complete unit that cannot be cut wrongly, and Kardec's own words rather than a summary of them |

**The title is not case-transformed.** The corpus stores these in capitals and
the app already displays them that way. Lowercasing would need an exception
list for `DEUS`, `JESUS`, `CRISTO`; getting that wrong once, in an app about
this doctrine, costs more than the capitals do.

**The payload is encrypted end to end**, so the push service — Google, Apple —
sees ciphertext, not which chapter a reader was sent. Worth stating because
this project would not otherwise put the reading in a third party's hands.

The job computes the passage with `get_daily_passage()`, which is deterministic
and calls no model. It uses the **server's** date, in UTC; for a morning
reminder in Brazil (08:00 local = 11:00 UTC) the dates agree. They would only
diverge for a reminder late at night, which this product does not offer.

## 3. The day's first explanation is cached

Measured, not assumed: the daily passage's explanation is requested as

```js
streamStudy(source.book, source.item_number, source.chapter, source.part, …)
```

— **no profile, no history**. The response is determined entirely by the
passage, so it is the same for every reader that day. Today that means one LLM
call per reader per day to produce identical text.

Cached, it becomes one call a day, and three things improve:

1. **Cost.** N calls become one.
2. **Nobody waits.** The explanation streams in over seconds today. From cache
   it is simply there — and streaming's whole purpose, shortening a perceived
   wait, is moot when there is no wait.
3. **It becomes one shared thing.** Two readers get subtly different
   explanations today and nobody can inspect either. Cached, there is exactly
   one artefact a day: reviewable, correctable, and the same reflection for
   everyone — which for a "reflexão do dia" is a feature.

### Where it lives, and what keys it

A Firestore document per day, in a collection separate from the push
subscriptions and joined to nothing — the same rule that governs that store
governs this one. It is a **second** collection, not a field added to the
first.

**Keyed by the passage's identity, not by the date.** `(book, chapter,
item_number, part)` plus the date. Keying on the date alone would serve stale
prose after an edit to `data/markdown_files/trecho_diario.md`, and that file is
hand-curated precisely because its contents get corrected.

### Never cache a failure

If `find_unsupported_quotes` withholds the answer, or generation fails, nothing
is written. A cached failure is served to every reader all day — the difference
between saving a call and publishing a defect.

### Why this does not violate the model-prose rule

`CLAUDE.md` forbids generated pages carrying model output, because *"a
generated page is model prose living for years outside every guard this project
built"*. That objection does not reach here, and the distinction is the whole
argument:

- There, prose was produced by a **different path with no guards at all**.
- Here it is produced by the **same `/study` pipeline**, with `max_distance`
  and `find_unsupported_quotes` running exactly as they do now — once instead
  of N times — and it lives for a day, not for years.

One honest cost: an explanation that is poor but passes the guards now reaches
every reader that day rather than one. The compensating gain is that it becomes
a single, inspectable artefact instead of N invisible ones. That trade is
accepted deliberately, and named here so it is not discovered later.

Only the **first** message is cached. Everything the reader asks afterwards is
theirs and is unchanged.

### The cache is warmed before the notification goes out, not after

A lazy cache — filled by whoever opens first — defeats itself here, and
precisely because the reminder works. At 08:00 the notification reaches
everyone at once, everyone opens within seconds, everyone finds the cache
empty, and everyone triggers the generation together. One call a day becomes
dozens inside one minute, and each of those readers waits for the stream that
the cache existed to remove.

So the order inside the Job is part of the design, not an implementation
detail. Each hourly run:

1. **ensures the day's explanation exists** — one cheap Firestore read when it
   already does, one generation when it does not;
2. **then** sends the notifications due that hour.

The work is already in the right place: the Job computes `get_daily_passage()`
anyway, to build the notification body. The first run of the day pays the
generation; every later run reads. Nobody opens onto a cold cache, whatever
hour they chose — this is not a property of 08:00, it holds for every hour.

**A failed warm-up must not hold back the notification.** If generation fails —
the model is down, or `find_unsupported_quotes` withholds — the notification is
sent regardless. It carries the chapter title and is worth having on its own,
and whoever opens it falls through to today's normal path, with the stream.
A cache miss is a slower reader; a suppressed notification is a reader who
never knew.

**Both paths write the same store.** Until push is provisioned the Job does
nothing at all — `main()` returns early without VAPID keys — so the cache is
filled lazily, by the first reader to open the passage. That is the correct
behaviour for a project where the reminder is off: the caching benefit does not
depend on push existing, only its warming does.

## What does not change

The five-field subscription record and its rule against joining. The privacy
copy — this stores no more about anyone. The crisis floor. The iOS install
path. `/study` for every other caller.

## Testing

| What | How |
|---|---|
| Hourly cadence serves whole hours exactly | `is_due` tests with the window at 60 and Brazilian offsets |
| A broken-offset zone is late but never skipped | a test at UTC+5:45, asserting it fires within the hour |
| The picker offers only whole hours | assertion on the rendered options |
| The notification carries the chapter title | test on the payload the sender builds |
| A failure is never cached | test that a withheld answer leaves the store empty |
| A corpus edit invalidates the cache | test that a different passage identity misses |
| The cached answer equals the live one | one comparison test, so the cache cannot silently drift from the pipeline |
| The warm-up runs before the sending | test on the Job's ordering, since the reverse order is silently wrong rather than broken |
| A failed warm-up still sends | test that a generation error leaves the notifications going out |

## Prerequisites

Unchanged from the previous spec and still not done: Firestore, VAPID keys, the
Job, the Scheduler, the IAM bindings. Verified 2026-08-29 — the Firestore API
is not even enabled on the project yet.
