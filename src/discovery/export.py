"""A Page vira o JSON que a rota Astro das trilhas lê.

Escrito em vez do HTML que render.py produzia até a Fase 2. A divisão de
trabalho é a que já existia, agora explícita: **o Python resolve identidade de
passagem** — `passage_text`, com a regra do "só resolve se houver exatamente
um", e o rejunte de subchunks pelas costuras que o próprio split registrou —
e **o Astro só formata**. As duas regras foram pagas com bugs e estão
testadas; reimplementá-las em JavaScript seria duplicar lógica carregada.

Nenhum modelo escreve aqui, pelo mesmo motivo de antes: uma página gerada é
texto que vive anos FORA de todas as guardas de request-time deste projeto.
"""

from dataclasses import asdict

from src.discovery.content import Page


def trilha_content(page: Page) -> dict:
    """As chaves são contrato com frontend/src/pages/trilhas/[slug].astro.

    `title` é o <h1> e `meta_title` é o <title>: para uma trilha eles diferem
    (o segundo leva o nome do site), e colapsar os dois numa chave só obrigaria
    a rota a montar a string — prosa nova num arquivo que não pode ter.
    """
    return {
        "id": page.slug,
        "title": page.heading,
        "meta_title": page.title,
        "meta_description": page.meta_description,
        "intro": page.intro,
        "passages": [asdict(p) for p in page.passages],
    }
