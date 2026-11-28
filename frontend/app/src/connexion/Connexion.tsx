import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle, ArrowLeft, Brain, Eye, EyeOff, Globe2, KeyRound, Loader2, Lock, LogIn, MessageCircleQuestion, ShieldCheck, UserRound,
} from 'lucide-react'
import clsx from 'clsx'
import logo from '../assets/afi/logo.png'
import mascotte from '../assets/afi/mascotte.webp'
import { useLangue } from '../langue'
import type { LangueUI } from '../types'

/* Page de connexion : le serveur vérifie le compte, pose un cookie de session HttpOnly (la page ne voit jamais le
   jeton) et dit où aller selon le rôle (administrateur : /admin/). */

const TEXTES: Record<LangueUI, Record<string, string>> = {
  fr: {
    espace: 'Espace de gestion', titreMarque: 'Pilotez Dalila', sousMarque: "L'assistante de la carte interactive de l'AFI, en 8 langues.",
    p1: 'Questions mal traitées', p1d: 'Ce que les visiteurs demandent et que Dalila comprend mal, par langue.',
    p2: 'Apprentissage', p2d: 'Les mots et les lieux appris, contrôlés, à annuler en un clic.',
    p3: 'Sources', p3d: "L'état de chaque page officielle lue par Dalila.",
    titre: 'Connexion', sous: "Accès réservé aux comptes de l'AFI.", identifiant: 'Identifiant', mot: 'Mot de passe',
    afficher: 'Afficher le mot de passe', masquer: 'Masquer le mot de passe', majuscules: 'Majuscules activées',
    entrer: 'Se connecter', attente: 'Vérification…', retour: 'Retour à la carte',
    panne: 'Service injoignable : réessayez dans un instant.',
    securite: 'Connexion protégée : session fermée après 30 minutes sans activité, compte bloqué après 5 essais.',
    oubli: 'Mot de passe oublié ? Demandez à l\'administrateur du serveur de le réinitialiser.',
    ministere: "Ministère de l'Industrie, des Mines et de l'Énergie",
  },
  ar: {
    espace: 'فضاء التسيير', titreMarque: 'إدارة دليلة', sousMarque: 'مساعدة الخريطة التفاعلية للوكالة العقارية الصناعية، بثماني لغات.',
    p1: 'الأسئلة غير المفهومة', p1d: 'ما يسأل عنه الزوار ولا تفهمه دليلة جيدًا، حسب اللغة.',
    p2: 'التعلّم', p2d: 'الكلمات والأماكن المتعلَّمة، مراقبة، ويمكن إلغاؤها بنقرة.',
    p3: 'المصادر', p3d: 'حالة كل صفحة رسمية تقرؤها دليلة.',
    titre: 'تسجيل الدخول', sous: 'الدخول مخصّص لحسابات الوكالة العقارية الصناعية.', identifiant: 'المعرّف', mot: 'كلمة العبور',
    afficher: 'إظهار كلمة العبور', masquer: 'إخفاء كلمة العبور', majuscules: 'الأحرف الكبيرة مفعّلة',
    entrer: 'الدخول', attente: 'جارٍ التحقق…', retour: 'العودة إلى الخريطة',
    panne: 'تعذّر الاتصال بالخدمة: أعد المحاولة بعد قليل.',
    securite: 'دخول محمي: تُغلق الجلسة بعد 30 دقيقة دون نشاط، ويُقفل الحساب بعد 5 محاولات.',
    oubli: 'نسيت كلمة العبور؟ اطلب من مسؤول الخادم إعادة تعيينها.',
    ministere: 'وزارة الصناعة والمناجم والطاقة',
  },
  en: {
    espace: 'Management area', titreMarque: 'Run Dalila', sousMarque: "The assistant of AFI's interactive map, in 8 languages.",
    p1: 'Poorly handled questions', p1d: 'What visitors ask and Dalila misunderstands, by language.',
    p2: 'Learning', p2d: 'Words and places learned, checked, undone in one click.',
    p3: 'Sources', p3d: 'The state of every official page Dalila reads.',
    titre: 'Sign in', sous: 'Reserved for AFI accounts.', identifiant: 'Username', mot: 'Password',
    afficher: 'Show password', masquer: 'Hide password', majuscules: 'Caps Lock is on',
    entrer: 'Sign in', attente: 'Checking…', retour: 'Back to the map',
    panne: 'Service unreachable: try again in a moment.',
    securite: 'Protected sign-in: session closed after 30 minutes of inactivity, account locked after 5 attempts.',
    oubli: 'Forgot your password? Ask the server administrator to reset it.',
    ministere: 'Ministry of Industry, Mines and Energy',
  },
}

