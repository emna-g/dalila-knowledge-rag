import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, MessageCircle, X } from 'lucide-react'
import { api } from '../api'
import { DISTANCES, EQUIPEMENTS, nombre, unite } from '../i18n'
import { useLangue, useNom } from '../langue'
import type { FicheZone } from '../types'

interface Props { ids: number[]; onFermer: () => void; onZone: (id: number) => void; onDemander: (texte: string) => void; onRetirer: (id: number) => void }

export function Comparateur({ ids, onFermer, onZone, onDemander, onRetirer }: Props) {
  const { t, langue } = useLangue()
  const nom = useNom()
  const [fiches, setFiches] = useState<FicheZone[]>([])
  useEffect(() => { Promise.all(ids.map((id) => api.fiche(id))).then(setFiches).catch(() => setFiches([])) }, [ids])

  const dist = (f: FicheZone, type: string) => f.distances.find((d) => d.type === type)
  const eq = (f: FicheZone, type: string) => f.equipements.find((e) => e.type === type)
  const meilleur = (vals: (number | null | undefined)[], plusPetit = true) => {
    const v = vals.filter((x): x is number => x != null)
    return v.length ? (plusPetit ? Math.min(...v) : Math.max(...v)) : null
  }
  const prixMin = meilleur(fiches.map((f) => f.prix_m2_dt))
  const lotsMax = meilleur(fiches.map((f) => f.lots_disponibles), false)

  const lignes: { titre: string; valeur: (f: FicheZone) => React.ReactNode; top?: (f: FicheZone) => boolean }[] = [
    { titre: t.gouvernorat, valeur: (f) => nom(f.gouvernorat, f.gouvernorat_ar) },
    { titre: t.parM2, valeur: (f) => f.prix_m2_dt != null ? nombre(f.prix_m2_dt, langue) : '—', top: (f) => f.prix_m2_dt != null && f.prix_m2_dt === prixMin },
    { titre: `${t.parM2} · ${t.subventionne}`, valeur: (f) => f.prix_m2_subventionne_dt != null ? nombre(f.prix_m2_subventionne_dt, langue, 2) : '—' },
    { titre: t.lotsDispo, valeur: (f) => nombre(f.lots_disponibles, langue), top: (f) => f.lots_disponibles > 0 && f.lots_disponibles === lotsMax },
    { titre: `${t.lotsDispo} (${t.m2})`, valeur: (f) => f.surface_lot_min_m2 != null ? <bdi dir="ltr">{nombre(f.surface_lot_min_m2, langue)} – {nombre(f.surface_lot_max_m2, langue)}</bdi> : '—' },
    { titre: t.encheres, valeur: (f) => nombre(f.lots_aux_encheres, langue) },
    { titre: t.surfaceTotale, valeur: (f) => f.surface_totale_m2 != null ? `${nombre(f.surface_totale_m2 / 10000, langue, 1)} ${t.ha}` : '—' },
    { titre: t.dr, valeur: (f) => f.developpement_regional ? <Check size={18} className="inline text-vert" aria-label="oui" /> : '—' },
    ...['port', 'aeroport', 'autoroute', 'gare'].map((k) => ({ titre: DISTANCES[k][langue], valeur: (f: FicheZone) => { const d = dist(f, k); return d ? `${nombre(d.km, langue)} ${t.km}` : '—' } })),
    ...['electricite_puissance', 'eau_debit', 'gaz_pression'].map((k) => ({ titre: EQUIPEMENTS[k][langue], valeur: (f: FicheZone) => { const e = eq(f, k); return e ? `${e.valeur ?? '✓'} ${unite(e.unite, langue)}` : '—' } })),
    { titre: t.cahiers, valeur: (f) => f.cahiers.length ? <a href={f.cahiers[0].lien} target="_blank" rel="noopener noreferrer" className="font-medium text-lien underline">PDF</a> : '—' },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 grid place-items-center bg-nuit/50 p-4 backdrop-blur-sm"
      onClick={onFermer} role="dialog" aria-modal="true" aria-label={t.comparaison} onKeyDown={(e) => e.key === 'Escape' && onFermer()}>
      <motion.div initial={{ y: 20, scale: 0.98 }} animate={{ y: 0, scale: 1 }} onClick={(e) => e.stopPropagation()}
        className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl bg-white shadow-flotte">
        <div className="flex items-center border-b border-trait px-6 py-4">
          <h2 className="text-xl font-bold text-marine">{t.comparaison}</h2>
          <button type="button" autoFocus onClick={onFermer} aria-label={t.fermer} className="ms-auto grid size-10 place-items-center rounded-xl text-doux hover:bg-fond"><X size={20} aria-hidden /></button>
        </div>
        <div className="defile overflow-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead className="sticky top-0 bg-white">
              <tr>
                <th className="w-48 p-4" />
                {fiches.map((f) => (
                  <th key={f.zone_id} className="border-s border-trait p-4 text-start align-top">
                    <button type="button" onClick={() => { onZone(f.zone_id); onFermer() }} className="text-lg font-bold text-marine hover:underline">{nom(f.nom, f.nom_ar)}</button>
                    <button type="button" onClick={() => onRetirer(f.zone_id)} className="ms-2 text-xs font-normal text-doux hover:text-alerte">{t.retirerComparaison}</button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lignes.map((l, i) => (
                <tr key={l.titre} className={i % 2 ? 'bg-fond/60' : ''}>
                  <th scope="row" className="p-3 ps-6 text-start font-medium text-doux first-letter:uppercase">{l.titre}</th>
                  {fiches.map((f) => (
                    <td key={f.zone_id} className={`border-s border-trait p-3 font-semibold ${l.top?.(f) ? 'text-vert-texte' : 'text-encre'}`}>
                      {l.valeur(f)}{l.top?.(f) && <span className="ms-1.5 rounded-full bg-vert/10 px-1.5 py-0.5 text-[10px] font-bold uppercase">★</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-3 border-t border-trait bg-fond/60 px-6 py-4">
          <p className="text-xs text-doux">{t.source}</p>
          <button type="button" onClick={() => { onDemander(
            langue === 'ar' ? `قارن بين المناطق: ${fiches.map((f) => nom(f.nom, f.nom_ar)).join('، ')}. أيها أنسب لمشروع صناعي؟`
              : langue === 'en' ? `Compare the zones ${fiches.map((f) => f.nom).join(', ')}. Which one suits an industrial project best?`
                : `Compare les zones ${fiches.map((f) => f.nom).join(', ')}. Laquelle convient le mieux à un projet industriel ?`); onFermer() }}
            className="ms-auto flex min-h-11 items-center gap-2 rounded-xl bg-marine px-5 font-semibold text-white hover:bg-marine-fonce">
            <MessageCircle size={18} aria-hidden /> {t.demanderZone}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
