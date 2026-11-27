import type { FicheZone, Lot, ReponseDalila, Zone } from './types'

// Même adresse que l'API (frontend/serveur.py), ou VITE_API pour un service ailleurs.
const API = (import.meta.env.VITE_API as string | undefined)?.replace(/\/+$/, '') ?? ''

async function lire<T>(chemin: string, delaiMs = 15000): Promise<T> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), delaiMs)
  try {
    const r = await fetch(API + chemin, { signal: ctrl.signal })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

async function envoyer(chemin: string, corps: unknown, delaiMs: number): Promise<Response> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), delaiMs)
  try {
    return await fetch(API + chemin, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps), signal: ctrl.signal,
    })
  } finally {
    clearTimeout(t)
  }
}

const fiches = new Map<number, Promise<FicheZone>>()
const lotsCache = new Map<number, Promise<Lot[]>>()

export const api = {
  zones: () => lire<Zone[]>('/carte/zones'),
  fiche: (id: number) => {
    if (!fiches.has(id)) fiches.set(id, lire<FicheZone>(`/carte/zones/${id}`).catch((e) => { fiches.delete(id); throw e }))
    return fiches.get(id)!
  },
  lots: (zoneId: number) => {
    if (!lotsCache.has(zoneId)) lotsCache.set(zoneId, lire<Lot[]>(`/carte/zones/${zoneId}/lots`).catch((e) => { lotsCache.delete(zoneId); throw e }))
    return lotsCache.get(zoneId)!
  },
  lot: (id: number) => lire<Lot>(`/carte/lots/${id}`),
  sante: () => lire<{ pret: boolean; base: boolean; modele: string }>('/sante', 8000),

  /** POST /carte/chatbot : l'API répond en 35 s au plus ; 90 s de marge pour un processeur chargé. */
  async demander(corps: { message: string; history: { role: string; content: string }[]; lang: string; contexte?: object | null; session_id: string }) {
    const r = await envoyer('/carte/chatbot', corps, 90000)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return (await r.json()) as ReponseDalila
  },
  avis: (log_id: number, utile: boolean) => envoyer('/carte/chatbot/avis', { log_id, utile }, 15000),

  /** POST /carte/voix/lire : WAV, ou null (204 : pas de voix pour cette écriture, la réponse reste en texte). */
  async voix(texte: string, lang: string): Promise<Blob | null> {
    const r = await envoyer('/carte/voix/lire', { texte, lang }, 45000)
    return r.status === 200 ? await r.blob() : null
  },

  /** POST /carte/voix/transcrire : l'audio n'est ni écrit ni gardé par le service. */
  async transcrire(audio: Blob): Promise<{ texte: string; langue: string; duree_s: number }> {
    const f = new FormData()
    f.append('audio', audio, 'question.webm')
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 120000)   // premier appel : Whisper se charge
    try {
      const r = await fetch(API + '/carte/voix/transcrire', { method: 'POST', body: f, signal: ctrl.signal })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      return j
    } finally {
      clearTimeout(t)
    }
  },
}
