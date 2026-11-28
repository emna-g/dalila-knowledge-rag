import type { DemandeEnvoyee, DemandePreremplie, FicheZone, Lot, ReponseDalila, Zone } from './types'

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
  /** Avis, avec un commentaire facultatif (flux F06). */
  avis: (log_id: number, utile: boolean, commentaire?: string) =>
    envoyer('/carte/chatbot/avis', { log_id, utile, commentaire: commentaire?.trim() || null }, 15000),

  /** POST /carte/etude : première question de l'étude de projet guidée (10 questions, puis PDF). */
  async etude(session_id: string, lang: string) {
    const r = await envoyer('/carte/etude', { session_id, lang }, 30000)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return (await r.json()) as ReponseDalila
  },

  /** BF11 : demande d'acquisition préremplie (lot, zone, projet de l'étude de cette conversation, pièces). */
  demandePreremplie: (lot_id: number, session_id?: string | null) =>
    lire<DemandePreremplie>(`/carte/demande?lot_id=${lot_id}${session_id ? `&session_id=${encodeURIComponent(session_id)}` : ''}`),
  /** Le brouillon en PDF : produit seulement avec confirme = true ; ni déposé ni gardé par le service. */
  async demandePdf(corps: DemandeEnvoyee): Promise<Blob> {
    const r = await envoyer('/carte/demande/pdf', corps, 60000)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.blob()
  },

  /** POST /carte/voix/lire : WAV, ou null (204 : pas de voix, la réponse reste en texte) ; note : un dialecte lu par
   *  la voix arabe est signalé par l'API (en-tête X-Dalila-Lecture, BF8). */
  async voix(texte: string, lang: string): Promise<{ wav: Blob | null; note: string | null }> {
    const r = await envoyer('/carte/voix/lire', { texte, lang }, 45000)
    const brut = r.headers.get('X-Dalila-Lecture')
    const note = brut ? new DOMParser().parseFromString(brut, 'text/html').documentElement.textContent : null
    return { wav: r.status === 200 ? await r.blob() : null, note }
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
