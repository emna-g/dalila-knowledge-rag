import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BadgePercent, ChevronDown, FileCheck2, MapPinned, Mic, Minus, RotateCcw, SendHorizontal, Square, ThumbsDown, ThumbsUp,
  Volume2, X, AlertTriangle,
} from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api'
import { DICOS_DALILA, LANGUES_DALILA } from '../i18n'
import { useLangue } from '../langue'
import type { LangueDalila, ReponseDalila } from '../types'
import { analyser, Rendu, type Analyse } from './rendu'
import mascotte from '../assets/afi/mascotte.webp'
import visage from '../assets/afi/visage.webp'

export type Etat = 'repos' | 'ecoute' | 'recherche' | 'parle'
export interface Demande { texte: string; contexte?: Record<string, unknown> | null; n: number }
interface Message {
  id: number
  role: 'visiteur' | 'dalila'
  texte: string
  lang: LangueDalila
  reponse?: ReponseDalila
  analyse?: Analyse
  avis?: boolean
  parVoix?: boolean
}

interface Props {
  ouvert: boolean
  onFermer: () => void
  demande: Demande | null
  contexte: Record<string, unknown> | null
  onRetirerContexte: () => void
  onZone: (id: number) => void
  onLot: (id: number) => void
  onCiter: (ids: number[]) => void
}

const HISTORIQUE = 20
let suivant = 1

