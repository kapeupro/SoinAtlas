#!/usr/bin/env python3
"""
Génère un échantillon SYNTHÉTIQUE des 3 fichiers RPPS, au format attendu par
`02_load_postgres.py` (séparateur « | », en-tête en 1re ligne, UTF-8).

But : permettre de faire tourner toute la chaîne (chargement -> vues -> API ->
carte) SANS télécharger le ~1 Go de données réelles, et sans manipuler de
données personnelles réelles. Les praticiens, noms et structures sont inventés ;
seuls les codes postaux / communes sont réels (pris dans une petite liste) pour
que la géolocalisation de la carte fonctionne.

    python make_sample.py --n 5000 --out ./data
"""
import argparse
import os
import random

# Quelques communes réelles (code postal, ville, département) réparties sur le
# territoire — assez pour que les jointures géo et le choroplèthe aient du sens.
COMMUNES = [
    ("75011", "PARIS 11E ARRONDISSEMENT", "75"), ("69003", "LYON 3E ARRONDISSEMENT", "69"),
    ("13006", "MARSEILLE 6E ARRONDISSEMENT", "13"), ("31000", "TOULOUSE", "31"),
    ("44000", "NANTES", "44"), ("33000", "BORDEAUX", "33"), ("59000", "LILLE", "59"),
    ("67000", "STRASBOURG", "67"), ("35000", "RENNES", "35"), ("06000", "NICE", "06"),
    ("38000", "GRENOBLE", "38"), ("21000", "DIJON", "21"), ("49000", "ANGERS", "49"),
    ("63000", "CLERMONT-FERRAND", "63"), ("87000", "LIMOGES", "87"), ("19000", "TULLE", "19"),
    ("15000", "AURILLAC", "15"), ("48000", "MENDE", "48"), ("23000", "GUERET", "23"),
    ("32000", "AUCH", "32"), ("20000", "AJACCIO", "2A"), ("20200", "BASTIA", "2B"),
    ("97200", "FORT-DE-FRANCE", "972"), ("97400", "SAINT-DENIS", "974"),
    ("50000", "SAINT-LO", "50"), ("55000", "BAR-LE-DUC", "55"),
]
PROFESSIONS = [
    ("10", "Médecin"), ("60", "Infirmier"), ("40", "Chirurgien-Dentiste"),
    ("50", "Sage-Femme"), ("70", "Masseur-Kinésithérapeute"), ("21", "Pharmacien"),
]
SPECIALITES = ["Médecine Générale", "Cardiologie et maladie vasculaires", "Pédiatrie",
               "Psychiatrie", "Radio-diagnostic", "Dermatologie et vénérologie",
               "Gynécologie-obstétrique", "Ophtalmologie", "Anesthesie-réanimation"]
SECTEURS = ["Cabinet individuel", "Cabinet de groupe", "Etablissement Public de santé",
            "Exercice en Société", "Pharmacie d'officine", "Etab. Privé Non PSPH"]
MODES = ["Libéral", "Salarié"]
NOMS = ["MARTIN", "BERNARD", "DUBOIS", "THOMAS", "ROBERT", "RICHARD", "PETIT", "DURAND",
        "LEROY", "MOREAU", "SIMON", "LAURENT", "LEFEBVRE", "MICHEL", "GARCIA", "DAVID"]
PRENOMS = ["Marie", "Pierre", "Sophie", "Jean", "Camille", "Thomas", "Julie", "Nicolas",
           "Claire", "Paul", "Léa", "Antoine", "Emma", "Lucas", "Chloé", "Hugo"]

# En-têtes EXACTS des 3 fichiers réels (slugifiés identiquement par le loader).
H_PERSONNE = [
    "Type d'identifiant PP", "Identifiant PP", "Identification nationale PP",
    "Code civilité d'exercice", "Libellé civilité d'exercice", "Code civilité",
    "Libellé civilité", "Nom d'exercice", "Prénom d'exercice", "Code profession",
    "Libellé profession", "Code catégorie professionnelle", "Libellé catégorie professionnelle",
    "Code type savoir-faire", "Libellé type savoir-faire", "Code savoir-faire",
    "Libellé savoir-faire", "Code mode exercice", "Libellé mode exercice",
    "Numéro SIRET site", "Numéro SIREN site", "Numéro FINESS site",
    "Numéro FINESS établissement juridique", "Identifiant technique de la structure",
    "Raison sociale site", "Enseigne commerciale site",
    "Complément destinataire (coord. structure)", "Complément point géographique (coord. structure)",
    "Numéro Voie (coord. structure)", "Indice répétition voie (coord. structure)",
    "Code type de voie (coord. structure)", "Libellé type de voie (coord. structure)",
    "Libellé Voie (coord. structure)", "Mention distribution (coord. structure)",
    "Bureau cedex (coord. structure)", "Code postal (coord. structure)",
    "Code commune (coord. structure)", "Libellé commune (coord. structure)",
    "Code pays (coord. structure)", "Libellé pays (coord. structure)",
    "Téléphone (coord. structure)", "Téléphone 2 (coord. structure)",
    "Télécopie (coord. structure)", "Adresse e-mail (coord. structure)",
    "Code Département (structure)", "Libellé Département (structure)",
    "Ancien identifiant de la structure", "Autorité d'enregistrement",
    "Code secteur d'activité", "Libellé secteur d'activité",
    "Code section tableau pharmaciens", "Libellé section tableau pharmaciens",
    "Code rôle", "Libellé rôle", "Code genre activité", "Libellé genre activité",
]
H_SAVOIR = [
    "Type d'identifiant PP", "Identifiant PP", "Identification nationale PP",
    "Nom d'exercice", "Prénom d'exercice", "Code profession", "Libellé profession",
    "Code catégorie professionnelle", "Libellé catégorie professionnelle",
    "Code type savoir-faire", "Libellé type savoir-faire", "Code savoir-faire",
    "Libellé savoir-faire",
]
H_DIPL = [
    "Type d'identifiant PP", "Identifiant PP", "Identification nationale PP",
    "Nom d'exercice", "Prénom d'exercice", "Code type diplôme obtenu",
    "Libellé type diplôme obtenu", "Code diplôme obtenu", "Libellé diplôme obtenu",
    "Code type autorisation", "Libellé type autorisation",
    "Code discipline autorisation", "Libellé discipline autorisation",
]


