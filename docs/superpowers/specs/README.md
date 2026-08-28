# Índice das specs

Dezenas de arquivos com nome de data não dizem o que existe. Este índice
agrupa por assunto, não por ordem cronológica, e marca o que **deixou de valer**
— uma decisão superada continua no repositório porque o raciocínio dela ainda
explica o estado atual, mas ler a spec sem saber que foi substituída leva a
implementar o que já foi desfeito.

Convenção de estado:

- **vale** — descreve o comportamento atual
- **superada** — substituída por outra decisão, com o link
- **declinada** — foi construída ou medida e recusada com base na evidência
- **pendente** — aprovada, ainda não implementada

Convenção de idioma: as specs a partir de 2026-07-28 são escritas em inglês,
junto com os comentários de código e os docs principais. As anteriores ficam
como foram escritas — são registro histórico, não documentação viva. Ver
[2026-07-28-english-code-and-docs-design](2026-07-28-english-code-and-docs-design.md).

---

## Fundamentos

| Spec | Assunto | Estado |
|---|---|---|
| [2026-06-20-ingestion-rag-api-design](2026-06-20-ingestion-rag-api-design.md) | As três camadas — ingestão, RAG e API — desenhadas de uma vez sobre o parsing pronto | vale |
| [2026-07-28-english-code-and-docs-design](2026-07-28-english-code-and-docs-design.md) | Comentários e docs principais em inglês; produto, prompts e este arquivo de specs continuam em português | pendente |

## Retrieval e fundamentação

| Spec | Assunto | Estado |
|---|---|---|
| [2026-07-01-embedding-model-switch-design](2026-07-01-embedding-model-switch-design.md) | Troca para `BAAI/bge-m3` e aumento do teto de chunk para 800 chars | vale |
| [2026-07-15-anchor-retrieval-and-nudge-fixes-design](2026-07-15-anchor-retrieval-and-nudge-fixes-design.md) | `blend_anchor`: o trecho em leitura enviesa a busca sem nunca entrar no prompt | vale |
| [2026-07-15-chapter-commentary-grounding-design](2026-07-15-chapter-commentary-grounding-design.md) | Comentário de capítulo como âncora doutrinária das passagens do Evangelho | vale |
| [2026-07-01-chapter-summaries-design](2026-07-01-chapter-summaries-design.md) | Resumos de capítulo curados para o card do trecho diário | vale |
| [2026-08-05-curadoria-trecho-e-trilhas-design](2026-08-05-curadoria-trecho-e-trilhas-design.md) | 23 passagens do trecho diário estavam cortadas antes do desfecho (que no Evangelho costuma ser a parte misericordiosa); os 44 passos das trilhas evangélicas apontavam para o versículo em vez do Kardec; Q.100 sobreviveu nas trilhas depois de sair do `obras.js` | vale |
| [2026-07-26-gemini-embedding-retrieval-eval-design](2026-07-26-gemini-embedding-retrieval-eval-design.md) | Quatro modelos de embedding medidos contra o bge-m3 | vale como medição — **nenhum bateu o bge-m3**; levou à via hospedada |
| [2026-08-03-parent-context-expansion-design](2026-08-03-parent-context-expansion-design.md) | O `/chat` expande cada chunk recuperado para o item inteiro antes do prompt; o chip continua mostrando o subchunk que venceu | **declinada** — construída e medida; as respostas mudam (cosseno 0.891), mas a groundedness no subconjunto-alvo faz −0.002 a 1.41× de prompt. `expand_to_item` fica `False` |

## Segurança e sensibilidade