const LANGUES: { code: LangueUI; court: string }[] = [{ code: 'fr', court: 'FR' }, { code: 'ar', court: 'عربي' }, { code: 'en', court: 'EN' }]

/** Une page de ce site seulement (jamais une adresse externe : pas de redirection ouverte). */
function sure(suite: unknown) {
  return typeof suite === 'string' && suite.startsWith('/') && !suite.startsWith('//') && !suite.includes('\\') ? suite : '/'
}

/** Les arcs du logo de l'AFI, en grand et très discrets. */
function Arcs({ className }: { className?: string }) {
  return (
    <svg aria-hidden className={className} viewBox="0 0 400 400">
      <path d="M200 20a180 180 0 0 1 180 180" fill="none" stroke="#E94E1B" strokeWidth="30" strokeLinecap="round" />
      <path d="M380 200a180 180 0 0 1-180 180" fill="none" stroke="#04B4E3" strokeWidth="30" strokeLinecap="round" />
      <path d="M200 70a130 130 0 0 1 130 130" fill="none" stroke="#FFED00" strokeWidth="22" strokeLinecap="round" />
      <path d="M330 200a130 130 0 0 1-130 130" fill="none" stroke="#008D36" strokeWidth="22" strokeLinecap="round" />
    </svg>
  )
}

