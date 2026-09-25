# Gold Set e benchmark offline — v1

Gold Set e editorial_feedback são fontes distintas. Gold é anotação deliberada
"EU CORTARIA ESTE TRECHO"; feedback são decisões humanas de produção. Nada é
promovido automaticamente, e este módulo não consulta SQLite nem o produto.

## Formato e autoria

`schema.json` descreve o documento JSON: `schema_version: 1` e `gold_cuts`.
Cada entrada exige `gold_id`, `vod_id`, `campaign_id`, `creator`,
`expected_start`, `expected_end`, `would_clip: true`. São opcionais
`content_type`, `priority`, `notes` (textos não vazios) e `metadata` (objeto livre).
Use notes/metadata para autoria, justificativa e revisão, se necessário.
Não há enums editoriais impostos nem campanhas cadastradas pelo benchmark.

Tempos são números finitos em **segundos absolutos desde o início da VOD**,
não timestamps relativos ao chunk. Início >= 0, fim > início. IDs não vazios
são únicos dentro de cada documento (inclusive entre VODs). O validador Python
verifica essas relações; JSON Schema sozinho não compara campos nem garante
unicidade de um campo dentro do array. Campos desconhecidos são rejeitados:
extensões devem ficar em metadata. Arquivos UTF-8, inclusive com BOM, são aceitos.

Predictions usam documento `schema_version: 1`, `predictions: [...]`.
Cada entrada exige `prediction_id`, `vod_id`, `campaign_id`, `start`, `end`.
Aceita `creator` opcional e `metadata` arbitrária. A **ordem do array é o ranking**;
score em metadata não reordena nada. Intervalos iguais com IDs distintos são
permitidos para medir duplicatas. IDs duplicados são erro, nunca deduplicados silenciosamente.

Correspondências exigem o mesmo par exato `(campaign_id, vod_id)`.
Creator é informação de autoria/identificação, não chave de matching.
IDs não são normalizados: prepare os dois conjuntos usando os mesmos identificadores.
Prioridade do gold não altera pesos ou matching.

Os arquivos em `samples/` são **sintéticos**, derivados do exemplo de aceite.
Não comprovam qualidade editorial na produção. Para um gold real, o operador
deve assistir e anotar deliberadamente cada momento; use arquivos pequenos,
sem mídias, cookies, URLs assinadas, tokens ou dados privados. IDs e segundos
bastam para o benchmark. Metadata/notes são livres: revise seu conteúdo antes
de commit. Não se deve tratar toda aprovação antiga como ground truth.

## Execução local (PowerShell, raiz do projeto)

```powershell
.\.venv\Scripts\python.exe -m miner.benchmark --gold benchmarks/gold/samples/gold.json --predictions benchmarks/gold/samples/predictions.json
```

O único resultado é JSON em stdout. Para guardar, redirecione para **um novo
arquivo de relatório**, nunca para gold/predictions. Erros vão para stderr,
com saída 2. A CLI não escreve dados, não minera, não exporta e não cria servidor.

Configuração explícita:

```powershell
.\.venv\Scripts\python.exe -m miner.benchmark --gold benchmarks/gold/samples/gold.json --predictions benchmarks/gold/samples/predictions.json --iou-threshold 0.5 --boundary-tolerance 3 --top-k 3 5 10
```

API Python: `evaluate(gold_document, prediction_document, iou_threshold=0.5,
boundary_tolerance=3, top_k=(3, 5, 10), metadata_filter=None)`.
`temporal_metrics(g_start, g_end, p_start, p_end)` mede um par isolado.
Não há dependências externas: apenas biblioteca padrão Python.

## Matching ótimo, não guloso

1. Criar arestas apenas na mesma VOD/campanha com IoU >= threshold (inclusivo).
2. Maximizar quantidade de pares válidos 1:1.
3. Entre soluções dessa cardinalidade, maximizar **soma dos IoUs**.
4. Em empate, minimizar **soma dos boundary MAEs**.
5. Persistindo empate, escolher o conjunto de pares `(gold_id, prediction_id)`
   lexicograficamente menor por IDs (ordem de strings Python, sensível a maiúsculas).

Usa fluxo máximo de custo mínimo com caminhos aumentantes e Bellman-Ford na
rede residual. Associações anteriores podem ser desfeitas para atingir o ótimo.
Custos são tuplas lexicográficas; frações exatas da representação decimal de
entrada evitam epsilon/arredondamento decidir matches e empates. Um bit por
aresta implementa o último desempate. Só a saída converte métricas para float.
O matching global é independente da ordem recebida; Top-K respeita essa ordem.

