import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapLayerMouseEvent } from 'maplibre-gl'
import type { ExpressionSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { FeatureCollection, Point } from 'geojson'
import 'maplibre-gl/dist/maplibre-gl.css'
import urlWorker from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { Layers, Satellite, Map as IconeCarte, ChevronDown } from 'lucide-react'
import clsx from 'clsx'
import { ETATS, nombre } from '../i18n'
import { useLangue } from '../langue'
import type { Lot, Statut, Zone } from '../types'

maplibregl.setWorkerUrl(urlWorker)   // MapLibre 6 : le worker est un fichier à part, copié par Vite

const STYLE = 'https://tiles.openfreemap.org/styles/positron'
const SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const POLICE = ['Noto Sans Bold']
const TUNISIE: [[number, number], [number, number]] = [[7.6, 30.3], [11.6, 37.4]]

interface Props {
  zones: Zone[]
  zoneChoisie: Zone | null
  lots: Lot[]
  lotChoisi: number | null
  citees: number[]
  fond: 'plan' | 'satellite'
  marges: { gauche: number; droite: number }
  onZone: (id: number) => void
  onLot: (id: number) => void
  onFond: (f: 'plan' | 'satellite') => void
}

const couleurEtat = ['match', ['get', 'statut'],
  ...Object.entries(ETATS).flatMap(([k, e]) => [k, e.couleur]), '#B9C2C7'] as unknown as ExpressionSpecification

function zonesGeo(zones: Zone[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: zones.map((z) => ({
      type: 'Feature', id: z.zone_id,
      geometry: { type: 'Point', coordinates: [z.lng, z.lat] },
      properties: { id: z.zone_id, nom: z.nom, nom_ar: z.nom_ar ?? z.nom, dispo: z.lots_disponibles, encheres: z.lots_aux_encheres },
    })),
  }
}

function lotsGeo(lots: Lot[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: lots.filter((l) => l.contour.length >= 3).map((l) => ({
      type: 'Feature', id: l.lot_id,
      geometry: { type: 'Polygon', coordinates: [[...l.contour, l.contour[0]]] },
      properties: { id: l.lot_id, numero: l.numero, statut: l.statut, surface: l.surface_m2 },
    })),
  }
}

export function Carte({ zones, zoneChoisie, lots, lotChoisi, citees, fond, marges, onZone, onLot, onFond }: Props) {
  const { t, langue } = useLangue()
  const boite = useRef<HTMLDivElement>(null)
  const carte = useRef<maplibregl.Map | null>(null)
  const [prete, setPrete] = useState(false)
  const [legende, setLegende] = useState(false)
  const reperes = useRef<maplibregl.Marker[]>([])
  const rappels = useRef({ onZone, onLot })
  rappels.current = { onZone, onLot }

  /* ---------- création ---------- */
  useEffect(() => {
    if (!boite.current) return
    const m = new maplibregl.Map({
      container: boite.current, style: STYLE, bounds: TUNISIE, fitBoundsOptions: { padding: 40 },
      attributionControl: { compact: true }, maxPitch: 60,
    })
    carte.current = m
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    m.addControl(new maplibregl.FullscreenControl(), 'top-right')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right')

    m.once('style.load', () => {   // dès que le style est lu, sans attendre toutes les tuiles
      const premierTexte = m.getStyle().layers.find((l) => l.type === 'symbol')?.id
      m.addSource('satellite', { type: 'raster', tiles: [SATELLITE], tileSize: 256, maxzoom: 17,
        attribution: 'Imagerie © Esri, Maxar, Earthstar Geographics' })
      m.addLayer({ id: 'satellite', type: 'raster', source: 'satellite', layout: { visibility: 'none' } }, premierTexte)

      /* lots d'une zone */
      m.addSource('lots', { type: 'geojson', data: lotsGeo([]) })
      m.addLayer({ id: 'lots-fond', type: 'fill', source: 'lots', paint: {
        'fill-color': couleurEtat,
        'fill-opacity': ['case', ['boolean', ['feature-state', 'survol'], false], 0.75, 0.45] } })
      m.addLayer({ id: 'lots-bord', type: 'line', source: 'lots', paint: {
        'line-color': couleurEtat, 'line-width': ['interpolate', ['linear'], ['zoom'], 13, 0.6, 18, 2.2] } })
      m.addLayer({ id: 'lots-choisi', type: 'line', source: 'lots', filter: ['==', ['get', 'id'], -1], paint: {
        'line-color': '#FFED00', 'line-width': 4 } })
      m.addLayer({ id: 'lots-numero', type: 'symbol', source: 'lots', minzoom: 16.2, layout: {
        'text-field': ['get', 'numero'], 'text-font': POLICE, 'text-size': 11, 'text-allow-overlap': false },
        paint: { 'text-color': '#0B2A42', 'text-halo-color': '#fff', 'text-halo-width': 1.4 } })

      /* zones, regroupées quand on s'éloigne */
      m.addSource('zones', { type: 'geojson', data: zonesGeo([]), cluster: true, clusterRadius: 34, clusterMaxZoom: 7,
        clusterProperties: { dispo: ['+', ['get', 'dispo']] } })
      m.addLayer({ id: 'groupes-halo', type: 'circle', source: 'zones', filter: ['has', 'point_count'], paint: {
        'circle-color': '#17598B', 'circle-opacity': 0.16,
        'circle-radius': ['step', ['get', 'point_count'], 26, 4, 32, 8, 38] } })
      m.addLayer({ id: 'groupes', type: 'circle', source: 'zones', filter: ['has', 'point_count'], paint: {
        'circle-color': '#17598B', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5,
        'circle-radius': ['step', ['get', 'point_count'], 18, 4, 22, 8, 27] } })
      m.addLayer({ id: 'groupes-texte', type: 'symbol', source: 'zones', filter: ['has', 'point_count'], layout: {
        'text-field': ['to-string', ['get', 'dispo']], 'text-font': POLICE, 'text-size': 13, 'text-allow-overlap': true },
        paint: { 'text-color': '#fff' } })
      m.addLayer({ id: 'zone-halo', type: 'circle', source: 'zones', filter: ['!', ['has', 'point_count']], paint: {
        'circle-color': ['case', ['>', ['get', 'dispo'], 0], '#008D36', ['>', ['get', 'encheres'], 0], '#E94E1B', '#5B6670'],
        'circle-opacity': 0.18,
        'circle-radius': ['+', 16, ['*', 1.4, ['sqrt', ['get', 'dispo']]]] } })
      m.addLayer({ id: 'zone', type: 'circle', source: 'zones', filter: ['!', ['has', 'point_count']], paint: {
        'circle-color': ['case', ['>', ['get', 'dispo'], 0], '#008D36', ['>', ['get', 'encheres'], 0], '#E94E1B', '#7C8A93'],
        'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5,
        'circle-radius': ['+', 11, ['*', 1.1, ['sqrt', ['get', 'dispo']]]] } })
      m.addLayer({ id: 'zone-choisie', type: 'circle', source: 'zones', filter: ['==', ['get', 'id'], -1], paint: {
        'circle-color': 'transparent', 'circle-stroke-color': '#FFED00', 'circle-stroke-width': 4,
        'circle-radius': ['+', 15, ['*', 1.1, ['sqrt', ['get', 'dispo']]]] } })
      m.addLayer({ id: 'zone-texte', type: 'symbol', source: 'zones', filter: ['!', ['has', 'point_count']], layout: {
        'text-field': ['to-string', ['get', 'dispo']], 'text-font': POLICE, 'text-size': 12, 'text-allow-overlap': true },
        paint: { 'text-color': '#fff' } })
      m.addLayer({ id: 'zone-nom', type: 'symbol', source: 'zones', filter: ['!', ['has', 'point_count']], minzoom: 7.5, layout: {
        'text-field': ['get', 'nom'], 'text-font': POLICE, 'text-size': 12.5, 'text-offset': [0, 1.9], 'text-anchor': 'top',
        'text-max-width': 9 },
        paint: { 'text-color': '#0B2A42', 'text-halo-color': '#fff', 'text-halo-width': 1.6 } })

      /* interactions */
      const bulle = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 16, className: 'bulle-zone' })
      m.on('click', 'groupes', async (e: MapLayerMouseEvent) => {
        const f = e.features?.[0]
        if (!f) return
        const zoom = await (m.getSource('zones') as GeoJSONSource).getClusterExpansionZoom(f.properties.cluster_id as number)
        m.easeTo({ center: (f.geometry as Point).coordinates as [number, number], zoom: zoom + 0.3 })
      })
      m.on('click', 'zone', (e) => { const id = e.features?.[0]?.properties.id; if (id != null) rappels.current.onZone(Number(id)) })
      m.on('click', 'lots-fond', (e) => { const id = e.features?.[0]?.properties.id; if (id != null) rappels.current.onLot(Number(id)) })
      for (const couche of ['groupes', 'zone', 'lots-fond']) {
        m.on('mouseenter', couche, () => { m.getCanvas().style.cursor = 'pointer' })
        m.on('mouseleave', couche, () => { m.getCanvas().style.cursor = ''; bulle.remove() })
      }
      m.on('mousemove', 'zone', (e) => {
        const p = e.features?.[0]?.properties
        if (!p) return
        const nom = document.documentElement.lang === 'ar' ? p.nom_ar : p.nom
        bulle.setLngLat(e.lngLat).setHTML('').addTo(m)
        const el = document.createElement('div')
        el.className = 'text-sm'
        const b = document.createElement('strong'); b.textContent = nom; b.className = 'block text-marine'
        const s = document.createElement('span'); s.textContent = `${p.dispo} ${document.documentElement.lang === 'ar' ? 'مقسم متاح' : document.documentElement.lang === 'en' ? 'available lots' : 'lots disponibles'}`
        s.className = 'text-doux'
        el.append(b, s); bulle.setDOMContent(el)
      })
      let survol: number | null = null
      m.on('mousemove', 'lots-fond', (e) => {
        const f = e.features?.[0]
        if (!f) return
        if (survol != null) m.setFeatureState({ source: 'lots', id: survol }, { survol: false })
        survol = f.id as number
        m.setFeatureState({ source: 'lots', id: survol }, { survol: true })
        const st = ETATS[f.properties.statut as Statut] ?? ETATS.sans_statut
        const lg = (document.documentElement.lang || 'fr') as 'fr' | 'ar' | 'en'
        const el = document.createElement('div'); el.className = 'text-sm'
        const b = document.createElement('strong'); b.className = 'block text-marine'
        b.textContent = `${lg === 'ar' ? 'مقسم' : 'Lot'} ${f.properties.numero}`
        const s = document.createElement('span'); s.className = 'text-doux'
        s.textContent = `${st[lg]}${f.properties.surface ? ' · ' + nombre(Number(f.properties.surface), lg) + ' m²' : ''}`
        el.append(b, s)
        bulle.setLngLat(e.lngLat).setDOMContent(el).addTo(m)
      })
      m.on('mouseleave', 'lots-fond', () => { if (survol != null) m.setFeatureState({ source: 'lots', id: survol }, { survol: false }); survol = null })
      setPrete(true)
    })
    return () => { m.remove(); carte.current = null }
  }, [])

  /* ---------- noms des lieux dans la langue de l'interface ---------- */
  useEffect(() => {
    const m = carte.current
    if (!m || !prete) return
    for (const l of m.getStyle().layers) {
      if (l.type !== 'symbol' || l.source !== 'openmaptiles') continue
      const champ = m.getLayoutProperty(l.id, 'text-field')
      if (!champ) continue
      m.setLayoutProperty(l.id, 'text-field', langue === 'ar'
        ? ['coalesce', ['get', 'name:ar'], ['get', 'name']]
        : ['coalesce', ['get', `name:${langue}`], ['get', 'name:latin'], ['get', 'name']])
    }
    m.setLayoutProperty('zone-nom', 'text-field', ['get', langue === 'ar' ? 'nom_ar' : 'nom'])
  }, [langue, prete])

  /* ---------- données ---------- */
  useEffect(() => {
    if (prete) (carte.current?.getSource('zones') as GeoJSONSource | undefined)?.setData(zonesGeo(zones))
  }, [zones, prete])

  useEffect(() => {
    if (prete) (carte.current?.getSource('lots') as GeoJSONSource | undefined)?.setData(lotsGeo(lots))
  }, [lots, prete])

  useEffect(() => {
    const m = carte.current
    if (!m || !prete) return
    m.setLayoutProperty('satellite', 'visibility', fond === 'satellite' ? 'visible' : 'none')
  }, [fond, prete])

  /* ---------- zone choisie : la carte s'y rend ---------- */
  useEffect(() => {
    const m = carte.current
    if (!m || !prete) return
    m.setFilter('zone-choisie', ['==', ['get', 'id'], zoneChoisie?.zone_id ?? -1])
    const pad = { top: 60, bottom: 60, left: marges.gauche + 40, right: marges.droite + 40 }
    if (!zoneChoisie) { m.fitBounds(TUNISIE, { padding: pad, duration: 1200 }); return }
    const avecContour = lots.filter((l) => l.zone_id === zoneChoisie.zone_id && l.contour.length >= 3)
    if (avecContour.length) {
      const b = new maplibregl.LngLatBounds()
      avecContour.forEach((l) => l.contour.forEach((p) => b.extend(p)))
      m.fitBounds(b, { padding: pad, maxZoom: 17, duration: 1600 })
    } else {
      m.flyTo({ center: [zoneChoisie.lng, zoneChoisie.lat], zoom: 14, duration: 1600, padding: pad })
    }
  }, [zoneChoisie, lots, prete, marges.gauche, marges.droite])

  /* ---------- lot choisi ---------- */
  useEffect(() => {
    const m = carte.current
    if (!m || !prete) return
    m.setFilter('lots-choisi', ['==', ['get', 'id'], lotChoisi ?? -1])
    const l = lots.find((x) => x.lot_id === lotChoisi)
    if (l && l.contour.length >= 3) {
      const b = new maplibregl.LngLatBounds()
      l.contour.forEach((p) => b.extend(p))
      m.fitBounds(b, { padding: { top: 120, bottom: 120, left: marges.gauche + 120, right: marges.droite + 120 }, maxZoom: 17.5, duration: 1200 })
    }
  }, [lotChoisi, lots, prete, marges.gauche, marges.droite])

  /* ---------- zones citées par Dalila : repères qui pulsent ---------- */
  useEffect(() => {
    const m = carte.current
    if (!m || !prete) return
    reperes.current.forEach((r) => r.remove())
    reperes.current = citees.map((id) => zones.find((z) => z.zone_id === id)).filter((z): z is Zone => !!z).map((z) => {
      const el = document.createElement('div'); el.className = 'repere-cite'
      return new maplibregl.Marker({ element: el }).setLngLat([z.lng, z.lat]).addTo(m)
    })
  }, [citees, zones, prete])

  return (
    <div className="relative h-full w-full">
      <div ref={boite} className="h-full w-full" role="region" aria-label={t.titre} />

      {/* fond de carte */}
      <div className="absolute top-3 start-3 z-10 flex rounded-xl bg-white/95 p-1 shadow-carte backdrop-blur">
        {(['plan', 'satellite'] as const).map((f) => (
          <BoutonFond key={f} actif={fond === f} onClick={() => onFond(f)}>
            {f === 'plan' ? <IconeCarte size={16} aria-hidden /> : <Satellite size={16} aria-hidden />}
            {f === 'plan' ? t.plan : t.satellite}
          </BoutonFond>
        ))}
      </div>

      {/* légende */}
      <div className="absolute bottom-8 start-3 z-10 hidden w-56 rounded-2xl bg-white/95 shadow-carte backdrop-blur sm:block">
        <button type="button" onClick={() => setLegende(!legende)} aria-expanded={legende}
          className="flex w-full items-center gap-2 px-4 py-3 text-sm font-semibold text-marine">
          <Layers size={16} aria-hidden /> {t.legende}
          <ChevronDown size={16} className={clsx('ms-auto transition-transform', legende && 'rotate-180')} aria-hidden />
        </button>
        {legende && (
          <ul className="space-y-1.5 px-4 pb-4 text-[13px]">
            <li className="flex items-center gap-2.5"><span className="size-3.5 rounded-full bg-vert ring-2 ring-white" />{langue === 'ar' ? 'منطقة بها مقاسم متاحة' : langue === 'en' ? 'Zone with available lots' : 'Zone avec lots disponibles'}</li>
            <li className="flex items-center gap-2.5"><span className="size-3.5 rounded-full bg-alerte ring-2 ring-white" />{langue === 'ar' ? 'مقاسم للبتة فقط' : langue === 'en' ? 'Auction lots only' : 'Lots aux enchères seulement'}</li>
            <li className="flex items-center gap-2.5"><span className="grid size-5 place-items-center rounded-full bg-marine text-[10px] font-bold text-white">12</span>{langue === 'ar' ? 'مجموعة مناطق' : langue === 'en' ? 'Group of zones' : 'Groupe de zones'}</li>
            <li className="pt-1 text-xs font-semibold uppercase tracking-wide text-doux">{t.lots}</li>
            {(Object.keys(ETATS) as Statut[]).map((k) => (
              <li key={k} className="flex items-center gap-2.5">
                <span className="h-3 w-4 rounded-sm border-2" style={{ borderColor: ETATS[k].couleur, background: ETATS[k].couleur + '66', borderStyle: ETATS[k].motif === 'plein' ? 'solid' : ETATS[k].motif === 'tirets' ? 'dashed' : 'dotted' }} />
                {ETATS[k][langue]}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function BoutonFond({ actif, onClick, children }: { actif: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={actif}
      className={clsx('flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition',
        actif ? 'bg-marine text-white shadow' : 'text-doux hover:bg-fond hover:text-marine')}>
      {children}
    </button>
  )
}
