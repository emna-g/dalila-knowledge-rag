import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { FournisseurLangue } from '../langue'
import { Connexion } from './Connexion'

createRoot(document.getElementById('root')!).render(<StrictMode><FournisseurLangue><Connexion /></FournisseurLangue></StrictMode>)
