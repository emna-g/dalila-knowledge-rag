import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Building2, ChevronDown, FileText, Gavel, Landmark, RotateCcw, Scale, Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import { nombre } from '../i18n'
import { useLangue, useNom } from '../langue'
import type { Zone } from '../types'

export interface Filtres {
  texte: string
  gouvernorat: string
  surface: number | null
  prixMax: number | null
  dispo: boolean
  encheres: boolean
  dr: boolean
  cahier: boolean
  tri: 'lots' | 'prix' | 'nom'
}

export const FILTRES_VIDES: Filtres = { texte: '', gouvernorat: '', surface: null, prixMax: null, dispo: false, encheres: false, dr: false, cahier: false, tri: 'lots' }

const sansAccents = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export function filtrer(zones: Zone[], f: Filtres): Zone[] {
  const t = sansAccents(f.texte.trim())
  const r = zones.filter((z) =>
    (!t || sansAccents(z.nom).includes(t) || sansAccents(z.gouvernorat).includes(t) || (z.nom_ar ?? '').includes(f.texte.trim()) || (z.gouvernorat_ar ?? '').includes(f.texte.trim())) &&
    (!f.gouvernorat || z.gouvernorat === f.gouvernorat) &&
    (!f.dispo || z.lots_disponibles > 0) &&
    (!f.encheres || z.lots_aux_encheres > 0) &&
    (!f.dr || z.developpement_regional) &&
    (!f.cahier || z.cahier_des_charges) &&
    (f.prixMax == null || (z.prix_m2_dt != null && z.prix_m2_dt <= f.prixMax)) &&
    (f.surface == null || (z.surface_lot_max_m2 != null && z.surface_lot_max_m2 >= f.surface)))
  return r.sort((a, b) =>
    f.tri === 'nom' ? a.nom.localeCompare(b.nom)
      : f.tri === 'prix' ? (a.prix_m2_dt ?? 1e9) - (b.prix_m2_dt ?? 1e9)
        : f.encheres ? b.lots_aux_encheres - a.lots_aux_encheres : b.lots_disponibles - a.lots_disponibles)
}

interface Props {
  zones: Zone[]
  resultats: Zone[]
  chargement: boolean
  filtres: Filtres
  setFiltres: (f: Filtres) => void
  onZone: (id: number) => void
  comparer: number[]
  basculerComparer: (id: number) => void
  survol: (id: number | null) => void
}

