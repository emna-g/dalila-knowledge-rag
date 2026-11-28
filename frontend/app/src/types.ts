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
  /** langue détectée du message (codes du contrat : fr, en, ar, de, tr, tn, dz, ly) et son écriture */
  langue?: string | null
  ecriture?: 'arabe' | 'latin' | string | null
  /** session à renvoyer : sert à suivre une étude de projet guidée */
  session_id?: string | null
}

export type LangueUI = 'fr' | 'ar' | 'en'
// codes du contrat /carte/chatbot (cahier des charges, IV.3) : tunisien tn, algérien dz, libyen ly
export type LangueDalila = 'fr' | 'ar' | 'tn' | 'dz' | 'ly' | 'en' | 'de' | 'tr'

/** GET /carte/demande : demande d'acquisition préremplie (BF11). Lot et prix relus dans la base de l'AFI. */
export interface DemandePreremplie {
  lot: { lot_id: number; numero: string; surface_m2: number | null; statut: Statut; libelle_statut: string; a_confirmer: boolean
    prix_m2_dt: number | null; prix_m2_a_confirmer: boolean; prix_terrain_dt: number | null } | null
  zone: { zone_id: number; nom: string; nom_ar: string | null; gouvernorat: string; gouvernorat_ar: string | null
    developpement_regional: boolean; groupe: string | null } | null
  projet: { activite?: string; produits?: string; investissement_texte?: string; emplois_texte?: string; surface_texte?: string }
  lot_disponible: boolean
  lieu_depot: string
  pieces: { id: string; titre: string; texte: string }[]
  formulaire_officiel: string
}

export interface DemandeEnvoyee {
  lot_id: number
  demandeur: { nom: string; forme_juridique: string; representant: string; telephone: string; courriel: string; adresse: string }
  projet: { activite: string; produits: string; investissement_dt: number | null; emplois: number | null; dont_cadres: number | null
    delai_realisation_mois: number | null; justification_surface: string }
  confirme: boolean
  lang: string
}
