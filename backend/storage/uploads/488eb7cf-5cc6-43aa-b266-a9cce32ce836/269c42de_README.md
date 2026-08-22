# NEXA AI

Plataforma de IA própria, especializada em programação e desenvolvimento de
software. Chat com histórico persistente, upload de arquivos de código,
análise segura de projetos `.zip`, análise de imagens (screenshots de erro,
diagramas) e integração com modelos locais via **Ollama**.

> ⚠️ **A NEXA AI não tem acesso ao seu computador.** Não existe agente local,
> não há acesso a filesystem, câmera, microfone ou execução de comandos. A
> única forma de a IA "ver" algo é através de upload manual feito pelo
> usuário na interface.

---

## 1. Visão geral

```
Frontend (HTML/CSS/JS) ──fetch──▶ Backend (FastAPI) ──HTTP──▶ Ollama (LLM local)
                                        │
                                        ▼
                                 SQLite (conversas, mensagens, arquivos)
```

- **Frontend**: HTML5 + CSS3 + JavaScript puro (sem framework/build step).
- **Backend**: Python + FastAPI, expõe a API REST e orquestra LLM, arquivos e banco.
- **Modelo**: Ollama, rodando local ou em um servidor próprio — não incluso na nuvem.
- **Banco**: SQLite por padrão (`DATABASE_URL` trocável para PostgreSQL).

## 2. Arquitetura e estrutura de pastas

```
nexa-ai/
├── frontend/
│   ├── index.html          # UI (sidebar, chat, composer)
│   ├── style.css           # tema escuro, responsivo
│   ├── app.js               # chamadas à API, upload, markdown, drag&drop
│   └── assets/
│
├── backend/
│   ├── main.py               # app FastAPI, CORS, tratamento global de erros
│   ├── config.py             # todas as configurações via .env
│   ├── database.py           # engine/sessão SQLAlchemy
│   ├── routes/
│   │   ├── health.py         # GET  /api/health
│   │   ├── chat.py           # POST /api/chat
│   │   ├── files.py          # POST /api/files/upload, GET/DELETE
│   │   └── conversations.py  # CRUD de conversas
│   ├── services/
│   │   ├── llm.py             # abstração LLMProvider + OllamaProvider
│   │   ├── vision.py          # análise de imagens (modelo multimodal)
│   │   ├── file_analyzer.py   # validação/leitura segura de arquivos
│   │   └── project_analyzer.py# extração segura de ZIP + resumo do projeto
│   ├── models/
│   │   ├── models.py          # Conversation, Message, UploadedFile (ORM)
│   │   └── schemas.py         # Pydantic (request/response)
│   └── requirements.txt
│
├── tests/                    # pytest (health, chat, conversas, uploads, ZIP)
├── storage/uploads/          # arquivos enviados pelos usuários (ignorado no git)
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### Fluxo de uma mensagem de chat
1. Frontend envia `POST /api/chat` com `{ message, conversation_id }`.
2. `routes/chat.py` carrega o histórico da conversa e o texto de todos os
   arquivos/ZIPs anexados a ela (até `MAX_CONTEXT_CHARS`).
3. Se houver imagens anexadas, usa `services/vision.py` (modelo multimodal);
   caso contrário, `services/llm.py` (texto).
4. A resposta é salva no banco e devolvida ao frontend.

### Fluxo de upload
1. Frontend envia `POST /api/files/upload?conversation_id=...` (multipart).
2. `services/file_analyzer.py` sanitiza o nome, valida extensão/tamanho.
3. Se for `.zip`, `services/project_analyzer.py` extrai em diretório
   temporário isolado, valida cada entrada (ZIP Slip, profundidade, tamanho
   descompactado) e gera um resumo do projeto (linguagens, arquivos-chave,
   estrutura), salvo ao lado do ZIP para ser reaproveitado no chat.
4. O diretório temporário de extração é sempre removido ao final.

### Segurança
- Whitelist de extensões; `.exe/.bat/.cmd/.dll/...` são sempre bloqueados.
- Nomes de arquivo sanitizados (sem path traversal).
- Limites configuráveis de tamanho de arquivo, tamanho de ZIP, nº de arquivos
  no ZIP, profundidade de diretórios e tamanho descompactado (proteção
  básica contra zip bomb).
- Nenhum arquivo enviado é executado, nunca.
- Exceções nunca vazam stack trace para o cliente — apenas uma mensagem
  amigável (o detalhe completo vai para o log do servidor).
- CORS restrito às origens definidas em `CORS_ORIGINS`.
- Segredos apenas via `.env` — nunca no frontend.

## 3. Instalação

### Pré-requisitos
- Python 3.11+
- [Ollama](https://ollama.com) instalado
- (opcional) Docker + Docker Compose

### 3.1 Configurar o Ollama
```bash
# instale um modelo de texto (exemplos)
ollama pull qwen2.5-coder:7b

