from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from aplicacao.dominio.usuario import agora_utc


@dataclass(kw_only=True)
class Sessao:
    usuario_id: UUID
    token_hash: str = field(repr=False)
    expira_em: datetime
    id: UUID = field(default_factory=uuid4)
    criado_em: datetime = field(default_factory=agora_utc)
    revogado_em: datetime | None = None

    def __post_init__(self) -> None:
        for data in (self.criado_em, self.expira_em, self.revogado_em):
            if data is not None and (data.tzinfo is None or data.utcoffset() is None):
                raise ValueError("Datas da sessão devem incluir fuso horário.")
        if self.expira_em <= self.criado_em:
            raise ValueError("A expiração deve ser posterior à criação.")
        if len(self.token_hash) != 64 or any(c not in "0123456789abcdef" for c in self.token_hash):
            raise ValueError("Resumo de sessão inválido.")

    def esta_valida(self, agora: datetime) -> bool:
        return self.revogado_em is None and self.criado_em <= agora < self.expira_em
