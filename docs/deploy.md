# Deploy — backend no Cloud Run, frontend na Vercel

Desenho e justificativas em
`docs/superpowers/specs/2026-07-27-deploy-cloud-run-vercel-design.md`.
Aqui ficam só os comandos, na ordem em que funcionam.

**Serviço no ar:** `https://kardec-api-391789792183.us-central1.run.app`
(projeto `dialogando-doutrina`, região `us-central1`).

## Duas armadilhas que já custaram um deploy cada

**1. `.gcloudignore` é obrigatório.** Sem ele o gcloud usa o `.gitignore` como
substituto — e `data/embeddings/` é gitignorado por ser regenerável. O build
falha em `COPY data/embeddings/`. Pior: ao criar o arquivo, tudo que o
`.gitignore` protegia precisa ser reexcluído à mão, **incluindo o `.env`**, que
senão sobe para o bucket de fontes do Cloud Build.

**2. Os padrões de modelo do provider não são os que você usa.** A primeira
revisão subiu sem `CHAT_MODEL` e todo `/chat` respondeu `generation_failed`
com 503 da Together, porque o padrão apontava para um modelo que a conta não
serve — enquanto local funcionava, já que o `.env` sobrescrevia. O padrão foi
corrigido em `config.py`, mas a lição fica: **o que o `.env` esconde, o deploy
revela.**

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
# Esperado: kardec_docs 7348 — e mais nada.
# (era 7327 até 2026-07-29, quando `_build_id` passou a incluir `part`: sem ele
#  os dois "CAPÍTULO I" de Céu e o Inferno colidiam e 20 trechos se sobrescreviam;
#  e 7347 até 2026-08-02, quando `_closes_a_sentence` parou de cortar frase em
#  abreviatura e o item 18 do cap. XIII de A Gênese ganhou um subchunk.)
```

Se aparecerem `kardec_docs_e5` ou `kardec_docs_gemini_*`, são lixo de avaliação
e não podem ir para a imagem:

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

O `cd frontend` acima não é só conveniência: `getStaticPaths()` em
`frontend/src/pages/trilhas/[slug].astro` ancora em `process.cwd()`, e só
resolve porque o build roda com esse cwd. Ver o comentário naquele arquivo
antes de mudar como o build é disparado (por exemplo, de um script na raiz
do monorepo).

Defina `PUBLIC_API_URL` com a URL do Cloud Run nas variáveis de ambiente do
projeto na Vercel (Settings → Environment Variables) e refaça o deploy. O
`frontend/src/services/api.js:3` já lê essa variável. O prefixo é
`PUBLIC_`, não `VITE_` — desde a migração para Astro só variáveis com esse
prefixo chegam ao cliente, e essa troca já custou um `localhost:8000` dentro
do bundle de produção em 2026-08-09; `scripts/check_api_base.mjs` existe por
causa disso.

`frontend/public/` vai junto com o build, sem configuração nenhuma: o
`preview.png`, o `robots.txt`, o `sitemap.xml` e a página estática
`sobre/index.html` chegam ao ar do jeito que estão no repositório — não
precisam de `vercel.json`.

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

Depois do deploy do frontend, nesta ordem — cada passo prova algo que o
anterior não prova:

1. `https://dialogandodoutrina.com.br/sobre/` devolve a página estática, não o
   app. É a única das três que o build local não consegue provar — só o
   servidor real resolve (ou não) a barra final.
2. O card de compartilhamento em `developers.facebook.com/tools/debug`, **antes**
   de mandar o link para qualquer pessoa — o WhatsApp cacheia a prévia com
   força, então um erro descoberto depois do primeiro envio é caro de corrigir.
3. Google Search Console: registrar a propriedade e submeter o
   `https://dialogandodoutrina.com.br/sitemap.xml`.

## Redeploy: o comando do passo 3 é para a PRIMEIRA vez

`--set-env-vars` **substitui o conjunto inteiro**. O serviço no ar hoje tem
`CHAT_MODEL`, `CONDENSER_MODEL` e `CORS_ALLOWED_ORIGINS`, que aquele comando não
lista — rodá-lo cru apaga os três, e perder `CHAT_MODEL` é exatamente a
armadilha nº 2 lá de cima (todo `/chat` em 503).

Num redeploy **manual**, omita os flags de env: o Cloud Run preserva a
configuração existente.