| Spec | Assunto | Estado |
|---|---|---|
| [2026-07-15-sensitivity-tiering-design](2026-07-15-sensitivity-tiering-design.md) | Camadas `normal / abalo / crise`; o piso determinístico por palavra-chave só pode ser escalado, nunca baixado | vale — é a regra mais longa do CLAUDE.md |
| [2026-08-04-quote-check-false-positive-design](2026-08-04-quote-check-false-positive-design.md) | `_has_anchor` é binário: uma palavra conjugada ("dependa"→"depende") derruba a resposta inteira e o leitor ouve "não encontrei" com a passagem na tela. 5 retenções em 6 dias, nenhuma delas invenção | **proposta** — §3.2 travada até a medição de §4 existir |
| [2026-07-26-desligar-reflexivo-design](2026-07-26-desligar-reflexivo-design.md) | Desliga o Refletir **preservando** o piso de crise, movido para módulo próprio | vale |

## Conversa: modos, orquestração e tom

| Spec | Assunto | Estado |
|---|---|---|
| [2026-06-22-estudar-obra-design](2026-06-22-estudar-obra-design.md) | Modo 1 — Estudar uma Obra | vale |
| [2026-06-22-abrir-evangelho-design](2026-06-22-abrir-evangelho-design.md) | Modo 4 — trecho diário determinístico, sem LLM | vale |
| [2026-06-30-chat-tone-and-source-citations-design](2026-06-30-chat-tone-and-source-citations-design.md) | Tom do `/chat` e citações clicáveis | vale |
| [2026-07-05-followup-question-chips-design](2026-07-05-followup-question-chips-design.md) | Chips de seguimento via marcador `[SEGUIR]` | vale |
| [2026-07-05-conversation-flow-batch-a-design](2026-07-05-conversation-flow-batch-a-design.md) | Lote de correções de qualidade no backend da conversa | vale |
| [2026-07-09-mode-orchestrator-design](2026-07-09-mode-orchestrator-design.md) | Classificador de intenção que sugere trocar de modo, sem destruir o turno | vale — o alvo `refletir` está desconectado |
| [2026-07-27-streaming-design](2026-07-27-streaming-design.md) | `POST /chat/stream` por SSE e a janela de retenção dos marcadores | vale |
| [2026-07-28-study-trecho-streaming-design](2026-07-28-study-trecho-streaming-design.md) | Estende o stream ao `/study` (lendo o `contexto` do JSON incrementalmente) e ao trecho diário | vale |
| [2026-07-28-adaptive-response-profile-design](2026-07-28-adaptive-response-profile-design.md) | **Guarda-chuva** — a forma da resposta deixa de ser propriedade da rota; eixos fluidos ajustados pela conversa, fundamentação sempre constante | pendente |
| [2026-07-28-profile-seam-design](2026-07-28-profile-seam-design.md) | Etapa 1 do guarda-chuva — a costura do profile, refactor puro e invisível | pendente |
| [2026-07-28-grounding-markers-design](2026-07-28-grounding-markers-design.md) | Etapa 2 do guarda-chuva — os dois vocabulários de marcador (`[fonte N]` no `/chat`, `[item N]` no `/study`); o modelo marca **onde**, o código resolve **o quê** | vale |

## Modelos e provedores

| Spec | Assunto | Estado |
|---|---|---|
| [2026-07-20-llm-provider-switch-and-structured-output-design](2026-07-20-llm-provider-switch-and-structured-output-design.md) | `LLM_PROVIDER` por env e saída JSON estruturada | vale |
| [2026-07-24-riv-ai-prose-generator-design](2026-07-24-riv-ai-prose-generator-design.md) | `riv-ai-v2` como gerador de prosa | **declinada** na evidência (2026-07-25); maquinário mantido dormente |
| [2026-07-26-gemini-vs-llama-generator-design](2026-07-26-gemini-vs-llama-generator-design.md) | A/B `gemini-3.6-flash` × llama 70B | vale como medição — empate técnico em fundamentação |

## Deploy e operação

