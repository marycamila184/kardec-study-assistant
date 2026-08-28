# The study reminder, by Web Push

**Date:** 2026-08-27
**Status:** approved, pending implementation

## What this reverses, and what it does not

[2026-08-05-desligar-lembrete-design](2026-08-05-desligar-lembrete-design.md)
switched the reminder off and said what bringing it back would cost. Two costs,
and only one of them has moved.

The first was iPhone reach, gated on a measurement: "depends on how much of the
audience is on iPhone — measurable in Vercel Analytics, not guessable." **That
measurement is still not available.** Web Analytics is not enabled on the Vercel
project — the API returns 404 — even though `@vercel/analytics` is a dependency.
The gate was not passed. It was overtaken: the author decided to build push
regardless, so the number no longer decides *whether*, only how much effort the
iOS install path deserves. Section "The iPhone" below makes that path
unconditional, which is what the missing number would otherwise have sized.

The second cost was storage, and it has not moved at all — it has been accepted.
A push subscription is a durable per-device identifier held server-side. This
backend has never held one: it does not generate a `session_id`, does not derive
one from IP or cookie, and treats the absence of the `X-Session-Id` header as
the refusal. **Push is the first datastore in this project's history.** Not the
first database of a system that had others — the first. Today there is no
Postgres, no Firestore, no Redis; the rate limiter lives in process memory and
the turn log is a line on stdout.

That is the real weight of this spec, and the reason the rules in "What is
stored" are written as rules rather than as implementation notes.

## What is stored

One record per device:

```
{ endpoint, keys, hour, timezone, last_seen }
```

No name, no e-mail, no IP, no user-agent, no identifier the project generated.

`last_seen` is a date, and it exists only to make the third deletion rule below
possible — an expiry with nothing recording activity would never fire. It is
written when the subscription is created and refreshed when the reader opens the
app from a reminder: the service worker's `notificationclick` handler posts the
endpoint back, and the store stamps the date. **Nothing else about that visit is
recorded** — not what was read, not for how long, not from where. A date is the
smallest thing that can distinguish a device still in use from one that is not,
and storing less would mean keeping records forever.

Deleted in three circumstances:

1. the reader turns the reminder off;
2. the push service answers **410 Gone** — the device is gone, and the record is
   removed on the spot rather than retried;
3. **90 days** pass without anyone opening the app from a reminder — measured
   by `last_seen` above, swept by the same Cloud Run Job that sends.

The third one exists because the first two are not enough on their own. Someone
who simply stops using the app never presses a button, and without expiry their
device would stay registered indefinitely, along with the hour it used to study.
Deletion should not require the reader to ask.

### The rule that keeps this from spreading

**The subscription is never joined to anything.** Not to `session_id`, not to
the turn log, not to `POST /feedback`, not to a conversation. It lives in its
own store, which nothing else reads and which reads nothing else. The turn log
gains no field from this work — not one.

Without that written down, this project would acquire through the back door
precisely the linkability that
[2026-07-27](2026-07-27-log-de-conversas-design.md) and
[2026-07-28](2026-07-28-log-de-sessao-e-feedback-design.md) spent two specs
avoiding: an identifier that persists across sessions, attached to a device,
correlatable with everything that device wrote. The store being separate is not
an implementation detail. It is the entire safeguard.

## The pieces

| Piece | Choice | Why |
|---|---|---|
| Store | **Firestore, native mode** | Scales to zero, generous free tier, same GCP project as Cloud Run, no server and no connection pool to run. Cloud SQL bills while idle and is a cannon for a key-value list |
| Trigger | **Cloud Run Job** + Cloud Scheduler, every 15 minutes | The Job runs the *same image* with a different command (`python -m src.push.dispatch`). **No new public surface**: an endpoint on the API would mean validating OIDC on a service deployed `--allow-unauthenticated`. 15 minutes covers the half-hour and quarter-hour timezones |
| Sending | `pywebpush`, VAPID keys in Secret Manager | The same path the LLM keys already take |

Dependency cost, checked rather than assumed: 14 packages, dominated by
`cryptography`; `grpcio` already arrives with chromadb. Tens of megabytes
against the 4.7 GB the `ingest` group exists to keep out of the image. It goes
in the runtime dependencies.