> **Isto já aconteceu, apesar de estar escrito aqui.** Em 2026-08-03 o job de
> deploy (`.github/workflows/deploy.yml`) rodava com
> `--set-env-vars 'LLM_PROVIDER=...,EMBEDDING_PROVIDER=...'` e apagou os três.
> `CHAT_MODEL` sobreviveu por acaso — o padrão do `config.py` já é o mesmo
> valor desde a armadilha nº 2. `CONDENSER_MODEL` caiu para o Qwen 7B sem
> ninguém ver. E `CORS_ALLOWED_ORIGINS` voltou ao padrão
> `http://localhost:5173`, o que **derrubou o site**: toda preflight do
> navegador virou `400 Disallowed CORS origin` e o frontend ficou preso em
> "Carregando trecho do dia…" — enquanto `/health`, `/evangelho`, `/paths` e
> `/chat` respondiam 200 no curl, porque curl não manda `Origin` nem obedece à
> resposta. O deploy foi reportado como verde.
>
> **Na CI a regra é a inversa da manual:** o job declara o conjunto **inteiro**,
> o que torna a substituição correta em vez de destrutiva, e o serviço no ar
> deixa de ser a fonte da verdade. Variável nova no serviço tem de entrar
> naquele arquivo também. Como o valor do CORS tem vírgulas, o separador vira
> `@` pelo prefixo `^@^`. E o job passou a fazer uma preflight de verdade
> depois de subir — o único lugar onde essa falha é observável, já que
> `TestClient` não emite preflight (ver o comentário do middleware em
> `src/api/main.py:13-16`).

```bash
gcloud run deploy kardec-api --source . --region us-central1 \
  --allow-unauthenticated --memory 512Mi --cpu 1 \
  --min-instances 0 --max-instances 3 --concurrency 20 --timeout 120
```

Para mudar **uma** variável sem tocar nas outras, `--update-env-vars`. Quando o
valor contém vírgula (o caso do CORS), o delimitador precisa ser trocado:

```bash
gcloud run services update kardec-api --region us-central1 \
  --update-env-vars '^@^CORS_ALLOWED_ORIGINS=https://kardec-study-assistant.vercel.app,https://dialogandodoutrina.com.br,https://www.dialogandodoutrina.com.br'
```

**Confira o tráfego depois de subir.** Em 2026-07-28 o serviço estava com o
tráfego preso numa revisão antiga e uma tag `probe` órfã: o deploy do dia
anterior tinha subido e nunca entrado no ar, servindo 0% — e a saída do gcloud
reporta a revisão *com tag*, não a que acabou de ser criada, o que faz a
confusão passar despercebida.

```bash
gcloud run services describe kardec-api --region us-central1 \
  --format='yaml(spec.traffic,status.latestReadyRevisionName)'
gcloud run services update-traffic kardec-api --region us-central1 --to-latest
```

### O Job do lembrete não se atualiza sozinho

`gcloud run jobs create` fixa a imagem no momento em que o Job é criado. Um
redeploy da API publica uma imagem nova e **não** mexe no Job: ele continua
rodando o código antigo, indefinidamente, sem erro nenhum. Depois de cada
redeploy que toque `src/push/`:

```bash
IMAGEM=$(gcloud run services describe kardec-api --region us-central1 \
  --format='value(spec.template.spec.containers[0].image)')
gcloud run jobs update kardec-push --region us-central1 --image "$IMAGEM"
```

## 7. Log de conversas: o sink para BigQuery

O stdout do container já vai para o Cloud Logging. O sink dá durabilidade além
dos 30 dias e uma linguagem de consulta melhor que o Logs Explorer. Nada no app
muda. Desenho em
`docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md`.

Faça **depois** de o backend novo estar no ar: um sink criado antes de as linhas
existirem produz uma tabela vazia e a impressão de que não funcionou.

```bash
PROJECT=dialogando-doutrina

# 31536000s = 12 meses, a retenção declarada na spec. Retenção exercida por
# configuração, não por inércia.
bq --location=us-central1 mk --dataset --default_table_expiration 31536000 \
  "${PROJECT}:kardec_logs"

gcloud logging sinks create kardec-conversas \
  "bigquery.googleapis.com/projects/${PROJECT}/datasets/kardec_logs" \
  --log-filter='resource.type="cloud_run_revision"
    AND resource.labels.service_name="kardec-api"
    AND (jsonPayload.event="chat_turn" OR jsonPayload.event="feedback")' \
  --use-partitioned-tables
```

**A armadilha:** o sink escreve com uma conta de serviço própria, criada junto
com ele, que **não nasce com permissão**. Sem o passo abaixo o sink existe,
aparenta estar certo e não escreve nada.

```bash
SINK_SA=$(gcloud logging sinks describe kardec-conversas --format='value(writerIdentity)')
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="$SINK_SA" --role=roles/bigquery.dataEditor
```

