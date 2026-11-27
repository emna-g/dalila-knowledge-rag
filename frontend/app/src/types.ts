export type Statut = 'disponible' | 'reserve' | 'mis_aux_encheres' | 'attribue' | 'non_disponible' | 'sans_statut'

export interface Zone {
  zone_id: number
  nom: string
  nom_ar: string | null
  gouvernorat: string
  gouvernorat_ar: string | null
  lat: number
  lng: number
  prix_m2_dt: number | null
  prix_m2_subventionne_dt: number | null
  surface_totale_m2: number | null
  surface_amenagee_m2: number | null
  lots_disponibles: number
  lots_a_confirmer: number
  lots_aux_encheres: number
  lots_par_etat: Partial<Record<Statut, number>>
  surface_lot_min_m2: number | null
  surface_lot_max_m2: number | null
  developpement_regional: boolean
  groupe_developpement_regional: number | null
  cahier_des_charges: boolean
}

export interface FicheZone extends Zone {
  distances: { type: string; nom: string | null; km: number | null }[]
  equipements: { type: string; valeur: string | number | null; unite: string | null }[]
  cahiers: { annee: number | null; lien: string; remarque: string | null }[]
  plans: { nom: string; lien: string }[]
  services: Record<string, { nom: string | null; km: number | null }>
}

export interface Lot {
  lot_id: number
  zone_id: number
  numero: string
  statut: Statut
  surface_m2: number | null
  prix_m2_dt: number | null
  a_confirmer: boolean
  contour: [number, number][]
}

export interface ReponseDalila {
  message: string
  log_id: number | null
  source: 'dalila' | 'repli' | string
  action: string | null
  duree_s: number
}

export type LangueUI = 'fr' | 'ar' | 'en'
export type LangueDalila = 'fr' | 'ar' | 'aeb' | 'arq' | 'ayl' | 'en' | 'de' | 'tr'