export function Recherche({ zones, resultats, chargement, filtres, setFiltres, onZone, comparer, basculerComparer, survol }: Props) {
  const { t, langue } = useLangue()
  const nom = useNom()
  const [avances, setAvances] = useState(false)
  const gouvernorats = useMemo(() => {
    const m = new Map<string, string | null>()
    zones.forEach((z) => m.set(z.gouvernorat, z.gouvernorat_ar))
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [zones])
  const total = useMemo(() => zones.reduce((s, z) => s + z.lots_disponibles, 0), [zones])
  const maj = (p: Partial<Filtres>) => setFiltres({ ...filtres, ...p })
  const actifs = filtres.surface != null || filtres.prixMax != null || filtres.dr || filtres.cahier

  return (
    <div className="defile h-full overflow-y-auto">
      {/* chiffres clés */}
      <div className="grid grid-cols-3 gap-2 px-4 pt-3">
        {[
          { v: zones.length, l: t.zones, i: Building2 },
          { v: total, l: t.lotsDispo, i: Sparkles },
          { v: gouvernorats.length, l: t.gouvernorats, i: Landmark },
        ].map(({ v, l, i: I }) => (
          <div key={l} className="rounded-2xl bg-gradient-to-br from-marine to-marine-fonce px-3 py-2.5 text-white shadow-carte">
            <p className="flex items-center gap-1.5 text-lg font-bold leading-none"><I size={15} className="opacity-70" aria-hidden />{chargement ? <span className="inline-block h-4 w-8 animate-pulse rounded bg-white/30" /> : nombre(v, langue)}</p>
            <p className="mt-1 text-[11px] leading-tight opacity-80">{l}</p>
          </div>
        ))}
      </div>

      {/* recherche */}
      <div className="mx-4 my-3 rounded-2xl border border-trait bg-white p-3.5 shadow-carte">
        <h2 className="mb-2.5 flex items-center gap-2.5 font-semibold text-encre">
          <span className="grid size-8 place-items-center rounded-xl bg-sarcelle text-white"><Search size={16} aria-hidden /></span>
          {t.rechercheTitre}
        </h2>
        <label className="relative block">
          <span className="sr-only">{t.recherche}</span>
          <Search size={17} className="pointer-events-none absolute top-1/2 start-3 -translate-y-1/2 text-doux" aria-hidden />
          <input type="search" value={filtres.texte} onChange={(e) => maj({ texte: e.target.value })} placeholder={t.recherche}
            className="h-11 w-full rounded-xl border border-trait bg-fond/60 ps-10 pe-3 outline-none transition focus:border-lien focus:bg-white focus:ring-2 focus:ring-lien/20" />
        </label>
        <label className="mt-2 block">
          <span className="sr-only">{t.gouvernorat}</span>
          <select value={filtres.gouvernorat} onChange={(e) => maj({ gouvernorat: e.target.value })}
            className="h-11 w-full rounded-xl border border-trait bg-fond/60 px-3 outline-none focus:border-lien focus:ring-2 focus:ring-lien/20">
            <option value="">{t.tous}</option>
            {gouvernorats.map(([fr, ar]) => <option key={fr} value={fr}>{nom(fr, ar)}</option>)}
          </select>
        </label>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Puce actif={filtres.dispo} onClick={() => maj({ dispo: !filtres.dispo })}>
            <span className="size-2 rounded-full bg-vert" /> {t.dispoSeulement}
          </Puce>
          <Puce actif={filtres.encheres} onClick={() => maj({ encheres: !filtres.encheres })}>
            <Gavel size={14} aria-hidden /> {t.encheresSeulement}
          </Puce>
        </div>

        <button type="button" onClick={() => setAvances(!avances)} aria-expanded={avances}
          className="mt-2.5 flex w-full items-center gap-2 rounded-xl border border-trait px-3 py-2 text-start text-sm hover:bg-fond">
          <SlidersHorizontal size={16} className="text-sarcelle" aria-hidden />
          <span className="font-medium">{t.filtresAvances}</span>
          {actifs && <span className="size-2 rounded-full bg-alerte" />}
          <ChevronDown size={16} className={clsx('ms-auto transition-transform', avances && 'rotate-180')} aria-hidden />
        </button>
        {avances && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="space-y-3 overflow-hidden pt-3">
            <Champ libelle={t.surface} unite={t.m2} valeur={filtres.surface} pas={500} onChange={(v) => maj({ surface: v })} />
            <Champ libelle={t.prixMax} unite={t.parM2} valeur={filtres.prixMax} pas={5} onChange={(v) => maj({ prixMax: v })} />
            <div className="flex flex-wrap gap-2">
              <Puce actif={filtres.dr} onClick={() => maj({ dr: !filtres.dr })}><Landmark size={14} aria-hidden /> {t.dr}</Puce>
              <Puce actif={filtres.cahier} onClick={() => maj({ cahier: !filtres.cahier })}><FileText size={14} aria-hidden /> {t.avecCahier}</Puce>
            </div>
          </motion.div>
        )}
        <div className="mt-2.5 flex items-center gap-2">
          <button type="button" onClick={() => setFiltres(FILTRES_VIDES)}
            className="flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-xl border border-trait px-3 text-sm font-medium text-doux hover:bg-fond hover:text-marine">
            <RotateCcw size={15} aria-hidden /> {t.reinitialiser}
          </button>
          <label className="ms-auto flex min-w-0 items-center gap-2 whitespace-nowrap text-sm text-doux">
            <span className="sr-only">{t.trier}</span>
            <select value={filtres.tri} onChange={(e) => maj({ tri: e.target.value as Filtres['tri'] })}
              className="h-10 min-w-0 rounded-xl border border-trait bg-white px-2 font-medium text-encre" aria-label={t.trier}>
              <option value="lots">{t.triLots}</option><option value="prix">{t.triPrix}</option><option value="nom">{t.triNom}</option>
            </select>
          </label>
        </div>
      </div>

      <p className="px-5 pb-2 text-sm font-medium text-doux" aria-live="polite">{chargement ? t.chargement : t.zonesTrouvees(resultats.length)}</p>

      {/* résultats */}
      <ul className="space-y-2 px-4 pb-6">
        {chargement && [0, 1, 2, 3, 4].map((i) => (
          <li key={i} className="flex gap-3 rounded-2xl border border-trait bg-white p-3.5" aria-hidden>
            <span className="size-11 animate-pulse rounded-xl bg-brume" />
            <span className="flex-1 space-y-2 pt-1"><span className="block h-4 w-2/3 animate-pulse rounded bg-brume" /><span className="block h-3 w-1/3 animate-pulse rounded bg-brume" /></span>
          </li>
        ))}
        {!chargement && resultats.length === 0 && <li className="rounded-2xl border border-dashed border-trait p-6 text-center text-sm text-doux">{t.aucuneZone}</li>}
        {resultats.map((z, i) => {
          const choisie = comparer.includes(z.zone_id)
          return (
            <motion.li key={z.zone_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.02 }}
              onMouseEnter={() => survol(z.zone_id)} onMouseLeave={() => survol(null)}
              className="group relative rounded-2xl border border-trait bg-white shadow-sm transition hover:-translate-y-0.5 hover:border-lien/40 hover:shadow-carte">
              <button type="button" onClick={() => onZone(z.zone_id)} className="block w-full p-3.5 pe-12 text-start">
                <div className="flex items-start gap-3">
                  <span className={clsx('mt-0.5 grid size-11 shrink-0 place-items-center rounded-xl text-sm font-bold text-white',
                    filtres.encheres ? 'bg-alerte' : z.lots_disponibles > 0 ? 'bg-vert' : z.lots_aux_encheres > 0 ? 'bg-alerte' : 'bg-[#7C8A93]')}>
                    {filtres.encheres ? z.lots_aux_encheres : z.lots_disponibles}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-encre group-hover:text-marine">{nom(z.nom, z.nom_ar)}</span>
                    <span className="block text-[13px] text-doux">{nom(z.gouvernorat, z.gouvernorat_ar)}</span>
                    <span className="mt-1.5 flex flex-wrap gap-1.5 text-[12px]">
                      {z.prix_m2_dt != null
                        ? <span className="rounded-md bg-fond px-1.5 py-0.5 font-semibold text-marine">{nombre(z.prix_m2_dt, langue)} {t.parM2}</span>
                        : <span className="rounded-md bg-fond px-1.5 py-0.5 text-doux">{t.prixNonPublie}</span>}
                      {z.lots_aux_encheres > 0 && <span className="rounded-md bg-alerte/10 px-1.5 py-0.5 font-medium text-alerte">{z.lots_aux_encheres} · {t.encheres}</span>}
                      {z.developpement_regional && <span className="rounded-md bg-sauge px-1.5 py-0.5 text-[#3c5a1e]">{t.dr}</span>}
                    </span>
                  </span>
                </div>
              </button>
              <button type="button" onClick={() => basculerComparer(z.zone_id)} aria-pressed={choisie}
                aria-label={`${choisie ? t.retirerComparaison : t.ajouterComparaison} ${z.nom}`} title={choisie ? t.retirerComparaison : t.ajouterComparaison}
                className={clsx('absolute top-3 end-3 grid size-9 place-items-center rounded-lg border transition',
                  choisie ? 'border-marine bg-marine text-white' : 'border-trait text-doux opacity-70 hover:text-marine group-hover:opacity-100')}>
                <Scale size={16} aria-hidden />
              </button>
            </motion.li>
          )
        })}
      </ul>
    </div>
  )
}

function Puce({ actif, onClick, children }: { actif: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={actif}
      className={clsx('flex min-h-9 items-center gap-1.5 rounded-full border px-2.5 text-[12.5px] font-medium transition',
        actif ? 'border-marine bg-marine text-white' : 'border-trait bg-white text-doux hover:border-marine/40 hover:text-marine')}>
      {children}
    </button>
  )
}

function Champ({ libelle, unite, valeur, pas, onChange }: { libelle: string; unite: string; valeur: number | null; pas: number; onChange: (v: number | null) => void }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-doux">{libelle}</span>
      <span className="flex h-11 items-center rounded-xl border border-trait bg-fond/60 focus-within:border-lien focus-within:ring-2 focus-within:ring-lien/20">
        <input type="number" min={0} step={pas} inputMode="numeric" value={valeur ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          className="h-full min-w-0 flex-1 bg-transparent px-3 outline-none" />
        <span className="pe-3 text-doux">{unite}</span>
      </span>
    </label>
  )
}
