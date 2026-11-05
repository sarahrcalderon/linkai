# Linkai

Monorepositório com backend FastAPI e frontend React, TypeScript e Tailwind CSS.

## Requisitos

- Python 3.12+
- Node.js 22+

## Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn aplicacao.principal:app --reload
pytest
ruff check .
ruff format --check .
```

API: http://localhost:8000/api/saude

## Frontend

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test
npm run build
```

Site: http://localhost:5173

## Segurança e escopo

Esta fase implementa apenas a fundação, um endpoint de saúde e a interface inicial. Cadastro, login, e-mails, links e métricas serão implementados nas próximas fases. Nenhuma credencial deve ser versionada.

## Commits sugeridos

1. `chore: criar estrutura inicial do monorepositorio`
2. `feat: adicionar api e endpoint de saude`
3. `feat: adicionar interface inicial responsiva`
4. `test: configurar verificacoes de qualidade`

Execute e valide cada etapa antes de registrar o commit. Os arquivos deste pacote não foram commitados automaticamente.