export function Dalila({ ouvert, onFermer, demande, contexte, onRetirerContexte, onZone, onLot, onCiter }: Props) {
  const { t: tUI, langue } = useLangue()
  const [lang, setLang] = useState<LangueDalila>(() => (localStorage.getItem('dalila_lang') as LangueDalila) || langue)
  const [messages, setMessages] = useState<Message[]>([])
  const [saisie, setSaisie] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [etat, setEtat] = useState<Etat>('repos')
  const [etape, setEtape] = useState(0)
  const [ecoule, setEcoule] = useState(0)
  const [note, setNote] = useState<{ texte: string; erreur?: boolean } | null>(null)
  const [service, setService] = useState<'pret' | 'prepare' | 'absent' | null>(null)
  const [consentement, setConsentement] = useState(false)
  const [lecture, setLecture] = useState<number | null>(null)
  const [menuLangue, setMenuLangue] = useState(false)
  const session = useRef(crypto.randomUUID?.() ?? String(Date.now()))
  const fil = useRef<HTMLDivElement>(null)
  const champ = useRef<HTMLTextAreaElement>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const enregistreur = useRef<MediaRecorder | null>(null)
  const prochaineParVoix = useRef(false)
  const rtl = LANGUES_DALILA.find((l) => l.code === lang)?.rtl ?? false
  // les textes du panneau suivent la langue choisie pour Dalila (arabe et dialectes : textes en arabe)
  const t = DICOS_DALILA[lang] ?? tUI

  useEffect(() => { localStorage.setItem('dalila_lang', lang) }, [lang])
  // l'interface change de langue : Dalila suit, sauf si le visiteur a choisi un dialecte
  useEffect(() => { setLang((l) => (['aeb', 'arq', 'ayl'].includes(l) && langue === 'ar' ? l : langue)) }, [langue])

  /* service prêt ? */
  useEffect(() => {
    if (!ouvert) return
    let fini = false
    const verifier = () => api.sante().then((s) => {
      if (fini) return
      setService(s.pret ? 'pret' : 'prepare')
      if (!s.pret) setTimeout(verifier, 8000)
    }).catch(() => !fini && setService('absent'))
    verifier()
    return () => { fini = true }
  }, [ouvert])

  useEffect(() => {
    const dernier = messages[messages.length - 1]
    if (dernier?.role === 'dalila' && !occupe) {
      // une réponse arrive : on la montre depuis son début (une longue réponse ne défile pas jusqu'en bas)
      fil.current?.querySelector(`[data-message="${dernier.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    if (messages.length || occupe || consentement) fil.current?.scrollTo({ top: fil.current.scrollHeight, behavior: 'smooth' })
  }, [messages, occupe, note, consentement])
  useEffect(() => { if (ouvert) setTimeout(() => champ.current?.focus(), 250) }, [ouvert])

  /* attente : étapes et secondes */
  useEffect(() => {
    if (!occupe) return
    const debut = Date.now()
    const i = setInterval(() => {
      const s = Math.round((Date.now() - debut) / 1000)
      setEcoule(s); setEtape(Math.min(3, Math.floor(s / 6)))
    }, 500)
    return () => { clearInterval(i); setEcoule(0); setEtape(0) }
  }, [occupe])

  const arreterLecture = useCallback(() => {
    audio.current?.pause(); audio.current = null; setLecture(null)
    setEtat((e) => (e === 'parle' ? 'repos' : e))
  }, [])

  const lire = useCallback(async (m: Message) => {
    if (lecture === m.id) { arreterLecture(); return }
    arreterLecture()
    setLecture(m.id)
    try {
      const wav = await api.voix(m.texte, m.lang)
      if (!wav) { setLecture(null); setNote({ texte: t.dlPasDeVoix }); return }
      const url = URL.createObjectURL(wav)
      const a = new Audio(url)
      audio.current = a
      a.onended = () => { URL.revokeObjectURL(url); if (audio.current === a) arreterLecture() }
      setEtat('parle')
      await a.play()
    } catch { setLecture(null); setEtat('repos') }
  }, [lecture, arreterLecture, t.dlPasDeVoix])

  const envoyer = useCallback(async (texte: string, ctx?: Record<string, unknown> | null) => {
    texte = texte.trim().slice(0, 500)
    if (!texte || occupe) return
    const parVoix = prochaineParVoix.current; prochaineParVoix.current = false
    const langEnvoi = lang
    const historique = messages.slice(-HISTORIQUE).map((m) => ({ role: m.role === 'visiteur' ? 'user' : 'assistant', content: m.texte }))
    setMessages((ms) => [...ms, { id: suivant++, role: 'visiteur', texte, lang: langEnvoi }])
    setSaisie(''); setNote(null); setOccupe(true); setEtat('recherche')
    let r: ReponseDalila
    try {
      r = await api.demander({ message: texte, history: historique, lang: langEnvoi, contexte: ctx ?? contexte, session_id: session.current })
    } catch (e) {
      r = { message: (e as Error).name === 'AbortError' ? t.dlDelai : t.dlHorsService, log_id: null, source: 'repli', action: null, duree_s: 0 }
    }
    const a = analyser(r.message)
    const msg: Message = { id: suivant++, role: 'dalila', texte: r.message, lang: langEnvoi, reponse: r, analyse: a, parVoix }
    setMessages((ms) => [...ms, msg])
    setOccupe(false); setEtat('repos')
    if (a.zones.length) onCiter([...new Set(a.zones.map((z) => z.id))])
    if (parVoix) lire(msg)
  }, [occupe, lang, messages, contexte, t.dlDelai, t.dlHorsService, onCiter, lire])

  /* questions venues de la carte */
  const derniere = useRef(0)
  useEffect(() => {
    if (demande && demande.n !== derniere.current) { derniere.current = demande.n; envoyer(demande.texte, demande.contexte) }
  }, [demande, envoyer])

  /* micro */
  const enregistrer = async () => {
    arreterLecture()
    try {
      const flux = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(flux)
      const morceaux: Blob[] = []
      rec.ondataavailable = (e) => e.data.size && morceaux.push(e.data)
      rec.onstop = async () => {
        flux.getTracks().forEach((p) => p.stop())
        enregistreur.current = null
        setEtat('recherche'); setNote({ texte: t.dlTranscription })
        try {
          const j = await api.transcrire(new Blob(morceaux, { type: rec.mimeType || 'audio/webm' }))
          setSaisie(j.texte.trim()); prochaineParVoix.current = true
          setNote({ texte: t.dlVerifier })      // le texte reconnu est vu, et corrigé si besoin, AVANT l'envoi
          champ.current?.focus()
        } catch (e) { setNote({ texte: `${t.dlMicroIndispo} (${(e as Error).message})`, erreur: true }) }
        setEtat('repos')
      }
      enregistreur.current = rec
      rec.start(); setEtat('ecoute'); setNote({ texte: t.dlEcoute })
    } catch (e) { setNote({ texte: `${t.dlMicroIndispo} (${(e as Error).name})`, erreur: true }) }
  }
  const micro = () => {
    if (enregistreur.current?.state === 'recording') { enregistreur.current.stop(); return }
    if (localStorage.getItem('dalila_micro') !== 'oui') { setConsentement(true); return }
    enregistrer()
  }
  const microDispo = typeof window !== 'undefined' && !!navigator.mediaDevices && 'MediaRecorder' in window

  const avis = (m: Message, utile: boolean) => {
    if (m.reponse?.log_id == null) return
    api.avis(m.reponse.log_id, utile).catch(() => {})
    setMessages((ms) => ms.map((x) => (x.id === m.id ? { ...x, avis: utile } : x)))
  }

  const nouvelle = () => { arreterLecture(); setMessages([]); setNote(null); onCiter([]); session.current = crypto.randomUUID?.() ?? String(Date.now()) }
  const cas = useMemo(() => [MapPinned, BadgePercent, FileCheck2], [])
  const nomLangue = LANGUES_DALILA.find((l) => l.code === lang)?.nom

  return (
    <AnimatePresence>
      {ouvert && (
        <motion.aside initial={{ x: rtl ? -40 : 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: rtl ? -40 : 40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          className="fixed inset-0 z-40 flex flex-col bg-white lg:static lg:inset-auto lg:z-auto lg:h-full lg:w-[440px] lg:shrink-0 lg:border-s lg:border-trait"
          aria-label={t.dlNom} dir={rtl ? 'rtl' : 'ltr'} lang={['aeb', 'arq', 'ayl'].includes(lang) ? 'ar' : lang}
          onKeyDown={(e) => { if (e.key === 'Escape') onFermer() }}>

          {/* en-tête */}
          <div className="relative z-20 flex items-center gap-3 border-b border-trait bg-gradient-to-r from-white to-fond px-4 py-3">
            <Anneau etat={etat} taille={52} />
            <div className="min-w-0 flex-1">
              <p className="text-lg font-bold leading-tight text-marine">{t.dlNom}</p>
              <p className="flex items-center gap-1.5 text-xs text-doux">
                <span className={clsx('size-2 rounded-full', service === 'pret' ? 'bg-vert' : service === 'prepare' ? 'bg-orange animate-pulse' : service === 'absent' ? 'bg-alerte' : 'bg-trait')} />
                {t.dlRole}
              </p>
            </div>
            <div className="relative">
              <button type="button" onClick={() => setMenuLangue(!menuLangue)} aria-expanded={menuLangue} aria-label={t.dlLangue}
                className="flex min-h-10 items-center gap-1 rounded-xl border border-trait bg-white px-2.5 text-[13px] font-medium hover:bg-fond">
                {nomLangue?.split(' · ')[0]} <ChevronDown size={14} aria-hidden />
              </button>
              <AnimatePresence>
                {menuLangue && (
                  <motion.ul initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className="absolute end-0 top-12 z-50 w-52 overflow-hidden rounded-xl border border-trait bg-white py-1 shadow-flotte" role="listbox" aria-label={t.dlLangue}>
                    {LANGUES_DALILA.map((l) => (
                      <li key={l.code}>
                        <button type="button" role="option" aria-selected={l.code === lang} onClick={() => { setLang(l.code); setMenuLangue(false) }}
                          className={clsx('flex min-h-10 w-full items-center px-3 text-start text-sm hover:bg-fond', l.code === lang && 'font-semibold text-marine')}
                          dir={l.rtl ? 'rtl' : 'ltr'}>{l.nom}</button>
                      </li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </div>
            {messages.length > 0 && (
              <button type="button" onClick={nouvelle} aria-label={t.dlNouvelle} title={t.dlNouvelle} className="grid size-10 place-items-center rounded-xl text-doux hover:bg-fond hover:text-marine">
                <RotateCcw size={18} aria-hidden />
              </button>
            )}
            <button type="button" onClick={onFermer} aria-label={t.dlReduire} title={t.dlReduire} className="grid size-10 place-items-center rounded-xl text-doux hover:bg-fond hover:text-marine">
              <span className="hidden lg:block"><Minus size={18} aria-hidden /></span><span className="lg:hidden"><X size={20} aria-hidden /></span>
            </button>
          </div>

          {service && service !== 'pret' && (
            <p className={clsx('flex items-center gap-2 px-4 py-2 text-[13px]', service === 'absent' ? 'bg-alerte/10 text-[#a3330f]' : 'bg-sable text-doux')} role="status">
              <AlertTriangle size={15} aria-hidden /> {service === 'absent' ? t.dlHorsService : t.dlPreparation}
            </p>
          )}

          {/* conversation */}
          <div ref={fil} className="defile flex-1 space-y-4 overflow-y-auto bg-fond/70 px-4 py-5" aria-live="polite">
            {messages.length === 0 && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <div className="flex items-end gap-3">
                  <img src={mascotte} alt="" className="h-52 w-auto shrink-0 drop-shadow-xl" />
                  <div className="relative mb-12 rounded-2xl rounded-es-sm bg-white p-4 shadow-carte">
                    <p className="font-bold text-marine">{t.dlBonjour}</p>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-doux">{t.dlIntro}</p>
                  </div>
                </div>
                <div className="mt-2 space-y-2.5">
                  {t.dlCas.map((c, i) => {
                    const I = cas[i]
                    const teinte = ['bg-lien', 'bg-sarcelle', 'bg-orange'][i]
                    return (
                      <section key={c.titre} className="rounded-2xl border border-trait bg-white p-3.5 shadow-sm">
                        <h3 className="flex items-center gap-2.5 text-[14px] font-semibold">
                          <span className={clsx('grid size-8 place-items-center rounded-full text-white', teinte)}><I size={16} aria-hidden /></span>
                          <span><span className="block">{c.titre}</span><span className="block text-xs font-normal text-doux">{c.texte}</span></span>
                        </h3>
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {c.questions.map((q) => (
                            <button key={q} type="button" onClick={() => envoyer(q)}
                              className="min-h-9 rounded-xl border border-marine/20 bg-marine/[0.03] px-3 py-1.5 text-start text-[13px] font-medium text-marine transition hover:border-marine hover:bg-marine hover:text-white">
                              {q}
                            </button>
                          ))}
                        </div>
                      </section>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {messages.map((m) => m.role === 'visiteur' ? (
              <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="ms-auto w-fit max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-sm bg-marine px-4 py-2.5 text-[15px] text-white shadow-sm" dir="auto">
                {m.texte}
              </motion.div>
            ) : (
              <motion.div key={m.id} data-message={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex scroll-mt-3 gap-2.5">
                <img src={visage} alt="" className="mt-1 size-9 shrink-0 rounded-full border-2 border-white object-cover shadow" />
                <div className={clsx('min-w-0 flex-1 rounded-2xl rounded-ss-sm border bg-white p-3.5 shadow-sm', m.reponse?.source === 'repli' ? 'border-alerte/40' : 'border-trait')} dir="auto">
                  <Rendu analyse={m.analyse!} onZone={onZone} onLot={onLot} libelleLot={t.lot} libelleSources={t.dlSources} />
                  {m.analyse!.choix.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {m.analyse!.choix.map((c) => (
                        <button key={c} type="button" disabled={occupe} onClick={() => envoyer(c)}
                          className="min-h-9 rounded-xl border border-marine bg-white px-3 text-start text-[13px] font-semibold text-marine transition hover:bg-marine hover:text-white disabled:opacity-50" dir="auto">
                          {c}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex items-center gap-1 border-t border-brume pt-2 text-xs text-doux">
                    <span className="me-auto">{m.avis != null ? t.dlMerci : m.reponse?.duree_s ? `${Math.round(m.reponse.duree_s)} ${t.dlSecondes}` : ''}</span>
                    <Icone etiquette={lecture === m.id ? t.dlStop : t.dlLire} actif={lecture === m.id} onClick={() => lire(m)}>
                      {lecture === m.id ? <Square size={15} aria-hidden /> : <Volume2 size={16} aria-hidden />}
                    </Icone>
                    {m.reponse?.log_id != null && (<>
                      <Icone etiquette={t.dlUtile} actif={m.avis === true} onClick={() => avis(m, true)}><ThumbsUp size={15} aria-hidden /></Icone>
                      <Icone etiquette={t.dlPasUtile} actif={m.avis === false} onClick={() => avis(m, false)}><ThumbsDown size={15} aria-hidden /></Icone>
                    </>)}
                  </div>
                </div>
              </motion.div>
            ))}

            {occupe && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3" role="status">
                <Anneau etat="recherche" taille={36} />
                <div className="rounded-2xl bg-white px-4 py-2.5 text-sm text-doux shadow-sm">
                  <span className="me-2">{t.dlReflechit[etape]}</span>
                  <span className="points me-2 inline-flex gap-1 text-marine"><span /><span /><span /></span>
                  <span className="tabular-nums text-xs">{ecoule} {t.dlSecondes}</span>
                </div>
              </motion.div>
            )}

            {consentement && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} role="dialog" aria-label={t.dlConsentTitre}
                className="rounded-2xl border border-ciel bg-white p-4 shadow-carte">
                <p className="flex items-center gap-2 font-semibold text-marine"><Mic size={17} aria-hidden /> {t.dlConsentTitre}</p>
                <p className="mt-1.5 text-sm text-doux">{t.dlConsent}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" autoFocus onClick={() => { localStorage.setItem('dalila_micro', 'oui'); setConsentement(false); enregistrer() }}
                    className="min-h-10 rounded-xl bg-marine px-4 text-sm font-semibold text-white hover:bg-marine-fonce">{t.dlAutoriser}</button>
                  <button type="button" onClick={() => { setConsentement(false); champ.current?.focus() }}
                    className="min-h-10 rounded-xl border border-trait px-4 text-sm font-semibold text-marine hover:bg-fond">{t.dlEcrire}</button>
                </div>
              </motion.div>
            )}
            {note && <p className={clsx('text-center text-[13px]', note.erreur ? 'text-[#a3330f]' : 'text-doux')} role={note.erreur ? 'alert' : undefined}>{note.texte}</p>}
          </div>

          {/* contexte venu de la carte */}
          <AnimatePresence>
            {contexte && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                className="flex items-center gap-2 border-t border-trait bg-sauge px-4 py-2 text-[13px]">
                <MapPinned size={15} className="shrink-0 text-[#3c5a1e]" aria-hidden />
                <span className="min-w-0 flex-1 truncate"><span className="text-doux">{t.dlContexte} </span><strong>{String(contexte.nom ?? '')}</strong></span>
                <button type="button" onClick={onRetirerContexte} aria-label={t.fermer} className="grid size-8 place-items-center rounded-lg hover:bg-white/60"><X size={15} aria-hidden /></button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* saisie */}
          <form className="border-t border-trait bg-white p-3" onSubmit={(e) => { e.preventDefault(); envoyer(saisie) }}>
            <div className={clsx('flex items-end gap-2 rounded-2xl border bg-fond/60 p-1.5 transition focus-within:border-lien focus-within:bg-white focus-within:ring-2 focus-within:ring-lien/20',
              etat === 'ecoute' ? 'border-ciel ring-2 ring-ciel/30' : 'border-trait')}>
              <label htmlFor="dalila-champ" className="sr-only">{t.dlPlaceholder}</label>
              <textarea id="dalila-champ" ref={champ} value={saisie} rows={1} maxLength={500} dir="auto" placeholder={t.dlPlaceholder}
                onChange={(e) => { setSaisie(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px' }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); envoyer(saisie) } }}
                className="max-h-36 min-h-10 flex-1 resize-none overflow-y-auto bg-transparent px-2.5 py-2 text-[15px] outline-none" />
              {microDispo && (
                <button type="button" onClick={micro} aria-label={etat === 'ecoute' ? t.dlArreter : t.dlParler} title={etat === 'ecoute' ? t.dlArreter : t.dlParler}
                  className={clsx('grid size-10 shrink-0 place-items-center rounded-xl transition', etat === 'ecoute' ? 'bg-ciel text-white' : 'text-doux hover:bg-white hover:text-marine')}>
                  {etat === 'ecoute' ? <Square size={16} aria-hidden /> : <Mic size={19} aria-hidden />}
                </button>
              )}
              <button type="submit" disabled={occupe || !saisie.trim()} aria-label={t.dlEnvoyer} title={t.dlEnvoyer}
                className="grid size-10 shrink-0 place-items-center rounded-xl bg-marine text-white shadow transition hover:bg-marine-fonce disabled:opacity-40">
                <SendHorizontal size={18} className={rtl ? '-scale-x-100' : ''} aria-hidden />
              </button>
            </div>
            <p className="mt-2 px-1 text-center text-[11px] leading-snug text-doux">{t.dlPied}</p>
          </form>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

/** Les arcs du logo autour du visage de Dalila : repos, écoute, recherche, parle. */
export function Anneau({ etat, taille }: { etat: Etat; taille: number }) {
  return (
    <span className="anneau relative inline-block shrink-0" data-etat={etat} style={{ width: taille, height: taille }} aria-hidden>
      <svg viewBox="0 0 44 44" className="absolute inset-0 size-full">
        <path d="M22 2a20 20 0 0 1 20 20" fill="none" stroke="#17598B" strokeWidth="3" strokeLinecap="round" />
        <path d="M42 22a20 20 0 0 1-20 20" fill="none" stroke="#04B4E3" strokeWidth="3" strokeLinecap="round" />
        <path d="M22 42A20 20 0 0 1 2 22" fill="none" stroke="#008D36" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <img src={visage} alt="" className="absolute rounded-full object-cover" style={{ inset: taille * 0.12, width: taille * 0.76, height: taille * 0.76 }} />
    </span>
  )
}

function Icone({ etiquette, actif, onClick, children }: { etiquette: string; actif?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-label={etiquette} title={etiquette} aria-pressed={actif}
      className={clsx('grid size-9 place-items-center rounded-lg transition', actif ? 'bg-marine/10 text-marine' : 'hover:bg-fond hover:text-marine')}>
      {children}
    </button>
  )
}
