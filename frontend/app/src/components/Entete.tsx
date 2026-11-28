import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Gavel, Globe, Home, LogIn, MapPin, Scale } from 'lucide-react'
import clsx from 'clsx'
import logo from '../assets/afi/logo.png'
import { useLangue } from '../langue'
import type { LangueUI } from '../types'

interface Props {
  encheres: boolean
  onEncheres: () => void
  nbComparer: number
  onComparer: () => void
  onAccueil: () => void
}

export function Entete({ encheres, onEncheres, nbComparer, onComparer, onAccueil }: Props) {
  const { t, langue } = useLangue()
  return (
    <header className="relative z-30 bg-white">
      <div className="relative flex h-[84px] items-center gap-5 overflow-hidden px-5 lg:px-8">
        {/* fond : arcs du logo, très discrets */}
        <svg aria-hidden className="pointer-events-none absolute -end-24 -top-40 h-[420px] w-[620px] opacity-[0.10]" viewBox="0 0 400 400">
          <path d="M200 20a180 180 0 0 1 180 180" fill="none" stroke="#E94E1B" strokeWidth="34" />
          <path d="M380 200a180 180 0 0 1-180 180" fill="none" stroke="#0A6FA9" strokeWidth="34" />
          <path d="M200 70a130 130 0 0 1 130 130" fill="none" stroke="#FFED00" strokeWidth="24" />
          <path d="M330 200a130 130 0 0 1-130 130" fill="none" stroke="#008D36" strokeWidth="24" />
        </svg>
        <a href="https://www.afi.nat.tn" target="_blank" rel="noopener noreferrer" className="shrink-0" aria-label={t.agence}>
          <img src={logo} alt={t.agence} className="h-[68px] w-auto" />
        </a>
        <div className="hidden h-12 w-px bg-trait sm:block" />
        <div className="flex min-w-0 items-center gap-3">
          <span className="hidden size-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-sarcelle to-marine text-white shadow-carte sm:grid">
            <MapPin size={24} aria-hidden />
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold uppercase tracking-wide text-marine lg:text-[26px]">
              {t.titre}
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="h-1 w-6 rounded bg-sarcelle" /><span className="h-1 w-4 rounded bg-orange" /><span className="h-1 w-3 rounded bg-jaune" />
              <p className="truncate text-xs text-doux lg:text-sm">{t.sousTitre}</p>
            </div>
          </div>
        </div>
        <div className="ms-auto hidden text-end xl:block">
          <p className="text-[13px] font-semibold text-marine">{langue === 'ar' ? 'الجمهورية التونسية' : langue === 'en' ? 'Republic of Tunisia' : 'République tunisienne'}</p>
          <p className="text-xs text-doux">{t.ministere}</p>
        </div>
      </div>

      <nav className="flex h-14 items-center gap-2 border-y border-trait/80 bg-white/90 px-3 backdrop-blur lg:px-6" aria-label="Navigation">
        <button type="button" onClick={onAccueil} className="flex min-h-10 items-center gap-2 rounded-xl px-3 font-medium text-marine hover:bg-fond">
          <Home size={18} aria-hidden /> <span className="hidden sm:inline">{t.accueil}</span>
        </button>
        <div className="ms-auto flex items-center gap-2">
          <button type="button" onClick={onEncheres} aria-pressed={encheres}
            className={clsx('flex min-h-10 items-center gap-2 rounded-xl px-4 font-semibold transition',
              encheres ? 'bg-alerte text-white shadow-carte' : 'bg-sarcelle text-white hover:bg-marine')}>
            <Gavel size={18} aria-hidden /> <span className="hidden sm:inline">{t.encheres}</span>
          </button>
          <button type="button" onClick={onComparer} disabled={nbComparer < 2}
            className="relative flex min-h-10 items-center gap-2 rounded-xl border border-trait px-3 font-medium text-marine transition hover:bg-fond disabled:opacity-50">
            <Scale size={18} aria-hidden /> <span className="hidden md:inline">{t.comparer}</span>
            {nbComparer > 0 && <span className="grid size-5 place-items-center rounded-full bg-marine text-[11px] font-bold text-white">{nbComparer}</span>}
          </button>
          <ChoixLangue />
          <a href="/connexion/" className="flex min-h-10 items-center gap-2 rounded-xl border border-trait px-3 font-medium text-marine transition hover:bg-fond"
            aria-label={langue === 'ar' ? 'تسجيل الدخول' : langue === 'en' ? 'Sign in' : 'Connexion'}>
            <LogIn size={18} aria-hidden className="rtl:rotate-180" />
            <span className="hidden lg:inline">{langue === 'ar' ? 'تسجيل الدخول' : langue === 'en' ? 'Sign in' : 'Connexion'}</span>
          </a>
        </div>
      </nav>
    </header>
  )
}

const LANGUES: { code: LangueUI; court: string; nom: string }[] = [
  { code: 'fr', court: 'FR', nom: 'Français' },
  { code: 'ar', court: 'عربي', nom: 'العربية' },
  { code: 'en', court: 'EN', nom: 'English' },
]

/** Le globe : menu de la langue de tout le site (comme sur la carte actuelle de l'AFI). */
function ChoixLangue() {
  const { langue, changer } = useLangue()
  const [ouvert, setOuvert] = useState(false)
  const boite = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ouvert) return
    const dehors = (e: MouseEvent) => { if (!boite.current?.contains(e.target as Node)) setOuvert(false) }
    document.addEventListener('mousedown', dehors)
    return () => document.removeEventListener('mousedown', dehors)
  }, [ouvert])
  const actuelle = LANGUES.find((l) => l.code === langue)!
  return (
    <div ref={boite} className="relative" onKeyDown={(e) => { if (e.key === 'Escape') setOuvert(false) }}>
      <button type="button" onClick={() => setOuvert(!ouvert)} aria-expanded={ouvert} aria-haspopup="listbox"
        aria-label={`Langue du site · لغة الموقع · Site language : ${actuelle.nom}`}
        className="flex min-h-10 items-center gap-2 rounded-xl border border-trait px-3 font-semibold text-marine transition hover:bg-fond">
        <Globe size={18} aria-hidden />
        <span className={langue === 'ar' ? 'font-arabe' : ''}>{actuelle.court}</span>
        <ChevronDown size={15} className={clsx('transition-transform', ouvert && 'rotate-180')} aria-hidden />
      </button>
      {ouvert && (
        <ul role="listbox" aria-label="Langue · لغة · Language"
          className="absolute end-0 top-12 z-50 w-44 overflow-hidden rounded-xl border border-trait bg-white py-1 shadow-flotte">
          {LANGUES.map((l) => (
            <li key={l.code}>
              <button type="button" role="option" aria-selected={l.code === langue} lang={l.code}
                onClick={() => { changer(l.code); setOuvert(false) }}
                className={clsx('flex min-h-11 w-full items-center gap-2 px-3 text-start hover:bg-fond',
                  l.code === langue ? 'font-semibold text-marine' : 'text-encre', l.code === 'ar' && 'font-arabe')}>
                <span className="flex-1">{l.nom}</span>
                {l.code === langue && <Check size={16} aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