def cell(values, header, **overrides):
    """Construit une ligne complète (colonnes vides par défaut, surchargées par nom)."""
    row = {h: "" for h in header}
    row.update(overrides)
    return "|".join(row[h] for h in header)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000, help="nombre de praticiens à générer")
    ap.add_argument("--out", default="./data")
    args = ap.parse_args()
    rng = random.Random(42)  # déterministe : même échantillon à chaque run
    os.makedirs(args.out, exist_ok=True)

    f_pers = open(os.path.join(args.out, "PS_LibreAcces_Personne_activite.txt"), "w", encoding="utf-8")
    f_sav = open(os.path.join(args.out, "PS_LibreAcces_SavoirFaire.txt"), "w", encoding="utf-8")
    f_dip = open(os.path.join(args.out, "PS_LibreAcces_Dipl_AutExerc.txt"), "w", encoding="utf-8")
    f_pers.write("|".join(H_PERSONNE) + "\n")
    f_sav.write("|".join(H_SAVOIR) + "\n")
    f_dip.write("|".join(H_DIPL) + "\n")

    for i in range(args.n):
        rpps = f"99{i:09d}"  # identifiant fictif (préfixe 99, jamais utilisé en vrai)
        nom, prenom = rng.choice(NOMS), rng.choice(PRENOMS)
        code_prof, lib_prof = rng.choice(PROFESSIONS)
        cp, ville, _dep = rng.choice(COMMUNES)
        spec = rng.choice(SPECIALITES)
        tel = f"0{rng.randint(1,5)}{rng.randint(10000000,99999999)}" if rng.random() < 0.45 else ""
        email = f"{prenom.lower()}.{nom.lower()}@exemple.fr" if rng.random() < 0.1 else ""
        base = dict(zip(["Identifiant PP", "Nom d'exercice", "Prénom d'exercice",
                         "Code profession", "Libellé profession"],
                        [rpps, nom, prenom, code_prof, lib_prof]))

        f_pers.write(cell(base, H_PERSONNE,
            **{"Type d'identifiant PP": "8", "Libellé civilité d'exercice": rng.choice(["M", "Mme"]),
               "Libellé mode exercice": rng.choice(MODES),
               "Raison sociale site": f"{rng.choice(['CABINET', 'CENTRE', 'POLE'])} {nom}",
               "Numéro Voie (coord. structure)": str(rng.randint(1, 200)),
               "Libellé type de voie (coord. structure)": rng.choice(["RUE", "AVENUE", "BOULEVARD"]),
               "Libellé Voie (coord. structure)": rng.choice(["DE LA REPUBLIQUE", "VICTOR HUGO", "PASTEUR", "DE LA GARE"]),
               "Code postal (coord. structure)": cp, "Libellé commune (coord. structure)": ville,
               "Téléphone (coord. structure)": tel, "Adresse e-mail (coord. structure)": email,
               "Libellé secteur d'activité": rng.choice(SECTEURS)}) + "\n")

        if rng.random() < 0.7:
            f_sav.write(cell(base, H_SAVOIR, **{"Libellé savoir-faire": spec}) + "\n")

        f_dip.write(cell(base, H_DIPL,
            **{"Libellé diplôme obtenu": f"Diplôme d'État de {lib_prof}"}) + "\n")

    for f in (f_pers, f_sav, f_dip):
        f.close()
    print(f"Échantillon généré dans {args.out}/ : {args.n} praticiens synthétiques.")
    print("Chaîne complète : python 02_load_postgres.py --data", args.out,
          '--dsn "$DSN"  puis  psql "$DSN" -f 03_views.sql')


if __name__ == "__main__":
    main()