export function Connexion() {
  const { langue, changer, rtl } = useLangue()
  const t = TEXTES[langue]
  const [identifiant, setIdentifiant] = useState('')
  const [mot, setMot] = useState('')
  const [voir, setVoir] = useState(false)
  const [majuscules, setMajuscules] = useState(false)
  const [erreur, setErreur] = useState<{ texte: string; bloque: boolean } | null>(null)
  const [attente, setAttente] = useState(false)
  const [secousse, setSecousse] = useState(0)
  const champMot = useRef<HTMLInputElement>(null)

  useEffect(() => {   // déjà connecté : directement à sa page
    fetch('/auth/moi', { credentials: 'same-origin' }).then(async (r) => { if (r.ok) location.replace(sure((await r.json()).suite)) }).catch(() => {})
  }, [])

  const envoyer = async (e: React.FormEvent) => {
    e.preventDefault()
    if (attente || !identifiant.trim() || !mot) return
    setErreur(null)
    setAttente(true)
    try {
      const r = await fetch('/auth/connexion', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifiant: identifiant.trim(), mot_de_passe: mot }),
      })
      const d = await r.json().catch(() => ({}))
      if (r.ok) { location.replace(sure(d.suite)); return }
      setMot('')
      setErreur({ texte: typeof d.detail === 'string' ? d.detail : `Erreur ${r.status}`, bloque: r.status === 429 })
      setSecousse((n) => n + 1)
      champMot.current?.focus()
    } catch {
      setErreur({ texte: t.panne, bloque: false })
    } finally {
      setAttente(false)
    }
  }

  const touche = (e: React.KeyboardEvent<HTMLInputElement>) => setMajuscules(e.getModifierState?.('CapsLock') ?? false)
  const points = [
    { Icone: MessageCircleQuestion, titre: t.p1, texte: t.p1d },
    { Icone: Brain, titre: t.p2, texte: t.p2d },
    { Icone: Globe2, titre: t.p3, texte: t.p3d },
  ]

  return (
    <div className="flex min-h-full flex-col overflow-x-hidden bg-fond lg:flex-row">
      {/* ------------------------------------------------ marque */}
      <aside className="relative overflow-hidden bg-gradient-to-br from-nuit via-marine-fonce to-sarcelle text-white lg:flex lg:w-[46%] lg:flex-col">
        <Arcs className="pointer-events-none absolute -end-40 -top-44 h-[560px] w-[560px] opacity-[0.16]" />
        <Arcs className="pointer-events-none absolute -bottom-56 -start-48 h-[480px] w-[480px] rotate-180 opacity-[0.08]" />
        <div className="relative flex items-center gap-3 px-6 pt-6 lg:px-12 lg:pt-10">
          <span className="grid size-11 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/20 backdrop-blur">
            <ShieldCheck size={22} aria-hidden />
          </span>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">{t.espace}</p>
            <p className="text-sm text-white/80">{t.ministere}</p>
          </div>
        </div>

        <div className="relative flex items-end gap-6 px-6 pb-8 pt-6 lg:flex-1 lg:flex-col lg:items-start lg:justify-center lg:px-12 lg:pb-12">
          <div className="min-w-0 flex-1 lg:flex-none">
            <motion.h2 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
              className="text-2xl font-bold leading-tight sm:text-3xl lg:text-[44px]">
              {t.titreMarque}
            </motion.h2>
            <div className="mt-3 flex items-center gap-2" aria-hidden>
              <span className="h-1.5 w-10 rounded bg-ciel" /><span className="h-1.5 w-6 rounded bg-orange" /><span className="h-1.5 w-4 rounded bg-jaune" />
            </div>
            <p className="mt-4 max-w-md text-sm text-white/80 sm:text-base">{t.sousMarque}</p>

            <ul className="mt-8 hidden max-w-md space-y-4 lg:block lg:max-w-[calc(100%-11rem)] xl:max-w-[calc(100%-13rem)]">
              {points.map(({ Icone, titre, texte }, i) => (
                <motion.li key={titre} initial={{ opacity: 0, x: rtl ? 16 : -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.1 }}
                  className="flex gap-4 rounded-2xl bg-white/[0.07] p-4 ring-1 ring-white/10 backdrop-blur-sm">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10"><Icone size={20} aria-hidden /></span>
                  <span>
                    <span className="block font-semibold">{titre}</span>
                    <span className="block text-sm text-white/75">{texte}</span>
                  </span>
                </motion.li>
              ))}
            </ul>
          </div>
          <motion.img src={mascotte} alt="" aria-hidden initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }}
            className="h-28 w-auto shrink-0 drop-shadow-2xl sm:h-36 lg:absolute lg:bottom-0 lg:end-6 lg:h-[260px] xl:h-[320px]" />
        </div>
      </aside>

      {/* ------------------------------------------------ formulaire */}
      <main className="relative flex flex-1 flex-col px-4 py-8 sm:px-8 lg:py-10">
        <div className="flex items-center justify-between gap-3">
          <a href="/" className="flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-medium text-marine hover:bg-white">
            <ArrowLeft size={16} aria-hidden className="rtl:rotate-180" /> {t.retour}
          </a>
          <div className="flex rounded-xl border border-trait bg-white p-1" role="group" aria-label="Langue · لغة · Language">
            {LANGUES.map((l) => (
              <button key={l.code} type="button" onClick={() => changer(l.code)} aria-pressed={langue === l.code} lang={l.code}
                className={clsx('min-h-8 rounded-lg px-3 text-sm font-semibold transition', l.code === 'ar' && 'font-arabe',
                  langue === l.code ? 'bg-marine text-white' : 'text-marine hover:bg-fond')}>
                {l.court}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center py-8">
          <motion.form key={secousse} onSubmit={envoyer} noValidate
            initial={secousse ? { x: 0 } : { opacity: 0, y: 16 }}
            animate={secousse ? { x: [0, -10, 10, -6, 6, 0] } : { opacity: 1, y: 0 }}
            transition={{ duration: secousse ? 0.4 : 0.45 }}
            className="w-full max-w-md rounded-3xl border border-trait bg-white p-6 shadow-flotte sm:p-9">
            <img src={logo} alt="Agence Foncière Industrielle" className="h-14 w-auto" />
            <h1 className="mt-6 text-2xl font-bold text-marine">{t.titre}</h1>
            <p className="mt-1 text-sm text-doux">{t.sous}</p>

            <label className="mt-7 block text-sm font-semibold text-encre" htmlFor="identifiant">{t.identifiant}</label>
            <div className="relative mt-1.5">
              <UserRound size={18} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-doux" aria-hidden />
              <input id="identifiant" autoComplete="username" autoCapitalize="none" spellCheck={false} required maxLength={80} autoFocus
                value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} dir="ltr" aria-invalid={!!erreur && !erreur.bloque}
                className="min-h-12 w-full rounded-xl border border-trait bg-fond ps-11 pe-3 text-start transition focus:border-marine focus:bg-white focus:outline-none focus:ring-4 focus:ring-marine/10" />
            </div>

            <label className="mt-5 block text-sm font-semibold text-encre" htmlFor="mot">{t.mot}</label>
            <div className="relative mt-1.5">
              <Lock size={18} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-doux" aria-hidden />
              <input id="mot" ref={champMot} type={voir ? 'text' : 'password'} autoComplete="current-password" required maxLength={200}
                value={mot} onChange={(e) => setMot(e.target.value)} onKeyUp={touche} onKeyDown={touche} dir="ltr"
                aria-invalid={!!erreur && !erreur.bloque} aria-describedby={majuscules ? 'majuscules' : undefined}
                className="min-h-12 w-full rounded-xl border border-trait bg-fond ps-11 pe-12 text-start transition focus:border-marine focus:bg-white focus:outline-none focus:ring-4 focus:ring-marine/10" />
              <button type="button" onClick={() => setVoir(!voir)} aria-label={voir ? t.masquer : t.afficher} aria-pressed={voir}
                className="absolute end-1.5 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg text-doux transition hover:bg-brume hover:text-marine">
                {voir ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
              </button>
            </div>
            {majuscules && (
              <p id="majuscules" className="mt-2 flex items-center gap-1.5 text-xs font-medium text-orange">
                <KeyRound size={14} aria-hidden /> {t.majuscules}
              </p>
            )}

            {erreur && (
              <div className={clsx('mt-5 flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm',
                erreur.bloque ? 'border-orange/30 bg-orange/5 text-orange' : 'border-alerte/25 bg-alerte/5 text-alerte')} role="alert">
                <AlertTriangle size={18} className="mt-px shrink-0" aria-hidden />
                <span>{erreur.texte}</span>
              </div>
            )}

            <button type="submit" disabled={attente || !identifiant.trim() || !mot}
              className="mt-7 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-marine to-sarcelle font-semibold text-white shadow-carte transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-55">
              {attente ? <Loader2 size={18} className="animate-spin" aria-hidden /> : <LogIn size={18} aria-hidden className="rtl:rotate-180" />}
              {attente ? t.attente : t.entrer}
            </button>

            <p className="mt-5 text-center text-xs text-doux">{t.oubli}</p>
          </motion.form>
        </div>

        <p className="mx-auto flex max-w-md items-start gap-2 text-xs text-doux">
          <ShieldCheck size={15} className="mt-px shrink-0 text-vert-texte" aria-hidden /> {t.securite}
        </p>
      </main>
    </div>
  )
}
