# JurisShift

JurisShift é um protótipo de análise de jurisprudência portuguesa focado em identificar posições divergentes, mostrar a sua evolução no tempo e ligar cada conclusão à evidência textual dos acórdãos analisados.

Aplicação online: https://jurisshift-production.up.railway.app/

## Stack

- FastAPI
- SQLite + FTS5
- React + TypeScript + Vite
- GPT-5.6 Luna
- Docker
- Railway

## Como correr com Docker

### 1. Clonar o projeto

```bash
git clone https://github.com/davidvieira51756-code/JurisShift.git
cd JurisShift
```

### 2. Criar `.env` na raiz

```env
OPENAI_API_KEY=coloque_a_sua_chave_aqui
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.6-luna
```

### 3. Construir a imagem

```bash
docker build -t jurisshift .
```

### 4. Iniciar

```bash
docker run --rm --name jurisshift -p 8000:8000 --env-file .env jurisshift
```

Abrir:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/api/health
```

## Como correr sem Docker

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

### Frontend

Noutro terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## Notas

- A base de dados SQLite com o corpus analisado está em `data/jurisshift.db`.
- O chatbot responde apenas com base no corpus da questão selecionada.
- Casos sem evidência suficientemente robusta ficam marcados para revisão e não sustentam automaticamente uma divergência.
- O corpus é delimitado e não pretende representar toda a jurisprudência portuguesa.
