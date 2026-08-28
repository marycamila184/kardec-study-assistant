"""O primeiro armazenamento da história deste projeto.

Cinco campos, num store que não cruza com nada: nunca com `session_id`, nunca
com o log de turnos, nunca com o feedback. Essa separação não é detalhe de
implementação — é a salvaguarda inteira. Ver
docs/superpowers/specs/2026-08-27-lembrete-push-design.md

`_client()` é a costura: os testes trocam ele, e nada aqui fala com o
Firestore fora desta função.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

from src.core.config import settings


@dataclass(frozen=True)
class Subscription:
    endpoint: str
    keys: dict[str, str]
    hour: str
    timezone: str
    last_seen: date

    # Sem __eq__ próprio: o do dataclass compara campo a campo e `keys` é um
    # dict, que compara por valor. Escrever um à mão aqui seria pior do que
    # inútil — com eq=True (o padrão) o dataclass instala o dele DEPOIS do
    # corpo da classe, e o escrito à mão sumiria sem aviso.
    #
    # Cuidado: `frozen=True` gera um __hash__, mas ele levanta TypeError
    # porque `keys` é um dict. Ninguém põe uma Subscription num set hoje;
    # quem for o primeiro descobre aqui em vez de em produção.


def to_document(sub: Subscription) -> dict:
    """O registro como vai para o Firestore — e só ele.

    Escrito à mão em vez de `asdict()` de propósito: um campo novo no
    dataclass não vaza para o store sem alguém passar por aqui e reler a
    regra acima.
    """
    return {
        "endpoint": sub.endpoint,
        "keys": sub.keys,
        "hour": sub.hour,
        "timezone": sub.timezone,
        "last_seen": sub.last_seen.isoformat(),
    }


def from_document(doc: dict) -> Subscription:
    return Subscription(
        endpoint=doc["endpoint"],
        keys=doc["keys"],
        hour=doc["hour"],
        timezone=doc["timezone"],
        last_seen=date.fromisoformat(doc["last_seen"]),
    )


@lru_cache(maxsize=1)
def _client():
    from google.cloud import firestore

    return firestore.Client()


def _doc_id(endpoint: str) -> str:
    """O id do documento é o hash do endpoint, não o endpoint.

    Endpoint tem barra e é longo demais para id de documento; o hash é
    estável e serve de chave sem precisar de índice.
    """
    from hashlib import sha256

    return sha256(endpoint.encode()).hexdigest()


def _colecao():
    return _client().collection(settings.push_collection)


def save(sub: Subscription) -> None:
    _colecao().document(_doc_id(sub.endpoint)).set(to_document(sub))


def delete(endpoint: str) -> None:
    _colecao().document(_doc_id(endpoint)).delete()


def touch(endpoint: str, today: date) -> None:
    """Carimba last_seen. Só a data — nada sobre a visita.

    Silencioso quando o documento não existe: o service worker avisa que
    alguém abriu o app por um lembrete, e nesse meio-tempo a inscrição pode
    já ter sido desligada ou varrida pelos 90 dias. Isso é uma corrida
    normal, não um erro — `update()` levantaria NotFound e a rota devolveria
    500 para um clique que não tem nada de errado.
    """
    from google.api_core.exceptions import NotFound

    try:
        _colecao().document(_doc_id(endpoint)).update({"last_seen": today.isoformat()})
    except NotFound:
        pass


def all_subscriptions() -> list[Subscription]:
    return [from_document(d.to_dict()) for d in _colecao().stream()]


def delete_stale(today: date, max_age_days: int) -> int:
    """Apaga quem não aparece há mais de `max_age_days`. Devolve quantos.

    Existe porque desligar e o 410 não bastam: quem simplesmente parou de usar
    nunca aperta botão nenhum, e sem isto ficaria registrado para sempre. O
    apagamento não pode depender de a pessoa pedir.

    Lê a coleção inteira e filtra aqui em vez de perguntar ao Firestore com
    um `where`. Na escala deste projeto isso é irrelevante e evita um índice;
    se um dia forem dezenas de milhares de registros, é este o lugar a mudar.
    """
    limite = today - timedelta(days=max_age_days)
    apagados = 0
    for sub in all_subscriptions():
        if sub.last_seen < limite:
            delete(sub.endpoint)
            apagados += 1
    return apagados