Configuração: `0 < iou_threshold <= 1`; tolerância finita >= 0 segundos.
Threshold zero é inválido para não considerar intervalos sem interseção matches.
Top-K aceita inteiros positivos distintos. `top_k=()` na API desativa essa avaliação.
Tolerância **não é critério de detecção**: um trecho pode ser encontrado e ter
limites ruins. Não há quota, filtro editorial ou alteração do detector.

## Definição oficial das métricas

Para gold `[gs, ge]`, prediction `[ps, pe]`:

- `intersection = max(0, min(ge, pe) - max(gs, ps))`.
- `union = (ge-gs) + (pe-ps) - intersection` (não é o envelope temporal).
- `temporal_iou = intersection / union`.
- `start_error = abs(gs-ps)`, `end_error = abs(ge-pe)` (segundos).
- `boundary_mae = (start_error + end_error) / 2` por par.

Com G golds, P predictions e M pares do matching ótimo:

| Campo | Definição |
|---|---|
| gold_count / prediction_count / matched_count | G / P / M |
| recall | M / G |
| precision | M / P |
| false_positive_count | P - M |
| false_negative_count | G - M |
| mean_temporal_iou | Média de IoU somente nos M matches |
| mean_start_error / mean_end_error | Média dos erros de início/fim nos M matches |
| boundary_mae | Média dos MAEs nos M matches |
| boundary_start_within_tolerance_rate | Matches com start_error <= tolerância / M |
| boundary_end_within_tolerance_rate | Matches com end_error <= tolerância / M |
| boundary_both_within_tolerance_rate | Matches com ambos os erros <= tolerância / M |
| precision_at_k | Matches ótimos no prefixo de min(K,P) predictions / min(K,P) |

**Precision@K rematcheia cada prefixo independentemente.** Uma prediction tardia
melhor não pode retirar um acerto da primeira página. O denominador é a quantidade
real disponível, nunca K quando há menos de K. Exemplo: 1 acerto entre 2 predictions
resulta em Precision@10 = 1/2. Top-K é global na ordem do documento, não média por VOD.
São expostos também contagens/denominadores, configuração, pares, erros individuais,
IDs sem correspondência e ordem das predictions para auditoria.

Divisão por zero produz **null**, nunca NaN nem acerto artificial.
Gold vazio com predictions: precision=0, recall=null. Predictions vazias com gold:
precision=null, recall=0. Ambos vazios: ambos null. Sem matches, médias e taxas de
boundary são null. Precision@K sem predictions também é null.

O exemplo de aceite (70–115 contra 72–113) encontra 1 match: interseção 41 s,
união 45 s, IoU 0,911111..., erros 2 s/2 s, MAE 2 s. Precision/recall/Precision@3/5/10
são 1, limites dentro de 3 s. Isso responde ao exemplo; não mede um Miner real.

## Preparação para prioridade A

Predictions podem carregar `metadata: {"priority": "A"}`. A API aceita
`metadata_filter={"priority": "A"}` (igualdade por campo, AND); a CLI aceita
o mesmo objeto JSON em `--metadata-filter`. Filtro preserva a ordem relativa,
mantém todo o gold e informa `input_prediction_count` antes do filtro. Recall
então mede a cobertura do gold por esse subconjunto. Campos ausentes não passam.
Nenhuma prioridade é criada ou inferida. Não há classificação A/B/C no produto.

**Precisão temporal não é approval/publicable rate.** Essa taxa futura exige
julgamentos humanos explícitos de publicabilidade sobre candidatos A avaliados.
Filtrar predictions prepara a API, mas B1 não inventa esses julgamentos ou métricas.

## Limitações e custo

Um gold incompleto faz cortes bons não anotados aparecerem como falsos positivos.
Compare escopos iguais e anote de forma suficientemente completa antes de interpretar
precision como qualidade editorial; FN/FP aqui são relativos ao conjunto fornecido.
Métricas temporais não provam narrativa, direitos, qualidade visual ou publicabilidade.

O algoritmo foi escolhido para golds pequenos. Com V nós, E arestas e M matches,
custo aproximado O(M × V × E) por avaliação, mais construção O(G × P).
Top-K repete matching em prefixos (3, 5, 10 por padrão). Frações e desempate de E bits
têm custo adicional; o tamanho das arestas determina memória e tempo. Não é solução
para milhões de candidatos. Não amostra nem baixa mídia, e não exige GPU ou modelos.
Em bases grandes, medir desempenho antes de ampliar. B1 termina aqui; B2 e Trilha A
dependem de nova tarefa.
