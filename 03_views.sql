-- Vue consolidée : un praticien avec ses spécialités agrégées.
-- À lancer après le chargement (scripts/02_load_postgres.py).
-- psql "$DSN" -f scripts/03_views.sql

DROP MATERIALIZED VIEW IF EXISTS annuaire CASCADE;

CREATE MATERIALIZED VIEW annuaire AS
SELECT
    p.identifiant_pp,
    p.libelle_civilite_d_exercice         AS civilite,
    p.nom_d_exercice,
    p.prenom_d_exercice,
    p.code_profession,
    p.libelle_profession,
    p.libelle_mode_exercice               AS mode_d_exercice,
    p.libelle_secteur_d_activite          AS secteur,
    p.raison_sociale_site                 AS raison_sociale_structure,
    -- adresse professionnelle (coordonnées structure, extraction libre accès)
    nullif(trim(concat_ws(' ',
        p.numero_voie_coord_structure,
        p.indice_repetition_voie_coord_structure,
        p.libelle_type_de_voie_coord_structure,
        p.libelle_voie_coord_structure)), '') AS adresse,
    p.code_postal_coord_structure         AS code_postal,
    p.libelle_commune_coord_structure     AS ville,
    -- code_departement_structure est vide dans l'extraction : dérivé du code postal
    -- (2 chiffres, 3 pour l'outre-mer ; la Corse reste "20")
    CASE
        WHEN p.code_postal_coord_structure ~ '^9[78]'  THEN left(p.code_postal_coord_structure, 3)
        WHEN p.code_postal_coord_structure ~ '^20[01]' THEN '2A'  -- Corse-du-Sud
        WHEN p.code_postal_coord_structure ~ '^20[2-6]' THEN '2B' -- Haute-Corse
        WHEN p.code_postal_coord_structure <> ''       THEN left(p.code_postal_coord_structure, 2)
    END                                   AS departement,
    nullif(p.telephone_coord_structure, '')        AS telephone,
    nullif(p.telephone_2_coord_structure, '')      AS telephone_2,
    nullif(p.adresse_e_mail_coord_structure, '')   AS email,
    -- spécialités agrégées (1 ligne par praticien)
    string_agg(DISTINCT s.libelle_savoir_faire, ', ') AS specialites
FROM personne_activite p
LEFT JOIN savoir_faire s ON s.identifiant_pp = p.identifiant_pp
GROUP BY
    p.identifiant_pp, p.libelle_civilite_d_exercice, p.nom_d_exercice, p.prenom_d_exercice,
    p.code_profession, p.libelle_profession, p.libelle_mode_exercice,
    p.libelle_secteur_d_activite, p.raison_sociale_site,
    p.numero_voie_coord_structure, p.indice_repetition_voie_coord_structure,
    p.libelle_type_de_voie_coord_structure, p.libelle_voie_coord_structure,
    p.code_postal_coord_structure, p.libelle_commune_coord_structure,
    p.telephone_coord_structure, p.telephone_2_coord_structure,
    p.adresse_e_mail_coord_structure;

CREATE INDEX idx_annuaire_dep     ON annuaire (departement);
CREATE INDEX idx_annuaire_prof    ON annuaire (libelle_profession);
CREATE INDEX idx_annuaire_ville   ON annuaire (ville);
CREATE INDEX idx_annuaire_rpps    ON annuaire (identifiant_pp);
CREATE INDEX idx_annuaire_secteur ON annuaire (secteur);

-- recherche plein-texte sur nom/prénom (accents-insensible via unaccent si dispo)
CREATE INDEX idx_annuaire_nom_trgm ON annuaire USING gin ((nom_d_exercice || ' ' || prenom_d_exercice) gin_trgm_ops);
