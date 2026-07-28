# The prompts

Every prompt the system sends lives here as Markdown, one file per piece, and is
loaded at runtime. Editing a file changes what the model is told — there is no
second copy in the Python, so the two cannot drift apart.

## How to edit

Change the file, restart the API. Nothing else.

Placeholders in `{braces}` are filled in by the code (`{passages}`,
`{caveat}`, …). Leave them alone unless you are also changing the caller: a
missing placeholder raises at request time, and an unknown one is ignored
silently, which is worse.

After editing, run:

```bash
uv run pytest                                        # nothing is broken
uv run python -m scripts.capture_prompt_baseline     # record the new prompt
uv run python -m scripts.compare_profiles            # see what it changed
```

The baseline exists so the next unintended change is visible as a diff. Running
the capture script is how you say "this change was on purpose".

## What belongs here, and what does not

**Here:** judgement — tone, what counts as close enough, how to explain, when to
say the works are silent.

**Not here:** anything that can be checked. This was learned the hard way on
2026-07-28, when five rules written plainly in these files were followed only
when convenient: references in prose, invented quotations, the assistant talking
about itself, internal vocabulary, and a false premise inside a question. Each
now has code behind it, and the code is what holds.

The clearest case: `citation_precision` asked the model to write full references
and measured **zero** across two A/B runs, the second with every contradicting
rule removed. It works now because the model only marks *where* the reference
goes and code writes it from metadata. If a rule here can be verified in code,
it belongs in code — a prompt rule is a request, not a guarantee.

## A rule that contradicts its neighbour gets obeyed unpredictably

The same measurement showed this. When one paragraph said "never write a
reference in the prose" and a later one asked for full references, the model
followed the first and the second did nothing at all. If a new rule carves out
an exception, say so where the original rule is, in its own words — see how
`near-miss.md` names the exception to "never end on a question".

## Examples earn their length

`chat-system.md` carries two worked examples — a normal answer and one where the
passages do not cover the question. They were measured on 2026-07-28: with them,
the prompt is 18% SHORTER than the version without them (1289 tokens against
1563), because an example replaces several paragraphs of description, and the
answers got shorter and better delimited too.

That is the same lesson as the rest of this file from the other direction. A rule
in prose is a request; an example is a demonstration, and this model follows what
it is shown far more reliably than what it is told.

## The files

| File | What it is |
|---|---|
| `chat-system.md` | The `/chat` system prompt. Holds the `{placeholders}` the others fill, and carries the marker contract, the voice rules and two worked examples inline |
| `chat-seguir.md` | The `[SEGUIR]` follow-up contract, and when to leave it empty. A SLOT rather than inline prose because `scripts/compare_generators.py` swaps this constant to A/B follow-up variants — inline it and that harness silently stops testing anything |
| `chat-caveat.md` | The medical/mediumship caveat, added when `crisis.py` asks for it |
| `chat-sensitive.md` | Gentler handling on the `abalo` tier — never lowered by anything |
| `study-system.md` | The `/study` (Explicador) system prompt, JSON output |
| `study-rules.md` | The rules shared by the study output formats |
| `study-item-marker.md` | The `[item N]` contract for chapter commentary |

`crisis.py` is deliberately not here. That text is fixed, is decided in code
before any model call, and is read by someone in crisis — it is not a prompt and
must never become editable as one.
