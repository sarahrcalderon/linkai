import asyncio
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher, Type, extract_parameters
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.modelos import ModeloUsuario
from aplicacao.principal import criar_aplicacao

pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def ambiente_cadastro():
    url = os.getenv("URL_BANCO_TESTE")
    if not url:
        pytest.skip("Configure URL_BANCO_TESTE para testar cadastro em PostgreSQL real.")
    app = criar_aplicacao(Configuracao(_env_file=None, url_banco=url))
    esquema = "teste_cadastro_" + uuid4().hex

    def migrar(conexao):
        configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        configuracao.attributes["connection"] = conexao
        command.upgrade(configuracao, "head")

    async with app.router.lifespan_context(app):
        banco = app.state.banco
        try:
            async with banco.motor.begin() as conexao:
                await conexao.execute(text(f'CREATE SCHEMA "{esquema}"'))
                await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
                await conexao.run_sync(migrar)
            banco.sessoes = async_sessionmaker(
                banco.motor.execution_options(schema_translate_map={None: esquema}),
                expire_on_commit=False,
            )
            transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as cliente:
                yield cliente, banco, esquema
        finally:
            async with banco.motor.begin() as conexao:
                await conexao.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))


def dados_validos():
    return {"nome": " Ana Silva ", "email": " ANA@EXAMPLE.COM ", "senha": "Senha longa de teste!"}


async def contar_usuarios(banco):
    async with banco.sessoes() as sessao:
        return await sessao.scalar(select(func.count()).select_from(ModeloUsuario))


async def test_cadastro_persiste_hash_sem_autenticar(ambiente_cadastro, caplog):
    cliente, banco, _ = ambiente_cadastro
    dados = dados_validos()
    resposta = await cliente.post("/api/autenticacao/cadastro", json=dados)
    assert resposta.status_code == 202
    assert set(resposta.json()) == {"mensagem"}
    assert "verificação de e-mail" in resposta.json()["mensagem"]
    assert not resposta.cookies
    assert "set-cookie" not in resposta.headers
    async with banco.sessoes() as sessao:
        usuario = await sessao.scalar(select(ModeloUsuario))
        assert usuario.nome == "Ana Silva"
        assert usuario.email == "ana@example.com"
        assert usuario.email_verificado is False and usuario.ativo is True
        assert usuario.senha_hash != dados["senha"]
        assert extract_parameters(usuario.senha_hash).type == Type.ID
        assert PasswordHasher().verify(usuario.senha_hash, dados["senha"])
        assert usuario.senha_hash not in resposta.text
        assert usuario.senha_hash not in caplog.text
    assert dados["senha"] not in resposta.text + caplog.text
    assert "senha" not in resposta.text and "hash" not in resposta.text


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"nome": " "},
        {"nome": "a" * 101},
        {"nome": 123},
        {"nome": "Ana\nSilva"},
        {"email": "invalido"},
        {"email": "a" * 255 + "@example.com"},
        {"email": None},
        {"senha": "curta"},
        {"senha": "a" * 129},
        {"senha": " " * 12},
        {"senha": "senha\ncomprida"},
        {"senha": 123456789012},
        {"ativo": True},
        {"email_verificado": True},
    ],
)
async def test_rejeita_campos_invalidos(ambiente_cadastro, alteracoes):
    cliente, banco, _ = ambiente_cadastro
    resposta = await cliente.post("/api/autenticacao/cadastro", json=dados_validos() | alteracoes)
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "dados_invalidos"
    assert "input" not in resposta.text
    assert dados_validos()["senha"] not in resposta.text
    assert await contar_usuarios(banco) == 0


@pytest.mark.parametrize("campo", ["nome", "email", "senha"])
async def test_rejeita_campo_ausente(ambiente_cadastro, campo):
    cliente, banco, _ = ambiente_cadastro
    dados = dados_validos()
    del dados[campo]
    resposta = await cliente.post("/api/autenticacao/cadastro", json=dados)
    assert resposta.status_code == 422
    assert await contar_usuarios(banco) == 0