Verificação (o sink não é instantâneo; espere de 2 a 5 minutos):

```bash
API=$(gcloud run services describe kardec-api --region us-central1 --format='value(status.url)')
curl -s -X POST "$API/chat" -H 'Content-Type: application/json' \
  -H 'X-Session-Id: teste-do-sink' \
  -d '{"question":"o que é o perispírito?"}' > /dev/null

bq ls kardec_logs   # o nome da tabela varia com o tipo de log
bq query --use_legacy_sql=false \
  'SELECT jsonPayload.session_id, jsonPayload.mode, jsonPayload.question
   FROM `dialogando-doutrina.kardec_logs.run_googleapis_com_stdout`
   WHERE jsonPayload.session_id = "teste-do-sink"'
```

## Lembrete por push

Uma vez só, no projeto GCP que já roda a API.

```bash
# 1. Firestore em modo nativo, na mesma região do Cloud Run.
gcloud services enable firestore.googleapis.com
gcloud firestore databases create --location=us-central1 --type=firestore-native

# 2. Chaves VAPID. A pública vai para o build do frontend; a privada, para o
#    Secret Manager, pelo mesmo caminho das chaves de LLM.
#
# O formato importa e não é o mesmo dos dois lados: o navegador quer o ponto
# público não comprimido (65 bytes) em base64url, e o pywebpush quer o escalar
# privado (32 bytes) em base64url. As duas linhas abaixo produzem exatamente
# isso — foram executadas antes de entrarem aqui.
uv run python - <<'PY'
import base64
from py_vapid import Vapid01
from cryptography.hazmat.primitives import serialization

v = Vapid01()
v.generate_keys()

publica = base64.urlsafe_b64encode(
    v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
).decode().rstrip("=")

privada = base64.urlsafe_b64encode(
    v.private_key.private_numbers().private_value.to_bytes(32, "big")
).decode().rstrip("=")

print("PUBLIC  (PUBLIC_VAPID_KEY, na Vercel):", publica)
print("PRIVATE (vapid-private-key, no Secret Manager):", privada)
PY

printf '%s' 'A_CHAVE_PRIVADA' | gcloud secrets create vapid-private-key --data-file=-
gcloud secrets add-iam-policy-binding vapid-private-key \
  --member="serviceAccount:$(gcloud projects describe $(gcloud config get-value project) \
    --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

# 3. O Job: MESMA imagem da API, outro comando. Nenhuma superfície pública.
#
# A imagem é lida do serviço que está no ar em vez de escrita à mão: a API sobe
# com `--source .`, então quem escolhe o nome do repositório é o Cloud Build, e
# um caminho chutado aqui falha na hora de criar o Job.
IMAGEM=$(gcloud run services describe kardec-api --region us-central1 \
  --format='value(spec.template.spec.containers[0].image)')

# --max-retries 0: uma execução repetida manda o lembrete de novo. O dispatch
# não tem idempotência (isso exigiria um sexto campo no registro, recusado), e
# pular um tique de 15 minutos custa menos que uma notificação duplicada.
gcloud run jobs create kardec-push \
  --image "$IMAGEM" \
  --region us-central1 \
  --command /app/.venv/bin/python --args -m,src.push.dispatch \
  --max-retries 0 \
  --set-secrets 'VAPID_PRIVATE_KEY=vapid-private-key:latest' \
  --set-env-vars 'VAPID_PUBLIC_KEY=A_CHAVE_PUBLICA'

# Sem esta permissão o Scheduler recebe 403 a cada 15 minutos, em silêncio, e
# nenhum lembrete chega — com todo o resto aparentemente configurado.
CONTA="$(gcloud projects describe $(gcloud config get-value project) \
  --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

gcloud run jobs add-iam-policy-binding kardec-push \
  --region us-central1 \
  --member="serviceAccount:${CONTA}" \
  --role=roles/run.invoker

# 4. O Scheduler, de 15 em 15 minutos — o passo que cobre fusos de meia e de
#    quarto de hora.
gcloud scheduler jobs create http kardec-push-tick \
  --location us-central1 \
  --schedule '*/15 * * * *' \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$(gcloud config get-value project)/jobs/kardec-push:run" \
  --http-method POST \
  --oauth-service-account-email "${CONTA}"
```

E na Vercel, a variável de ambiente do frontend: **`PUBLIC_VAPID_KEY`** com a
chave pública. O prefixo é `PUBLIC_`, não `VITE_` — o Astro só expõe ao
cliente as variáveis com esse prefixo, e trocar isso foi o que gravou
`localhost:8000` dentro do bundle de produção em 2026-08-09.
