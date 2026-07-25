from openai import BadRequestError, OpenAI

from src.core.config import settings

_clients: dict[str, OpenAI] = {}


def get_client(role: str = "json") -> OpenAI:
    """Returns the OpenAI-compatible client for a lane.

    "json"  — structured-output agents (Curador, orchestrator, condenser,
              sensitivity). Always the LLM_PROVIDER provider.
    "prose" — /chat generation and Explicador. PROSE_PROVIDER when set, otherwise
              identical to the json lane.

    Clients are cached per provider name, so both lanes share one client while
    the prose lane is off.
    """
    name = settings.prose_provider_name if role == "prose" else settings.llm_provider
    if name not in _clients:
        _clients[name] = OpenAI(
            api_key=settings.api_key_for(name),
            base_url=settings.provider(name).base_url,
        )
    return _clients[name]


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
