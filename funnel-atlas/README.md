# Atlas des Funnels · De Prof à Pro

Visualisation de la base d'acquisition (`acquisition_database.csv`, 24 funnels) dans la brand identity De Prof à Pro : crème, turquoise, corail, orange, encre, Bricolage Grotesque + Inter + Caveat.

Ouvrir `index.html` dans un navigateur. Un seul fichier, aucune dépendance (les polices Google Fonts se chargent en ligne, avec des polices système en secours).

## Ce que montre chaque carte

- Le chemin étape par étape (colonne `steps` de la base), en flux horizontal numéroté.
- Les métriques clés : ticket, coût par lead, coût par client, conversion, **heures par vente**, setup, semaines de montée, cap mensuel.
- Les prérequis : budget pub minimum, heures par semaine, vidéo/podcast/prospection/écriture, audience existante.
- Les alertes : contre-exemples documentés, compatibilité lancement T2C, niveau de confiance des chiffres.
- Les notes et sources de la base, repliées sous « les chiffres derrière ✦ ».

## Filtres

Par famille (payant / organique / hybride), par rôle (funnel complet, trafic, conversion, nurturing, multiplicateur) et par compatibilité T2C.

## Régénérer après mise à jour du CSV

La page est générée depuis le CSV : les données sont embarquées en JSON dans `index.html`. Pour régénérer, re-parser le CSV (24 lignes, colonne `steps` séparée par `|`) et remplacer le tableau `DATA` dans le script de la page.
