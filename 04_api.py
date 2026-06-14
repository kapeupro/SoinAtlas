#!/usr/bin/env python3
"""
API de recherche dans l'annuaire RPPS.

    pip install fastapi uvicorn psycopg2-binary
    export DSN="postgresql://rpps:rpps@localhost:5432/rpps"
    uvicorn scripts.04_api:app --reload

Endpoints :
    GET /praticiens?profession=Médecin&departement=69&q=durand&page=1
    GET /praticiens/{rpps}
    GET /stats/professions
    GET /stats/departements
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse

DSN = os.environ.get("DSN", "postgresql://rpps:rpps@localhost:5432/rpps")
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")
PAGE_SIZE = 20
INDEX_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

app = FastAPI(title="Annuaire RPPS")


@app.get("/", include_in_schema=False)
def home():
    # Le token Mapbox n'est jamais écrit dans le dépôt : il est injecté ici
    # depuis la variable d'environnement MAPBOX_TOKEN (placeholder dans index.html).
    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read().replace("__MAPBOX_TOKEN__", MAPBOX_TOKEN)
    return HTMLResponse(html)


def db():
    return psycopg2.connect(DSN, cursor_factory=RealDictCursor)


@app.get("/praticiens")
def search(
    profession: str | None = None,
    departement: str | None = None,
    ville: str | None = None,
    specialite: str | None = None,
    secteur: str | None = None,
    avec_tel: bool = False,
    q: str | None = Query(None, description="recherche nom/prénom"),
    page: int = 1,
):
    where, params = [], []
    if profession:
        where.append("libelle_profession ILIKE %s"); params.append(f"%{profession}%")
    if departement:
        where.append("departement = %s"); params.append(departement)
    if ville:
        where.append("ville ILIKE %s"); params.append(f"%{ville}%")
    if specialite:
        where.append("specialites ILIKE %s"); params.append(f"%{specialite}%")
    if secteur:
        where.append("secteur = %s"); params.append(secteur)
    if avec_tel:
        where.append("telephone IS NOT NULL")
    if q:
        where.append("(nom_d_exercice || ' ' || prenom_d_exercice) ILIKE %s")
        params.append(f"%{q}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (max(page, 1) - 1) * PAGE_SIZE

    with db() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM annuaire {clause}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT * FROM annuaire {clause} ORDER BY nom_d_exercice "
            f"LIMIT {PAGE_SIZE} OFFSET {offset}", params)
        rows = cur.fetchall()
    return {"total": total, "page": page, "page_size": PAGE_SIZE, "results": rows}


@app.get("/geo/praticiens")
def geo(
    profession: str | None = None,
    departement: str | None = None,
    ville: str | None = None,
    specialite: str | None = None,
    secteur: str | None = None,
    avec_tel: bool = False,
    q: str | None = None,
):
    """Agrégat par code postal (centroïde commune) -> GeoJSON pour la carte."""
    where, params = [], []
    if profession:
        where.append("a.libelle_profession ILIKE %s"); params.append(f"%{profession}%")
    if departement:
        where.append("a.departement = %s"); params.append(departement)
    if ville:
        where.append("a.ville ILIKE %s"); params.append(f"%{ville}%")
    if specialite:
        where.append("a.specialites ILIKE %s"); params.append(f"%{specialite}%")
    if secteur:
        where.append("a.secteur = %s"); params.append(secteur)
    if avec_tel:
        where.append("a.telephone IS NOT NULL")
    if q:
        where.append("(a.nom_d_exercice || ' ' || a.prenom_d_exercice) ILIKE %s")
        params.append(f"%{q}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    # On agrège d'abord annuaire par code postal seul : l'index
    # (code_postal, identifiant_pp) permet un group-aggregate en flux,
    # puis on joint les ~6 300 centroïdes de communes_geo à la fin.
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""WITH par_cp AS (
                    SELECT a.code_postal,
                           min(a.ville) AS ville,
                           COUNT(DISTINCT a.identifiant_pp) AS nb
                    FROM annuaire a
                    {clause}
                    GROUP BY a.code_postal
                )
                SELECT g.lon, g.lat, c.code_postal, c.ville, c.nb
                FROM par_cp c
                JOIN communes_geo g ON g.code_postal = c.code_postal""", params)
        rows = cur.fetchall()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {"cp": r["code_postal"], "ville": r["ville"], "nb": r["nb"]},
        } for r in rows],
    }


