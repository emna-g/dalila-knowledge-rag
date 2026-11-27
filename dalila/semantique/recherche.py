"""Recherche des passages à citer, directement dans MariaDB (passages et vecteurs dans dalila_passages).

    from dalila.semantique.recherche import Recherche
    r = Recherche(modele="bge", reranker=True)   # « e5 » est le modèle léger de secours
    r.chercher("comodités près de Sidi Achour", zone_ids=["930508"], k=5)

Étapes :
1) Lexique : un message tunisien reçoit les mots équivalents (français, arabe standard) ; sinon rien ne change.
2) Pré-filtres SQL : passages « principaux », assez longs (pas les mentions légales), et — si une zone est
   reconnue — seulement les cahiers des charges DE CETTE zone (les autres zones sont écartées).
3) Recherche par le sens : distance cosinus calculée par MariaDB (VEC_DISTANCE_COSINE), recherche exacte.
4) Recherche par mots-clés (BM25) sur les mêmes passages.
5) Fusion des deux classements (RRF), bonus aux réponses validées par l'AFI, langue de la question en premier,
   fiches de l'autre régime (littoral / régional) écartées, au plus 2 passages par page.
6) Option : reclassement des 20 premiers par un « reranker » (modèle qui lit la question et le passage ensemble).
"""
import collections, math, re
from dalila.config import MODELE, MODELES_RECHERCHE, NOM_RERANKER, RERANKER, db
from dalila.langue.lexique.outils.normaliser import NormaliseurTunisien, tokens

