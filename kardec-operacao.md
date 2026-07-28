# Dialogando com a Doutrina — cola de operação

Arquivo local, fora do repositório. Atualizado em 2026-07-27.

## Links

| o quê | onde |
|---|---|
| **API (produção)** | https://kardec-api-391789792183.us-central1.run.app |
| API (URL alternativa, mesma coisa) | https://kardec-api-nr56lnqb6q-uc.a.run.app |
| Passagem do dia, para testar no navegador | https://kardec-api-391789792183.us-central1.run.app/evangelho |
| **Frontend (Vercel)** | ⚠️ ainda não implantado — falta importar o repo com `Root Directory = frontend` |
| Repositório | https://github.com/marycamila184/kardec-study-assistant |

**Projeto GCP:** `dialogando-doutrina` (número 391789792183) · região `us-central1` · conta marycamilainfo@gmail.com

| console | link |
|---|---|
| Serviço | https://console.cloud.google.com/run/detail/us-central1/kardec-api/metrics?project=dialogando-doutrina |
| Logs | https://console.cloud.google.com/run/detail/us-central1/kardec-api/logs?project=dialogando-doutrina |
| Revisões | https://console.cloud.google.com/run/detail/us-central1/kardec-api/revisions?project=dialogando-doutrina |
| Segredos | https://console.cloud.google.com/security/secret-manager?project=dialogando-doutrina |
| Builds | https://console.cloud.google.com/cloud-build/builds?project=dialogando-doutrina |
| Faturamento | https://console.cloud.google.com/billing?project=dialogando-doutrina |

## Ver como o chat está se saindo

Só funciona depois de mergear a branch `logs_implementation` e redeployar.

```bash
# turnos onde não encontrei fonte nenhuma — o sinal mais útil de qualidade
gcloud logging read 'jsonPayload.event="chat_turn" AND jsonPayload.not_found=true' \
  --limit 20 --format='value(jsonPayload.question)'

# falhas de geração (provedor fora do ar, modelo indisponível)
gcloud logging read 'jsonPayload.event="chat_turn" AND jsonPayload.generation_failed=true' \
  --limit 20 --format='value(timestamp,jsonPayload.question)'

# perguntas recentes com a resposta, para ler qualidade
gcloud logging read 'jsonPayload.event="chat_turn"' --limit 10 \
  --format='value(jsonPayload.question,jsonPayload.answer)'

# turnos lentos (acima de 15s)
gcloud logging read 'jsonPayload.event="chat_turn" AND jsonPayload.latency_ms>15000' --limit 20

# quantos turnos entraram em crise — só data e hora, sem texto, por desenho
gcloud logging read 'jsonPayload.safety_level="crise"' --limit 50 --format='value(timestamp)'

# erros da aplicação
gcloud run services logs read kardec-api --region us-central1 --limit 50 | grep -i error

# acompanhar ao vivo
gcloud run services logs tail kardec-api --region us-central1
```

## Deploy

```bash
# 1. o índice precisa existir e estar limpo ANTES do build (ele é assado na imagem)
EMBEDDING_PROVIDER= uv run python -m src.ingestion.pipeline
uv run python -c "
import chromadb
for c in chromadb.PersistentClient(path='data/embeddings/').list_collections():
    print(c.name, c.count())
"   # esperado: kardec_docs 7327 — e mais nada

# 2. subir (o Cloud Build constrói o Dockerfile; não precisa de docker local)
gcloud run deploy kardec-api --source . --region us-central1

# 3. depois que a Vercel existir, liberar o CORS
gcloud run services update kardec-api --region us-central1 \
  --update-env-vars 'CORS_ALLOWED_ORIGINS=https://SEU-APP.vercel.app'
```

## Configuração atual do serviço

| | |
|---|---|
| min / max instâncias | 1 / 3 |
| concorrência | 20 |
| memória / CPU | 512Mi / 1 |
| CPU boost no arranque | ligado |
| variáveis | `LLM_PROVIDER=together`, `EMBEDDING_PROVIDER=openrouter`, `CHAT_MODEL`, `CONDENSER_MODEL` |
| segredos | `TOGETHER_API_KEY`, `OPENROUTER_API_KEY` (Secret Manager) |

**Por que `min-instances 1`:** sem ele o cold start medido foi **11,4s**. Custa ~US$7/mês (tarifa ociosa, US$0,0000025 por vCPU-segundo). Reverter: `--min-instances 0`.

**Por que `concurrency 20` e não 80:** as rotas são síncronas e esperam no LLM, ocupando uma thread do pool por requisição.

## Custos

| item | |
|---|---|
| Cloud Run | ~US$7/mês (instância acordada) |
| Artifact Registry | centavos |
| Vercel | grátis |
| Embeddings (OpenRouter) | frações de centavo |
| **Together (geração)** | **o gasto real, proporcional ao uso** |

⚠️ **Configurar teto de gasto no painel da Together.** É a rede de baixo, independente do rate limit da aplicação.

## Limites da aplicação

- **1000 palavras** por mensagem, somando pergunta e histórico → resposta acolhedora, sem chamar modelo
- **20 requisições por IP a cada 10 minutos** em `/chat` e `/study` → 429. Contador por instância, então com 3 instâncias o teto efetivo pode chegar a 3×
- **Crise tem precedência sobre o limite de tamanho** — mensagem longa com ideação recebe o CVV 188, nunca "sua mensagem é muito longa"

## Quando algo quebrar

| sintoma | causa provável |
|---|---|
| `/chat` responde `generation_failed` | provedor fora do ar ou modelo indisponível. Ver logs; já aconteceu com um `CHAT_MODEL` que a conta não servia |
| Build falha em `COPY data/embeddings/` | `.gcloudignore` ausente ou o índice não foi gerado |
| Frontend com erro de CORS | falta `CORS_ALLOWED_ORIGINS` com a URL da Vercel |
| Tudo lento na primeira requisição | cold start — só se `min-instances` voltar para 0 |

## Pendências

- [ ] Frontend na Vercel (`Root Directory = frontend`, `VITE_API_URL`)
- [ ] CORS depois da URL da Vercel
- [ ] Teto de gasto na Together
- [ ] Mergear `logs_implementation` e redeployar para o log começar a valer
- [ ] Texto de transparência + link do formulário do Drive
- [ ] Rotacionar as chaves usadas na sessão de 2026-07-27
- [ ] `git config user.email` com o endereço noreply do GitHub
