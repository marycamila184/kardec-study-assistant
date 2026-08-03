from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Source(BaseModel):
    book: str
    chapter: str | None = None
    chapter_ref: str | None = None
    item_number: str | None = None
    excerpt: str | None = None


class ProfileState(BaseModel):
    """The shape the answer took, carried by the client between turns.

    Stateless by design, exactly like the conversation history: nothing is
    stored server-side. `pinned` lists the dimensions the reader asked for
    explicitly — they stop following anything the system infers later.

    Only the dimensions that currently do something are exposed. A field the
    prompt does not read yet would be a setting that silently fails.
    """

    citation_style: str = "chips"  # none | chips | inline
    citation_precision: str = "short"  # short | full
    depth: str = "normal"  # breve | normal | aprofundado
    vocabulary: str = "corrente"  # iniciante | corrente | tecnico
    pinned: list[str] = []


class ChatRequest(BaseModel):
    question: str
    history: list[Message] = []
    book_filter: str | None = None
    # The machine chapter id ("CAPÍTULO VII"). Set by callers that already know
    # the chapter — Explorar's Evangelho topics name one in the chip.
    chapter_filter: str | None = None
    current_mode: str | None = None
    anchor_text: str | None = None
    profile: ProfileState | None = None


class InlineRef(BaseModel):
    """Where in the prose a claim rests on a retrieved passage. `position` is an
    index into the clean text, so a client that ignores this field displays
    exactly what it displayed before inline markers existed."""

    position: int
    book: str
    chapter_title: str | None = None
    chapter_ref: str | None = None
    item_number: str | None = None
    excerpt: str | None = None


class StudiedItem(BaseModel):
    """The passage a question named, when it named one. Rendered as the "Da
    Obra" block — the source text visibly apart from the explanation, which is
    the rule the study modes exist to make structural."""

    book: str
    chapter_title: str | None = None
    chapter_ref: str | None = None
    item_number: str | None = None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    # The id of the logged turn, so the client can attach a vote to it. Not an
    # identifier of a person: it names one line, never repeats, and links
    # nothing to anything. None when the turn was not logged.
    turn_id: str | None = None
    studied_item: StudiedItem | None = None
    # The profile this answer was written with, for the client to carry into the
    # next turn. Echoed rather than assumed: a request that changed the shape
    # must be able to tell the client what it changed to.
    profile: ProfileState | None = None
    inline_refs: list[InlineRef] = []
    sources: list[Source]
    suggested_questions: list[str] = []
    not_found: bool = False
    suggested_mode: str | None = None
    suggested_item_number: str | None = None
    suggested_book: str | None = None
    generation_failed: bool = False
    safety_level: str | None = None


class FeedbackRequest(BaseModel):
    turn_id: str
    vote: Literal["up", "down"]
    # No comment field, deliberately: free text here would reopen the whole
    # sensitive-data question the 2026-07-28 spec settled. An extra field sent
    # by a client is ignored by pydantic and never reaches the log.


class PathStep(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    label: str


class PathSummary(BaseModel):
    id: str
    title: str
    description: str
    level: str
    step_count: int


class PathDetail(BaseModel):
    id: str
    title: str
    description: str
    level: str
    steps: list[PathStep]


class RelatedItem(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str | None = None
    preview: str
    conexao: str | None = None


class StudySource(BaseModel):
    book: str
    chapter_title: str | None = None
    chapter_ref: str | None = None
    item_number: str | None = None
    excerpt: str | None = None


class StudyRequest(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    conversation_history: list[Message] = []


class StudyResponse(BaseModel):
    original_text: str
    # Same meaning as on ChatResponse: names one logged line, so a vote can be
    # attached to it. Never repeats, links nothing to anyone.
    turn_id: str | None = None
    contexto: str
    inline_refs: list[InlineRef] = []
    conceitos_chave: list[str]
    perguntas: list[str]
    related_items: list[RelatedItem]
    sources: list[StudySource]
    # The chapter's other items, when they were used as grounding. Evangelho
    # only — see chapter_commentary() in retriever.py. Exposed because the
    # explanation draws on them and says so ("o comentário doutrinário de
    # Kardec sobre este capítulo…"); a reader who cannot open what was cited
    # is being asked to take the attribution on trust.
    chapter_context: list[StudySource] = []
    generation_failed: bool = False


# ReflectRequest and ReflectResponse are without a route while Refletir is
# switched off; see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
class ReflectRequest(BaseModel):
    situation: str
    conversation_history: list[Message] = []
    current_mode: str | None = None
    anchor_text: str | None = None


class ReflectResponse(BaseModel):
    opening: str
    doctrine_connection: str
    reflection_questions: list[str]
    is_closing: bool = False
    complementary_items: list[RelatedItem]
    sources: list[StudySource]
    not_found: bool = False
    generation_failed: bool = False
    suggested_mode: str | None = None
    suggested_item_number: str | None = None
    suggested_book: str | None = None
    safety_level: str | None = None


class EvangelhoSource(BaseModel):
    book: str
    chapter: str | None = None
    chapter_title: str | None = None
    item_number: str | None = None
    subchunk_index: int | None = None
    total_subchunks: int | None = None


class EvangelhoResponse(BaseModel):
    date: str
    content: str
    source: EvangelhoSource
    chapter_summary: str | None = None
