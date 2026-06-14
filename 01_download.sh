#!/usr/bin/env bash
# Télécharge les 3 fichiers de l'extraction RPPS en libre accès (Annuaire Santé / ANS)
# Source : data.gouv.fr — Licence Ouverte Etalab 2.0
set -euo pipefail

DATA_DIR="${1:-./data}"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

echo "==> Téléchargement des fichiers RPPS (≈1,1 Go au total)…"

# Fichier principal : identité + activité + structure d'exercice (≈769 Mo)
curl -L --fail --progress-bar \
  "https://www.data.gouv.fr/api/1/datasets/r/fffda7e9-0ea2-4c35-bba0-4496f3af935d" \
  -o "PS_LibreAcces_Personne_activite.txt"

# Annexe 1 : diplômes et autorisations d'exercice (≈260 Mo)
curl -L --fail --progress-bar \
  "https://www.data.gouv.fr/api/1/datasets/r/41ae70ac-90c8-4c4e-8644-4ef1b100f045" \
  -o "PS_LibreAcces_Dipl_AutExerc.txt"

# Annexe 2 : savoir-faire et spécialités (≈49 Mo)
curl -L --fail --progress-bar \
  "https://www.data.gouv.fr/api/1/datasets/r/fb55f15f-bd61-4402-b551-51ef387f2fab" \
  -o "PS_LibreAcces_SavoirFaire.txt"

echo "==> Terminé. Fichiers dans $DATA_DIR :"
ls -lh
