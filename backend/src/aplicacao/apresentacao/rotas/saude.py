from fastapi import APIRouter

roteador_saude = APIRouter(tags=["Saúde"])


@roteador_saude.get("/saude")
def consultar_saude() -> dict[str, str]:
    return {"situacao": "operacional"}