@app.get("/geo/solidaires")
def geo_solidaires():
    """Lieux de consultation solidaire (« Un médecin près de chez vous ») — points Santé.fr."""
    with db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT titre, adresse, code_postal, ville, lon, lat,
                              type_structure, telephone, site, infos
                       FROM lieux_solidaires""")
        rows = cur.fetchall()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {k: r[k] for k in
                ("titre", "adresse", "code_postal", "ville", "type_structure",
                 "telephone", "site", "infos")},
        } for r in rows],
    }


@app.get("/geo/densite")
def geo_densite(profession: str = "Médecin"):
    """Densité de praticiens pour 100 000 habitants, par département (choroplèthe lisible)."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """WITH par_dep AS (
                    SELECT departement AS code,
                           COUNT(DISTINCT identifiant_pp) AS nb
                    FROM annuaire
                    WHERE libelle_profession ILIKE %s AND departement IS NOT NULL
                    GROUP BY departement
                )
                SELECT d.code, d.nom, d.population, d.contour,
                       COALESCE(p.nb, 0) AS nb,
                       CASE WHEN d.population > 0
                            THEN round(100000.0 * COALESCE(p.nb, 0) / d.population, 1)
                       END AS densite
                FROM departements_geo d
                LEFT JOIN par_dep p ON p.code = d.code""",
            (f"%{profession}%",))
        rows = cur.fetchall()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": r["contour"],
            "properties": {
                "code": r["code"], "nom": r["nom"],
                "nb": r["nb"], "population": r["population"],
                "densite": float(r["densite"]) if r["densite"] is not None else None,
            },
        } for r in rows],
    }


@app.get("/geo/zones-sous-dotees")
def geo_zsd():
    """Contours départementaux + effectif d'installations en zones sous-dotées (choroplèthe)."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.code, d.nom, d.contour,
                      z.effectif, z.taux_evolution
               FROM departements_geo d
               LEFT JOIN zones_sous_dotees z
                 ON z.code_departement = d.code AND z.code_departement <> '999'""")
        rows = cur.fetchall()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": r["contour"],
            "properties": {
                "code": r["code"], "nom": r["nom"],
                "effectif": r["effectif"] or 0,
                "taux": r["taux_evolution"],
            },
        } for r in rows],
    }


@app.get("/zones-sous-dotees")
def zones(annee: str | None = None):
    """Installations de généralistes en zones sous-dotées, par département (DREES)."""
    with db() as conn, conn.cursor() as cur:
        # departement = '999' = agrégat régional, exclu de la vue par département
        cur.execute(
            """SELECT code_departement, libelle_departement, libelle_region,
                      effectif, taux_evolution, annee
               FROM zones_sous_dotees
               WHERE code_departement <> '999'
               ORDER BY effectif DESC NULLS LAST""")
        return cur.fetchall()


@app.get("/praticiens/{rpps}")
def detail(rpps: str):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM annuaire WHERE identifiant_pp = %s", (rpps,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Praticien introuvable")
        cur.execute("SELECT * FROM diplomes WHERE identifiant_pp = %s", (rpps,))
        row["diplomes"] = cur.fetchall()
    return row


@app.get("/stats/professions")
def stats_prof():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT libelle_profession AS profession, COUNT(*) AS nb "
            "FROM annuaire GROUP BY 1 ORDER BY 2 DESC")
        return cur.fetchall()


@app.get("/stats/specialites")
def stats_spec():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT libelle_savoir_faire AS specialite, "
            "COUNT(DISTINCT identifiant_pp) AS nb "
            "FROM savoir_faire WHERE libelle_savoir_faire <> '' "
            "GROUP BY 1 ORDER BY 2 DESC")
        return cur.fetchall()


@app.get("/stats/secteurs")
def stats_secteurs():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT secteur, COUNT(*) AS nb FROM annuaire "
            "WHERE secteur <> '' GROUP BY 1 ORDER BY 2 DESC")
        return cur.fetchall()


@app.get("/stats/departements")
def stats_dep():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT departement, COUNT(*) AS nb "
            "FROM annuaire GROUP BY 1 ORDER BY 2 DESC")
        return cur.fetchall()
