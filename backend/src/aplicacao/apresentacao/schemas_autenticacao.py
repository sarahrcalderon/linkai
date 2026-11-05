from uuid import UUID

from pydantic import BaseModel

from aplicacao.casos_de_uso.contratos_autenticacao import EntradaLogin, ResultadoAutenticacao


class LoginEntradaHTTP(EntradaLogin):
    pass


class UsuarioPublicoHTTP(BaseModel):
    id: UUID
    nome: str
    email: str
    email_verificado: bool


class AutenticacaoSaidaHTTP(BaseModel):
    usuario: UsuarioPublicoHTTP
    csrf: str

    @classmethod
    def do_resultado(cls, resultado: ResultadoAutenticacao):
        usuario = resultado.usuario
        return cls(
            usuario=UsuarioPublicoHTTP(
                id=usuario.id,
                nome=usuario.nome,
                email=usuario.email,
                email_verificado=usuario.email_verificado,
            ),
            csrf=resultado.csrf,
        )
