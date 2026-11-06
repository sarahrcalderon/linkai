from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from aplicacao.casos_de_uso.contratos_verificacao import (
    CodigosVerificacao,
    DesafioGerado,
    TransacoesVerificacao,
)
from aplicacao.dominio.usuario import agora_utc
from aplicacao.dominio.verificacao_email import VerificacaoEmail


class VerificarEmail:
    def __init__(
        self,
        transacoes: TransacoesVerificacao,
        codigos: CodigosVerificacao,
        validade_segundos: int = 600,
        limite_tentativas: int = 5,
        intervalo_reenvio: int = 60,
        limite_envios: int = 5,
        janela_envios: int = 3600,
        relogio: Callable[[], datetime] = agora_utc,
    ) -> None:
        if (
            min(
                validade_segundos,
                limite_tentativas,
                intervalo_reenvio,
                limite_envios,
                janela_envios,
            )
            < 1
        ):
            raise ValueError("Parâmetros de verificação devem ser positivos.")
        self.transacoes = transacoes
        self.codigos = codigos
        self.validade = validade_segundos
        self.limite_tentativas = limite_tentativas
        self.intervalo_reenvio = intervalo_reenvio
        self.limite_envios = limite_envios
        self.janela_envios = janela_envios
        self.relogio = relogio

    async def gerar_desafio(self, usuario_id: UUID) -> DesafioGerado | None:
        # Também é o fluxo interno de reenvio. Bloqueio do usuário serializa todas as operações.
        async with self.transacoes() as contexto:
            usuario = await contexto.usuarios.obter_para_atualizacao(usuario_id)
            if usuario is None or not usuario.ativo or usuario.email_verificado:
                return None
            agora = self.relogio()
            anterior = await contexto.verificacoes.obter_ultima(usuario_id)
            if anterior and agora < anterior.criado_em + timedelta(seconds=self.intervalo_reenvio):
                return None
            recentes = await contexto.verificacoes.obter_recentes(
                usuario_id, agora - timedelta(seconds=max(self.janela_envios, self.validade))
            )
            inicio_janela = agora - timedelta(seconds=self.janela_envios)
            quantidade = sum(d.criado_em >= inicio_janela for d in recentes)
            if quantidade >= self.limite_envios:
                return None
            # Evita que um número antigo coincida com o novo por sorteio na janela protegida.
            for _ in range(20):
                codigo = self.codigos.gerar()
                if not any(
                    self.codigos.conferir(codigo, d.codigo_hash, d.id, usuario_id) for d in recentes
                ):
                    break
            else:
                raise RuntimeError("Não foi possível gerar um novo desafio.")
            identificador = uuid4()
            desafio = VerificacaoEmail(
                id=identificador,
                usuario_id=usuario_id,
                codigo_hash=self.codigos.resumir(codigo, identificador, usuario_id),
                criado_em=agora,
                expira_em=agora + timedelta(seconds=self.validade),
                limite_tentativas=self.limite_tentativas,
            )
            await contexto.verificacoes.invalidar_anteriores(usuario_id, agora)
            await contexto.verificacoes.adicionar(desafio)
            return DesafioGerado(
                id=desafio.id, usuario_id=usuario_id, expira_em=desafio.expira_em, codigo=codigo
            )

    async def confirmar(self, usuario_id: UUID, codigo: str) -> bool:
        async with self.transacoes() as contexto:
            usuario = await contexto.usuarios.obter_para_atualizacao(usuario_id)
            if usuario is None or not usuario.ativo or usuario.email_verificado:
                return False
            desafio = await contexto.verificacoes.obter_ultima(usuario_id)
            agora = self.relogio()
            if desafio is None or not desafio.disponivel(agora):
                return False
            if not self.codigos.conferir(codigo, desafio.codigo_hash, desafio.id, usuario_id):
                desafio.registrar_erro(agora)
                await contexto.verificacoes.atualizar(desafio)
                # Retorno normal confirma o contador; exceção de negócio não deve revertê-lo.
                return False
            desafio.utilizar(agora)
            await contexto.verificacoes.atualizar(desafio)
            await contexto.usuarios.marcar_email_verificado(usuario_id, agora)
            return True

    async def invalidar(self, usuario_id: UUID) -> None:
        async with self.transacoes() as contexto:
            if await contexto.usuarios.obter_para_atualizacao(usuario_id) is not None:
                await contexto.verificacoes.invalidar_anteriores(usuario_id, self.relogio())
