# Podcastfy Gemini Flash Boilerplate

Un boilerplate full-stack pronto all'uso per testare Podcastfy con FastAPI e Next.js.
L'applicazione riceve una lista di link, usa Playwright con Firefox per estrarre i testi e genera tracce audio con il modello **Gemini 2.5 Flash Preview TTS**.
Il frontend Next.js mostra i risultati e permette l'ascolto degli MP3 generati.

## Architettura

```
frontend/  → Next.js 14 (React) per l'interfaccia utente
backend/   → FastAPI + Playwright + Podcastfy TTS (Gemini Flash)
podcastfy/ → Modulo Python con i provider TTS e le utility originali
```

## Requisiti

- Python 3.11+
- Node.js 18+
- Playwright con browser Firefox (`playwright install firefox`)
- `ffmpeg` installato nel sistema (richiesto da `pydub`)
- Chiave API Gemini impostata nella variabile d'ambiente `PODCASTFY_GEMINI_API_KEY`

## Setup Backend

```bash
# Installa le dipendenze Python (Poetry o pip)
poetry install
# oppure
pip install -e .

# Installa Playwright con Firefox
playwright install firefox

# Avvia il server FastAPI
PODCASTFY_GEMINI_API_KEY="<la-tua-chiave>" uvicorn backend.app.main:app --reload
```

Endpoint principali:
- `POST /api/generate` → accetta `{ "links": ["https://..." ] }` e restituisce gli MP3 generati
- `GET /health` → health check semplice
- `/static/*` → file audio generati

## Setup Frontend

```bash
cd frontend
npm install
npm run dev
```

Per puntare l'interfaccia ad un backend remoto imposta `NEXT_PUBLIC_API_URL` prima di avviare Next.js.
Di default l'app usa `http://localhost:8000`.

## Flusso di utilizzo

1. Incolla fino a dieci URL nell'interfaccia Next.js e invia il form.
2. Il backend visita ogni link con Playwright (Firefox) ed estrae titolo e testo principale.
3. Il testo viene trasformato in uno script Q/A e convertito in audio via Gemini Flash TTS.
4. Il frontend mostra titolo, riassunto e player audio per ogni link elaborato.

## Personalizzazione

- Modifica le voci o i parametri di Gemini in `backend/app/services.py` nella sezione `provider_config`.
- Cambia lo stile dell'interfaccia aggiornando `frontend/app/globals.css`.
- Aggiorna gli allowed origins dell'API in `backend/app/config.py`.

## Testing rapido

```bash
# Backend (richiede la chiave API e Playwright installato)
pytest tests

# Frontend linting
cd frontend && npm run lint
```

## Licenza

Distribuito sotto licenza Apache 2.0 come il progetto originario Podcastfy.
