import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, ArrowLeft, Brain, Check, Download, ExternalLink, Globe2, LogOut, MessageCircleQuestion, RefreshCw, Search, ShieldAlert, Undo2, UserRound, X } from 'lucide-react'
import clsx from 'clsx'
import logo from '../assets/afi/logo.png'

/* ------------------------------------------------------------------ données */
interface Besoin { question: string; langues: string[]; posee: number; repli: number; pas_utile: number; utile: number; commentaires: string; derniere_fois: string | null }
interface Appris {
  candidat: number; genre: 'lieu' | 'synonyme'; terme: string; cible: string; conversations: number
  statut: 'propose' | 'publie' | 'rejete' | 'annule'; controles: Record<string, boolean | string[]>
  propose_le: string | null; decide_le: string | null; annule_le: string | null; annule_par: string | null
  appris_id: number | null; actif: boolean; annulable: boolean
}
type EtatSource = 'ok' | 'erreur' | 'a_relire' | 'en_retard' | 'jamais_lue' | 'inactive'
interface Source { url: string; organisme: string; type: string; delai_jours: string; utilise_par: string; etat: EtatSource; derniere_lecture_ok: string | null; derniere_tentative: string | null; erreur: string | null; echecs: number; statut_http: number | null }
interface Sources { origine: string; total: number; resume: Partial<Record<EtatSource, number>>; sources: Source[] }

class ErreurAdmin extends Error {
  statut: number
  constructor(statut: number, message: string) { super(message); this.statut = statut }
}

