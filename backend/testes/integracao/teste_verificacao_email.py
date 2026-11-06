import asyncio
import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from aplicacao.casos_de_uso.autenticar_usuario import AutenticarUsuario
from aplicacao.casos_de_uso.contratos_autenticacao import CredenciaisInvalidas, EntradaLogin
from aplicacao.casos_de_uso.verificar_email import VerificarEmail
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.dominio.verificacao_email import VerificacaoEmail
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.codigos_verificacao import CodigosVerificacaoHMAC
from aplicacao.infraestrutura.hash_senha import HashSenhaArgon2id
from aplicacao.infraestrutura.modelos import ModeloUsuario, ModeloVerificacaoEmail
from aplicacao.infraestrutura.repositorio_sessoes import RepositorioSessoesSQLAlchemy
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from aplicacao.infraestrutura.tokens import TokensSeguros
from aplicacao.infraestrutura.transacoes_verificacao import (
    TransacoesVerificacaoSQLAlchemy,
    criar_verificacao_email,
)

pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def ambiente():
    url = os.getenv("URL_BANCO_TESTE")
    if not url:
        pytest.skip("Configure URL_BANCO_TESTE para homologar verificações.")
    banco = BancoDados(Configuracao(_env_file=None, url_banco=url))
    esquema = "teste_verificacao_" + uuid4().hex

    def migrar(conexao):
        configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        configuracao.attributes["connection"] = conexao
        command.upgrade(configuracao, "head")

    try:
        async with banco.motor.begin() as conexao:
            await conexao.execute(text(f'CREATE SCHEMA "{esquema}"'))
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.run_sync(migrar)
        banco.sessoes = async_sessionmaker(
            banco.motor.execution_options(schema_translate_map={None: esquema}),
            expire_on_commit=False,
        )
        usuario = Usuario(
            nome="Ana",
            email="ana@example.com",
            senha_hash=await HashSenhaArgon2id().gerar("Frase longa de teste!"),
        )
        async with banco.transacao() as sessao:
            await RepositorioUsuariosSQLAlchemy(sessao).adicionar(usuario)
        agora = [agora_utc()]
        servico = VerificarEmail(
            TransacoesVerificacaoSQLAlchemy(banco),
            CodigosVerificacaoHMAC(SecretStr("s" * 32)),
            relogio=lambda: agora[0],
        )
        yield banco, esquema, usuario, servico, agora
    finally:
        async with banco.motor.begin() as conexao:
            await conexao.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        await banco.encerrar()


async def consultar(banco):
    async with banco.sessoes() as sessao:
        usuario = await sessao.scalar(select(ModeloUsuario))
        desafios = (
            await sessao.scalars(
                select(ModeloVerificacaoEmail).order_by(ModeloVerificacaoEmail.criado_em)
            )
        ).all()
        return usuario, desafios


async def test_geracao_persistencia_e_privacidade(ambiente, caplog):
    banco, _, usuario, servico, agora = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    codigo = desafio.codigo.get_secret_value()
    assert len(codigo) == 6 and codigo.isascii() and codigo.isdecimal()
    assert codigo not in repr(desafio) + desafio.model_dump_json() + caplog.text
    persistido, desafios = await consultar(banco)
    assert not persistido.email_verificado
    assert desafios[0].codigo_hash == servico.codigos.resumir(codigo, desafio.id, usuario.id)
    assert desafios[0].codigo_hash != codigo
    assert desafios[0].expira_em == agora[0] + timedelta(minutes=10)
    assert desafios[0].tentativas == 0


async def test_confirma_uma_vez_e_atualiza_usuario(ambiente):
    banco, _, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    assert await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    assert not await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    persistido, desafios = await consultar(banco)
    assert persistido.email_verificado and desafios[0].utilizado_em is not None


async def test_erros_persistem_e_bloqueiam_no_limite(ambiente):
    banco, _, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    incorreto = "000000" if desafio.codigo.get_secret_value() != "000000" else "999999"
    for _ in range(5):
        assert not await servico.confirmar(usuario.id, incorreto)
    assert not await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    persistido, desafios = await consultar(banco)
    assert not persistido.email_verificado
    assert desafios[0].tentativas == 5 and desafios[0].invalidado_em is not None


async def test_expiracao_exata(ambiente):
    banco, _, usuario, servico, agora = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    agora[0] = desafio.expira_em
    assert not await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    assert not (await consultar(banco))[0].email_verificado


async def test_reenvio_invalida_anterior_e_tem_limites(ambiente):
    banco, _, usuario, servico, agora = ambiente
    primeiro = await servico.gerar_desafio(usuario.id)
    assert await servico.gerar_desafio(usuario.id) is None
    for _ in range(4):
        agora[0] += timedelta(seconds=60)
        assert await servico.gerar_desafio(usuario.id) is not None
    agora[0] += timedelta(seconds=60)
    assert await servico.gerar_desafio(usuario.id) is None
    _, desafios = await consultar(banco)
    assert len(desafios) == 5 and all(d.invalidado_em for d in desafios[:-1])
    # HMAC antigo nunca autentica o desafio atual, mesmo se o número sorteado coincidir.
    assert not servico.codigos.conferir(
        primeiro.codigo.get_secret_value(), desafios[0].codigo_hash, desafios[-1].id, usuario.id
    )
    agora[0] += timedelta(hours=1)
    assert await servico.gerar_desafio(usuario.id) is not None


