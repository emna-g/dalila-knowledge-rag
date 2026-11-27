import type { ReactNode } from 'react'
import { FileText, ExternalLink, MapPin, LayoutGrid } from 'lucide-react'

/*
 * Rendu d'une réponse de l'API (/carte/chatbot) :
 *   [[ZONE:id:nom]]  -> bouton qui montre la zone sur la carte
 *   [[LOT:id:numéro]] -> bouton qui montre le lot
 *   [[PDF:url:titre]] -> carte « document »
 *   [[CHOIX:texte]]   -> bouton de réponse rapide sous la réponse
 *   « - … »           -> ligne d'une liste (fiche)
 *   [titre](url)      -> lien ; une ligne qui n'a que des liens = les sources
 * Le texte reste du texte (jamais du HTML) ; seuls les liens http(s) sont rendus. Les nombres avec unité en gras.
 */
const JETON = /\[\[(ZONE|LOT|CHOIX|PDF):([^\]]+)\]\]|\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*\n]+)\*\*/g
const NOMBRE = /(\d[\d   ,.]*\s?(?:DT\/m²|DT|TND|m²|km|ha|jours?|mois|%|د\/م²|م²|كم)?)/g
const SOURCE = /^\[[^\]]+\]\(https?:\/\/[^)\s]+\)(\s*·\s*\[[^\]]+\]\(https?:\/\/[^)\s]+\))*$/

export interface Analyse {
  blocs: Bloc[]
  choix: string[]
  documents: { url: string; titre: string }[]
  sources: { url: string; titre: string }[]
  zones: { id: number; nom: string }[]
  lots: { id: number; numero: string }[]
}
type Morceau = { t: 'texte'; v: string } | { t: 'gras'; v: string } | { t: 'zone'; id: number; nom: string } | { t: 'lot'; id: number; numero: string } | { t: 'lien'; url: string; v: string }
type Bloc = { t: 'p'; lignes: Morceau[][] } | { t: 'liste'; items: Morceau[][] }

