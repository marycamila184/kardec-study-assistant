from openai import BadRequestError, OpenAI

from src.core.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        provider = settings.active_provider
        _client = OpenAI(
            api_key=settings.active_api_key,
            base_url=provider.base_url,
        )
    return _client


def create_json_completion(client, model, messages, max_tokens, structured=None):
    """Chat completion whose output is expected to be JSON. Adds
    response_format=json_object when structured output is enabled, and retries
    once WITHOUT it if the provider/model rejects the parameter. Callers still
    parse the returned content themselves (their existing regex extraction)."""
    if structured is None:
        structured = settings.structured_output
    if structured:
        try:
            return client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                response_format={"type": "json_object"},
            )
        except BadRequestError:
            pass
    return client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