async def test_indice_parcial_impede_duas_verificacoes_pendentes(ambiente):
    banco, _, usuario, servico, agora = ambiente
    await servico.gerar_desafio(usuario.id)
    outro = VerificacaoEmail(
        usuario_id=usuario.id,
        codigo_hash="a" * 64,
        criado_em=agora[0],
        expira_em=agora[0] + timedelta(minutes=10),
    )
    with pytest.raises(IntegrityError):
        async with banco.transacao() as sessao:
            sessao.add(ModeloVerificacaoEmail(**vars(outro)))
    assert len((await consultar(banco))[1]) == 1


async def test_falha_no_commit_reverte_consumo_e_verificacao(ambiente):
    banco, esquema, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'CREATE FUNCTION "{esquema}".falhar_confirmacao() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Falha controlada de teste'; END $$"
            )
        )
        await conexao.execute(
            text(
                f'CREATE CONSTRAINT TRIGGER falha_commit AFTER UPDATE ON "{esquema}".usuarios '
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
                f'EXECUTE FUNCTION "{esquema}".falhar_confirmacao()'
            )
        )
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    persistido, desafios = await consultar(banco)
    assert not persistido.email_verificado and desafios[0].utilizado_em is None
    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'DROP TRIGGER falha_commit ON "{esquema}".usuarios'))
    assert await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())


async def test_reenvio_recusa_numero_antigo_e_preserva_anterior_em_falha(ambiente):
    banco, _, usuario, servico, agora = ambiente
    primeiro = await servico.gerar_desafio(usuario.id)
    antigo = primeiro.codigo.get_secret_value()
    novo = "000000" if antigo != "000000" else "999999"
    agora[0] += timedelta(seconds=60)
    with patch.object(servico.codigos, "gerar", return_value=antigo):
        with pytest.raises(RuntimeError):
            await servico.gerar_desafio(usuario.id)
    assert (await consultar(banco))[1][0].invalidado_em is None
    with patch.object(servico.codigos, "gerar", side_effect=[antigo, novo]):
        segundo = await servico.gerar_desafio(usuario.id)
    assert segundo.codigo.get_secret_value() == novo
    assert not await servico.confirmar(usuario.id, antigo)
    assert await servico.confirmar(usuario.id, novo)


async def test_confirmacoes_concorrentes_consumem_apenas_uma_vez(ambiente):
    banco, _, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    resultados = await asyncio.gather(
        *[servico.confirmar(usuario.id, desafio.codigo.get_secret_value()) for _ in range(2)]
    )
    assert sorted(resultados) == [False, True]
    persistido, desafios = await consultar(banco)
    assert persistido.email_verificado and desafios[0].utilizado_em is not None


async def test_geracoes_e_erros_concorrentes_sao_serializados(ambiente):
    banco, _, usuario, servico, _ = ambiente
    gerados = await asyncio.gather(*[servico.gerar_desafio(usuario.id) for _ in range(2)])
    assert sum(d is not None for d in gerados) == 1
    desafio = next(d for d in gerados if d is not None)
    incorreto = "000000" if desafio.codigo.get_secret_value() != "000000" else "999999"
    assert not any(
        await asyncio.gather(*[servico.confirmar(usuario.id, incorreto) for _ in range(8)])
    )
    assert (await consultar(banco))[1][0].tentativas == 5


async def test_rollback_preserva_codigo_e_usuario(ambiente):
    banco, esquema, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'ALTER TABLE "{esquema}".usuarios '
                "ADD CONSTRAINT bloquear_verificacao CHECK (NOT email_verificado)"
            )
        )
    with pytest.raises(IntegrityError):
        await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    persistido, desafios = await consultar(banco)
    assert not persistido.email_verificado and desafios[0].utilizado_em is None
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(f'ALTER TABLE "{esquema}".usuarios DROP CONSTRAINT bloquear_verificacao')
        )
    assert await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())


async def test_invalida_manualmente_e_recusa_usuario_ausente(ambiente):
    banco, _, usuario, servico, _ = ambiente
    desafio = await servico.gerar_desafio(usuario.id)
    await servico.invalidar(usuario.id)
    assert not await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    assert await servico.gerar_desafio(uuid4()) is None
    assert not await servico.confirmar(uuid4(), "123456")
    assert not (await consultar(banco))[0].email_verificado


async def test_login_permanece_bloqueado_ate_confirmacao(ambiente):
    banco, _, usuario, servico, _ = ambiente

    async def login():
        async with banco.transacao() as sessao:
            caso = AutenticarUsuario(
                RepositorioUsuariosSQLAlchemy(sessao),
                RepositorioSessoesSQLAlchemy(sessao),
                HashSenhaArgon2id(),
                TokensSeguros(),
                usuario.senha_hash,
                28800,
            )
            return await caso.executar(
                EntradaLogin(email=usuario.email, senha="Frase longa de teste!"), None
            )

    desafio = await servico.gerar_desafio(usuario.id)
    with pytest.raises(CredenciaisInvalidas):
        await login()
    assert await servico.confirmar(usuario.id, desafio.codigo.get_secret_value())
    assert (await login()).usuario.id == usuario.id


async def test_factory_exige_segredo_sem_afetar_api_existente(ambiente):
    banco, _, usuario, _, _ = ambiente
    with pytest.raises(ValueError, match="VERIFICACAO_SEGREDO"):
        criar_verificacao_email(banco, Configuracao(_env_file=None, verificacao_segredo=None))
    servico = criar_verificacao_email(
        banco, Configuracao(_env_file=None, verificacao_segredo="s" * 32)
    )
    assert await servico.gerar_desafio(usuario.id) is not None