async def test_email_duplicado_tem_mesma_resposta(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    primeira = await cliente.post("/api/autenticacao/cadastro", json=dados_validos())
    segunda = await cliente.post(
        "/api/autenticacao/cadastro",
        json=dados_validos() | {"email": "ana@example.com", "senha": "Outra senha diferente!"},
    )
    assert primeira.status_code == segunda.status_code == 202
    assert primeira.json() == segunda.json()
    assert await contar_usuarios(banco) == 1
    async with banco.sessoes() as sessao:
        usuario = await sessao.scalar(select(ModeloUsuario))
        assert PasswordHasher().verify(usuario.senha_hash, dados_validos()["senha"])


async def test_cadastro_concorrente_persiste_apenas_um(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    respostas = await asyncio.gather(
        *[cliente.post("/api/autenticacao/cadastro", json=dados_validos()) for _ in range(2)]
    )
    assert [resposta.status_code for resposta in respostas] == [202, 202]
    assert respostas[0].json() == respostas[1].json()
    assert await contar_usuarios(banco) == 1


async def test_falha_no_commit_nao_retorna_sucesso_e_faz_rollback(ambiente_cadastro, caplog):
    cliente, banco, esquema = ambiente_cadastro
    # Restrição adiada força falha no COMMIT, depois do flush e do retorno do caso de uso.
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'ALTER TABLE "{esquema}".usuarios ADD CONSTRAINT nome_unico_teste '
                "UNIQUE (nome) DEFERRABLE INITIALLY DEFERRED"
            )
        )
    primeira = await cliente.post("/api/autenticacao/cadastro", json=dados_validos())
    assert primeira.status_code == 202
    falha = await cliente.post(
        "/api/autenticacao/cadastro", json=dados_validos() | {"email": "outra@example.com"}
    )
    assert falha.status_code == 503
    assert falha.json()["erro"]["codigo"] == "servico_indisponivel"
    assert "INSERT" not in falha.text and "Traceback" not in falha.text
    assert dados_validos()["senha"] not in caplog.text + falha.text
    assert await contar_usuarios(banco) == 1
    terceira = await cliente.post(
        "/api/autenticacao/cadastro",
        json=dados_validos() | {"nome": "Bia", "email": "bia@example.com"},
    )
    assert terceira.status_code == 202
    assert await contar_usuarios(banco) == 2


async def test_rate_limit_conta_invalidos_e_ignora_cabecalho_forjado(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    for _ in range(5):
        resposta = await cliente.post("/api/autenticacao/cadastro", json={})
        assert resposta.status_code == 422
    bloqueada = await cliente.post(
        "/api/autenticacao/cadastro",
        json=dados_validos(),
        headers={"X-Forwarded-For": "192.0.2.10"},
    )
    assert bloqueada.status_code == 429
    assert int(bloqueada.headers["Retry-After"]) > 0
    assert bloqueada.json()["erro"]["codigo"] == "limite_excedido"
    assert await contar_usuarios(banco) == 0
    assert (await cliente.get("/api/saude")).status_code == 200


async def test_limite_corpo_em_stream_e_json_invalido(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro

    async def corpo():
        yield b"a" * 4096
        yield b"b" * 4097

    grande = await cliente.post("/api/autenticacao/cadastro", content=corpo())
    assert grande.status_code == 413
    assert grande.json()["erro"]["codigo"] == "corpo_excedido"
    malformada = await cliente.post(
        "/api/autenticacao/cadastro",
        content=b'{"senha": "segredo-nao-refletir",',
        headers={"Content-Type": "application/json"},
    )
    assert malformada.status_code == 422
    assert "segredo-nao-refletir" not in malformada.text
    assert await contar_usuarios(banco) == 0
