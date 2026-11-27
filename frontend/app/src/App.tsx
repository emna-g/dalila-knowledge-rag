import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { List, Scale, X } from 'lucide-react'
import clsx from 'clsx'
import { api } from './api'
import { useLangue, useNom } from './langue'
import type { Lot, Zone } from './types'
import { Entete } from './components/Entete'
import { Carte } from './components/Carte'
import { Recherche, FILTRES_VIDES, filtrer, type Filtres } from './components/Recherche'
import { FicheZone } from './components/FicheZone'
import { Comparateur } from './components/Comparateur'
import { Dalila, Anneau, type Demande } from './dalila/Dalila'

/** Lien partageable : #zone=931402&lot=261 */
function lireAdresse(): { zone: number | null; lot: number | null } {
  const p = new URLSearchParams(location.hash.slice(1))
  const n = (k: string) => (p.get(k) && /^\d+$/.test(p.get(k)!) ? Number(p.get(k)) : null)
  return { zone: n('zone'), lot: n('lot') }
}

export default function App() {
  const { t } = useLangue()
  const nom = useNom()
  const [zones, setZones] = useState<Zone[]>([])
  const [erreur, setErreur] = useState(false)
  const [filtres, setFiltres] = useState<Filtres>(FILTRES_VIDES)
  const [zoneId, setZoneId] = useState<number | null>(null)
  const [lots, setLots] = useState<Lot[]>([])
  const [lotId, setLotId] = useState<number | null>(null)
  const [citees, setCitees] = useState<number[]>([])
  const [fond, setFond] = useState<'plan' | 'satellite'>('plan')
  const [comparer, setComparer] = useState<number[]>([])
  const [comparateur, setComparateur] = useState(false)
  const [dalila, setDalila] = useState(() => window.innerWidth >= 1280)
  const [demande, setDemande] = useState<Demande | null>(null)
  const [contexte, setContexte] = useState<Record<string, unknown> | null>(null)
  const [panneauMobile, setPanneauMobile] = useState(false)
  const [survol, setSurvol] = useState<number | null>(null)
  const [cadrage, setCadrage] = useState(0)
  const premierFiltre = useRef(true)

  const choisirZone = useCallback((id: number | null, lot: number | null = null) => {
    setZoneId(id); setLotId(lot)
    if (id != null) setPanneauMobile(true)
    if (id == null) { setLots([]); return }
    api.lots(id).then((l) => setLots(l)).catch(() => setLots([]))
  }, [])

  useEffect(() => {
    api.zones().then((z) => {
      setZones(z)
      const a = lireAdresse()
      if (a.zone != null && z.some((x) => x.zone_id === a.zone)) choisirZone(a.zone, a.lot)
    }).catch(() => setErreur(true))
  }, [choisirZone])

  // l'adresse suit la sélection (lien à partager, bouton « précédent » du navigateur)
  useEffect(() => {
    if (!zones.length) return          // pas avant d'avoir lu l'adresse de départ
    const h = zoneId != null ? `#zone=${zoneId}${lotId != null ? `&lot=${lotId}` : ''}` : ''
    if (location.hash !== h) history.replaceState(null, '', h || location.pathname)
  }, [zoneId, lotId, zones.length])

  const resultats = useMemo(() => filtrer(zones, filtres), [zones, filtres])
  const zone = zones.find((z) => z.zone_id === zoneId) ?? null

  // un filtre change : la carte se cadre sur les zones trouvées
  useEffect(() => {
    if (premierFiltre.current) { premierFiltre.current = false; return }
    setCadrage((c) => c + 1)
  }, [filtres.gouvernorat, filtres.texte, filtres.dispo, filtres.encheres, filtres.dr, filtres.cahier, filtres.surface, filtres.prixMax])

  // garder le contexte de Dalila en accord avec la sélection sur la carte
  useEffect(() => {
    if (!zone) { setContexte(null); return }
    const l = lots.find((x) => x.lot_id === lotId)
    setContexte(l ? { zone: zone.zone_id, lot: l.lot_id, nom: `${t.lot} ${l.numero} · ${nom(zone.nom, zone.nom_ar)}` } : { zone: zone.zone_id, nom: nom(zone.nom, zone.nom_ar) })
  }, [zone, lotId, lots, t.lot, nom])

  const allerAuLot = useCallback(async (id: number) => {
    if (lots.some((l) => l.lot_id === id)) { setLotId(id); setPanneauMobile(true); return }
    try { const l = await api.lot(id); choisirZone(l.zone_id, id) } catch { /* lot sans contour : rien à montrer */ }
  }, [lots, choisirZone])

  const demander = useCallback((texte: string, ctx?: object) => {
    setDalila(true)
    setDemande({ texte, contexte: (ctx as Record<string, unknown>) ?? contexte, n: Date.now() })
  }, [contexte])

  const basculerComparer = (id: number) => setComparer((c) => c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-3))
  const mobile = () => window.innerWidth < 1024

  return (
    <div className="flex h-full flex-col">
      <Entete encheres={filtres.encheres} onEncheres={() => setFiltres({ ...filtres, encheres: !filtres.encheres })}
        nbComparer={comparer.length} onComparer={() => setComparateur(true)}
        onAccueil={() => { choisirZone(null); setFiltres(FILTRES_VIDES); setCitees([]); setPanneauMobile(false) }} />

      <main className="relative flex min-h-0 flex-1">
        {/* panneau : à gauche sur ordinateur, en bas de l'écran sur téléphone (la carte reste visible) */}
        <aside aria-label={zone ? nom(zone.nom, zone.nom_ar) : t.rechercheTitre}
          className={clsx('z-30 bg-white transition-transform duration-300',
            'max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:h-[52dvh] max-lg:rounded-t-3xl max-lg:shadow-flotte',
            'lg:relative lg:w-[400px] lg:shrink-0 lg:border-e lg:border-trait',
            panneauMobile ? 'max-lg:translate-y-0' : 'max-lg:translate-y-full')}>
          <div className="flex h-11 items-center justify-center lg:hidden">
            <span className="h-1.5 w-12 rounded-full bg-trait" aria-hidden />
            <button type="button" onClick={() => setPanneauMobile(false)} aria-label={t.fermer}
              className="absolute end-3 top-1.5 grid size-9 place-items-center rounded-lg text-doux hover:bg-fond"><X size={18} aria-hidden /></button>
          </div>
          <div className="h-[calc(100%-2.75rem)] overflow-hidden max-lg:rounded-t-2xl lg:h-full">
            <AnimatePresence mode="wait" initial={false}>
              {zone ? (
                <motion.div key={`z${zone.zone_id}`} className="h-full" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.2 }}>
                  <FicheZone zone={zone} lots={lots} lotChoisi={lotId} onLot={setLotId} onRetour={() => choisirZone(null)}
                    onDemander={demander} comparee={comparer.includes(zone.zone_id)} basculerComparer={() => basculerComparer(zone.zone_id)} />
                </motion.div>
              ) : (
                <motion.div key="recherche" className="h-full" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: 0.2 }}>
                  <Recherche zones={zones} resultats={resultats} filtres={filtres} setFiltres={setFiltres} chargement={!zones.length && !erreur}
                    onZone={(id) => choisirZone(id)} comparer={comparer} basculerComparer={basculerComparer} survol={setSurvol} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </aside>

        {/* carte */}
        <section className="relative min-w-0 flex-1">
          <Carte zones={resultats} zoneChoisie={zone} lots={lots} lotChoisi={lotId} citees={citees} fond={fond}
            survol={survol} cadrage={cadrage} basMobile={panneauMobile} encheres={filtres.encheres}
            onZone={(id) => choisirZone(id)} onLot={(id) => { setLotId(id); setPanneauMobile(true) }} onFond={setFond} />
          {!zones.length && (
            <div className={clsx('pointer-events-none absolute inset-x-0 top-16 z-10 mx-auto w-fit rounded-xl px-4 py-2 text-sm shadow-carte',
              erreur ? 'bg-alerte text-white' : 'bg-white/95')} role="status">
              {erreur ? t.erreurZones : t.chargement}
            </div>
          )}
          {!panneauMobile && (
            <button type="button" onClick={() => setPanneauMobile(true)}
              className="absolute bottom-24 start-3 z-10 flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 font-semibold text-marine shadow-carte lg:hidden">
              <List size={18} aria-hidden /> {t.zonesTrouvees(resultats.length)}
            </button>
          )}

          {/* barre de comparaison */}
          <AnimatePresence>
            {comparer.length > 0 && !(panneauMobile && mobile()) && (
              <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 30, opacity: 0 }}
                className="absolute bottom-8 left-1/2 z-10 flex max-w-[calc(100%-2rem)] -translate-x-1/2 flex-wrap items-center gap-2 rounded-2xl bg-nuit/95 p-2 ps-4 text-white shadow-flotte backdrop-blur">
                <Scale size={18} className="text-ciel" aria-hidden />
                {comparer.map((id) => { const z = zones.find((x) => x.zone_id === id); return z && (
                  <span key={id} className="flex items-center gap-1 rounded-lg bg-white/10 px-2 py-1 text-sm">
                    {nom(z.nom, z.nom_ar)}
                    <button type="button" onClick={() => basculerComparer(id)} aria-label={`${t.retirerComparaison} ${z.nom}`} className="rounded p-0.5 hover:bg-white/20"><X size={14} aria-hidden /></button>
                  </span>) })}
                <button type="button" disabled={comparer.length < 2} onClick={() => setComparateur(true)}
                  className="min-h-10 rounded-xl bg-white px-4 text-sm font-semibold text-marine disabled:opacity-50">{t.comparerN(comparer.length)}</button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Dalila réduite : la mascotte en bouton */}
          <AnimatePresence>
            {!dalila && !(panneauMobile && mobile()) && (
              <motion.button type="button" onClick={() => setDalila(true)} initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }}
                className="group absolute bottom-8 end-4 z-20 flex items-center gap-3 rounded-full bg-white p-1.5 pe-5 shadow-flotte ring-1 ring-trait transition hover:-translate-y-0.5">
                <Anneau etat="repos" taille={58} />
                <span className="text-start">
                  <span className="block font-bold text-marine">{t.dlOuvrir}</span>
                  <span className="block text-xs text-doux">{t.dlRole} · {t.huitLangues}</span>
                </span>
              </motion.button>
            )}
          </AnimatePresence>
        </section>

        <Dalila ouvert={dalila} onFermer={() => setDalila(false)} demande={demande} contexte={contexte} onRetirerContexte={() => setContexte(null)}
          onZone={(id) => { choisirZone(id); if (mobile()) setDalila(false) }}
          onLot={(id) => { allerAuLot(id); if (mobile()) setDalila(false) }}
          onCiter={setCitees} />
      </main>

      <footer className="hidden h-9 items-center border-t border-trait bg-white px-6 text-xs text-doux md:flex">
        {t.droits}
        <span className="ms-auto">{t.source}</span>
      </footer>

      <AnimatePresence>
        {comparateur && comparer.length >= 2 && (
          <Comparateur ids={comparer} onFermer={() => setComparateur(false)} onZone={(id) => choisirZone(id)}
            onDemander={(q) => demander(q, {})} onRetirer={basculerComparer} />
        )}
      </AnimatePresence>
    </div>
  )
}
