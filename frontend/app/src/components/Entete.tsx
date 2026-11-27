import { Gavel, Globe, Home, MapPin, Scale } from 'lucide-react'
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
  const { t, langue, changer } = useLangue()
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
          <div className="flex items-center rounded-xl border border-trait p-0.5" role="group" aria-label="Langue">
            <Globe size={16} className="mx-2 text-doux" aria-hidden />
            {(['fr', 'ar', 'en'] as LangueUI[]).map((l) => (
              <button key={l} type="button" onClick={() => changer(l)} aria-pressed={langue === l} lang={l}
                className={clsx('min-h-9 min-w-10 rounded-lg px-2 text-sm font-semibold transition',
                  langue === l ? 'bg-marine text-white' : 'text-doux hover:text-marine')}>
                {l === 'ar' ? <span className="font-arabe">عربي</span> : l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </nav>
    </header>
  )
}
