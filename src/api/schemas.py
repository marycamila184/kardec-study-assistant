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


class ChatRequest(BaseModel):
    question: str
    history: list[Message] = []
    book_filter: str | None = None
    current_mode: str | None = None
    anchor_text: str | None = None


class InlineRef(BaseModel):
    """Where in the prose a claim rests on a retrieved passage. `position` is an
    index into the clean text, so a client that ignores this field displays
    exactly what it displayed before inline markers existed."""

    position: int
    book: str
    chapter_title: str | None = None
    item_number: str | None = None
    excerpt: str | None = None


class ChatResponse(BaseModel):
    answer: str
    inline_refs: list[InlineRef] = []
    sources: list[Source]
    suggested_questions: list[str] = []
    not_found: bool = False
    suggested_mode: str | None = None
    suggested_item_number: str | None = None
    suggested_book: str | None = None
    generation_failed: bool = False
    safety_level: str | None = None


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
    item_number: str | None = None
    excerpt: str | None = None


class StudyRequest(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    conversation_history: list[Message] = []


class StudyResponse(BaseModel):
    original_text: str
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
