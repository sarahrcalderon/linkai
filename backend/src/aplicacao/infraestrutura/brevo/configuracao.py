from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracaoBrevo(BaseSettings):
    api_key: SecretStr = Field(min_length=1, max_length=4096, repr=False)
    email_remetente: EmailStr = Field(max_length=254, repr=False)
    nome_remetente: str = Field(default="Linkai", min_length=1, max_length=100)
    timeout_segundos: float = Field(default=10, gt=0, le=30, allow_inf_nan=False)
    limite_tentativas: int = Field(default=3, ge=1, le=5)
    tempo_total_segundos: float = Field(default=20, gt=0, le=60, allow_inf_nan=False)

    model_config = SettingsConfigDict(
        env_prefix="BREVO_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("api_key")
    @classmethod
    def validar_chave(cls, valor: SecretStr) -> SecretStr:
        chave = valor.get_secret_value()
        if not chave.isascii() or any(c.isspace() or not c.isprintable() for c in chave):
            raise ValueError("Chave de API inválida.")
        return valor

    @field_validator("nome_remetente")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor or not valor.isprintable():
            raise ValueError("Nome do remetente inválido.")
        return valor
