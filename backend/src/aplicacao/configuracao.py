from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    ambiente: str = "desenvolvimento"
    origens_permitidas: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
