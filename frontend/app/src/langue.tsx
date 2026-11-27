import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { DICOS, joliNom, type Dico } from './i18n'
import type { LangueUI } from './types'

interface Ctx { langue: LangueUI; t: Dico; changer: (l: LangueUI) => void; rtl: boolean }
const Contexte = createContext<Ctx | null>(null)

function depart(): LangueUI {
  const memo = localStorage.getItem('afi_langue') as LangueUI | null
  if (memo && memo in DICOS) return memo
  const n = navigator.language.slice(0, 2)
  return n === 'ar' ? 'ar' : n === 'en' ? 'en' : 'fr'
}

export function FournisseurLangue({ children }: { children: ReactNode }) {
  const [langue, setLangue] = useState<LangueUI>(depart)
  const rtl = langue === 'ar'
  useEffect(() => {
    document.documentElement.lang = langue
    document.documentElement.dir = rtl ? 'rtl' : 'ltr'
    localStorage.setItem('afi_langue', langue)
  }, [langue, rtl])
  return <Contexte.Provider value={{ langue, t: DICOS[langue], changer: setLangue, rtl }}>{children}</Contexte.Provider>
}

export function useLangue() {
  const c = useContext(Contexte)
  if (!c) throw new Error('FournisseurLangue manquant')
  return c
}

/** Nom d'une zone ou d'un gouvernorat dans la langue de l'interface. */
export function useNom() {
  const { langue } = useLangue()
  return (fr: string, ar?: string | null) => (langue === 'ar' && ar ? ar : joliNom(fr))
}
