import argparse
import json
import os

from openai import OpenAI

from src.core.config import settings
from src.rag.chapter_summary_prompt import (
    build_chapter_summary_messages,
    clean_chapter_summary,
)

EVANGELHO_JSON_PATH = "data/json_files/evangelho.json"
SUMMARIES_PATH = "data/chapter_summaries/evangelho.json"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _client


def group_chapters(chunks: list[dict]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for c in chunks:
        grouped.setdefault(c["chapter_title"], []).append(c["content"])
    return {title: " ".join(parts) for title, parts in grouped.items()}


def _summarize(chapter_title: str, chapter_text: str) -> str:
    system, messages = build_chapter_summary_messages(chapter_title, chapter_text)
    response = _get_client().chat.completions.create(
        model=settings.chat_model,
        max_tokens=256,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return clean_chapter_summary(response.choices[0].message.content)


def generate_summaries(
    chunks: list[dict], existing: dict[str, str], force: bool = False
) -> dict[str, str]:
    grouped = group_chapters(chunks)
    result: dict[str, str] = {}
    for title, text in grouped.items():
        if not force and title in existing:
            result[title] = existing[title]
        else:
            result[title] = _summarize(title, text)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    with open(EVANGELHO_JSON_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    existing: dict[str, str] = {}
    if os.path.exists(SUMMARIES_PATH):
        with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    result = generate_summaries(chunks, existing, force=args.force)

    os.makedirs(os.path.dirname(SUMMARIES_PATH), exist_ok=True)
    with open(SUMMARIES_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(result)} chapter summaries to {SUMMARIES_PATH}")


if __name__ == "__main__":
    main()
