# Deploy — backend no Cloud Run, frontend na Vercel

Desenho e justificativas em
`docs/superpowers/specs/2026-07-27-deploy-cloud-run-vercel-design.md`.
Aqui ficam só os comandos, na ordem em que funcionam.

## 0. Antes de tudo: o índice

O container leva `data/embeddings/` assado dentro dele, então o índice precisa
existir e estar limpo **antes** do build.

```bash
# Reingerir com o modelo local: de graça, e a paridade medida em 2026-07-27
# (cosseno 0.999994) garante que consultas hospedadas batem neste índice.
# O EMBEDDING_PROVIDER vazio é obrigatório — sem ele a ingestão vai pela rede.
EMBEDDING_PROVIDER= uv run python -m src.ingestion.pipeline

# Confira que só a coleção de produção existe:
uv run python -c "
import chromadb
for c in chromadb.PersistentClient(path='data/embeddings/').list_collections():
    print(c.name, c.count())
"
# Esperado: kardec_docs 7327 — e mais nada.
```

Se aparecerem `kardec_docs_e5` ou `kardec_docs_gemini_*`, elas são lixo de
avaliação e não podem ir para a imagem:

```bash
uv run python -m scripts.build_production_index --out data/embeddings-prod
# depois aponte o Dockerfile/COPY para data/embeddings-prod, ou renomeie
```

## 1. gcloud: projeto e APIs

```bash
# Instale o SDK: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project SEU_PROJECT_ID      # o do número 391789792183
gcloud config set run/region us-central1

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

## 2. Segredos

Chave em `--set-env-vars` fica no histórico do shell e na descrição do serviço.
Vai para o Secret Manager.

```bash
printf '%s' 'SUA_TOGETHER_KEY'   | gcloud secrets create together-api-key   --data-file=-
printf '%s' 'SUA_OPENROUTER_KEY' | gcloud secrets create openrouter-api-key --data-file=-

# A conta de serviço padrão do Cloud Run precisa ler os segredos:
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
for S in together-api-key openrouter-api-key; do
  gcloud secrets add-iam-policy-binding $S \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
done
```

## 3. Backend

`--source .` faz o Cloud Build construir o `Dockerfile` do repositório — não
precisa de docker instalado na sua máquina.

```bash
gcloud run deploy kardec-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --concurrency 20 \
  --timeout 120 \
  --set-env-vars 'LLM_PROVIDER=together,EMBEDDING_PROVIDER=openrouter' \
  --set-secrets 'TOGETHER_API_KEY=together-api-key:latest,OPENROUTER_API_KEY=openrouter-api-key:latest'
```

Por que esses números:

- `--min-instances 0` é a escala a zero que torna a conta ~US$0. O preço é o
  cold start; meça antes de decidir pagar por 1 instância acordada.
- `--max-instances 3` é freio de gasto, não de capacidade. Sem teto, um pico
  (ou um loop) vira fatura.
- `--concurrency 20`, não os 80 do padrão: as rotas são síncronas e esperam em
  LLM, então cada requisição ocupa uma thread do pool. 80 requisições
  simultâneas numa instância enfileiram no threadpool e estouram o timeout.
- `--memory 512Mi` só é possível porque torch saiu da imagem.

Pegue a URL:

```bash
gcloud run services describe kardec-api --region us-central1 --format='value(status.url)'
curl -s "$(gcloud run services describe kardec-api --region us-central1 --format='value(status.url)')/health"
```

## 4. Frontend

```bash
cd frontend
npx vercel --prod        # a primeira vez pergunta o projeto e cria
```

Defina `VITE_API_URL` com a URL do Cloud Run nas variáveis de ambiente do
projeto na Vercel (Settings → Environment Variables) e refaça o deploy. O
`frontend/src/services/api.js:3` já lê essa variável.

## 5. A segunda ida: CORS

O backend precisa saber a URL da Vercel, que só existe depois do passo 4.

```bash
gcloud run services update kardec-api \
  --region us-central1 \
  --update-env-vars 'CORS_ALLOWED_ORIGINS=https://SEU-APP.vercel.app'
```

## 6. Verificação

```bash
API=$(gcloud run services describe kardec-api --region us-central1 --format='value(status.url)')

curl -s "$API/health"                    # {"status":"ok"}
curl -s "$API/evangelho" | head -c 200   # passagem do dia (prova que o markdown foi copiado)
curl -s "$API/paths" | head -c 200       # trilhas (prova data/paths)
curl -s -X POST "$API/chat" -H 'Content-Type: application/json' \
  -d '{"question":"o que é o perispírito?"}' | head -c 400
```

O `/chat` funcionando é a prova de que a via de embedding hospedada é a única em
produção: não existe torch nessa imagem para a via local usar.

Meça o cold start (primeira requisição depois de ~15 min parado):

```bash
curl -s -o /dev/null -w 'cold start: %{time_total}s\n' "$API/health"
```

Se doer, `--min-instances 1` resolve — mas aí a conta deixa de ser ~US$0, então
é decisão com número na mão, não por precaução.
