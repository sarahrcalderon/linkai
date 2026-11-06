import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aplicacao.dominio.usuario import agora_utc

SLUGS_RESERVADOS = frozenset(
    {
        "api",
        "admin",
        "login",
        "logout",
        "cadastro",
        "dashboard",
        "verificar-email",
        "reenviar-codigo",
        "static",
        "assets",
        "docs",
        "redoc",
        "openapi",
        "saude",
        "www",
    }
)


def normalizar_slug(valor: str) -> str:
    if not isinstance(valor, str):
        raise ValueError("Slug deve ser texto.")
    slug = valor.strip().lower()
    if not 3 <= len(slug) <= 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Slug deve ter 3 a 64 letras ASCII, números ou hífens entre segmentos.")
    if slug in SLUGS_RESERVADOS:
        raise ValueError("Slug reservado à plataforma.")
    return slug


def normalizar_numero_whatsapp(valor: str) -> str:
    if not isinstance(valor, str):
        raise ValueError("Número deve ser texto.")
    numero = re.sub(r"[ ().-]", "", valor.strip())
    if not numero.startswith("+"):
        numero = "+" + numero
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", numero):
        raise ValueError("Informe número internacional com código do país e 8 a 15 dígitos.")
    return numero


@dataclass(frozen=True, kw_only=True)
class Link:
    usuario_id: UUID
    nome: str
    slug: str
    numero_whatsapp: str = field(repr=False)
    mensagem: str | None = field(default=None, repr=False)
    id: UUID = field(default_factory=uuid4)
    ativo: bool = True
    criado_em: datetime = field(default_factory=agora_utc)
    atualizado_em: datetime = field(default_factory=agora_utc)
    excluido_em: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.usuario_id, UUID):
            raise ValueError("Identificadores devem ser UUIDs.")
        if not isinstance(self.nome, str):
            raise ValueError("Nome deve ser texto.")
        nome = self.nome.strip()
        if not 2 <= len(nome) <= 100 or any(unicodedata.category(c).startswith("C") for c in nome):
            raise ValueError("Nome deve ter 2 a 100 caracteres, sem controles.")
        if type(self.ativo) is not bool:
            raise ValueError("Estado ativo deve ser booleano.")
        if self.mensagem is not None:
            if not isinstance(self.mensagem, str):
                raise ValueError("Mensagem deve ser texto.")
            if len(self.mensagem) > 2000 or any(c in self.mensagem for c in "<>"):
                raise ValueError("Mensagem deve ser texto sem marcação, com até 2000 caracteres.")
            if any(
                unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in self.mensagem
            ):
                raise ValueError("Mensagem contém caracteres de controle inválidos.")
        for campo in ("criado_em", "atualizado_em", "excluido_em"):
            data = getattr(self, campo)
            if data is None and campo != "excluido_em":
                raise ValueError("Datas de criação e atualização são obrigatórias.")
            if data is not None:
                if (
                    not isinstance(data, datetime)
                    or data.tzinfo is None
                    or data.utcoffset() is None
                ):
                    raise ValueError("Datas devem incluir fuso horário.")
                object.__setattr__(self, campo, data.astimezone(UTC))
        if self.atualizado_em < self.criado_em:
            raise ValueError("Atualização não pode anteceder a criação.")
        if self.excluido_em is not None and (
            self.ativo or not self.criado_em <= self.excluido_em <= self.atualizado_em
        ):
            raise ValueError("Link excluído deve estar inativo e ter datas consistentes.")
        object.__setattr__(self, "nome", nome)
        object.__setattr__(self, "slug", normalizar_slug(self.slug))
        object.__setattr__(
            self, "numero_whatsapp", normalizar_numero_whatsapp(self.numero_whatsapp)
        )

    @property
    def disponivel_para_redirecionamento(self) -> bool:
        return self.ativo and self.excluido_em is None

    def excluir(self, agora: datetime | None = None) -> "Link":
        if self.excluido_em is not None:
            return self
        instante = agora if agora is not None else agora_utc()
        return replace(self, ativo=False, excluido_em=instante, atualizado_em=instante)
