from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    url_banco: SecretStr | None = None
    ambiente: str = "desenvolvimento"
    origens_permitidas: list[str] = ["http://localhost:5173"]
    cadastro_limite_tentativas: int = Field(default=5, ge=1, le=1000)
    cadastro_janela_segundos: int = Field(default=900, ge=1, le=86400)
    login_limite_tentativas: int = Field(default=10, ge=1, le=1000)
    login_janela_segundos: int = Field(default=900, ge=1, le=86400)
    sessao_duracao_segundos: int = Field(default=28800, ge=60, le=604800)
    sessao_cookie_seguro: bool | None = None
    sessao_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @property
    def cookie_seguro(self) -> bool:
        return self.ambiente == "producao" or self.sessao_cookie_seguro is True

    @model_validator(mode="after")
    def validar_seguranca(self):
        if self.ambiente not in {"desenvolvimento", "teste", "producao"}:
            raise ValueError("AMBIENTE deve ser desenvolvimento, teste ou producao.")
        if self.ambiente == "producao" and self.sessao_cookie_seguro is False:
            raise ValueError("Cookie Secure obrigatório em produção.")
        if self.sessao_cookie_samesite == "none" and not self.cookie_seguro:
            raise ValueError("SameSite=None exige cookie Secure e HTTPS.")
        for origem in self.origens_permitidas:
            url = urlsplit(origem)
            if (
                url.scheme not in {"http", "https"}
                or not url.netloc
                or url.path
                or url.query
                or url.fragment
                or url.username
                or url.password
                or "*" in origem
            ):
                raise ValueError("Configure origens HTTP explícitas, sem caminho ou curingas.")
            if self.ambiente == "producao" and url.scheme != "https":
                raise ValueError("Origens de produção devem usar HTTPS.")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
