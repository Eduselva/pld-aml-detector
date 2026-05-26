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
