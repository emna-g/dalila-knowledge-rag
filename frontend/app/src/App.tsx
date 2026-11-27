import { useCallback, useEffect, useMemo, useState } from 'react'
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
  const [, setSurvol] = useState<number | null>(null)

  useEffect(() => { api.zones().then(setZones).catch(() => setErreur(true)) }, [])

  const resultats = useMemo(() => filtrer(zones, filtres), [zones, filtres])
  const zone = zones.find((z) => z.zone_id === zoneId) ?? null

  const choisirZone = useCallback((id: number | null, lot: number | null = null) => {
    setZoneId(id); setLotId(lot); setPanneauMobile(id != null)
    if (id == null) { setLots([]); return }
    api.lots(id).then((l) => setLots(l)).catch(() => setLots([]))
  }, [])

  // garder le contexte de Dalila en accord avec la sélection sur la carte
  useEffect(() => {
    if (!zone) { setContexte(null); return }
    const l = lots.find((x) => x.lot_id === lotId)
    setContexte(l ? { zone: zone.zone_id, lot: l.lot_id, nom: `${t.lot} ${l.numero} · ${nom(zone.nom, zone.nom_ar)}` } : { zone: zone.zone_id, nom: nom(zone.nom, zone.nom_ar) })
  }, [zone, lotId, lots, t.lot, nom])

  const allerAuLot = useCallback(async (id: number) => {
    const deja = lots.find((l) => l.lot_id === id)
    if (deja) { setLotId(id); return }
    try { const l = await api.lot(id); choisirZone(l.zone_id, id) } catch { /* lot sans contour : rien à montrer */ }
  }, [lots, choisirZone])

  const demander = useCallback((texte: string, ctx?: object) => {
    setDalila(true)
    setDemande({ texte, contexte: (ctx as Record<string, unknown>) ?? contexte, n: Date.now() })
  }, [contexte])

  const basculerComparer = (id: number) => setComparer((c) => c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-3))
  const marges = { gauche: 0, droite: 0 }   // les panneaux sont à côté de la carte, pas dessus

  return (
    <div className="flex h-full flex-col">
      <Entete encheres={filtres.encheres} onEncheres={() => setFiltres({ ...filtres, encheres: !filtres.encheres })}
        nbComparer={comparer.length} onComparer={() => setComparateur(true)} onAccueil={() => { choisirZone(null); setFiltres(FILTRES_VIDES); setCitees([]) }} />

      <main className="relative flex min-h-0 flex-1">
        {/* panneau de gauche : recherche ou fiche d'une zone */}
        <aside className={clsx('absolute inset-y-0 start-0 z-20 w-full max-w-[400px] border-e border-trait bg-white shadow-flotte transition-transform lg:static lg:translate-x-0 lg:shadow-none',
          panneauMobile ? 'translate-x-0' : 'max-lg:ltr:-translate-x-full max-lg:rtl:translate-x-full')}>
          <button type="button" onClick={() => setPanneauMobile(false)} aria-label={t.fermer}
            className="absolute end-3 top-3 z-10 grid size-9 place-items-center rounded-lg bg-white/90 text-doux shadow lg:hidden"><X size={18} aria-hidden /></button>
          <AnimatePresence mode="wait" initial={false}>
            {zone ? (
              <motion.div key={`z${zone.zone_id}`} className="h-full" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.2 }}>
                <FicheZone zone={zone} lots={lots} lotChoisi={lotId} onLot={setLotId} onRetour={() => choisirZone(null)}
                  onDemander={demander} comparee={comparer.includes(zone.zone_id)} basculerComparer={() => basculerComparer(zone.zone_id)} />
              </motion.div>
            ) : (
              <motion.div key="recherche" className="h-full" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }} transition={{ duration: 0.2 }}>
                <Recherche zones={zones} resultats={resultats} filtres={filtres} setFiltres={setFiltres} onZone={(id) => choisirZone(id)}
                  comparer={comparer} basculerComparer={basculerComparer} survol={setSurvol} />
              </motion.div>
            )}
          </AnimatePresence>
        </aside>

        {/* carte */}
        <section className="relative min-w-0 flex-1">
          <Carte zones={resultats} zoneChoisie={zone} lots={lots} lotChoisi={lotId} citees={citees} fond={fond} marges={marges}
            onZone={(id) => choisirZone(id)} onLot={(id) => setLotId(id)} onFond={setFond} />
          {!zones.length && (
            <div className="pointer-events-none absolute inset-x-0 top-16 z-10 mx-auto w-fit rounded-xl bg-white/95 px-4 py-2 text-sm shadow-carte" role="status">
              {erreur ? t.erreurZones : t.chargement}
            </div>
          )}
          <button type="button" onClick={() => setPanneauMobile(true)}
            className="absolute bottom-24 start-3 z-10 flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 font-semibold text-marine shadow-carte lg:hidden">
            <List size={18} aria-hidden /> {t.zonesTrouvees(resultats.length)}
          </button>

          {/* barre de comparaison */}
          <AnimatePresence>
            {comparer.length > 0 && (
              <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 30, opacity: 0 }}
                className="absolute bottom-8 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-2xl bg-nuit/95 p-2 ps-4 text-white shadow-flotte backdrop-blur">
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
            {!dalila && (
              <motion.button type="button" onClick={() => setDalila(true)} initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }}
                className="group absolute bottom-8 end-4 z-20 flex items-center gap-3 rounded-full bg-white p-1.5 pe-5 shadow-flotte ring-1 ring-trait transition hover:-translate-y-0.5">
                <Anneau etat="repos" taille={58} />
                <span className="text-start">
                  <span className="block font-bold text-marine">{t.dlOuvrir}</span>
                  <span className="block text-xs text-doux">{t.dlRole} · 8 langues</span>
                </span>
              </motion.button>
            )}
          </AnimatePresence>
        </section>

        <Dalila ouvert={dalila} onFermer={() => setDalila(false)} demande={demande} contexte={contexte} onRetirerContexte={() => setContexte(null)}
          onZone={(id) => { choisirZone(id); if (window.innerWidth < 1024) setDalila(false) }}
          onLot={(id) => { allerAuLot(id); if (window.innerWidth < 1024) setDalila(false) }}
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
