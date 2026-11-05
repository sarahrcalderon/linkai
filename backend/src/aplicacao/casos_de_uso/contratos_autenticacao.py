from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from aplicacao.dominio.usuario import Usuario


class EntradaLogin(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    email: EmailStr = Field(max_length=254)
    senha: SecretStr = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, valor):
        return valor.strip().lower() if isinstance(valor, str) else valor


class CredenciaisInvalidas(Exception):
    pass


class SessaoInvalida(Exception):
    pass


class CsrfInvalido(Exception):
    pass


@dataclass(frozen=True)
class ResultadoAutenticacao:
    usuario: Usuario
    csrf: str = field(repr=False)


@dataclass(frozen=True)
class ResultadoLogin(ResultadoAutenticacao):
    token: str = field(repr=False)
    expira_em: datetime
