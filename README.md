# CrossLens Backend — Step 1 & 3

Questa repository contiene l'implementazione dei primi mattoni del backend di CrossLens:

- **Step 1 – Context Builder**: ingestione e normalizzazione della query iniziale, con estrazione di attori, organizzazioni,
  nazioni, categoria e *event signature* tramite OpenAI `o4-mini`.
- **Step 3 – Frame Cards**: estrazione dei contenuti dagli articoli trovati (Playwright + Firefox + Readability) e generazione delle
  frame card con il modello `o4-mini`.

## Requisiti

- Python 3.11+
- [Poetry](https://python-poetry.org/) oppure `pip`
- Chiave API OpenAI con accesso al modello `o4-mini`
- [Playwright](https://playwright.dev/python/) con browser **Firefox** installato (`playwright install firefox`) per l'estrazione reale degli articoli

## Variabili d'ambiente

| Variabile                   | Descrizione                                        |
|----------------------------|----------------------------------------------------|
| `CROSSLENS_OPENAI_API_KEY` | Chiave API OpenAI utilizzata dal backend           |
| `CROSSLENS_OPENAI_MODEL`   | (Opzionale) Modello da utilizzare, default `o4-mini` |

## Installazione rapida

```bash
poetry install  # oppure: pip install -e .
export CROSSLENS_OPENAI_API_KEY="sk-..."
playwright install firefox  # necessario per l'estrazione con Step 3
uvicorn backend.app.main:app --reload
```

Il server espone gli endpoint:

- `GET /health` — health check semplice.
- `POST /v1/context/build` — normalizza la query e restituisce il contesto estratto.
- `POST /v1/frames/analyze` — riceve i risultati di ricerca di Step 2 e genera le frame card per ogni articolo.

## Step 1 — Context Builder

### Esempio di richiesta

```http
POST /v1/context/build
Content-Type: application/json

{"query": "  Putin e Trump si incontrano per discutere dell'Ucraina  "}
```

### Risposta

```json
{
  "normalized_query": "Putin e Trump si incontrano per discutere dell'Ucraina",
  "nations_involved": ["RUS", "USA", "UKR"],
  "actors": ["Vladimir Putin", "Donald Trump"],
  "organizations": ["Kremlin", "Casa Bianca"],
  "topic_category": "geopolitica",
  "event_signature": "Summit Putin-Trump su Ucraina"
}
```

L'endpoint garantisce che la query venga ripulita (trim e deduplica degli spazi) e che il modello restituisca esclusivamente JSON
conforme allo schema richiesto.

## Step 3 — Frame Cards

### Esempio di richiesta

```json
{
  "event_signature": "Summit Putin-Trump su Ucraina",
  "per_country_results": [
    {
      "country": "USA",
      "items": [
        {
          "source": "NYTimes",
          "domain": "nytimes.com",
          "url": "https://www.nytimes.com/example",
          "title": "Trump e Putin cercano un accordo",
          "snippet": "I due leader si confrontano a porte chiuse..."
        }
      ]
    }
  ],
  "resolved_sources": [
    {"country": "USA", "source": "NYTimes", "orientation": "center-left ANTITRUMP"}
  ]
}
```

### Risposta

```json
{
  "event_signature": "Summit Putin-Trump su Ucraina",
  "frames": [
    {
      "country": "USA",
      "source": "NYTimes",
      "domain": "nytimes.com",
      "url": "https://www.nytimes.com/example",
      "title": "Trump e Putin cercano un accordo",
      "snippet": "I due leader si confrontano a porte chiuse...",
      "extracted_text": "...",
      "frame_card": {
        "tone": "analitico",
        "stance": "critico",
        "frame_label": "Occidente diffidente",
        "key_claims": ["Il Cremlino propone concessioni", "Washington resta cauta"],
        "evidence_level": "medio",
        "orientation_inherited": "center-left ANTITRUMP",
        "orientation_detected": "critico",
        "partial": false
      }
    }
  ]
}
```

Il campo `extracted_text` è valorizzato quando l'estrazione con Playwright va a buon fine. In caso di paywall o fallimento, il
sistema ricade su `title + snippet` e marca la frame card con `partial: true`.

L'estrazione utilizza Playwright in modalità headless con Firefox e l'algoritmo Readability per isolare il corpo dell'articolo.

## Testing

I test isolano il client OpenAI tramite *fake client* così da non effettuare chiamate reali durante la CI.

```bash
pytest tests/test_backend_api.py tests/test_context_service.py tests/test_frame_analysis_service.py
```

Per test end-to-end con il modello vero è sufficiente esportare la chiave API e inviare richieste al servizio FastAPI come mostrato
sopra. Per validare l'estrazione reale ricordarsi di installare Playwright e il browser Firefox.

## Step successivi

Questi due step rappresentano la base del flusso CrossLens. Gli endpoint successivi (ricerca Serper.dev, prompt builder/SSML,
orchetrazione TTS) verranno aggiunti iterativamente sopra questa struttura.
