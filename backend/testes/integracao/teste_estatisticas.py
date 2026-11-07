import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import OperationalError

import aplicacao.casos_de_uso.consultar_estatisticas as casos
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso, ModeloSessao, ModeloUsuario
from aplicacao.infraestrutura.repositorio_estatisticas import RepositorioEstatisticasSQLAlchemy
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy
from testes.integracao.teste_api_links import ambiente_links as ambiente_links
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro
from testes.integracao.teste_links import criar

pytestmark = pytest.mark.postgres
AGORA = datetime(2026, 11, 6, 12, 30, tzinfo=UTC)


async def preparar(banco, monkeypatch):
    monkeypatch.setattr(casos, "agora_utc", lambda: AGORA)
    async with banco.transacao() as s:
        usuarios = (await s.scalars(select(ModeloUsuario).order_by(ModeloUsuario.email))).all()
        links = [
            criar(usuarios[0], slug="primeiro"),
            criar(usuarios[0], slug="inativo", ativo=False),
            criar(usuarios[0], slug="excluido").excluir(),
            criar(usuarios[1], slug="alheio"),
        ]
        for link in links:
            await RepositorioLinksSQLAlchemy(s).adicionar(link)
    return usuarios, links


async def eventos(banco, link, instantes):
    async with banco.transacao() as s:
        s.add_all(
            [ModeloEventoAcesso(id=uuid4(), link_id=link.id, acessado_em=d) for d in instantes]
        )


@pytest.mark.parametrize("dias", [7, 30, 90])
async def test_periodos_limites_utc_e_agregacoes_reais(ambiente_links, monkeypatch, dias):
    c, banco, _, h = ambiente_links
    _, links = await preparar(banco, monkeypatch)
    inicio = AGORA.replace(hour=0, minute=0) - timedelta(days=dias - 1)
    # Antes/depois da janela, fronteiras exatas, virada UTC e offset local.
    instantes = [
        inicio - timedelta(microseconds=1),
        inicio,
        inicio + timedelta(hours=1),
        AGORA.replace(hour=0, minute=0) - timedelta(microseconds=1),
        datetime(2026, 11, 5, 21, tzinfo=timezone(timedelta(hours=-3))),
        AGORA - timedelta(microseconds=1),
        AGORA,
        AGORA + timedelta(days=1),
    ]
    await eventos(banco, links[0], instantes)
    r = await c.get(f"/api/links/{links[0].id}/estatisticas?dias={dias}", headers=h[0])
    assert r.status_code == 200 and r.headers["Cache-Control"] == "private, no-store"
    saida = r.json()
    assert set(saida) == {"link_id", "total_acessos", "data_inicial", "data_final", "serie_diaria"}
    assert saida["total_acessos"] == 5 and len(saida["serie_diaria"]) == dias
    assert saida["serie_diaria"][0]["acessos"] == 2 and saida["serie_diaria"][-1]["acessos"] == 2
    assert saida["serie_diaria"][-2]["acessos"] == 1
    assert all(d["acessos"] == 0 for d in saida["serie_diaria"][1:-2])
    assert [d["data"] for d in saida["serie_diaria"]] == sorted(
        d["data"] for d in saida["serie_diaria"]
    )
    assert datetime.fromisoformat(saida["data_inicial"]) == inicio
    assert datetime.fromisoformat(saida["data_final"]) == AGORA


@pytest.mark.parametrize("quantidade", [0, 1, 4])
async def test_sem_eventos_um_e_varios(ambiente_links, monkeypatch, quantidade):
    c, banco, _, h = ambiente_links
    _, links = await preparar(banco, monkeypatch)
    await eventos(banco, links[0], [AGORA - timedelta(seconds=1)] * quantidade)
    r = await c.get(f"/api/links/{links[0].id}/estatisticas", headers=h[0])
    assert r.status_code == 200 and r.json()["total_acessos"] == quantidade
    assert len(r.json()["serie_diaria"]) == 7