// La session est un cookie HttpOnly posé par /auth/connexion : le navigateur l'envoie seul, la page ne le voit jamais.
async function appel<T>(chemin: string, options: RequestInit = {}): Promise<T> {
  const r = await fetch(chemin, { ...options, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (r.status === 401) { location.replace('/connexion/'); throw new ErreurAdmin(401, 'connexion nécessaire') }
  if (!r.ok) {
    let detail = `Erreur ${r.status}`
    try { detail = (await r.json()).detail ?? detail } catch { /* corps vide */ }
    throw new ErreurAdmin(r.status, detail)
  }
  return r.json() as Promise<T>
}

/** Une ressource chargée à la demande, avec son état. */
function useDonnees<T>(chemin: string) {
  const [donnees, setDonnees] = useState<T | null>(null)
  const [erreur, setErreur] = useState<ErreurAdmin | null>(null)
  const [charge, setCharge] = useState(true)
  const recharger = useCallback(() => {
    setCharge(true)
    appel<T>(chemin).then((d) => { setDonnees(d); setErreur(null) })
      .catch((e) => setErreur(e instanceof ErreurAdmin ? e : new ErreurAdmin(0, 'Service injoignable')))
      .finally(() => setCharge(false))
  }, [chemin])
  useEffect(() => { recharger() }, [recharger])
  return { donnees, erreur, charge, recharger }
}

const date = (s: string | null) => s ? new Date(s.replace(' ', 'T')).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const LANGUES: Record<string, string> = { fr: 'Français', en: 'Anglais', ar: 'Arabe', aeb: 'Tunisien', tn: 'Tunisien', arq: 'Algérien', dz: 'Algérien', ayl: 'Libyen', ly: 'Libyen', de: 'Allemand', tr: 'Turc' }

/* ------------------------------------------------------------------ page */
type Onglet = 'questions' | 'apprentissage' | 'sources'

export function Admin() {
  const [onglet, setOnglet] = useState<Onglet>(() => (['questions', 'apprentissage', 'sources'].includes(location.hash.slice(1)) ? location.hash.slice(1) as Onglet : 'questions'))
  const [compte, setCompte] = useState<{ identifiant: string; nom: string | null; role: string } | null>(null)
  const [refus, setRefus] = useState<string | null>(null)
  useEffect(() => { history.replaceState(null, '', `#${onglet}`) }, [onglet])
  useEffect(() => {   // pas connecté : page de connexion ; connecté sans le rôle : message
    appel<{ identifiant: string; nom: string | null; role: string }>('/auth/moi')
      .then((c) => { if (c.role !== 'admin') setRefus("Ce compte n'a pas accès à l'administration."); setCompte(c) })
      .catch(() => { /* 401 : déjà redirigé */ })
  }, [])
  const deconnecter = async () => {
    try { await fetch('/auth/deconnexion', { method: 'POST', credentials: 'same-origin' }) } finally { location.replace('/connexion/') }
  }
  if (!compte) return <div className="min-h-full bg-fond" aria-busy="true" />

  const onglets: { id: Onglet; titre: string; sous: string; Icone: typeof Brain }[] = [
    { id: 'questions', titre: 'Questions mal traitées', sous: 'BF12', Icone: MessageCircleQuestion },
    { id: 'apprentissage', titre: 'Apprentissage', sous: 'BF21', Icone: Brain },
    { id: 'sources', titre: 'Sources', sous: 'BF15', Icone: Globe2 },
  ]

  return (
    <div className="min-h-full bg-fond">
      <header className="border-b border-trait bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
          <img src={logo} alt="Agence Foncière Industrielle" className="h-12 w-auto" />
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-marine">Administration de Dalila</h1>
            <p className="text-sm text-doux">Pour l'agent de l'AFI : ce que Dalila traite mal, ce qu'elle apprend, l'état de ses sources.</p>
          </div>
          <span className="ms-auto flex shrink-0 items-center gap-2 text-sm text-doux max-md:hidden">
            <UserRound size={16} aria-hidden /> {compte.nom || compte.identifiant}
          </span>
          <a href="/" className="flex min-h-10 shrink-0 items-center gap-2 rounded-xl border border-trait px-3 text-sm font-semibold text-marine hover:bg-fond max-md:ms-auto">
            <ArrowLeft size={16} aria-hidden /> <span className="max-sm:hidden">Retour à la carte</span>
          </a>
          <button type="button" onClick={deconnecter} className="flex min-h-10 shrink-0 items-center gap-2 rounded-xl border border-trait px-3 text-sm font-semibold text-marine hover:bg-fond">
            <LogOut size={16} aria-hidden /> <span className="max-sm:hidden">Se déconnecter</span>
          </button>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 sm:px-6" role="tablist" aria-label="Écrans d'administration">
          {onglets.map(({ id, titre, sous, Icone }) => (
            <button key={id} type="button" role="tab" aria-selected={onglet === id} onClick={() => setOnglet(id)}
              className={clsx('flex min-h-12 shrink-0 items-center gap-2 border-b-[3px] px-3 text-sm font-semibold transition',
                onglet === id ? 'border-marine text-marine' : 'border-transparent text-doux hover:text-marine')}>
              <Icone size={17} aria-hidden /> {titre} <span className="rounded bg-brume px-1.5 py-0.5 text-[11px] font-medium text-doux">{sous}</span>
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {refus != null ? (
          <Refus message={refus} onDeconnecter={deconnecter} />
        ) : (
          <div>
            {onglet === 'questions' && <Questions onRefus={setRefus} />}
            {onglet === 'apprentissage' && <Apprentissage onRefus={setRefus} />}
            {onglet === 'sources' && <SourcesEcran onRefus={setRefus} />}
          </div>
        )}
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------ éléments communs */
function Refus({ message, onDeconnecter }: { message: string; onDeconnecter: () => void }) {
  return (
    <div className="mx-auto mt-10 max-w-md rounded-2xl border border-trait bg-white p-6 shadow-carte" role="alert">
      <ShieldAlert className="text-alerte" aria-hidden />
      <h2 className="mt-3 text-lg font-bold text-marine">Accès refusé</h2>
      <p className="mt-1 text-sm text-doux">{message}</p>
      <button type="button" onClick={onDeconnecter} className="mt-4 min-h-11 w-full rounded-xl bg-marine font-semibold text-white hover:bg-marine-fonce">Se connecter avec un autre compte</button>
    </div>
  )
}

function useRefus<T>(r: ReturnType<typeof useDonnees<T>>, onRefus: (m: string) => void) {
  useEffect(() => {
    if (r.erreur && r.erreur.statut === 403) onRefus(r.erreur.message)   // 401 : renvoyé à la page de connexion
  }, [r.erreur, onRefus])
}

function Etat({ charge, erreur, vide, onRecharger, children }: { charge: boolean; erreur: ErreurAdmin | null; vide: boolean; onRecharger: () => void; children: ReactNode }) {
  if (erreur && erreur.statut !== 401 && erreur.statut !== 403) return (
    <div className="flex items-start gap-3 rounded-2xl border border-alerte/30 bg-alerte/5 p-5" role="alert">
      <AlertTriangle className="mt-0.5 shrink-0 text-alerte" aria-hidden />
      <div>
        <p className="font-semibold">Données indisponibles</p>
        <p className="text-sm text-doux">{erreur.statut === 503 ? 'La base de données ne répond pas. Vérifiez qu\'elle est démarrée (docker start dalila-db).' : erreur.message}</p>
        <button type="button" onClick={onRecharger} className="mt-3 flex min-h-10 items-center gap-2 rounded-xl border border-trait bg-white px-3 text-sm font-semibold text-marine"><RefreshCw size={15} aria-hidden /> Réessayer</button>
      </div>
    </div>
  )
  if (charge && vide) return <div className="space-y-2" aria-busy="true">{[0, 1, 2, 3].map((i) => <div key={i} className="h-14 animate-pulse rounded-xl bg-white" />)}</div>
  return <>{children}</>
}

function Chiffre({ valeur, libelle, ton = 'marine', actif, onClick }: { valeur: number | string; libelle: string; ton?: 'marine' | 'vert' | 'alerte' | 'orange' | 'doux'; actif?: boolean; onClick?: () => void }) {
  const couleur = { marine: 'text-marine', vert: 'text-vert-texte', alerte: 'text-alerte', orange: 'text-orange', doux: 'text-doux' }[ton]
  const Balise = onClick ? 'button' : 'div'
  return (
    <Balise type={onClick ? 'button' : undefined} onClick={onClick} aria-pressed={onClick ? !!actif : undefined}
      className={clsx('rounded-2xl border bg-white px-4 py-3 text-start shadow-carte transition', actif ? 'border-marine ring-2 ring-marine/20' : 'border-trait', onClick && 'hover:border-marine')}>
      <p className={clsx('text-2xl font-bold', couleur)}>{valeur}</p>
      <p className="text-xs font-medium text-doux">{libelle}</p>
    </Balise>
  )
}

function Recherche({ valeur, onChange, aide }: { valeur: string; onChange: (v: string) => void; aide: string }) {
  return (
    <label className="relative block min-w-0 flex-1">
      <span className="sr-only">{aide}</span>
      <Search size={17} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-doux" aria-hidden />
      <input type="search" value={valeur} onChange={(e) => onChange(e.target.value)} placeholder={aide}
        className="min-h-11 w-full rounded-xl border border-trait bg-white ps-10 pe-3 focus:border-marine focus:outline-none" />
    </label>
  )
}

function Bouton({ children, onClick, Icone }: { children: ReactNode; onClick: () => void; Icone: typeof Check }) {
  return <button type="button" onClick={onClick} className="flex min-h-11 shrink-0 items-center gap-2 rounded-xl border border-trait bg-white px-3 text-sm font-semibold text-marine hover:bg-fond"><Icone size={16} aria-hidden /> {children}</button>
}

/* ------------------------------------------------------------------ BF12 : questions mal traitées */
function Questions({ onRefus }: { onRefus: (m: string) => void }) {
  const [depuis, setDepuis] = useState('')
  const [tout, setTout] = useState(false)
  const [texte, setTexte] = useState('')
  const r = useDonnees<Besoin[]>(`/admin/api/besoins?tout=${tout}${depuis ? `&depuis=${depuis}` : ''}`)
  useRefus(r, onRefus)
  const lignes = useMemo(() => (r.donnees ?? []).filter((l) => l.question.toLowerCase().includes(texte.toLowerCase())), [r.donnees, texte])
  const total = (k: 'posee' | 'repli' | 'pas_utile') => (r.donnees ?? []).reduce((s, l) => s + l[k], 0)

  const exporter = () => {
    const tete = ['question', 'langues', 'posee', 'repli', 'pas_utile', 'utile', 'commentaires', 'derniere_fois']
    const csv = [tete.join(';'), ...lignes.map((l) => [l.question, l.langues.join(','), l.posee, l.repli, l.pas_utile, l.utile, l.commentaires, l.derniere_fois ?? '']
      .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';'))].join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    a.download = `questions_mal_traitees_${new Date().toISOString().slice(0, 10)}.csv`
    a.click(); URL.revokeObjectURL(a.href)
  }

  return (
    <section aria-labelledby="t-questions">
      <h2 id="t-questions" className="text-lg font-bold text-marine">Questions mal traitées</h2>
      <p className="mt-1 max-w-3xl text-sm text-doux">Les questions auxquelles Dalila n'a pas su répondre (réponse de secours) ou que les visiteurs ont notées « pas utile », regroupées et classées de la plus fréquente à la moins fréquente. Elles sont anonymisées. Elles montrent ce qu'il faut ajouter aux données ou aux exemples d'entraînement.</p>
      {r.donnees && <div className="mt-5 grid grid-cols-3 gap-3 sm:max-w-xl">
        <Chiffre valeur={(r.donnees ?? []).length} libelle={tout ? 'questions' : 'questions à traiter'} />
        <Chiffre valeur={total('repli')} libelle="réponses de secours" ton="alerte" />
        <Chiffre valeur={total('pas_utile')} libelle="avis « pas utile »" ton="orange" />
      </div>}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Recherche valeur={texte} onChange={setTexte} aide="Chercher dans les questions…" />
        <label className="flex min-h-11 items-center gap-2 rounded-xl border border-trait bg-white px-3 text-sm">
          Depuis le <input type="date" value={depuis} onChange={(e) => setDepuis(e.target.value)} className="bg-transparent" />
        </label>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-trait bg-white px-3 text-sm">
          <input type="checkbox" checked={tout} onChange={(e) => setTout(e.target.checked)} className="size-4 accent-marine" /> Aussi les questions sans problème
        </label>
        <Bouton onClick={exporter} Icone={Download}>Exporter (CSV)</Bouton>
        <Bouton onClick={r.recharger} Icone={RefreshCw}>Actualiser</Bouton>
      </div>
      <div className="mt-4">
        <Etat charge={r.charge} erreur={r.erreur} vide={!r.donnees} onRecharger={r.recharger}>
          {lignes.length === 0 ? (
            <p className="rounded-2xl border border-trait bg-white p-8 text-center text-doux">{texte ? 'Aucune question ne correspond.' : 'Aucune question mal traitée sur la période : rien à faire.'}</p>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-trait bg-white shadow-carte">
              <table className="w-full min-w-[760px] text-sm">
                <thead className="bg-fond text-start text-xs uppercase tracking-wide text-doux">
                  <tr><th className="px-4 py-3 text-start">Question</th><th className="px-3 py-3 text-start">Langue</th><th className="px-3 py-3 text-end">Posée</th><th className="px-3 py-3 text-end">Secours</th><th className="px-3 py-3 text-end">Pas utile</th><th className="px-3 py-3 text-end">Utile</th><th className="px-4 py-3 text-start">Dernière fois</th></tr>
                </thead>
                <tbody className="divide-y divide-trait">
                  {lignes.map((l, i) => (
                    <tr key={i} className="align-top hover:bg-fond/60">
                      <td className="max-w-md px-4 py-3">
                        <p dir="auto" className="font-medium">{l.question}</p>
                        {l.commentaires && <p dir="auto" className="mt-1 text-xs text-doux">Commentaires : {l.commentaires}</p>}
                      </td>
                      <td className="px-3 py-3 text-doux">{l.langues.map((x) => LANGUES[x] ?? x).join(', ')}</td>
                      <td className="px-3 py-3 text-end font-semibold">{l.posee}</td>
                      <td className={clsx('px-3 py-3 text-end font-semibold', l.repli ? 'text-alerte' : 'text-doux')}>{l.repli}</td>
                      <td className={clsx('px-3 py-3 text-end font-semibold', l.pas_utile ? 'text-orange' : 'text-doux')}>{l.pas_utile}</td>
                      <td className="px-3 py-3 text-end text-doux">{l.utile}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-doux">{date(l.derniere_fois)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Etat>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ BF21 : journal de l'apprentissage */
const STATUTS: Record<Appris['statut'], { nom: string; classe: string }> = {
  publie: { nom: 'Publié', classe: 'bg-vert/10 text-vert-texte' },
  propose: { nom: 'Proposé', classe: 'bg-ciel/10 text-lien' },
  rejete: { nom: 'Rejeté', classe: 'bg-brume text-doux' },
  annule: { nom: 'Annulé', classe: 'bg-alerte/10 text-alerte' },
}
const CONTROLES: Record<string, string> = {
  anonyme_sans_chiffre: 'Anonyme et sans chiffre', anonyme_et_pas_un_nombre: 'Anonyme, pas un nombre',
  lieu_existe: 'Le lieu existe', concept_existe: "L'activité existe", nom_libre: "Nom pas déjà pris",
  pas_libelle_d_un_autre: "Pas le nom d'une autre activité", designe_ce_lieu: 'Mène bien à ce lieu',
  mene_a_l_activite: "Mène bien à l'activité", noms_officiels_inchanges: 'Noms officiels inchangés',
  tests_des_outils: 'Tests des outils réussis', noms_changes: 'Noms changés',
}

function Apprentissage({ onRefus }: { onRefus: (m: string) => void }) {
  const r = useDonnees<Appris[]>('/admin/api/apprentissage')
  useRefus(r, onRefus)
  const [statut, setStatut] = useState<Appris['statut'] | null>(null)
  const [texte, setTexte] = useState('')
  const [confirmer, setConfirmer] = useState<Appris | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; texte: string } | null>(null)
  const liste = r.donnees ?? []
  const nb = (s: Appris['statut']) => liste.filter((a) => a.statut === s).length
  const lignes = liste.filter((a) => (!statut || a.statut === statut) && `${a.terme} ${a.cible}`.toLowerCase().includes(texte.toLowerCase()))

  const annuler = async (a: Appris) => {
    setConfirmer(null)
    try {
      await appel(`/admin/api/apprentissage/${a.genre}/${a.appris_id}/annuler`, { method: 'POST' })   // signé du compte connecté, côté serveur
      setMessage({ ok: true, texte: `« ${a.terme} » est annulé : Dalila ne l'utilise plus. Le journal garde la trace.` })
      r.recharger()
    } catch (e) {
      setMessage({ ok: false, texte: e instanceof Error ? e.message : 'Annulation impossible' })
    }
  }

  return (
    <section aria-labelledby="t-appr">
      <h2 id="t-appr" className="text-lg font-bold text-marine">Journal de l'apprentissage</h2>
      <p className="mt-1 max-w-3xl text-sm text-doux">Ce que Dalila a appris des conversations : des noms de lieux (« Qassrin » → Kasserine) et des mots pour une activité (« sardine » → conserverie de poisson). Jamais un prix, une disponibilité ou une condition. Chaque élément vient d'au moins 2 conversations et passe des contrôles avant d'être publié. « Annuler » le retire tout de suite ; le journal garde la trace.</p>
      {r.donnees && <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Chiffre valeur={nb('publie')} libelle="publiés (actifs ou annulés après)" ton="vert" actif={statut === 'publie'} onClick={() => setStatut(statut === 'publie' ? null : 'publie')} />
        <Chiffre valeur={nb('propose')} libelle="proposés" actif={statut === 'propose'} onClick={() => setStatut(statut === 'propose' ? null : 'propose')} />
        <Chiffre valeur={nb('rejete')} libelle="rejetés par les contrôles" ton="doux" actif={statut === 'rejete'} onClick={() => setStatut(statut === 'rejete' ? null : 'rejete')} />
        <Chiffre valeur={nb('annule')} libelle="annulés" ton="alerte" actif={statut === 'annule'} onClick={() => setStatut(statut === 'annule' ? null : 'annule')} />
      </div>}
      <div className="mt-5 flex flex-wrap gap-3">
        <Recherche valeur={texte} onChange={setTexte} aide="Chercher un mot ou un lieu…" />
        <Bouton onClick={r.recharger} Icone={RefreshCw}>Actualiser</Bouton>
      </div>
      {message && (
        <div className={clsx('mt-4 flex items-center gap-3 rounded-xl px-4 py-3 text-sm', message.ok ? 'bg-vert/10 text-vert-texte' : 'bg-alerte/10 text-alerte')} role="status">
          {message.ok ? <Check size={18} aria-hidden /> : <AlertTriangle size={18} aria-hidden />} <span className="flex-1">{message.texte}</span>
          <button type="button" onClick={() => setMessage(null)} aria-label="Fermer le message"><X size={16} aria-hidden /></button>
        </div>
      )}
      <div className="mt-4">
        <Etat charge={r.charge} erreur={r.erreur} vide={!r.donnees} onRecharger={r.recharger}>
          {lignes.length === 0 ? (
            <p className="rounded-2xl border border-trait bg-white p-8 text-center text-doux">{liste.length ? 'Aucun élément ne correspond.' : "Rien d'appris pour l'instant : il faut au moins 2 conversations qui montrent la même chose. Le cycle se lance avec python -m dalila.apprentissage.lieux_appris et synonymes_appris."}</p>
          ) : (
            <ul className="space-y-3">
              {lignes.map((a) => (
                <li key={a.candidat} className={clsx('rounded-2xl border border-trait bg-white p-4 shadow-carte', a.statut === 'annule' && 'opacity-75')}>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span className="rounded-lg bg-brume px-2 py-0.5 text-xs font-semibold text-doux">{a.genre === 'lieu' ? 'Nom de lieu' : 'Mot pour une activité'}</span>
                    <p className="font-semibold"><span dir="auto">« {a.terme} »</span> <span className="text-doux">→</span> <span dir="auto">{a.cible}</span></p>
                    <span className={clsx('rounded-full px-2.5 py-0.5 text-xs font-semibold', STATUTS[a.statut].classe)}>{STATUTS[a.statut].nom}{a.statut === 'publie' && !a.actif ? ' (inactif)' : ''}</span>
                    {a.annulable && (
                      <button type="button" onClick={() => setConfirmer(a)} className="ms-auto flex min-h-10 items-center gap-2 rounded-xl border border-alerte/40 px-3 text-sm font-semibold text-alerte hover:bg-alerte/5">
                        <Undo2 size={16} aria-hidden /> Annuler
                      </button>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-doux">
                    Vu dans {a.conversations} conversation{a.conversations > 1 ? 's' : ''} · proposé le {date(a.propose_le)}
                    {a.decide_le && <> · décidé le {date(a.decide_le)}</>}
                    {a.annule_le && <> · <span className="font-semibold text-alerte">annulé le {date(a.annule_le)}{a.annule_par ? ` par ${a.annule_par}` : ''}</span></>}
                  </p>
                  {Object.keys(a.controles).length > 0 && (
                    <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Contrôles">
                      {Object.entries(a.controles).map(([k, v]) => Array.isArray(v) ? (
                        <li key={k} className="rounded-lg bg-alerte/10 px-2 py-1 text-xs text-alerte">{CONTROLES[k] ?? k} : {v.join(', ')}</li>
                      ) : (
                        <li key={k} className={clsx('flex items-center gap-1 rounded-lg px-2 py-1 text-xs', v ? 'bg-vert/10 text-vert-texte' : 'bg-alerte/10 text-alerte')}>
                          {v ? <Check size={13} aria-hidden /> : <X size={13} aria-hidden />} {CONTROLES[k] ?? k}<span className="sr-only">{v ? ' : réussi' : ' : échoué'}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Etat>
      </div>

      {confirmer && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-nuit/50 p-4" role="dialog" aria-modal="true" aria-labelledby="t-confirmer"
          onKeyDown={(e) => { if (e.key === 'Escape') setConfirmer(null) }}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-flotte">
            <h3 id="t-confirmer" className="text-lg font-bold text-marine">Annuler cet apprentissage ?</h3>
            <p className="mt-2 text-sm">« <span dir="auto">{confirmer.terme}</span> » ne mènera plus à <span dir="auto">{confirmer.cible}</span>. Dalila arrête de l'utiliser tout de suite. Le journal garde la trace (date et auteur).</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" autoFocus onClick={() => setConfirmer(null)} className="min-h-11 rounded-xl border border-trait px-4 font-semibold text-doux hover:bg-fond">Garder</button>
              <button type="button" onClick={() => annuler(confirmer)} className="min-h-11 rounded-xl bg-alerte px-4 font-semibold text-white hover:brightness-95">Annuler l'apprentissage</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ BF15 : état des URL */
const ETATS: Record<EtatSource, { nom: string; aide: string; classe: string; ton: 'vert' | 'alerte' | 'orange' | 'doux' | 'marine' }> = {
  erreur: { nom: 'En erreur', aide: 'la dernière lecture a échoué', classe: 'bg-alerte/10 text-alerte', ton: 'alerte' },
  a_relire: { nom: 'À relire', aide: 'contenu changé, à valider', classe: 'bg-orange/10 text-orange', ton: 'orange' },
  en_retard: { nom: 'En retard', aide: 'pas relue depuis 2 fois le délai', classe: 'bg-orange/10 text-orange', ton: 'orange' },
  jamais_lue: { nom: 'Jamais lue', aide: 'ajoutée, pas encore lue', classe: 'bg-ciel/10 text-lien', ton: 'marine' },
  ok: { nom: 'À jour', aide: 'lue avec succès', classe: 'bg-vert/10 text-vert-texte', ton: 'vert' },
  inactive: { nom: 'Inactive', aide: 'actif = 0 dans la configuration', classe: 'bg-brume text-doux', ton: 'doux' },
}
const PAGE = 100

function SourcesEcran({ onRefus }: { onRefus: (m: string) => void }) {
  const r = useDonnees<Sources>('/admin/api/sources')
  useRefus(r, onRefus)
  const [filtre, setFiltre] = useState<EtatSource | null>(null)
  const [texte, setTexte] = useState('')
  const [nombre, setNombre] = useState(PAGE)
  const d = r.donnees
  const ordre: EtatSource[] = ['erreur', 'a_relire', 'en_retard', 'jamais_lue', 'ok', 'inactive']
  const lignes = useMemo(() => (d?.sources ?? [])
    .filter((s) => (!filtre || s.etat === filtre) && `${s.url} ${s.organisme}`.toLowerCase().includes(texte.toLowerCase()))
    .sort((a, b) => ordre.indexOf(a.etat) - ordre.indexOf(b.etat)), [d, filtre, texte]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setNombre(PAGE), [filtre, texte])

  return (
    <section aria-labelledby="t-sources">
      <h2 id="t-sources" className="text-lg font-bold text-marine">État des sources</h2>
      <p className="mt-1 max-w-3xl text-sm text-doux">
        Chaque adresse de la configuration (<code className="rounded bg-brume px-1">dalila/sources/config_sources.csv</code>) est relue chaque semaine. Ajouter ou retirer une source se fait dans ce fichier, sans toucher au code.
        {d && <> Dernier état lu {d.origine === 'fichier' ? 'dans le fichier d\'état du serveur' : d.origine === 'base' ? 'dans la base (agent_source_status)' : ': aucun'}.</>}
      </p>
      {d && (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {ordre.map((e) => <Chiffre key={e} valeur={d.resume[e] ?? 0} libelle={`${ETATS[e].nom} · ${ETATS[e].aide}`} ton={ETATS[e].ton} actif={filtre === e} onClick={() => setFiltre(filtre === e ? null : e)} />)}
        </div>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        <Recherche valeur={texte} onChange={setTexte} aide="Chercher une adresse ou un organisme (AFI, FIPA, APII…)" />
        <Bouton onClick={r.recharger} Icone={RefreshCw}>Actualiser</Bouton>
      </div>
      <div className="mt-4">
        <Etat charge={r.charge} erreur={r.erreur} vide={!d} onRecharger={r.recharger}>
          <p className="mb-2 text-sm text-doux" aria-live="polite">{lignes.length} source{lignes.length > 1 ? 's' : ''}{filtre ? ` · ${ETATS[filtre].nom.toLowerCase()}` : ''}</p>
          <div className="overflow-x-auto rounded-2xl border border-trait bg-white shadow-carte">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="bg-fond text-xs uppercase tracking-wide text-doux">
                <tr><th className="px-4 py-3 text-start">État</th><th className="px-3 py-3 text-start">Organisme</th><th className="px-3 py-3 text-start">Adresse</th><th className="px-3 py-3 text-start">Dernière lecture réussie</th><th className="px-4 py-3 text-start">Problème</th></tr>
              </thead>
              <tbody className="divide-y divide-trait">
                {lignes.slice(0, nombre).map((s) => (
                  <tr key={s.url} className="align-top hover:bg-fond/60">
                    <td className="px-4 py-3"><span className={clsx('whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', ETATS[s.etat].classe)}>{ETATS[s.etat].nom}</span></td>
                    <td className="px-3 py-3 font-medium">{s.organisme}<span className="block text-xs font-normal text-doux">{s.type} · tous les {s.delai_jours} j</span></td>
                    <td className="max-w-md px-3 py-3">
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-1 break-all text-lien hover:underline">{s.url.replace(/^https?:\/\/(www\.)?/, '')}<ExternalLink size={13} className="mt-1 shrink-0" aria-hidden /></a>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-doux">{date(s.derniere_lecture_ok)}</td>
                    <td className="px-4 py-3 text-xs">{s.erreur ? <span className="text-alerte">{s.erreur}{s.echecs > 1 ? ` (${s.echecs} échecs de suite)` : ''}</span> : s.etat === 'a_relire' ? 'Contenu changé : à valider avant usage' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {lignes.length > nombre && (
            <button type="button" onClick={() => setNombre(nombre + PAGE)} className="mx-auto mt-4 flex min-h-11 items-center rounded-xl border border-trait bg-white px-4 text-sm font-semibold text-marine hover:bg-fond">
              Afficher {Math.min(PAGE, lignes.length - nombre)} de plus ({lignes.length - nombre} restantes)
            </button>
          )}
        </Etat>
      </div>
    </section>
  )
}
