from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class EntradaCadastro(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    senha: SecretStr = Field(min_length=12, max_length=128, repr=False)

    @field_validator("nome", "email", mode="before")
    @classmethod
    def normalizar_texto(cls, valor):
        if isinstance(valor, str):
            return valor.strip()
        return valor

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        if any(not caractere.isprintable() for caractere in valor):
            raise ValueError("Nome contém caracteres de controle.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return valor.lower()

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor: SecretStr) -> SecretStr:
        senha = valor.get_secret_value()
        if not senha.strip() or any(not caractere.isprintable() for caractere in senha):
            raise ValueError("Senha não pode ser vazia ou conter caracteres de controle.")
        return valor