@pytest.mark.parametrize("dias", [7, 30, 90])
async def test_resumo_ativos_inativos_excluidos_e_outros(ambiente_links, monkeypatch, dias):
    c, banco, _, h = ambiente_links
    _, links = await preparar(banco, monkeypatch)
    for link, n in zip(links, [2, 3, 5, 7], strict=True):
        await eventos(banco, link, [AGORA - timedelta(seconds=1)] * n)
    r = await c.get(f"/api/estatisticas/resumo?dias={dias}", headers=h[0])
    assert r.status_code == 200 and r.headers["Cache-Control"] == "private, no-store"
    saida = r.json()
    assert (
        saida["links_ativos"] == 1 and saida["links_inativos"] == 1 and saida["total_acessos"] == 5
    )
    assert saida["serie_diaria"][-1]["acessos"] == 5
    assert len(saida["serie_diaria"]) == dias
    assert (await c.get(f"/api/links/{links[1].id}/estatisticas", headers=h[0])).json()[
        "total_acessos"
    ] == 3
    alheio = await c.get("/api/estatisticas/resumo", headers=h[1])
    assert alheio.json()["total_acessos"] == 7
    for identificador in [links[2].id, links[3].id, uuid4()]:
        r = await c.get(f"/api/links/{identificador}/estatisticas", headers=h[0])
        assert r.status_code == 404 and r.json() == {
            "erro": {"codigo": "link_nao_encontrado", "mensagem": "Link não encontrado."}
        }
        assert r.headers["Cache-Control"] == "private, no-store"
    assert not any(
        s in json.dumps(saida)
        for s in ["usuario_id", "numero_whatsapp", "mensagem", "user_agent", "link_id"]
    )


@pytest.mark.parametrize(
    "consulta",
    [
        "dias=0",
        "dias=1",
        "dias=8",
        "dias=91",
        "dias=7.0",
        "dias=-7",
        "dias=abc",
        "dias=",
        "usuario_id=qualquer",
        "inicio=2020-01-01",
        "fim=2030-01-01",
    ],
)
async def test_limites_query_sem_refletir_input(ambiente_links, consulta):
    c, _, _, h = ambiente_links
    for caminho in ["/api/estatisticas/resumo", f"/api/links/{uuid4()}/estatisticas"]:
        r = await c.get(caminho + "?" + consulta, headers=h[0])
        assert r.status_code == 422 and r.json()["erro"]["codigo"] == "dados_invalidos"
        assert r.headers["Cache-Control"] == "private, no-store"
        assert "qualquer" not in r.text


async def test_sessao_ausente_expirada_e_uuid(ambiente_links):
    c, banco, _, h = ambiente_links
    for caminho in ["/api/estatisticas/resumo", f"/api/links/{uuid4()}/estatisticas"]:
        r = await c.get(caminho)
        assert r.status_code == 401 and r.headers["Cache-Control"] == "private, no-store"
    assert (await c.get("/api/links/invalido/estatisticas", headers=h[0])).status_code == 422
    async with banco.transacao() as s:
        await s.execute(
            update(ModeloSessao).values(
                criado_em=agora_utc() - timedelta(hours=2),
                expira_em=agora_utc() - timedelta(hours=1),
            )
        )
    assert (await c.get("/api/estatisticas/resumo", headers=h[0])).status_code == 401


async def test_erro_infra_sanitizado(ambiente_links, monkeypatch):
    c, _, _, h = ambiente_links

    async def falhar(*args):
        raise OperationalError("sql-interno", {}, Exception("conteudo-privado"))

    monkeypatch.setattr(RepositorioEstatisticasSQLAlchemy, "resumo", falhar)
    r = await c.get("/api/estatisticas/resumo", headers=h[0])
    assert r.status_code == 503 and r.headers["Cache-Control"] == "private, no-store"
    assert "sql-interno" not in r.text and "conteudo-privado" not in r.text


async def test_resumo_vazio_sem_links(ambiente_links, monkeypatch):
    c, _, _, h = ambiente_links
    monkeypatch.setattr(casos, "agora_utc", lambda: AGORA)
    r = await c.get("/api/estatisticas/resumo", headers=h[0])
    assert r.status_code == 200
    assert r.json()["links_ativos"] == r.json()["links_inativos"] == r.json()["total_acessos"] == 0
    assert all(d["acessos"] == 0 for d in r.json()["serie_diaria"])


