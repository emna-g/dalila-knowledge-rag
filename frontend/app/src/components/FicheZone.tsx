import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft, ArrowRight, Building, Droplets, ExternalLink, FileText, Flame, Gavel, Landmark, MessageCircle, Phone, Plane,
  Recycle, Route, Scale, Ship, TrainFront, Zap, Fuel, X,
} from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api'
import { DISTANCES, EQUIPEMENTS, ETATS, SERVICES, nombre } from '../i18n'
import { useLangue, useNom } from '../langue'
import type { FicheZone as Fiche, Lot, Statut, Zone } from '../types'

const ICONES_ACCES: Record<string, typeof Plane> = { port: Ship, aeroport: Plane, autoroute: Route, gare: TrainFront, gazoduc: Fuel }
const ICONES_RESEAU: Record<string, typeof Plane> = { eau_debit: Droplets, electricite_puissance: Zap, gaz_pression: Flame, station_epuration: Recycle, telephone: Phone }

interface Props {
  zone: Zone
  lots: Lot[]
  lotChoisi: number | null
  onLot: (id: number | null) => void
  onRetour: () => void
  onDemander: (texte: string, contexte: object) => void
  comparee: boolean
  basculerComparer: () => void
}

export function FicheZone({ zone, lots, lotChoisi, onLot, onRetour, onDemander, comparee, basculerComparer }: Props) {
  const { t, langue, rtl } = useLangue()
  const nom = useNom()
  const [fiche, setFiche] = useState<Fiche | null>(null)
  const [onglet, setOnglet] = useState<'apercu' | 'lots' | 'infra' | 'docs'>('apercu')
  const [filtreEtat, setFiltreEtat] = useState<Statut | ''>('')

  useEffect(() => {
    setFiche(null)
    api.fiche(zone.zone_id).then(setFiche).catch(() => setFiche(null))
  }, [zone.zone_id])
  useEffect(() => { if (lotChoisi != null) setOnglet('lots') }, [lotChoisi])

  const etats = useMemo(() => {
    const c: Partial<Record<Statut, number>> = {}
    lots.forEach((l) => { c[l.statut] = (c[l.statut] ?? 0) + 1 })
    return Object.keys(c).length ? c : zone.lots_par_etat
  }, [lots, zone.lots_par_etat])
  const totalLots = Object.values(etats).reduce((s, n) => s + (n ?? 0), 0)
  const lot = lots.find((l) => l.lot_id === lotChoisi) ?? null
  const listeLots = useMemo(() => lots
    .filter((l) => !filtreEtat || l.statut === filtreEtat)
    .sort((a, b) => (a.statut === 'disponible' ? 0 : 1) - (b.statut === 'disponible' ? 0 : 1) || a.numero.localeCompare(b.numero, undefined, { numeric: true })),
  [lots, filtreEtat])
  const Fleche = rtl ? ArrowRight : ArrowLeft
  const nomZone = nom(zone.nom, zone.nom_ar)

  const demanderZone = () => onDemander(
    langue === 'ar' ? `حدثني عن منطقة ${nomZone}: الأسعار، المقاسم المتاحة والشروط.`
      : langue === 'en' ? `Tell me about the ${zone.nom} zone: prices, available lots and conditions.`
        : `Parlez-moi de la zone ${zone.nom} : prix, lots disponibles et conditions.`,
    { zone: zone.zone_id, nom: zone.nom })

  return (
    <div className="flex h-full flex-col">
      {/* en-tête de la fiche */}
      <div className="relative overflow-hidden bg-gradient-to-br from-marine via-marine to-nuit px-5 pb-5 pt-4 text-white">
        <svg aria-hidden className="absolute -end-16 -top-16 size-56 opacity-20" viewBox="0 0 100 100">
          <path d="M50 5a45 45 0 0 1 45 45" fill="none" stroke="#04B4E3" strokeWidth="8" />
          <path d="M95 50a45 45 0 0 1-45 45" fill="none" stroke="#FFED00" strokeWidth="8" />
          <path d="M50 20a30 30 0 0 1 30 30" fill="none" stroke="#008D36" strokeWidth="6" />
        </svg>
        <div className="relative flex items-center gap-2">
          <button type="button" onClick={onRetour} className="flex min-h-9 items-center gap-1.5 rounded-lg bg-white/10 px-2.5 text-sm font-medium hover:bg-white/20">
            <Fleche size={16} aria-hidden /> {t.retour}
          </button>
          <button type="button" onClick={basculerComparer} aria-pressed={comparee}
            className={clsx('ms-auto flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition', comparee ? 'bg-white text-marine' : 'bg-white/10 hover:bg-white/20')}>
            <Scale size={15} aria-hidden /> {comparee ? t.retirerComparaison : t.ajouterComparaison}
          </button>
        </div>
        <h2 className="relative mt-4 text-2xl font-bold leading-tight">{nomZone}</h2>
        <p className="relative mt-0.5 text-sm text-white/80">{nom(zone.gouvernorat, zone.gouvernorat_ar)}</p>
        <div className="relative mt-3 flex flex-wrap gap-1.5 text-xs">
          {zone.developpement_regional && <span className="flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1"><Landmark size={13} aria-hidden /> {t.dr}{zone.groupe_developpement_regional ? ` · G${zone.groupe_developpement_regional}` : ''}</span>}
          {zone.lots_aux_encheres > 0 && <span className="flex items-center gap-1 rounded-full bg-alerte px-2.5 py-1 font-semibold"><Gavel size={13} aria-hidden /> {zone.lots_aux_encheres} · {t.encheres}</span>}
        </div>
        <button type="button" onClick={demanderZone}
          className="relative mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-white font-semibold text-marine shadow-lg transition hover:bg-brume">
          <MessageCircle size={18} aria-hidden /> {t.demanderZone}
        </button>
      </div>

      {/* chiffres clés */}
      <div className="grid grid-cols-2 gap-2 border-b border-trait bg-white p-4">
        <Chiffre libelle={t.lotsDispo} valeur={nombre(zone.lots_disponibles, langue)} accent="text-vert" />
        <Chiffre libelle={t.parM2.replace('/', ' / ')} valeur={zone.prix_m2_dt != null ? nombre(zone.prix_m2_dt, langue) : '—'}
          sous={zone.prix_m2_subventionne_dt != null ? `${nombre(zone.prix_m2_subventionne_dt, langue, 2)} ${t.subventionne}` : undefined} />
        <Chiffre libelle={t.surfaceTotale} valeur={zone.surface_totale_m2 != null ? `${nombre(zone.surface_totale_m2 / 10000, langue, 1)} ha` : '—'} />
        <Chiffre libelle={t.surfaceAmenagee} valeur={zone.surface_amenagee_m2 != null ? `${nombre(zone.surface_amenagee_m2 / 10000, langue, 1)} ha` : '—'} />
      </div>

      {/* onglets */}
      <div role="tablist" className="flex gap-1 border-b border-trait bg-white px-3">
        {([['apercu', t.apercu], ['lots', `${t.lots} · ${lots.length || totalLots}`], ['infra', t.infrastructures], ['docs', t.documents]] as const).map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={onglet === k} onClick={() => setOnglet(k)}
            className={clsx('relative min-h-11 flex-1 whitespace-nowrap px-1 text-[13px] font-medium transition', onglet === k ? 'text-marine' : 'text-doux hover:text-encre')}>
            {l}
            {onglet === k && <motion.span layoutId="onglet" className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-marine" />}
          </button>
        ))}
      </div>

      <div className="defile flex-1 overflow-y-auto bg-fond/60 p-4">
        <AnimatePresence mode="wait">
          <motion.div key={onglet} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="space-y-4">

            {onglet === 'apercu' && (<>
              <Carte titre={t.aEtat}>
                {totalLots > 0 ? (<>
                  <div className="flex h-3 overflow-hidden rounded-full bg-brume">
                    {(Object.keys(ETATS) as Statut[]).filter((k) => etats[k]).map((k) => (
                      <div key={k} style={{ width: `${(100 * (etats[k] ?? 0)) / totalLots}%`, background: ETATS[k].couleur }} title={`${ETATS[k][langue]} : ${etats[k]}`} />
                    ))}
                  </div>
                  <ul className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[13px]">
                    {(Object.keys(ETATS) as Statut[]).filter((k) => etats[k]).map((k) => (
                      <li key={k} className="flex items-center gap-2">
                        <span className="size-2.5 rounded-full" style={{ background: ETATS[k].couleur }} />
                        <span className="text-doux">{ETATS[k][langue]}</span>
                        <span className="ms-auto font-semibold">{etats[k]}</span>
                      </li>
                    ))}
                  </ul>
                </>) : <p className="text-sm text-doux">{t.pasDePlan}</p>}
              </Carte>
              <Acces fiche={fiche} />
              {zone.surface_lot_min_m2 != null && (
                <Carte titre={t.lotsDispo}>
                  <p className="text-sm text-doux">{nombre(zone.surface_lot_min_m2, langue)} – {nombre(zone.surface_lot_max_m2, langue)} m²</p>
                </Carte>
              )}
            </>)}

            {onglet === 'lots' && (<>
              <AnimatePresence>
                {lot && (
                  <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                    className="rounded-2xl border-2 border-jaune bg-white p-4 shadow-carte">
                    <div className="flex items-start">
                      <div>
                        <p className="text-lg font-bold text-marine">{t.lot} {lot.numero}</p>
                        <p className="text-sm" style={{ color: ETATS[lot.statut].couleur }}>● {ETATS[lot.statut][langue]}{lot.a_confirmer ? ` (${t.aConfirmer})` : ''}</p>
                      </div>
                      <button type="button" onClick={() => onLot(null)} aria-label={t.fermer} className="ms-auto grid size-9 place-items-center rounded-lg text-doux hover:bg-fond"><X size={18} aria-hidden /></button>
                    </div>
                    <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                      <div className="rounded-xl bg-fond p-2.5"><dt className="text-doux">m²</dt><dd className="text-lg font-bold">{nombre(lot.surface_m2, langue)}</dd></div>
                      <div className="rounded-xl bg-fond p-2.5"><dt className="text-doux">{t.parM2}</dt><dd className="text-lg font-bold">{nombre(lot.prix_m2_dt, langue)}</dd></div>
                      {lot.surface_m2 != null && lot.prix_m2_dt != null && (
                        <div className="col-span-2 rounded-xl bg-sauge p-2.5"><dt className="text-[#3c5a1e]">{t.prixTerrain} ({nombre(lot.surface_m2, langue)} × {nombre(lot.prix_m2_dt, langue)})</dt>
                          <dd className="text-xl font-bold text-encre">{nombre(Math.round(lot.surface_m2 * lot.prix_m2_dt), langue)} DT</dd></div>
                      )}
                    </dl>
                    <button type="button" onClick={() => onDemander(
                      langue === 'ar' ? `يهمني المقسم ${lot.numero} في ${nomZone}. كيف أشتريه وما هي الوثائق اللازمة؟`
                        : langue === 'en' ? `I'm interested in lot ${lot.numero} in ${zone.nom}. How do I buy it and which documents are needed?`
                          : `Je m'intéresse au lot ${lot.numero} de la zone ${zone.nom}. Comment l'acheter, et quels documents faut-il ?`,
                      { zone: zone.zone_id, lot: lot.lot_id, nom: `${t.lot} ${lot.numero} · ${zone.nom}` })}
                      className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-marine font-semibold text-white hover:bg-marine-fonce">
                      <MessageCircle size={17} aria-hidden /> {t.demanderZone}
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex flex-wrap gap-1.5">
                <FiltreEtat actif={filtreEtat === ''} onClick={() => setFiltreEtat('')}>{t.tous.split(' ')[0]} · {lots.length}</FiltreEtat>
                {(Object.keys(ETATS) as Statut[]).filter((k) => etats[k]).map((k) => (
                  <FiltreEtat key={k} actif={filtreEtat === k} onClick={() => setFiltreEtat(k)} couleur={ETATS[k].couleur}>{ETATS[k][langue]} · {etats[k]}</FiltreEtat>
                ))}
              </div>
              {lots.length === 0 ? <p className="rounded-xl border border-dashed border-trait p-5 text-center text-sm text-doux">{t.pasDePlan}</p> : (
                <ul className="overflow-hidden rounded-2xl border border-trait bg-white">
                  {listeLots.map((l) => (
                    <li key={l.lot_id} className="border-b border-trait/70 last:border-0">
                      <button type="button" onClick={() => onLot(l.lot_id)} aria-pressed={l.lot_id === lotChoisi}
                        className={clsx('flex min-h-12 w-full items-center gap-3 px-3.5 text-start text-sm transition hover:bg-fond', l.lot_id === lotChoisi && 'bg-jaune/20')}>
                        <span className="size-2.5 shrink-0 rounded-full" style={{ background: ETATS[l.statut].couleur }} />
                        <span className="w-16 font-semibold">{t.lot} {l.numero}</span>
                        <span className="text-doux">{nombre(l.surface_m2, langue)} m²</span>
                        <span className="ms-auto text-xs" style={{ color: ETATS[l.statut].couleur }}>{ETATS[l.statut][langue]}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>)}

            {onglet === 'infra' && (<>
              <Acces fiche={fiche} />
              <Carte titre={t.equipements}>
                {!fiche ? <Chargement /> : fiche.equipements.length === 0 ? <p className="text-sm text-doux">—</p> : (
                  <ul className="grid grid-cols-2 gap-2">
                    {fiche.equipements.map((e) => {
                      const I = ICONES_RESEAU[e.type] ?? Building
                      return (
                        <li key={e.type} className="rounded-xl bg-fond p-2.5">
                          <I size={18} className="text-sarcelle" aria-hidden />
                          <p className="mt-1 text-[12px] text-doux">{EQUIPEMENTS[e.type]?.[langue] ?? e.type}</p>
                          <p className="text-sm font-semibold">{e.valeur ?? '✓'} {e.unite ?? ''}</p>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Carte>
              <Carte titre={t.services}>
                {!fiche ? <Chargement /> : (
                  <ul className="space-y-1.5 text-sm">
                    {Object.entries(fiche.services).sort((a, b) => (a[1].km ?? 99) - (b[1].km ?? 99)).map(([k, s]) => (
                      <li key={k} className="flex items-center gap-2">
                        <span className="text-doux">{SERVICES[k]?.[langue] ?? k}</span>
                        <span className="truncate text-xs text-doux/70">{s.nom ?? ''}</span>
                        <span className="ms-auto shrink-0 font-semibold">{nombre(s.km, langue, 1)} km</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Carte>
            </>)}

            {onglet === 'docs' && (
              !fiche ? <Chargement /> : fiche.cahiers.length + fiche.plans.length === 0 ? <p className="rounded-xl border border-dashed border-trait p-5 text-center text-sm text-doux">{t.aucunDocument}</p> : (<>
                {fiche.cahiers.length > 0 && <Carte titre={t.cahiers}>{fiche.cahiers.map((c) => (
                  <Document key={c.lien} href={c.lien} titre={`${t.cahiers.replace(/s$/, '')}${c.annee ? ' · ' + c.annee : ''}`} sous={c.remarque ?? undefined} />))}</Carte>}
                {fiche.plans.length > 0 && <Carte titre={t.plans}>{fiche.plans.map((p) => <Document key={p.lien} href={p.lien} titre={p.nom} />)}</Carte>}
              </>)
            )}
            <p className="text-center text-[11px] text-doux">{t.source}</p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )

  function Acces({ fiche }: { fiche: Fiche | null }) {
    return (
      <Carte titre={t.distances}>
        {!fiche ? <Chargement /> : (
          <ul className="space-y-2">
            {fiche.distances.map((d) => {
              const I = ICONES_ACCES[d.type] ?? Route
              return (
                <li key={d.type + d.nom} className="flex items-center gap-3 text-sm">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-lien/10 text-lien"><I size={17} aria-hidden /></span>
                  <span className="min-w-0"><span className="block font-medium">{DISTANCES[d.type]?.[langue] ?? d.type}</span><span className="block truncate text-xs text-doux">{d.nom}</span></span>
                  <span className="ms-auto shrink-0 font-semibold text-marine">{nombre(d.km, langue)} km</span>
                </li>
              )
            })}
          </ul>
        )}
      </Carte>
    )
  }
}

function Carte({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-trait bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-doux">{titre}</h3>
      {children}
    </section>
  )
}

function Chiffre({ libelle, valeur, sous, accent }: { libelle: string; valeur: string; sous?: string; accent?: string }) {
  return (
    <div className="rounded-xl bg-fond p-3">
      <p className="truncate text-[12px] text-doux first-letter:uppercase">{libelle}</p>
      <p className={clsx('mt-0.5 text-xl font-bold', accent ?? 'text-encre')}>{valeur}</p>
      {sous && <p className="truncate text-[11px] font-medium text-vert">{sous}</p>}
    </div>
  )
}

function FiltreEtat({ actif, onClick, couleur, children }: { actif: boolean; onClick: () => void; couleur?: string; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={actif}
      className={clsx('flex min-h-8 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition', actif ? 'border-marine bg-marine text-white' : 'border-trait bg-white text-doux hover:text-marine')}>
      {couleur && <span className="size-2 rounded-full" style={{ background: couleur }} />}{children}
    </button>
  )
}

function Document({ href, titre, sous }: { href: string; titre: string; sous?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="mb-2 flex items-center gap-3 rounded-xl border border-trait p-3 text-sm transition last:mb-0 hover:border-lien/40 hover:bg-fond">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-alerte/10 text-alerte"><FileText size={18} aria-hidden /></span>
      <span className="min-w-0"><span className="block truncate font-semibold text-lien">{titre}</span>{sous && <span className="line-clamp-2 text-xs text-doux">{sous}</span>}</span>
      <ExternalLink size={15} className="ms-auto shrink-0 text-doux" aria-hidden />
    </a>
  )
}

function Chargement() {
  return <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-8 animate-pulse rounded-lg bg-brume" />)}</div>
}
