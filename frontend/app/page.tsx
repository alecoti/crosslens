'use client';

import { FormEvent, useState } from 'react';

interface AudioResult {
  url: string;
  title: string;
  summary: string;
  audio_url: string;
}

const DEFAULT_LINKS = [
  'https://blog.google/technology/ai/google-gemini-updates/',
  'https://simonwillison.net/2024/Jun/27/gemini-tts/'
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function HomePage() {
  const [linksInput, setLinksInput] = useState(DEFAULT_LINKS.join('\n'));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<AudioResult[]>([]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const links = linksInput
      .split(/\r?\n/)
      .map((link) => link.trim())
      .filter((link) => link.length > 0);

    if (links.length === 0) {
      setError('Inserisci almeno un link valido.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ links })
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Errore nella generazione dell\'audio');
      }

      const payload = await response.json();
      setResults(payload.results ?? []);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Errore sconosciuto');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main>
      <div className="card">
        <h1>Podcastfy · Gemini Flash Boilerplate</h1>
        <p>
          Incolla fino a dieci link agli articoli che vuoi trasformare in audio. Il backend FastAPI userà
          Playwright con Firefox per estrarre i contenuti e Gemini Flash TTS per creare i file MP3.
        </p>

        <form onSubmit={onSubmit}>
          <label htmlFor="links">Link (uno per riga)</label>
          <textarea
            id="links"
            value={linksInput}
            onChange={(event) => setLinksInput(event.target.value)}
            placeholder="https://esempio.com/articolo-1"
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Generazione in corso…' : 'Genera podcast'}
          </button>
        </form>

        {error && <p style={{ color: '#f87171', marginTop: '1rem' }}>{error}</p>}

        <div className="audio-grid">
          {results.map((result) => (
            <div className="audio-card" key={result.audio_url}>
              <h3>{result.title}</h3>
              <p>{result.summary}</p>
              <audio controls src={`${API_BASE}${result.audio_url}`} style={{ width: '100%' }} />
              <small>
                <a href={result.url} target="_blank" rel="noreferrer">
                  Vedi sorgente
                </a>
              </small>
            </div>
          ))}
        </div>

        <footer>
          Backend FastAPI: <code>{API_BASE}</code>
        </footer>
      </div>
    </main>
  );
}