async def test_utc_independe_do_fuso_da_sessao_postgresql(ambiente_links, monkeypatch):
    _, banco, _, _ = ambiente_links
    usuarios, links = await preparar(banco, monkeypatch)
    meia_noite = AGORA.replace(hour=0, minute=0)
    await eventos(banco, links[0], [meia_noite - timedelta(microseconds=1), meia_noite])
    async with banco.transacao() as s:
        await s.execute(text("SET LOCAL TIME ZONE 'Pacific/Honolulu'"))
        agregado = await RepositorioEstatisticasSQLAlchemy(s).por_link(
            links[0].id, usuarios[0].id, meia_noite - timedelta(days=1), AGORA
        )
        assert agregado.total == 2
        assert agregado.diarios == {meia_noite.date() - timedelta(days=1): 1, meia_noite.date(): 1}


async def test_volume_sintetico_e_plano_postgresql(ambiente_links, monkeypatch):
    _, banco, esquema, _ = ambiente_links
    usuarios, links = await preparar(banco, monkeypatch)
    inicio = AGORA.replace(hour=0, minute=0) - timedelta(days=89)
    async with banco.transacao() as s:
        await s.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await s.execute(
            text(
                "INSERT INTO eventos_acesso(id,link_id,acessado_em) "
                "SELECT gen_random_uuid(), :link, CAST(:inicio AS timestamptz) "
                "+ (n % 90) * interval '1 day' FROM generate_series(1,30000) AS n"
            ),
            {"link": links[0].id, "inicio": inicio},
        )
        await s.execute(text("ANALYZE eventos_acesso"))
    capturadas = []

    def capturar(conexao, cursor, instrucao, parametros, contexto, executemany):
        capturadas.append((instrucao, parametros))

    resultados = []
    for dias in [7, 90]:
        inicio_periodo = AGORA.replace(hour=0, minute=0) - timedelta(days=dias - 1)
        async with banco.transacao() as s:
            repo = RepositorioEstatisticasSQLAlchemy(s)
            capturadas.clear()
            event.listen(banco.motor.sync_engine, "before_cursor_execute", capturar)
            try:
                antes = perf_counter()
                resumo = await repo.resumo(usuarios[0].id, inicio_periodo, AGORA)
                duracao = (perf_counter() - antes) * 1000
            finally:
                event.remove(banco.motor.sync_engine, "before_cursor_execute", capturar)
            assert (
                len(capturadas) == 1
                and "GROUP BY" in capturadas[0][0]
                and "count(" in capturadas[0][0]
            )
            if dias == 90:
                assert resumo.acessos.total == 30000
            conexao = await s.connection()
            plano = (
                await conexao.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + capturadas[0][0], capturadas[0][1]
                )
            ).scalar_one()
            if isinstance(plano, str):
                plano = json.loads(plano)
            nos = []
            indices = []

            def percorrer(no, tipos, usados):
                tipos.append(no["Node Type"])
                if "Index Name" in no:
                    usados.append(no["Index Name"])
                for filho in no.get("Plans", []):
                    percorrer(filho, tipos, usados)

            percorrer(plano[0]["Plan"], nos, indices)
            resultados.append(
                {
                    "dias": dias,
                    "eventos_sinteticos": 30000,
                    "consultas_agregacao": 1,
                    "total": resumo.acessos.total,
                    "duracao_ms": round(duracao, 3),
                    "planejamento_ms": plano[0]["Planning Time"],
                    "execucao_plano_ms": plano[0]["Execution Time"],
                    "nos": nos,
                    "indices": indices,
                }
            )
    caminho = Path(__file__).parents[3] / "docs/relatorios/evidencias/fase6/desempenho6.3.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(
            {
                "ambiente": "PostgreSQL local isolado; dados sinteticos; "
                "sem garantia de capacidade produtiva",
                "medicoes": resultados,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