| Spec | Assunto | Estado |
|---|---|---|
| [2026-07-27-deploy-cloud-run-vercel-design](2026-07-27-deploy-cloud-run-vercel-design.md) | Backend no Cloud Run (US), frontend na Vercel — a região segue os provedores, não o usuário | vale |
| [2026-07-27-embedding-hospedado-design](2026-07-27-embedding-hospedado-design.md) | Tira o bge-m3 do processo: mesmo modelo por HTTP, ~4,7 GB a menos na imagem | vale |
| [2026-07-27-limites-de-abuso-design](2026-07-27-limites-de-abuso-design.md) | Teto de tamanho e rate limit por IP — a crise sempre passa na frente do teto | vale |
| [2026-07-27-log-de-conversas-design](2026-07-27-log-de-conversas-design.md) | Log anônimo por turno, um registro no fim, para avaliar qualidade | vale — vira o piso da spec abaixo |
| [2026-07-28-log-de-sessao-e-feedback-design](2026-07-28-log-de-sessao-e-feedback-design.md) | `session_id` sob consentimento opt-in, chunks recuperados no log, joinha/negativo, sink para BigQuery | vale |
| [2026-07-29-citacao-inline-clicavel-design](2026-07-29-citacao-inline-clicavel-design.md) | A referência vira link no ponto da frase; os chips passam a mostrar só o que não foi citado | vale |

## Frontend e UX

| Spec | Assunto | Estado |
|---|---|---|
| [2026-06-22-learning-paths-redesign](2026-06-22-learning-paths-redesign.md) | Trilhas: 2 percursos × 3 níveis, e o schema para itens do Evangelho por capítulo | vale |
| [2026-06-30-related-items-modal-design](2026-06-30-related-items-modal-design.md) | Relacionados como modal, não como mensagem sintética no chat | vale |
| [2026-07-01-five-ux-polish-items-design](2026-07-01-five-ux-polish-items-design.md) | Cinco ajustes independentes vindos do uso real | vale, **menos o item 5** (feedback e clique do lembrete) — o lembrete foi desligado, ver [2026-08-05-desligar-lembrete-design](2026-08-05-desligar-lembrete-design.md) |
| [2026-08-05-desligar-lembrete-design](2026-08-05-desligar-lembrete-design.md) | O lembrete diário é um `setInterval` dentro da página: só dispara com a aba aberta e em primeiro plano, e no iOS fora da tela de início nem existe. Desligado — código comentado, não apagado. Voltar exige Web Push, que é decisão de armazenamento e de privacidade antes de ser código | vale |
| [2026-07-01-guided-trilha-polish-and-explicador-depth-design](2026-07-01-guided-trilha-polish-and-explicador-depth-design.md) | Vazamento de notas de rodapé no texto exibido + profundidade do Explicador | vale |
| [2026-07-01-ux-polish-and-reflect-identity-design](2026-07-01-ux-polish-and-reflect-identity-design.md) | Cinco problemas de UX, incluindo o tempo de revelação do texto | parcialmente superada — a revelação agora vem do stream ([streaming](2026-07-27-streaming-design.md)) |
| [2026-07-02-guided-followup-buttons-design](2026-07-02-guided-followup-buttons-design.md) | O seguimento em texto livre passa a carregar o item em estudo | vale |
| [2026-07-02-sidebar-only-favorites-design](2026-07-02-sidebar-only-favorites-design.md) | Um só mecanismo de favoritar, na barra lateral | vale |
| [2026-07-05-card-footer-action-design](2026-07-05-card-footer-action-design.md) | Ações entre modos no rodapé do card | vale |
| [2026-07-05-study-handoff-frontend-design](2026-07-05-study-handoff-frontend-design.md) | O frontend abre o `/study` já preenchido a partir do `suggested_item_number` | vale |
| [2026-07-09-trilha-progress-states-design](2026-07-09-trilha-progress-states-design.md) | Retomar uma trilha de onde parou | vale |
| [2026-07-26-onboarding-single-screen-design](2026-07-26-onboarding-single-screen-design.md) | Onboarding de duas telas para uma | vale |
| [2026-07-25-history-first-navigation-design](2026-07-25-history-first-navigation-design.md) | Navegação a partir do histórico + lançador na home | **pendente** |
| [2026-08-04-discovery-and-about-page-design](2026-08-04-discovery-and-about-page-design.md) | Meta tags sociais, `preview.png`, a página `/sobre/` estática — que absorve a apresentação do Onboarding — robots e sitemap. Adiou explicitamente as páginas por tema, hoje em [2026-08-08](2026-08-08-static-discovery-pages-design.md) | vale — mas a barra final em `/sobre/` é forma canônica, **não** requisito: medido em 2026-08-05, `/sobre` e `/sobre/` devolvem os dois a página |
| [2026-08-08-static-discovery-pages-design](2026-08-08-static-discovery-pages-design.md) | Páginas estáticas por tema e por trilha, geradas do corpus committado: sem prosa de LLM, por isso escapam da objeção que adiou o trabalho em 2026-08-04. Inclui o deep link `/?book=…&item=…&part=…`, que hoje não existe — a SPA não lê URL nenhuma | **pendente** |
| [2026-08-05-trecho-no-dialogar-mobile-design](2026-08-05-trecho-no-dialogar-mobile-design.md) | No celular o trecho do dia só existe na home e não há caminho de volta para ela: o card volta na tela vazia do Dialogar, extraído em `TrechoCard` para não haver duas cópias | **superada** no mesmo dia por [2026-08-05-trecho-no-menu-design](2026-08-05-trecho-no-menu-design.md) — a extração do `TrechoCard` continua valendo |
| [2026-08-05-trecho-no-menu-design](2026-08-05-trecho-no-menu-design.md) | O trecho do dia vira a terceira aba do `MobileBottomNav`; no desktop fica só o card da home. A antiga aba "Hoje" caiu porque `isActive` era sempre falso — agora `convoId` começa com `trecho_`, o que dá o estado que faltava (e obriga a apagar Dúvida enquanto ela acende) | vale |
| [2026-08-27-pwa-instalavel-design](2026-08-27-pwa-instalavel-design.md) | Ícone na tela de início: manifest, ícones e favicon (que não existia). **Sem service worker** — medido, os assets `_astro` já são `immutable` por um ano, então não há o que acelerar, e a falha característica dele é fixar versão velha em silêncio. O lembrete fica de fora de propósito: é [2026-08-05](2026-08-05-desligar-lembrete-design.md), decidida por privacidade, e a ordem não custa nada porque no iOS o push só existe para app já instalado | vale |