**Explicitly rejected: FCM and OneSignal.** Both move the identifier to a third
party. That is worse privacy, not better, and it contradicts the only reason
this spec has rules in it.

### One duplicate a year, on purpose

On daylight-saving fall-back dates, the hour 01:00–01:59 occurs twice in local
time, and a device set to that hour fires twice. Fixing this would require
storing `last_sent` per record — a sixth field to track when the notification
was last delivered — but the spec deliberately holds to five fields to minimize
what is kept. One duplicate notification per year is an acceptable cost against
storing more durable state about a person. Spring-forward is unaffected: devices
set to a non-existent hour are simply skipped that day.

## The service worker, and why it does not undo yesterday's decision

Push requires a service worker.
[2026-08-27-pwa-instalavel-design](2026-08-27-pwa-instalavel-design.md), written
hours earlier, decided against having one. These reconcile, and not by luck.

That decision was against something specific: a worker that caches, and can
therefore **pin a stale shell onto a reader's device silently**. The measurement
behind it — `_astro` bundles already `immutable` for a year — said a caching
worker had nothing to accelerate and one thing to break.

This worker registers **`push` and `notificationclick`, and nothing else**. No
`fetch` handler, no cache, no request interception. A service worker without a
`fetch` handler cannot serve a stale anything; the failure mode that decision
was protecting against is structurally absent, not merely avoided by care.

`scripts/check_push_service_worker.mjs` enforces it: a `fetch` listener
appearing in that file fails CI. The reconciliation only holds while the worker
stays this small, so a guard holds it there.

## The iPhone

On iOS, Web Push exists **only for a web app already added to the Home Screen**.
No amount of backend work removes that.

So on iOS, when the app is not installed, the Settings panel does not show the
toggle. In its place it shows the short "Share → Add to Home Screen"
instructions. Once installed, the toggle appears.

This is the direct lesson of the 2026-08-05 failure, which was not that the
button did not work but how it failed: `requestNotif` opened with
`if (typeof Notification === 'undefined') return;`, so on an iPhone the button
did nothing, reported nothing, and went on offering to do the thing it had just
declined — for as long as the reader kept pressing. **A control is shown only
where it can work.** Where it cannot, the obstacle is turned into the path.

## Copy that moves first

`PRIVACY_NOTICE` in `frontend/src/constants/contact.js` and the `/sobre/` page
are edited **before** any subscription is ever stored, not after.

The standing rule is that the privacy copy may promise less than the code does,
never more. Today it describes a system that stores nothing of the kind. Storing
first and editing later is the one way to actually break that rule, and the
ordering is therefore part of the design rather than a courtesy.

## Consent

The toggle is the consent, and it is its own — unrelated to `X-Session-Id`,
which stays exactly as it is. Turning the reminder on is an explicit, deliberate
act that names what it does; the browser then asks for notification permission
on top of it. Nothing here is opt-out, and nothing is bundled into another
question.

## Testing

| What | How |
|---|---|
| Who is due in a given window | Python tests over `dispatch`, with timezones fixed |
| 410 deletes the record | Python test with a faked push service |
| The 90-day expiry removes and does not remove | Python tests either side of the boundary |
| The worker never gains a `fetch` handler | `scripts/check_push_service_worker.mjs`, in CI |
| The privacy copy moved | Same guard: refuse to build if the store exists in code and the copy has not been updated |
| Nothing joins subscription to turn log | Test asserting the log object has no new field, plus review |
| A notification really arrives | Manual, once, on a real Android and a real installed iPhone, app closed. No automation replaces this |

## Out of scope

Any notification that is not the daily study reminder. No "someone replied", no
news, no re-engagement, no streaks. The store exists for one message a day at an
hour the reader chose, and its justification does not extend past that.

## Prerequisites the author must do

Enabling Firestore and generating the VAPID key pair happen in the author's GCP
project; the commands are written down in `docs/deploy.md`, which gains a
section. Enabling Vercel Web Analytics is worth doing at the same time — not
because this spec waits on it, but because the next decision like this one
should not have to be made blind again.

**Noted in passing, not fixed here:** `docs/deploy.md` still instructs setting
`VITE_API_URL`. That has been wrong since the Astro migration, which exposes
`PUBLIC_`-prefixed variables — the same mismatch that put `localhost:8000` into
a production bundle on 2026-08-09.
