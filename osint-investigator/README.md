# OSINT Investigador

Ferramenta de investigação de inteligência de fontes abertas para prevenção à lavagem de dinheiro e fraudes.

---

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando
- Git instalado
- Conexão com a internet

Verifique se o Docker está funcionando:
```bash
docker --version
docker compose version
```

---

## Instalação e execução

### 1. Clone o repositório

```bash
git clone -b claude/osint-discussion-vUYfq https://github.com/Eduselva/pld-aml-detector.git
cd pld-aml-detector/osint-investigator
```

### 2. Suba os serviços

```bash
docker compose up --build
```

Na primeira execução o build leva cerca de 3–5 minutos (download das dependências). Nas próximas vezes é instantâneo.

Aguarde até ver estas mensagens no terminal:

```
redis        | Ready to accept connections
backend      | Application startup complete.
celery-worker| celery@... ready.
frontend     | VITE ready in ...ms  ➜  Local: http://localhost:5173/
```

### 3. Acesse a ferramenta

Abra no navegador: **http://localhost:5173**

---

## Como usar

### Nova investigação

1. Clique em **"Nova Investigação"**
2. Selecione o tipo de documento: **CPF** ou **CNPJ**
3. Preencha o **nome completo**
4. Digite o **número do documento** (com ou sem formatação)
5. Informe o **e-mail** (opcional — reduz falsos positivos)
6. Clique em **"Iniciar Investigação"**

A ferramenta coleta dados em paralelo de todas as fontes e apresenta o dossiê em segundos.

### Interpretando o score de risco

| Score | Nível | Significado |
|-------|-------|-------------|
| 0 – 25 | 🟢 Baixo | Nenhum indicador relevante encontrado |
| 26 – 50 | 🟡 Médio | Sinais de atenção — recomenda-se aprofundamento |
| 51 – 75 | 🟠 Alto | Múltiplos indicadores — investigação recomendada |
| 76 – 100 | 🔴 Crítico | Correspondências graves (PEP, OFAC, mídias negativas) |

> **Regra de piso:** qualquer correspondência exata em listas PEP ou OFAC eleva o score mínimo para **Alto (51)**, independente das demais fontes.

---

## Fontes consultadas

| Fonte | O que verifica |
|-------|---------------|
| **BrasilAPI (CNPJ)** | Situação cadastral, sócios, data de abertura, atividade |
| **Mídias negativas** | Notícias com termos: fraude, lavagem, COAF, preso, golpe, estelionato |
| **Lista PEP** | Pessoas politicamente expostas (cargos públicos) |
| **Lista OFAC/SDN** | Sanções internacionais e financiamento ao terrorismo |
| **HaveIBeenPwned** | Vazamentos de dados associados ao e-mail informado |
| **LinkedIn** | Perfil profissional público |
| **Instagram** | Perfil público (possível exibição de patrimônio) |
| **Twitter / X** | Atividade pública e menções |
| **TikTok** | Canal público e conteúdo |

---

## Configuração opcional

Crie um arquivo `.env` dentro da pasta `osint-investigator/` para habilitar funcionalidades extras:

```env
# Chave do HaveIBeenPwned (aumenta o limite de consultas)
# Obtenha em: https://haveibeenpwned.com/API/Key
HIBP_API_KEY=sua_chave_aqui
```

Sem a chave, o HIBP ainda funciona com limite reduzido de requisições.

---

## Parar os serviços

```bash
# Parar (mantém os dados)
docker compose stop

# Parar e remover containers (mantém os dados no volume)
docker compose down

# Parar e apagar tudo (inclusive banco de dados)
docker compose down -v
```

---

## Deploy no Railway (URL pública)

Para ter a ferramenta acessível por uma URL pública sem instalar nada localmente:

### 1. Crie uma conta no Railway
Acesse **railway.app** e crie uma conta gratuita (pode usar o login do GitHub).

### 2. Novo projeto → Deploy from GitHub Repo
- Clique em **"New Project"**
- Selecione **"Deploy from GitHub Repo"**
- Autorize o Railway a acessar sua conta GitHub
- Selecione o repositório **`Eduselva/pld-aml-detector`**
- Em **"Root Directory"** coloque: `osint-investigator`
- O Railway vai detectar o `railway.toml` e usar o `Dockerfile.railway` automaticamente

### 3. Adicione o Redis
- No painel do projeto, clique em **"+ New"** → **"Database"** → **"Redis"**
- O Railway cria automaticamente a variável `REDIS_URL` no serviço

### 4. Configure as variáveis de ambiente
No serviço principal, vá em **"Variables"** e adicione:
```
DATABASE_URL=sqlite+aiosqlite:////app/data/osint.db
DATA_DIR=/app/data
```

Opcional (para mais consultas ao HIBP):
```
HIBP_API_KEY=sua_chave_aqui
```

**Recomendado — Google Custom Search (mídias negativas muito mais precisas):**
```
GOOGLE_SEARCH_API_KEY=sua_chave_aqui
GOOGLE_SEARCH_CX=seu_cx_aqui
```

Como obter:
1. Acesse **console.developers.google.com** → crie um projeto → ative "Custom Search API"
2. Em **Credentials** → crie uma API Key → copie como `GOOGLE_SEARCH_API_KEY`
3. Acesse **programmablesearchengine.google.com** → crie um buscador (marque "Search the entire web") → copie o **Search engine ID** como `GOOGLE_SEARCH_CX`

Plano gratuito: 100 buscas/dia (suficiente para uso moderado). Sem essa configuração, a ferramenta usa DuckDuckGo como fallback.

### 5. Gere a URL pública
- Vá em **"Settings"** → **"Networking"** → **"Generate Domain"**
- Pronto — a ferramenta estará acessível em `https://seu-projeto.up.railway.app`

### Custo estimado no Railway
- Plano gratuito: $5 de crédito/mês (suficiente para uso moderado)
- Redis: ~$0.01/hora enquanto ativo
- App: cobra por uso de CPU/memória

---

## Atualizar para a versão mais recente

```bash
git pull origin claude/osint-discussion-vUYfq
docker compose up --build
```

---

## Segurança e privacidade

- **Todos os dados ficam na sua máquina** — nenhuma informação é enviada a servidores externos, exceto as consultas às fontes OSINT (BrasilAPI, HIBP, etc.)
- O banco de dados SQLite é armazenado em volume Docker local
- Não exponha a porta `5173` ou `8000` para a internet sem autenticação
- Para uso em equipe, rode em rede interna com VPN

---

## Solução de problemas

**Porta já em uso:**
```bash
# Verificar o que está usando a porta 8000 ou 5173
lsof -i :8000
lsof -i :5173
```

**Backend não inicia:**
```bash
docker compose logs backend
```

**Worker Celery não processa:**
```bash
docker compose logs celery-worker
```

**Resetar tudo do zero:**
```bash
docker compose down -v
docker compose up --build
```
