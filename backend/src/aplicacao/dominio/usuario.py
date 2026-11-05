from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def agora_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(kw_only=True)
class Usuario:
    nome: str
    email: str
    senha_hash: str = field(repr=False)
    id: UUID = field(default_factory=uuid4)
    email_verificado: bool = False
    ativo: bool = True
    criado_em: datetime = field(default_factory=agora_utc)
    atualizado_em: datetime = field(default_factory=agora_utc)

    def __post_init__(self) -> None:
        self.nome = self.nome.strip()
        self.email = self.email.strip().lower()
        if not 2 <= len(self.nome) <= 100:
            raise ValueError("Nome deve ter entre 2 e 100 caracteres.")
        if not self.email or len(self.email) > 254:
            raise ValueError("E-mail deve ter entre 1 e 254 caracteres.")
        if not self.senha_hash or len(self.senha_hash) > 512:
            raise ValueError("Hash de senha obrigat?rio, com at? 512 caracteres.")
        for data in (self.criado_em, self.atualizado_em):
            if data.tzinfo is None or data.utcoffset() is None:
                raise ValueError("Datas devem incluir fuso hor?rio.")
        self.criado_em = self.criado_em.astimezone(UTC)
        self.atualizado_em = self.atualizado_em.astimezone(UTC)
