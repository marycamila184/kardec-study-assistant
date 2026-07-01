import json
import re

_SYSTEM_TEMPLATE = """\
Você é um tutor socrático especializado na obra de Allan Kardec.

REGRA ABSOLUTA: responda SOMENTE com o objeto JSON abaixo — nenhum texto antes, \
nenhum texto depois, nenhuma observação, nenhum markdown. Qualquer caractere fora \
do JSON quebrará o sistema.

{{
  "contexto": "<1 a 2 frases indicando onde este item se encaixa na estrutura da \
doutrina, baseando-se apenas no trecho>",
  "conceitos_chave": [
    "<Termo exato do texto>: <definição extraída literalmente do trecho, sem paráfrase>"
  ],
  "perguntas": [
    "<pergunta aberta que leva o estudante a refletir sobre o trecho, sem revelar a resposta>"
  ]
}}

Regras estritas:
- "contexto": use SOMENTE o que está no trecho. Máximo 2 frases.
- "conceitos_chave": extraia os termos centrais com suas definições literais do texto. \
Entre 1 e 3 conceitos. Nunca invente definições. Se o trecho não definir o termo, \
não o inclua.
- "perguntas": formule entre 2 e 3 perguntas abertas que estimulem o pensamento \
crítico. Nunca responda as perguntas no próprio JSON. Nunca extrapole além do trecho.
- É proibido resumir, parafrasear ou explicar o trecho. O estudante já leu o texto. \
Seu papel é aprofundar, não substituir a leitura.
- Nunca personifique o Espiritismo como um agente que faz, valoriza ou defende algo \
(ex.: "o Espiritismo valoriza...", "o Espiritismo diz que..."). Atribua as afirmações \
à passagem, ao texto ou a Kardec (ex.: "esta passagem mostra que...", "o texto indica que...").

[TRECHO PRINCIPAL]
{main_passage}

[REFERÊNCIAS RELACIONADAS]
{related_passages}"""


def _format_related(chunks: list[dict]) -> str:
    if not chunks:
        return "(nenhuma)"
    parts = []
    for c in chunks:
        m = c["metadata"]
        parts.append(f"[{m['book']} | Item {m['item_number']}]\n\"{c['content']}\"")
    return "\n\n".join(parts)


def build_explicador_messages(
    main_text: str, related_chunks: list[dict]
) -> tuple[str, list[dict]]:
    system = _SYSTEM_TEMPLATE.format(
        main_passage=main_text,
        related_passages=_format_related(related_chunks),
    )
    messages = [{"role": "user", "content": "Analise o trecho acima de forma socrática."}]
    return system, messages


def _fix_conceitos_array(s: str) -> str:
    """Fix LLM habit of writing "term": "def" pairs inside the conceitos_chave array.

    Example of malformed input:
        "conceitos_chave": ["dever": "obrigação...", "lei": "regra..."]
    Becomes:
        "conceitos_chave": ["dever: obrigação...", "lei: regra..."]
    """
    def _replacer(m: re.Match) -> str:
        fixed = re.sub(r'"([^"]+)":\s*"([^"]+)"', r'"\1: \2"', m.group(2))
        return m.group(1) + fixed + m.group(3)

    return re.sub(
        r'("conceitos_chave"\s*:\s*\[)(.*?)(\])',
        _replacer,
        s,
        flags=re.DOTALL,
    )


def parse_explicador_json(text: str) -> tuple[str, list[str], list[str]]:
    """Returns (contexto, conceitos_chave, perguntas)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"```$", "", text.strip())
        text = text.strip()

    def _try_parse(s: str):
        data = json.loads(s)
        conceitos = data.get("conceitos_chave", [])
        # Handle case where LLM returned a list of objects instead of strings
        if conceitos and isinstance(conceitos[0], dict):
            conceitos = [f"{k}: {v}" for item in conceitos for k, v in item.items()]
        return (
            data.get("contexto", ""),
            conceitos,
            data.get("perguntas", []),
        )

    def _find_and_parse(s: str):
        try:
            return _try_parse(s)
        except (json.JSONDecodeError, AttributeError, ValueError):
            pass
        # Find outermost { } block
        start = s.find("{")
        if start != -1:
            depth, end = 0, -1
            for i, ch in enumerate(s[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end != -1:
                try:
                    return _try_parse(s[start: end + 1])
                except (json.JSONDecodeError, AttributeError, ValueError):
                    pass
        return None

    # Try with the malformed-array fix first, then raw text
    for candidate in [_fix_conceitos_array(text), text]:
        result = _find_and_parse(candidate)
        if result is not None:
            return result

    # Regex extraction fallback — never show raw JSON to the user
    contexto_m = re.search(r'"contexto"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    perguntas_m = re.findall(r'"((?:[^"\\]|\\.){30,}\?)"', text)
    contexto = contexto_m.group(1).replace('\\"', '"') if contexto_m else ""
    perguntas = [p.replace('\\"', '"') for p in perguntas_m[:3]]
    return contexto, [], perguntas
