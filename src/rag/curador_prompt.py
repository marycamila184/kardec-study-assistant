import json
import re

_SYSTEM_TEMPLATE = """\
Você é um curador especializado nas obras de Allan Kardec.

REGRA ABSOLUTA: responda SOMENTE com o array JSON abaixo — nenhum texto antes, \
nenhum texto depois, nenhum markdown. Qualquer caractere fora do JSON quebrará o sistema.

[
  {{"index": <número inteiro do candidato escolhido>, "conexao": "<1 frase em português \
explicando por que este trecho complementa doutrinariamente o trecho principal>"}}
]

Tarefas:
1. Leia o TRECHO PRINCIPAL.
2. Avalie cada CANDIDATO numerado.
3. Selecione entre 1 e 3 candidatos que complementam doutrinariamente o trecho principal.
4. Para cada selecionado, escreva uma frase curta (máximo 20 palavras) explicando a conexão.
5. Descarte candidatos que repetem o mesmo ponto ou não acrescentam nada novo.

Regras estritas:
- "index" deve ser o número inteiro exato do candidato (0, 1, 2…).
- "conexao" deve ser em português, baseada SOMENTE no conteúdo dos trechos — nunca invente.
- Nunca inclua o candidato no array se ele não conectar claramente ao trecho principal.
- Se nenhum candidato for relevante, retorne um array vazio: []

[TRECHO PRINCIPAL]
{main_passage}

[CANDIDATOS]
{candidates}"""


def _format_candidates(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        m = c["metadata"]
        parts.append(f"[{i}] {m['book']} — Item {m['item_number']}\n\"{c['content'][:300]}\"")
    return "\n\n".join(parts)


def build_curador_messages(
    main_text: str, candidates: list[dict]
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        main_passage=main_text[:600],
        candidates=_format_candidates(candidates),
    )
    messages = [{"role": "user", "content": "Selecione os candidatos mais relevantes."}]
    return system, messages


def parse_curador_json(text: str) -> list[dict]:
    """Returns list of {"index": int, "conexao": str}."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip()).strip()

    def _try_parse(s: str) -> list[dict]:
        data = json.loads(s)
        if isinstance(data, list):
            return [
                {"index": int(item["index"]), "conexao": str(item.get("conexao", ""))}
                for item in data
                if "index" in item
            ]
        return []

    try:
        return _try_parse(text)
    except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
        pass

    start = text.find("[")
    if start != -1:
        depth, end = 0, -1
        for i, ch in enumerate(text[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            try:
                return _try_parse(text[start: end + 1])
            except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
                pass

    return []
