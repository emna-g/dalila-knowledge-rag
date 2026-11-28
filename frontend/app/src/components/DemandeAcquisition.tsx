import { useEffect, useId, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Check, ChevronDown, Download, ExternalLink, FileSignature, Lock, MapPin, X } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api'
import { nombre } from '../i18n'
import { useLangue, useNom } from '../langue'
import type { DemandeEnvoyee, DemandePreremplie } from '../types'

/*
 * BF11 : préparer une demande d'acquisition depuis la conversation ou la fiche d'un lot.
 * Prérempli : le lot (relu dans la base de l'AFI) et le projet de l'étude guidée, si elle a été faite.
 * Le visiteur complète et coche la confirmation ; sans elle, pas de PDF. Rien n'est déposé ni gardé.
 */
interface Props {
  lotId: number | null
  sessionId: string | null
  onFermer: () => void
}

const VIDE: Omit<DemandeEnvoyee, 'lot_id' | 'lang' | 'confirme'> = {
  demandeur: { nom: '', forme_juridique: '', representant: '', telephone: '', courriel: '', adresse: '' },
  projet: { activite: '', produits: '', investissement_dt: null, emplois: null, dont_cadres: null, delai_realisation_mois: null, justification_surface: '' },
}

export function DemandeAcquisition({ lotId, sessionId, onFermer }: Props) {
  const { t, langue } = useLangue()
  const nom = useNom()
  const [pre, setPre] = useState<DemandePreremplie | null>(null)
  const [erreurChargement, setErreurChargement] = useState(false)
  const [d, setD] = useState(VIDE)
  const [confirme, setConfirme] = useState(false)
  const [etat, setEtat] = useState<'saisie' | 'envoi' | 'fait' | 'erreur'>('saisie')
  const [piecesOuvertes, setPiecesOuvertes] = useState(false)

  useEffect(() => {
    if (lotId == null) return
    api.demandePreremplie(lotId, sessionId).then((p) => {
      setPre(p)
      setD((x) => ({ ...x, projet: { ...x.projet, activite: p.projet.activite ?? '', produits: p.projet.produits ?? '' } }))
    }).catch(() => setErreurChargement(true))
  }, [lotId, sessionId])

  useEffect(() => {
    const echap = (e: KeyboardEvent) => { if (e.key === 'Escape') onFermer() }
    window.addEventListener('keydown', echap)
    return () => window.removeEventListener('keydown', echap)
  }, [onFermer])

  const majDemandeur = (k: keyof typeof d.demandeur, v: string) => setD({ ...d, demandeur: { ...d.demandeur, [k]: v } })
  const majProjet = (k: keyof typeof d.projet, v: string | number | null) => setD({ ...d, projet: { ...d.projet, [k]: v } })
  const entier = (v: string) => (v.trim() === '' ? null : Math.max(0, Math.round(Number(v.replace(/[\s,]/g, '')) || 0)))
  const pret = confirme && d.demandeur.nom.trim().length > 1 && d.projet.activite.trim().length > 1

  const telecharger = async () => {
    if (!pre?.lot || !pret) return
    setEtat('envoi')
    try {
      const pdf = await api.demandePdf({ ...d, lot_id: pre.lot.lot_id, confirme: true, lang: langue })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(pdf)
      a.download = `demande-acquisition-lot-${pre.lot.numero}.pdf`
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 2000)
      setEtat('fait')
    } catch {
      setEtat('erreur')
    }
  }

  const lot = pre?.lot
  const zone = pre?.zone
  return (
    <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-nuit/50 sm:items-center sm:p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onFermer() }}>
      <motion.div role="dialog" aria-modal="true" aria-labelledby="titre-demande" initial={{ y: 30 }} animate={{ y: 0 }}
        className="flex max-h-[94dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-flotte sm:rounded-3xl">
        <header className="flex items-start gap-3 border-b border-trait px-5 py-4">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-marine/10 text-marine"><FileSignature size={20} aria-hidden /></span>
          <div className="min-w-0">
            <h2 id="titre-demande" className="text-lg font-bold text-marine">{t.daTitre}</h2>
            <p className="text-sm text-doux">{t.daIntro}</p>
          </div>
          <button type="button" onClick={onFermer} aria-label={t.fermer} className="ms-auto grid size-9 shrink-0 place-items-center rounded-lg text-doux hover:bg-fond"><X size={18} aria-hidden /></button>
        </header>

        <div className="defile flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {lotId == null ? (
            <Note ton="info" Icone={MapPin}>{t.daChoisirLot}</Note>
          ) : erreurChargement ? (
            <Note ton="alerte" Icone={AlertTriangle}>{t.daErreur}</Note>
          ) : !pre ? (
            <div className="space-y-2" aria-busy="true">{[0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-fond" />)}</div>
          ) : (
            <>
              {/* le lot : relu dans la base, pas modifiable */}
              <section aria-labelledby="da-lot">
                <h3 id="da-lot" className="mb-2 text-sm font-bold uppercase tracking-wide text-doux">{t.daLot}</h3>
                {lot && zone && (
                  <div className="rounded-2xl border border-trait bg-fond/60 p-4">
                    <p className="font-bold text-marine">{t.lot} {lot.numero} · {nom(zone.nom, zone.nom_ar)} <span className="font-normal text-doux">({nom(zone.gouvernorat, zone.gouvernorat_ar)})</span></p>
                    <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
                      <div><dt className="text-doux">{t.m2}</dt><dd className="font-semibold">{nombre(lot.surface_m2, langue)}</dd></div>
                      <div><dt className="text-doux">{t.parM2}</dt><dd className="font-semibold">{nombre(lot.prix_m2_dt, langue)}{lot.prix_m2_a_confirmer ? ' *' : ''}</dd></div>
                      <div><dt className="text-doux">{t.prixTerrain}</dt><dd className="font-semibold">{lot.prix_terrain_dt != null ? `${nombre(lot.prix_terrain_dt, langue)} ${t.dt}` : '—'}</dd></div>
                    </dl>
                    {zone.developpement_regional && <p className="mt-2 w-fit rounded-md bg-sauge px-2 py-0.5 text-xs font-medium text-[#3c5a1e]">{t.dr}{zone.groupe ? ` · G${zone.groupe}` : ''}</p>}
                  </div>
                )}
                {!pre.lot_disponible && <div className="mt-2"><Note ton="alerte" Icone={AlertTriangle}>{t.daLotNonDispo}</Note></div>}
              </section>

              <section aria-labelledby="da-dem">
                <h3 id="da-dem" className="mb-1 text-sm font-bold uppercase tracking-wide text-doux">{t.daDemandeur}</h3>
                <p className="mb-3 flex items-center gap-1.5 text-xs text-doux"><Lock size={13} aria-hidden /> {t.daPrive}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Champ libelle={t.daNom} requis valeur={d.demandeur.nom} onChange={(v) => majDemandeur('nom', v)} max={150} large autoComplete="organization" />
                  <Champ libelle={t.daForme} valeur={d.demandeur.forme_juridique} onChange={(v) => majDemandeur('forme_juridique', v)} max={80} />
                  <Champ libelle={t.daRepresentant} valeur={d.demandeur.representant} onChange={(v) => majDemandeur('representant', v)} max={150} autoComplete="name" />
                  <Champ libelle={t.daTelephone} valeur={d.demandeur.telephone} onChange={(v) => majDemandeur('telephone', v)} max={40} type="tel" autoComplete="tel" />
                  <Champ libelle={t.daCourriel} valeur={d.demandeur.courriel} onChange={(v) => majDemandeur('courriel', v)} max={120} type="email" autoComplete="email" />
                  <Champ libelle={t.daAdresse} valeur={d.demandeur.adresse} onChange={(v) => majDemandeur('adresse', v)} max={300} large autoComplete="street-address" />
                </div>
              </section>

              <section aria-labelledby="da-proj">
                <h3 id="da-proj" className="mb-1 text-sm font-bold uppercase tracking-wide text-doux">{t.daProjet}</h3>
                {Object.keys(pre.projet).length > 0 && <p className="mb-3 flex items-center gap-1.5 text-xs font-medium text-vert-texte"><Check size={13} aria-hidden /> {t.daEtude}</p>}
                <div className="grid gap-3 sm:grid-cols-2">
                  <Champ libelle={t.daActivite} requis valeur={d.projet.activite} onChange={(v) => majProjet('activite', v)} max={300} large />
                  <Champ libelle={t.daProduits} valeur={d.projet.produits} onChange={(v) => majProjet('produits', v)} max={300} large />
                  <Champ libelle={t.daInvestissement} valeur={d.projet.investissement_dt?.toString() ?? ''} onChange={(v) => majProjet('investissement_dt', entier(v))} type="number"
                    aide={pre.projet.investissement_texte ? `${t.daIndication} : ${pre.projet.investissement_texte}` : undefined} />
                  <Champ libelle={t.daDelai} valeur={d.projet.delai_realisation_mois?.toString() ?? ''} onChange={(v) => majProjet('delai_realisation_mois', entier(v))} type="number" />
                  <Champ libelle={t.daEmplois} valeur={d.projet.emplois?.toString() ?? ''} onChange={(v) => majProjet('emplois', entier(v))} type="number"
                    aide={pre.projet.emplois_texte ? `${t.daIndication} : ${pre.projet.emplois_texte}` : undefined} />
                  <Champ libelle={t.daCadres} valeur={d.projet.dont_cadres?.toString() ?? ''} onChange={(v) => majProjet('dont_cadres', entier(v))} type="number" />
                  <Champ libelle={t.daJustification} valeur={d.projet.justification_surface} onChange={(v) => majProjet('justification_surface', v)} max={1500} large multiligne
                    aide={pre.projet.surface_texte ? `${t.daIndication} : ${pre.projet.surface_texte}` : undefined} />
                </div>
              </section>

              <section aria-labelledby="da-depot" className="space-y-2">
                <h3 id="da-depot" className="text-sm font-bold uppercase tracking-wide text-doux">{t.daDepot}</h3>
                <p className="text-sm" dir="auto">{pre.lieu_depot.replace(/\s*—\s*réponses AFI.*$/, '')}</p>
                <button type="button" onClick={() => setPiecesOuvertes(!piecesOuvertes)} aria-expanded={piecesOuvertes}
                  className="flex min-h-10 w-full items-center gap-2 rounded-xl border border-trait px-3 text-start text-sm font-semibold text-marine hover:bg-fond">
                  {t.daPieces}<ChevronDown size={16} className={clsx('ms-auto transition-transform', piecesOuvertes && 'rotate-180')} aria-hidden />
                </button>
                {piecesOuvertes && pre.pieces[0] && (
                  <p className="whitespace-pre-line rounded-xl bg-fond p-3 text-[13px] leading-relaxed" dir="ltr" lang="fr">{pre.pieces[0].texte}</p>
                )}
                <a href={pre.formulaire_officiel} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-lien underline underline-offset-2">
                  {t.daFormulaire}<ExternalLink size={13} aria-hidden />
                </a>
              </section>
            </>
          )}
        </div>

        {pre && lotId != null && (
          <footer className="space-y-3 border-t border-trait bg-fond/60 px-5 py-4">
            {etat === 'fait' && <Note ton="ok" Icone={Check}>{t.daFait}</Note>}
            {etat === 'erreur' && <Note ton="alerte" Icone={AlertTriangle}>{t.daErreur}</Note>}
            <label className="flex cursor-pointer items-start gap-3 text-sm">
              <input type="checkbox" checked={confirme} onChange={(e) => setConfirme(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-marine" />
              <span>{t.daConfirme}</span>
            </label>
            <button type="button" onClick={telecharger} disabled={!pret || etat === 'envoi'}
              className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-marine font-semibold text-white transition hover:bg-marine-fonce disabled:cursor-not-allowed disabled:opacity-45">
              <Download size={18} aria-hidden /> {etat === 'envoi' ? t.daPreparation : t.daTelecharger}
            </button>
          </footer>
        )}
      </motion.div>
    </motion.div>
  )
}

function Note({ ton, Icone, children }: { ton: 'ok' | 'alerte' | 'info'; Icone: typeof Check; children: ReactNode }) {
  return (
    <p role={ton === 'alerte' ? 'alert' : 'status'} className={clsx('flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm',
      ton === 'ok' ? 'bg-vert/10 text-vert-texte' : ton === 'alerte' ? 'bg-alerte/10 text-[#9a3412]' : 'bg-ciel/10 text-marine')}>
      <Icone size={17} className="mt-0.5 shrink-0" aria-hidden /> <span>{children}</span>
    </p>
  )
}

interface ChampProps {
  libelle: string; valeur: string; onChange: (v: string) => void; max?: number; requis?: boolean; large?: boolean
  multiligne?: boolean; type?: string; autoComplete?: string; aide?: string
}

function Champ({ libelle, valeur, onChange, max, requis, large, multiligne, type = 'text', autoComplete, aide }: ChampProps) {
  const id = useId()
  const { t } = useLangue()
  const classe = 'w-full rounded-xl border border-trait bg-white px-3 py-2.5 text-[15px] focus:border-marine focus:outline-none'
  return (
    <div className={clsx(large && 'sm:col-span-2')}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {libelle}{requis && <span className="text-alerte"> * <span className="sr-only">({t.daObligatoire})</span></span>}
      </label>
      {multiligne
        ? <textarea id={id} value={valeur} maxLength={max} rows={3} onChange={(e) => onChange(e.target.value)} className={classe} dir="auto" aria-describedby={aide ? `${id}-aide` : undefined} />
        : <input id={id} type={type} inputMode={type === 'number' ? 'numeric' : undefined} min={type === 'number' ? 0 : undefined} value={valeur} maxLength={max} required={requis}
            autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} className={classe} dir="auto" aria-describedby={aide ? `${id}-aide` : undefined} />}
      {aide && <p id={`${id}-aide`} className="mt-1 text-xs text-doux">{aide}</p>}
    </div>
  )
}