# opcional: modelo com suporte a imagens
ollama pull llava:7b
```

Copie `.env.example` para `.env` e preencha:
```
OLLAMA_MODEL=qwen2.5-coder:7b
VISION_MODEL=llava:7b
```

### 3.2 Windows

```powershell
cd nexa-ai
copy .env.example .env
notepad .env   # preencha OLLAMA_MODEL

cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Em outro terminal, sirva o frontend (qualquer servidor estático serve):
```powershell
cd nexa-ai\frontend
python -m http.server 5500
```

Abra `http://localhost:5500`.

### 3.3 Linux / macOS

```bash
cd nexa-ai
cp .env.example .env
nano .env   # preencha OLLAMA_MODEL

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Em outro terminal:
```bash
cd nexa-ai/frontend
python3 -m http.server 5500
```

Abra `http://localhost:5500`.

### 3.4 Docker

```bash
cp .env.example .env
# edite .env e preencha OLLAMA_MODEL
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5500`

Se o Ollama roda no seu host (fora do container), no Linux ajuste no `.env`:
```
OLLAMA_BASE_URL=http://172.17.0.1:11434
```
(No Windows/Mac, `host.docker.internal` já funciona por padrão — o
`docker-compose.yml` já mapeia isso.)

## 4. Uso

1. Abra o frontend, clique em **+ Nova conversa**.
2. Digite uma mensagem ou anexe arquivos (📎 ou arraste e solte).
3. Envie um `.zip` de projeto para que a IA entenda a estrutura completa.
4. Envie um screenshot de erro — funciona se `VISION_MODEL` estiver configurado.
5. Use **Exportar** para baixar os blocos de código gerados na conversa atual.

## 5. Testes

```bash
cd nexa-ai
pip install -r backend/requirements.txt -r tests/requirements-test.txt
python -m pytest tests/ -v
```

Cobre: health check, criação/consulta/remoção de conversas, chat (incluindo
Ollama offline/modelo ausente → erro amigável), upload de arquivos válidos e
bloqueados, e proteção contra ZIP Slip / ZIP inválido.

## 6. Deploy

- **Frontend**: hospede a pasta `frontend/` em Cloudflare Pages, Vercel ou
  GitHub Pages (é estático). Configure `window.NEXA_API_BASE_URL` no
  `index.html` (ou via variável de build) apontando para o backend.
- **Backend**: qualquer serviço compatível com FastAPI/Uvicorn (Railway,
  Render, Fly.io, VPS próprio). Ele respeita a variável de ambiente `PORT`
  fornecida pela plataforma.
- **Modelo (Ollama)**: **não** tente rodar um LLM local em planos gratuitos
  de hospedagem — eles normalmente não têm RAM/CPU/GPU suficientes. Rode o
  Ollama na sua máquina, em um servidor próprio com GPU, ou em um provedor
  de LLM auto-hospedado, e aponte `OLLAMA_BASE_URL` do backend para lá.

Arquitetura recomendada em produção: **frontend na nuvem** + **backend em
outro serviço** + **Ollama rodando localmente ou em servidor dedicado**.

## 7. Limitações conhecidas

- Sem autenticação/multiusuário nesta versão (é um projeto single-user).
- Sem rate limiting ativo (a estrutura permite adicionar facilmente com
  `slowapi`, por exemplo).
- Contexto de arquivos é truncado por `MAX_CONTEXT_CHARS` — projetos muito
  grandes não cabem inteiros no contexto do modelo.

## 8. Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| "Não foi possível conectar ao modelo configurado" | Ollama não está rodando | `ollama serve` ou abra o app do Ollama |
| "Nenhum modelo Ollama configurado" | `.env` sem `OLLAMA_MODEL` | Preencha e reinicie o backend |
| "modelo não foi encontrado" | Modelo não baixado | `ollama pull <nome-do-modelo>` |
| Erro de CORS no navegador | Origem do frontend não está em `CORS_ORIGINS` | Adicione a URL ao `.env` |
| Upload rejeitado | Extensão não suportada ou tamanho acima do limite | Veja `ALLOWED_EXTENSIONS`/`MAX_UPLOAD_SIZE_MB` em `config.py`/`.env` |
