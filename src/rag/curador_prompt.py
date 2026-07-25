import json

from src.rag.json_extract import extract_outermost, strip_code_fence
from src.rag.retriever import has_real_item_number

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
- O TRECHO PRINCIPAL pode estar truncado. Julgue pelo que está visível e não \
suponha que o trecho termina onde o texto acaba.
- Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que..."). Atribua as afirmações \
à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", "o texto \
indica que...").

[TRECHO PRINCIPAL]
{main_passage}

[CANDIDATOS]
{candidates}"""


def _format_candidates(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        m = c["metadata"]
        header = f"[{i}] {m['book']}"
        if has_real_item_number(m.get("item_number")):
            header += f" — Item {m['item_number']}"
        # 800 = the chunker's ceiling, so a candidate is never actually cut.
        # At 300 the model judged a doctrinal connection from a third of the
        # passage and was not told it was truncated — a plausible cause of
        # over-conservative selection.
        parts.append(f"{header}\n\"{c['content'][:800]}\"")
    return "\n\n".join(parts)


def build_curador_messages(
    main_text: str, candidates: list[dict]
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        main_passage=main_text[:1200],
        candidates=_format_candidates(candidates),
    )
    messages = [{"role": "user", "content": "Selecione os candidatos mais relevantes."}]
    return system, messages


def parse_curador_json(text: str) -> list[dict]:
    """Returns list of {"index": int, "conexao": str}."""
    text = strip_code_fence(text)

    def _try_parse(s: str) -> list[dict]:
        data = json.loads(s)
        if isinstance(data, list):
            seen_indices: set[int] = set()
            result = []
            for item in data:
                if "index" not in item:
                    continue
                idx = int(item["index"])
                if idx in seen_indices:
                    continue
                seen_indices.add(idx)
                result.append({"index": idx, "conexao": str(item.get("conexao", ""))})
            return result
        return []

    try:
        return _try_parse(text)
    except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
        pass

    block = extract_outermost(text, "[", "]")
    if block is not None:
        try:
            return _try_parse(block)
        except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
            pass

    return []