## Refletir — modo desligado

Todo este bloco descreve um modo que **não está roteado** em produção. O código
está desconectado, não apagado. A decisão e o motivo estão em
[2026-07-26-desligar-reflexivo-design](2026-07-26-desligar-reflexivo-design.md);
o piso de crise **não** saiu junto — virou `src/rag/crisis.py`, compartilhado.

| Spec | Assunto | Estado |
|---|---|---|
| [2026-06-22-refletir-situacao-design](2026-06-22-refletir-situacao-design.md) | Modo 3 — Refletir sobre uma Situação | superada por [desligar-reflexivo](2026-07-26-desligar-reflexivo-design.md) |
| [2026-07-02-guided-reflection-buttons-design](2026-07-02-guided-reflection-buttons-design.md) | Reflexão guiada só por botões, sem texto livre | superada por [desligar-reflexivo](2026-07-26-desligar-reflexivo-design.md) |
| [2026-07-02-refletir-more-situations-design](2026-07-02-refletir-more-situations-design.md) | De 4 para 8 situações iniciais | superada por [desligar-reflexivo](2026-07-26-desligar-reflexivo-design.md) |
| [2026-07-19-reflect-book-allowlist-design](2026-07-19-reflect-book-allowlist-design.md) | Lista de obras permitidas no Refletir | superada por [desligar-reflexivo](2026-07-26-desligar-reflexivo-design.md) |
