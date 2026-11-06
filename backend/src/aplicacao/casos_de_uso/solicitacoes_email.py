from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from aplicacao.casos_de_uso.verificar_email import VerificarEmail
from aplicacao.dominio.repositorio_usuarios import RepositorioUsuarios


class EntradaReenvio(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    email: EmailStr = Field(max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, valor):
        return valor.strip().lower() if isinstance(valor, str) else valor


class EntradaConfirmacao(EntradaReenvio):
    codigo: SecretStr = Field(min_length=6, max_length=6, repr=False)

    @field_validator("codigo")
    @classmethod
    def validar_codigo(cls, valor: SecretStr) -> SecretStr:
        codigo = valor.get_secret_value()
        if not codigo.isascii() or not codigo.isdecimal():
            raise ValueError("Informe um código de seis dígitos.")
        return valor


class SolicitacoesEmail:
    def __init__(self, usuarios: RepositorioUsuarios, verificacao: VerificarEmail) -> None:
        self.usuarios = usuarios
        self.verificacao = verificacao

    async def reenviar(self, entrada: EntradaReenvio) -> None:
        usuario = await self.usuarios.obter_por_email(entrada.email)
        if usuario is not None:
            await self.verificacao.gerar_desafio(usuario.id)

    async def confirmar(self, entrada: EntradaConfirmacao) -> bool:
        usuario = await self.usuarios.obter_por_email(entrada.email)
        if usuario is None:
            return False
        return await self.verificacao.confirmar(usuario.id, entrada.codigo.get_secret_value())
