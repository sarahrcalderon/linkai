import json
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr, ValidationError, validate_email

from aplicacao.casos_de_uso.contratos_entrega import ConteudoEntregaInvalido
from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado


class CifraOutbox:
    def __init__(self, chave: SecretStr | None) -> None:
        try:
            if chave is None:
                raise ValueError()
            self._cifra = Fernet(chave.get_secret_value().encode("ascii"))
        except (ValueError, UnicodeError):
            raise ValueError("Configure OUTBOX_CHAVE com uma chave Fernet válida.") from None

    def cifrar(self, destinatario: str, desafio: DesafioGerado) -> str:
        conteudo = {
            "destinatario": destinatario,
            "desafio": {
                "id": str(desafio.id),
                "usuario_id": str(desafio.usuario_id),
                "expira_em": desafio.expira_em.isoformat(),
                "codigo": desafio.codigo.get_secret_value(),
            },
        }
        return self._cifra.encrypt(json.dumps(conteudo).encode()).decode("ascii")

    def decifrar(self, dados: str, identificador: UUID) -> tuple[str, DesafioGerado]:
        try:
            conteudo = json.loads(self._cifra.decrypt(dados.encode("ascii")))
            desafio = DesafioGerado.model_validate(conteudo["desafio"])
            _, destinatario = validate_email(conteudo["destinatario"])
            if desafio.id != identificador or desafio.expira_em.tzinfo is None:
                raise ValueError()
            return destinatario, desafio
        except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError, ValidationError):
            raise ConteudoEntregaInvalido() from None