const sur = (u: string) => (/^https?:\/\//i.test(u) ? u : null)
function couper(v: string, aLaFin = false): [string, string] {
  const i = aLaFin ? v.lastIndexOf(':') : v.indexOf(':')
  return i < 0 ? [v, v] : [v.slice(0, i), v.slice(i + 1)]
}

export function analyser(texte: string): Analyse {
  const a: Analyse = { blocs: [], choix: [], documents: [], sources: [], zones: [], lots: [] }
  let courant: Bloc | null = null
  for (const brute of (texte || '').split(/\r?\n/)) {
    const ligne = brute.trim()
    if (!ligne) { courant = null; continue }
    if (SOURCE.test(ligne)) {
      for (const m of ligne.matchAll(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g)) a.sources.push({ titre: m[1], url: m[2] })
      continue
    }
    const estListe = /^[-•*]\s+/.test(ligne)
    const morceaux = decouper(estListe ? ligne.replace(/^[-•*]\s+/, '') : ligne, a)
    const vide = morceaux.every((m) => m.t === 'texte' && !m.v.trim())
    if (vide) continue
    if (estListe) {
      if (courant?.t !== 'liste') { courant = { t: 'liste', items: [] }; a.blocs.push(courant) }
      courant.items.push(morceaux)
    } else {
      if (courant?.t !== 'p') { courant = { t: 'p', lignes: [] }; a.blocs.push(courant) }
      courant.lignes.push(morceaux)
    }
  }
  return a
}

function decouper(ligne: string, a: Analyse): Morceau[] {
  const r: Morceau[] = []
  let dernier = 0
  for (const m of ligne.matchAll(JETON)) {
    if (m.index! > dernier) r.push({ t: 'texte', v: ligne.slice(dernier, m.index) })
    dernier = m.index! + m[0].length
    if (m[1] === 'CHOIX') a.choix.push(m[2].trim())
    else if (m[1] === 'PDF') { const [u, titre] = couper(m[2], true); const url = sur(u); if (url) a.documents.push({ url, titre }) }
    else if (m[1] === 'ZONE') { const [id, nom] = couper(m[2]); r.push({ t: 'zone', id: Number(id), nom }); a.zones.push({ id: Number(id), nom }) }
    else if (m[1] === 'LOT') { const [id, numero] = couper(m[2]); r.push({ t: 'lot', id: Number(id), numero }); a.lots.push({ id: Number(id), numero }) }
    else if (m[3]) { const url = sur(m[4]); r.push(url ? { t: 'lien', url, v: m[3] } : { t: 'texte', v: m[3] }) }
    else if (m[5]) r.push({ t: 'gras', v: m[5] })
  }
  if (dernier < ligne.length) r.push({ t: 'texte', v: ligne.slice(dernier) })
  return r
}

function avecNombres(v: string, cle: string): ReactNode[] {
  const out: ReactNode[] = []
  let d = 0, i = 0
  for (const m of v.matchAll(NOMBRE)) {
    const n = m[1].replace(/[\s,.]+$/, '')
    if (!n) continue
    out.push(v.slice(d, m.index), <strong key={`${cle}-${i++}`} className="font-semibold text-encre">{n}</strong>)
    d = m.index! + n.length
  }
  out.push(v.slice(d))
  return out
}

interface RenduProps {
  analyse: Analyse
  onZone: (id: number) => void
  onLot: (id: number) => void
  libelleLot: string
  libelleSources: string
}

export function Rendu({ analyse, onZone, onLot, libelleLot, libelleSources }: RenduProps) {
  const morceaux = (ms: Morceau[], cle: string, liste: boolean) => ms.map((m, i) => {
    const k = `${cle}-${i}`
    switch (m.t) {
      case 'texte': return <span key={k}>{liste ? avecNombres(m.v, k) : m.v}</span>
      case 'gras': return <strong key={k} className="font-semibold text-marine">{m.v}</strong>
      case 'lien': return <a key={k} href={m.url} target="_blank" rel="noopener noreferrer" className="font-medium text-lien underline underline-offset-2">{m.v}</a>
      case 'zone': return (
        <button key={k} type="button" onClick={() => onZone(m.id)}
          className="mx-0.5 inline-flex min-h-7 items-center gap-1 rounded-full border border-marine/30 bg-marine/5 px-2.5 align-middle text-[13px] font-semibold text-marine transition hover:bg-marine hover:text-white">
          <MapPin size={13} aria-hidden />{m.nom}
        </button>)
      case 'lot': return (
        <button key={k} type="button" onClick={() => onLot(m.id)}
          className="me-1 inline-flex min-h-7 items-center gap-1 rounded-full border border-vert/30 bg-vert/5 px-2.5 align-middle text-[13px] font-semibold text-vert transition hover:bg-vert hover:text-white">
          <LayoutGrid size={13} aria-hidden />{libelleLot} {m.numero}
        </button>)
    }
  })

  return (
    <div className="space-y-2.5 text-[15px] leading-relaxed">
      {analyse.blocs.map((b, i) => b.t === 'p'
        ? <p key={i}>{b.lignes.map((l, j) => <span key={j}>{j > 0 && <br />}{morceaux(l, `${i}-${j}`, false)}</span>)}</p>
        : <ul key={i} className="space-y-1.5">{b.items.map((it, j) => (
          <li key={j} className="rounded-xl border border-trait bg-fond/60 px-3 py-2 text-[14px]">{morceaux(it, `${i}-${j}`, true)}</li>))}</ul>)}
      {analyse.documents.map((d) => (
        <a key={d.url} href={d.url} target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-3 rounded-xl border border-trait bg-white p-2.5 text-sm transition hover:border-lien/40 hover:bg-fond">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-alerte/10 text-alerte"><FileText size={17} aria-hidden /></span>
          <span className="min-w-0 flex-1 truncate font-semibold text-lien">{d.titre}</span>
          <ExternalLink size={14} className="shrink-0 text-doux" aria-hidden />
        </a>
      ))}
      {analyse.sources.length > 0 && (
        <p className="rounded-lg border border-sable-bord bg-sable px-3 py-2 text-[12.5px] text-doux">
          <span className="font-semibold">{libelleSources} · </span>
          {analyse.sources.map((s, i) => (
            <span key={s.url}>{i > 0 && ' · '}<a href={s.url} target="_blank" rel="noopener noreferrer" className="text-lien underline underline-offset-2">{s.titre}</a></span>
          ))}
        </p>
      )}
    </div>
  )
}
