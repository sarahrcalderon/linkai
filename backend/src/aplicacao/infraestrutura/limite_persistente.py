import hashlib
import hmac
from datetime import timedelta

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert

from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.modelos import ModeloLimiteRequisicoes


async def permitir_requisicao(
    banco: BancoDados,
    configuracao: Configuracao,
    origem: str,
    caminho: str,
    limite: int,
    janela: int,
) -> bool:
    if configuracao.verificacao_segredo is None:
        raise ValueError("Configure VERIFICACAO_SEGREDO para proteção persistente.")
    chave = hmac.new(
        configuracao.verificacao_segredo.get_secret_value().encode(),
        f"linkai-limite:{caminho}:{origem}".encode(),
        hashlib.sha256,
    ).hexdigest()
    agora = agora_utc()
    expirou = ModeloLimiteRequisicoes.inicio <= agora - timedelta(seconds=janela)
    consulta = insert(ModeloLimiteRequisicoes).values(chave=chave, inicio=agora, tentativas=1)
    consulta = consulta.on_conflict_do_update(
        index_elements=[ModeloLimiteRequisicoes.chave],
        set_={
            "inicio": case((expirou, agora), else_=ModeloLimiteRequisicoes.inicio),
            "tentativas": case(
                (expirou, 1), else_=func.least(ModeloLimiteRequisicoes.tentativas + 1, limite + 1)
            ),
        },
    )
    async with banco.transacao() as sessao:
        quantidade = await sessao.scalar(consulta.returning(ModeloLimiteRequisicoes.tentativas))
    return quantidade <= limite
