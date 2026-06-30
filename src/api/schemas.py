from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Source(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str | None = None
    excerpt: str | None = None


class ChatRequest(BaseModel):
    question: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    not_found: bool = False
    suggested_mode: str | None = None


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
    item_number: str
    preview: str
    conexao: str | None = None


class StudySource(BaseModel):
    book: str
    chapter_title: str | None = None
    item_number: str
    excerpt: str | None = None


class StudyRequest(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    conversation_history: list[Message] = []


class StudyResponse(BaseModel):
    original_text: str
    contexto: str
    conceitos_chave: list[str]
    perguntas: list[str]
    related_items: list[RelatedItem]
    sources: list[StudySource]
    generation_failed: bool = False


class ReflectRequest(BaseModel):
    situation: str
    conversation_history: list[Message] = []


class ReflectResponse(BaseModel):
    opening: str
    doctrine_connection: str
    reflection_questions: list[str]
    complementary_items: list[RelatedItem]
    sources: list[StudySource]
    not_found: bool = False
    generation_failed: bool = False


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
