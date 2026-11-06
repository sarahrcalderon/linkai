from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aplicacao.dominio.usuario import agora_utc


@dataclass(kw_only=True)
class VerificacaoEmail:
    usuario_id: UUID
    codigo_hash: str = field(repr=False)
    expira_em: datetime
    id: UUID = field(default_factory=uuid4)
    criado_em: datetime = field(default_factory=agora_utc)
    utilizado_em: datetime | None = None
    invalidado_em: datetime | None = None
    tentativas: int = 0
    limite_tentativas: int = 5

    def __post_init__(self) -> None:
        for campo in ("criado_em", "expira_em", "utilizado_em", "invalidado_em"):
            data = getattr(self, campo)
            if data is not None:
                if data.tzinfo is None or data.utcoffset() is None:
                    raise ValueError("Datas da verificação devem incluir fuso horário.")
                setattr(self, campo, data.astimezone(UTC))
        if self.expira_em <= self.criado_em:
            raise ValueError("Prazo de verificação inválido.")
        if not 0 <= self.tentativas <= self.limite_tentativas or self.limite_tentativas < 1:
            raise ValueError("Limites de tentativas inválidos.")
        if len(self.codigo_hash) != 64 or any(
            c not in "0123456789abcdef" for c in self.codigo_hash
        ):
            raise ValueError("Resumo de verificação inválido.")

    def disponivel(self, agora: datetime) -> bool:
        return (
            self.utilizado_em is None
            and self.invalidado_em is None
            and self.criado_em <= agora < self.expira_em
            and self.tentativas < self.limite_tentativas
        )

    def registrar_erro(self, agora: datetime) -> None:
        if not self.disponivel(agora):
            raise ValueError("Verificação indisponível.")
        self.tentativas += 1
        if self.tentativas == self.limite_tentativas:
            self.invalidado_em = agora

    def utilizar(self, agora: datetime) -> None:
        if not self.disponivel(agora):
            raise ValueError("Verificação indisponível.")
        self.utilizado_em = agora
