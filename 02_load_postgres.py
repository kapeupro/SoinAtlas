#!/usr/bin/env python3
"""
Chargement des fichiers RPPS (Annuaire Santé) dans PostgreSQL.

- Fichiers source : .txt séparés par "|", encodage UTF-8, avec en-tête.
- Détection automatique des noms de colonnes (ils peuvent varier légèrement
  d'une extraction mensuelle à l'autre : accents, espaces, casse).
- Chargement en streaming par lots -> pas besoin de tout charger en RAM.
- Clé de jointure entre les 3 fichiers : l'identifiant RPPS ("Identifiant PP").

Usage :
    pip install psycopg2-binary
    python scripts/02_load_postgres.py --data ./data --dsn "postgresql://user:pass@localhost:5432/rpps"
"""
import argparse
import csv
import io
import os
import re
import sys
import unicodedata

import psycopg2
from psycopg2.extras import execute_values

BATCH = 5000
DELIM = "|"

FILES = {
    "personne_activite": "PS_LibreAcces_Personne_activite.txt",
    "diplomes":          "PS_LibreAcces_Dipl_AutExerc.txt",
    "savoir_faire":      "PS_LibreAcces_SavoirFaire.txt",
}


def slug(col: str) -> str:
    """Normalise un en-tête de colonne en nom SQL sûr : 'Nom d'exercice' -> nom_d_exercice."""
    s = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "col"


def read_header(path: str):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=DELIM)
        return next(reader)


def create_table(cur, table: str, headers):
    cols = [slug(h) for h in headers]
    # déduplication des noms de colonnes
    seen, final = {}, []
    for c in cols:
        if c in seen:
            seen[c] += 1
            final.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            final.append(c)
    coldefs = ", ".join(f'"{c}" TEXT' for c in final)
    cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
    cur.execute(f'CREATE TABLE "{table}" ({coldefs});')
    return final


def load_file(conn, table: str, path: str):
    headers = read_header(path)
    with conn.cursor() as cur:
        cols = create_table(cur, table, headers)
        ncols = len(cols)
        collist = ", ".join(f'"{c}"' for c in cols)
        insert = f'INSERT INTO "{table}" ({collist}) VALUES %s'

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=DELIM)
            next(reader)  # skip header
            batch, total = [], 0
            for row in reader:
                # ajuste la longueur de la ligne au nombre de colonnes
                if len(row) < ncols:
                    row = row + [""] * (ncols - len(row))
                elif len(row) > ncols:
                    row = row[:ncols]
                batch.append(row)
                if len(batch) >= BATCH:
                    execute_values(cur, insert, batch)
                    total += len(batch)
                    batch = []
                    print(f"  {table}: {total:,} lignes…", end="\r")
            if batch:
                execute_values(cur, insert, batch)
                total += len(batch)
        conn.commit()
        print(f"  {table}: {total:,} lignes chargées." + " " * 20)
    return cols


def add_indexes(conn):
    """Index sur la clé RPPS + colonnes de filtre courantes, si elles existent."""
    candidates = {
        "personne_activite": ["identifiant_pp", "code_profession", "libelle_profession",
                               "commune_coordonnees_structure", "departement"],
        "diplomes":          ["identifiant_pp"],
        "savoir_faire":      ["identifiant_pp", "libelle_savoir_faire"],
    }
    with conn.cursor() as cur:
        for table, cols in candidates.items():
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                (table,))
            existing = {r[0] for r in cur.fetchall()}
            for col in cols:
                if col in existing:
                    idx = f"idx_{table}_{col}"
                    cur.execute(
                        f'CREATE INDEX IF NOT EXISTS "{idx}" ON "{table}" ("{col}");')
                    print(f"  index: {idx}")
        conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./data")
    ap.add_argument("--dsn", required=True, help="postgresql://user:pass@host:port/db")
    args = ap.parse_args()

    conn = psycopg2.connect(args.dsn)
    for table, fname in FILES.items():
        path = os.path.join(args.data, fname)
        if not os.path.exists(path):
            print(f"!! fichier manquant, ignoré : {path}")
            continue
        print(f"==> Chargement {fname} -> table {table}")
        cols = load_file(conn, table, path)
        print(f"    colonnes : {', '.join(cols[:8])}{' …' if len(cols) > 8 else ''}")

    print("==> Création des index…")
    add_indexes(conn)
    conn.close()
    print("==> Terminé.")


if __name__ == "__main__":
    main()
