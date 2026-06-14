# SoinAtlas

**Annuaire cartographique des professionnels de santé** — pipeline de données +
interface web au-dessus de l'**Annuaire Santé (RPPS)**, à partir des données
ouvertes de l'État (≈1,08 M de praticiens).

**Sources** : Agence du Numérique en Santé (ANS), DREES, Santé.fr — via
[data.gouv.fr](https://www.data.gouv.fr).
**Licence des données** : [Licence Ouverte / Open Licence Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
(réutilisation libre, y compris commerciale, avec attribution).
**Licence du code** : MIT (voir [`LICENSE`](LICENSE)).

> ⚠️ Ce dépôt ne contient **aucune donnée**. Les jeux de données sont
> téléchargés depuis data.gouv.fr (ou générés synthétiquement, voir plus bas).

---

## Ce que fait le projet

1. **Télécharge** les fichiers de l'extraction RPPS libre accès (≈1,1 Go).
2. **Charge** dans PostgreSQL (streaming, faible RAM, détection auto des colonnes).
3. **Consolide** en une vue `annuaire` (1 ligne par activité, spécialités agrégées)
   + tables d'enrichissement (centroïdes communes, contours départements, lieux
   solidaires, zones sous-dotées).
4. **Expose** une API REST (FastAPI) **et** une interface web (carte Mapbox,
   recherche, stats) servie sur le même port.

```
01_download.sh        téléchargement des fichiers RPPS
02_load_postgres.py   chargement + index
03_views.sql          vue consolidée `annuaire` + index trigram
04_api.py             API REST + sert l'interface web (/)
index.html            interface web (un seul fichier, zéro build)
make_sample.py        génère un échantillon synthétique (tester sans le 1 Go)
```

---

## Démarrage rapide

### Prérequis
- PostgreSQL (avec l'extension `pg_trgm`)
- Python 3.11+
- Un **token Mapbox** gratuit ([account.mapbox.com](https://account.mapbox.com/access-tokens/)) pour la carte

### 1. Environnement Python
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Base de données
```bash
createdb rpps
export DSN="postgresql://localhost:5432/rpps"
psql "$DSN" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

### 3. Données — au choix

**Option A — échantillon synthétique (rapide, sans téléchargement, sans données réelles)**
```bash
python make_sample.py --n 5000 --out ./data
```

**Option B — vraies données RPPS (~1,1 Go)**
```bash
bash 01_download.sh ./data
```

### 4. Chargement + vues
```bash
python 02_load_postgres.py --data ./data --dsn "$DSN"
psql "$DSN" -f 03_views.sql
```

> Les tables d'enrichissement (communes, départements, lieux solidaires, zones
> sous-dotées) sont peuplées par des scripts ponctuels qui appellent
> `geo.api.gouv.fr` et data.gouv.fr. Voir les commentaires dans `04_api.py`
> (endpoints `/geo/*`) pour les tables attendues : `communes_geo`,
> `departements_geo`, `lieux_solidaires`, `zones_sous_dotees`.

### 5. Lancer l'API + l'interface
```bash
export MAPBOX_TOKEN="pk.xxxxxxxx"     # votre token Mapbox
uvicorn 04_api:app --port 8000 --reload
# -> interface  : http://localhost:8000
# -> docs API   : http://localhost:8000/docs
```

---

## Configuration (variables d'environnement)

| Variable        | Défaut                                      | Rôle |
|-----------------|---------------------------------------------|------|
| `DSN`           | `postgresql://rpps:rpps@localhost:5432/rpps`| Connexion PostgreSQL |
| `MAPBOX_TOKEN`  | *(vide)*                                    | Token Mapbox, **injecté côté serveur** dans la page. Sans token, l'interface fonctionne mais la carte est désactivée. |

Le token n'est **jamais écrit dans le code** : `index.html` contient un
placeholder `__MAPBOX_TOKEN__` que `04_api.py` remplace à la volée par la valeur
de `MAPBOX_TOKEN`. Pensez à **restreindre votre token par URL** sur mapbox.com.

---

## Interface web

- **Recherche** : nom/prénom, profession, ville, département, spécialité,
  secteur d'activité, « avec téléphone » — instantanée (debounce) + pagination.
- **Fiche praticien** : coordonnées professionnelles, structure, diplômes.
- **Carte** (3 vues exclusives + 1 overlay) :
  - *Densité de médecins* (choroplèthe /100 000 hab. — révèle les déserts médicaux)
  - *Points par code postal* (agrégat de praticiens)
  - *Zones sous-dotées* (installations de généralistes, DREES)
  - overlay *Lieux de consultation solidaire* (Santé.fr)
- **Stats** : par profession, par département, zones sous-dotées.

---

## API (extraits)

```
GET /praticiens?profession=&departement=&ville=&specialite=&secteur=&avec_tel=&q=&page=
GET /praticiens/{rpps}
GET /geo/praticiens     (GeoJSON, agrégat par code postal — suit les filtres)
GET /geo/densite?profession=Médecin   (choroplèthe densité /100k hab.)
GET /geo/zones-sous-dotees            (choroplèthe départemental)
GET /geo/solidaires                   (points lieux solidaires)
GET /stats/professions | /stats/departements | /stats/specialites | /stats/secteurs
GET /zones-sous-dotees
```

---

## Notes & limites connues

- La vue `annuaire` a **1 ligne par activité**, pas par praticien : un médecin
  exerçant sur N sites apparaît N fois.
- Le champ « Code Département » de l'extraction est vide → le département est
  **dérivé du code postal** (2 chiffres ; 3 pour l'outre-mer ; Corse 2A/2B selon
  la tranche de CP).
- Choroplèthes **métropole uniquement** (contours `france-geojson`). Les DOM
  restent présents dans le panneau stats.

## ⚠️ RGPD

Ce sont des **données personnelles de professionnels**. Pour une publication :
- ne diffuser que les **coordonnées professionnelles** de l'extraction libre accès ;
- prévoir une procédure de **droit d'opposition / déréférencement** ;
- **citer la source** (Annuaire Santé / ANS · DREES · Santé.fr, Licence Ouverte 2.0).

Le `.gitignore` exclut `data/` pour éviter tout commit accidentel de données réelles.
