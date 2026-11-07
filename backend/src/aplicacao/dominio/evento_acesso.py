from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aplicacao.dominio.usuario import agora_utc


@dataclass(frozen=True, slots=True, kw_only=True)
class EventoDeAcesso:
    """Acesso registrado, não pessoa única, conversa ou mensagem enviada."""

    link_id: UUID
    id: UUID = field(default_factory=uuid4)
    acessado_em: datetime = field(default_factory=agora_utc)

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.link_id, UUID):
            raise ValueError("Identificadores devem ser UUIDs.")
        if (
            not isinstance(self.acessado_em, datetime)
            or self.acessado_em.tzinfo is None
            or self.acessado_em.utcoffset() is None
        ):
            raise ValueError("Data de acesso deve incluir fuso horário.")
        object.__setattr__(self, "acessado_em", self.acessado_em.astimezone(UTC))