PRIORITAIRES = {"reponse_validee_afi": 1.0, "fiche_zone": 1.0, "formulaire": 0.6, "procedure": 0.6}
AUTRE_REGIME = {"developpement_regional": {15, 16, 17}, "littoral": {12, 13, 14}}  # fiches AFI, vérifiées sur les titres
STOP = set("le la les de des du un une et a au aux en dans pour par sur est que qui quoi quel quelle ce il y l d "
           "the of to in and is what how في من على الى إلى و ما".split())


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.tf = [collections.Counter(w for w in tokens(d) if w not in STOP) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df = collections.Counter(w for t in self.tf for w in t)
        self.idf = {w: math.log(1 + (len(docs) - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, q, candidats):
        qt = [w for w in tokens(q) if w not in STOP and w in self.idf]
        out = []
        for i in candidats:
            tf, s = self.tf[i], 0.0
            for w in qt:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s:
                out.append((s, i))
        return [i for _, i in sorted(out, reverse=True)]


class Recherche:
    def __init__(self, modele=MODELE, reranker=RERANKER, lexique=True, echantillon=False):
        self.cfg = MODELES_RECHERCHE[modele]
        self.con = db("root" if echantillon else "ro")
        filtre = " AND id IN (SELECT id FROM dalila_echantillon_eval)" if echantillon else ""
        self.filtre_echantillon = filtre
        with self.con.cursor() as cur:  # sans vecteurs, la recherche par le sens renverrait rien, sans le dire
            cur.execute(f"SELECT COUNT(*) AS avec, SUM({self.cfg['colonne']} IS NULL) AS sans "
                        f"FROM dalila_passages WHERE 1=1{filtre}")
            r = cur.fetchone()
        if not r["avec"] or int(r["sans"] or 0) == r["avec"]:
            if echantillon:
                etapes = (
                    "python -m dalila.connaissances.echantillon --taille 1500, puis "
                    f"python -m dalila.connaissances.vectoriser --modele {modele} --echantillon"
                )
            else:
                etapes = (
                    "python -m dalila.connaissances.echantillon --taille 1500, puis "
                    "python -m dalila.connaissances.vectoriser --modele e5 --echantillon et évaluer cet échantillon; "
                    f"après validation seulement, index complet avec --modele {modele} --index-complet"
                )
            raise RuntimeError(
                f"Aucun vecteur « {modele} » dans dalila_passages ({self.cfg['colonne']} vide) : lancer {etapes}."
            )
        if int(r["sans"] or 0):
            print(f"attention : {r['sans']}/{r['avec']} passages sans vecteur « {modele} » "
                  "(trouvés seulement par mots-clés)")
        from dalila.moteurs.embeddings import modele as charger_modele
        self.modele = charger_modele(modele)  # partagé avec les autres modules (un seul chargement)
        self.reranker = None
        if reranker:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(NOM_RERANKER, device=None, max_length=512)
        self.norm = NormaliseurTunisien() if lexique else None
        with self.con.cursor() as cur:
            cur.execute("SELECT id, type, titre, texte, source_url, date_source, langue, zone_id, page, article, texte_ocr, "
                        f"kb_id, pertinence, contient_chiffre, longueur FROM dalila_passages WHERE 1=1{filtre}")
            self.P = cur.fetchall()
        self.pos = {p["id"]: i for i, p in enumerate(self.P)}
        self.bm25 = BM25([f"{p['titre'] or ''} {p['texte']}" for p in self.P])

    @staticmethod
    def langue_de(question):
        ar = sum("؀" <= ch <= "ۿ" for ch in question)
        lat = sum(ch.isalpha() and ch.isascii() for ch in question)
        return "ar" if ar > lat else "fr"

    def requete(self, question):
        if self.norm is None:
            return question, False
        r = self.norm.analyser(question)
        return r["requete_pour_rag"], r["tunisien"]

    def _garde(self, p, zone_ids):
        if p["pertinence"] == "secondaire" or (p["longueur"] or 0) < 200:
            return False
        if zone_ids and p["type"] == "cahier_des_charges" and p["zone_id"] not in zone_ids:
            return False
        return True

    def chercher(self, question, k=5, zone_ids=None, regime=None, langue="auto", profondeur=60, fiches_afi=None,
                 demarche=False):
        """fiches_afi : fiches de la base de connaissances AFI du service reconnu par le graphe (mises en tête).
        demarche : la question porte sur une démarche (papiers, procédure) : les réponses validées de l'AFI passent devant."""
        q, tn = self.requete(question)
        if langue == "auto":
            langue = self.langue_de(question)
        vec = self.modele.encode([self.cfg["prefixe_question"] + q], normalize_embeddings=True)[0]
        vtxt = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        col = self.cfg["colonne"]
        sql = (f"SELECT id, VEC_DISTANCE_COSINE({col}, VEC_FromText(%s)) AS d FROM dalila_passages "
               f"WHERE {col} IS NOT NULL AND pertinence <> 'secondaire' AND longueur >= 200{self.filtre_echantillon}")
        p = [vtxt]
        if zone_ids:
            sql += " AND (type <> 'cahier_des_charges' OR zone_id IN (" + ",".join(["%s"] * len(zone_ids)) + "))"
            p += list(zone_ids)
        sql += " ORDER BY d LIMIT %s"
        p.append(profondeur)
        with self.con.cursor() as cur:
            cur.execute(sql, p)
            sens = cur.fetchall()
        sim = {r["id"]: 1 - r["d"] for r in sens}
        score = collections.defaultdict(float)
        for rang, r in enumerate(sens):
            score[r["id"]] += 1 / (60 + rang)
        candidats = [i for i, pp in enumerate(self.P) if self._garde(pp, zone_ids)]
        for rang, i in enumerate(self.bm25.scores(q, candidats)[:profondeur]):
            score[self.P[i]["id"]] += 1 / (60 + rang)
        for pp in self.P:  # les fiches du service reconnu sont toujours candidates
            if fiches_afi and pp["kb_id"] in fiches_afi and pp["id"] not in score:
                score[pp["id"]] += 1 / 120
        for i in list(score):
            pp = self.P[self.pos[i]]
            score[i] += PRIORITAIRES.get(pp["type"], 0) * 0.005
            if langue and pp["langue"] not in (langue, "toutes"):
                score[i] -= 0.01
            if fiches_afi and pp["kb_id"] in fiches_afi:
                score[i] += 0.03
            if demarche and pp["type"] == "reponse_validee_afi":
                score[i] += 0.01
            if regime and pp["kb_id"] in AUTRE_REGIME.get(regime, set()):
                del score[i]
        ordre = sorted(score, key=score.get, reverse=True)
        if self.reranker is not None:
            top = ordre[:20]
            rs = self.reranker.predict([(question, self.P[self.pos[i]]["texte"][:1500]) for i in top])
            ordre = [i for _, i in sorted(zip(rs, top), reverse=True)] + ordre[20:]
        out, par_page = [], collections.Counter()
        for i in ordre:
            if len(out) == k:
                break
            pp = self.P[self.pos[i]]
            page = pp["source_url"] if str(pp["source_url"]).startswith("http") else i
            if par_page[page] >= 2:
                continue
            par_page[page] += 1
            out.append({"id": i, "type": pp["type"], "titre": pp["titre"], "source_url": pp["source_url"],
                        "date_source": pp["date_source"], "zone_id": pp["zone_id"], "article": pp["article"],
                        "texte_ocr": bool(pp["texte_ocr"]), "contient_chiffre": bool(pp["contient_chiffre"]),
                        "similarite": round(sim.get(i, 0), 3), "texte": pp["texte"]})
        return {"question": question, "tunisien": tn, "requete": q, "resultats": out}
