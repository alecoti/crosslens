import './globals.css';
import type { Metadata } from 'next';
import { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Podcastfy Gemini Flash Boilerplate',
  description:
    'Inserisci i link degli articoli, estrai il contenuto con Playwright Firefox e ascolta l\'audio generato con Gemini Flash.'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
