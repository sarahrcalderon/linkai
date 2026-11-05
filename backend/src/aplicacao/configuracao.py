from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    url_banco: SecretStr | None = None
    ambiente: str = "desenvolvimento"
    origens_permitidas: list[str] = ["http://localhost:5173"]
    cadastro_limite_tentativas: int = Field(default=5, ge=1, le=1000)
    cadastro_janela_segundos: int = Field(default=900, ge=1, le=86400)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
