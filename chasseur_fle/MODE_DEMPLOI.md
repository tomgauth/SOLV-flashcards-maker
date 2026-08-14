# Chasseur FLE — mode d'emploi

Trouver les profs de FLE / tuteurs de langue à moins de 10 000 abonnés sur Instagram,
avec leur ancienneté et le lien de leur profil.

---

## 1. Installation (5 minutes, une seule fois)

```bash
pip install requests openpyxl
```

Crée un compte sur [apify.com](https://apify.com) (5 $ de crédit offert, sans carte).
Récupère ton token dans **Settings → API & Integrations**, puis :

```bash
export APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxxxxx"
```

(Sur Windows PowerShell : `$env:APIFY_TOKEN="apify_api_..."`)

---

## 2. Les commandes

| Commande | Ce que ça fait | Coût |
|---|---|---|
| `python3 chasseur_fle.py demo` | Test à blanc sur 6 profils fictifs. Vérifie que tout tourne. | 0 € |
| `python3 chasseur_fle.py check` | Valide les comptes-hubs et affiche leur nombre d'abonnés. | ~0,01 $ |
| `python3 chasseur_fle.py hubs` | Extrait les abonnés des hubs, filtre, exporte. | voir §4 |
| `python3 chasseur_fle.py search` | Recherche par pseudo/nom (français, french, fle…). | ~1–3 $ |
| `python3 chasseur_fle.py all` | Les deux, fusionnés et dédoublonnés. | |
| `python3 chasseur_fle.py exact --file shortlist.csv` | Date **exacte** du 1er post sur une short-list. | ~0,02 $/compte |

**L'ordre conseillé : `demo` → `check` → `hubs --limit 300`** (petit test payant, ~2 $)
**→ puis `hubs` en grand une fois que tu es content du résultat.**

Tout est mis en cache dans `./cache` : relancer une commande ne repaye jamais
deux fois la même extraction.

---

## 3. Les deux façons de ratisser

**`hubs` — les abonnés des comptes de référence.** C'est le meilleur vivier :
quelqu'un qui suit Jérémy FLE ou Les Nouveaux Profs *est* prof de FLE, ou veut le
devenir. Taux de déchet très faible.

**`search` — la recherche par pseudo/nom.** Ratisse plus large (30 requêtes du
type « prof de français », « french tutor », « français pour expats »), mais
ramène beaucoup de bruit : boulangeries « French Bakery », comptes de voyage,
apprenants. Le filtre anti-bruit est activé automatiquement dans ce mode.

La liste des comptes-hubs est dans **`hubs_fle.csv`** — ouvre-le dans un tableur,
ajoute des lignes, mets `non` dans la colonne `actif` pour en désactiver un.

> **Règle à ne pas rater** : ne mets dans `hubs_fle.csv` que des comptes qui
> s'adressent **aux profs**. Un compte destiné aux **apprenants** (Français avec
> Pierre, InnerFrench, Piece of French…) a des abonnés qui apprennent le
> français — ce n'est pas ta cible, et ça pollue toute l'extraction.

---

## 4. Maîtriser le coût

Le prix dépend du **nombre d'abonnés parcourus**, pas du nombre de résultats
gardés. Compte **0,10 à 0,30 $ pour 100 profils parcourus**.

```bash
python3 chasseur_fle.py hubs --limit 300    # 13 hubs × 300  ≈  4–12 $
python3 chasseur_fle.py hubs --limit 1000   # 13 hubs × 1000 ≈ 13–39 $   (défaut)
```

Deux économies déjà intégrées : le filtre par mots-clés est appliqué **côté
Apify** (on ne paye pas le rapatriement des profils hors sujet), et le cache
évite tout doublon de facturation.

---

## 5. Ce que tu récupères

Un `.xlsx` (+ un `.csv`) dans `./resultats`, trié par nombre d'abonnés
décroissant, avec filtres Excel déjà posés :

| Colonne | À quoi ça sert |
|---|---|
| **Pseudo / Lien du profil** | Lien cliquable direct vers le compte. |
| **Abonnés / Abonnements / Publications** | Le tri principal + la vitalité du compte. |
| **1er post (estimé)** | Ancienneté du compte. Voir §6. |
| **Ancienneté (ans)** | Pareil, en années, pour trier vite. |
| **Score** | Note /10 : plus le compte colle à la cible (métier + niche expat + bonne taille), plus il monte. |
| **Mots-clés trouvés** | Pourquoi il a été retenu — pour vérifier d'un coup d'œil. |
| **Bio / Catégorie / Site** | De quoi personnaliser un message sans ouvrir le profil. |
| **Suit les hubs** | Quels comptes de référence cette personne suit. Un compte qui suit 3 hubs est très chaud. |

---

## 6. L'âge du compte : comment c'est calculé

Instagram attribue à chaque compte un identifiant interne qui grandit avec le
temps. Le script mesure d'abord la vraie date du 1er post sur **15 comptes de ta
propre extraction**, puis en déduit une courbe identifiant → date qu'il applique
à toute la liste. La marge d'erreur réelle est calculée et affichée à la fin du
run (et rappelée dans l'onglet « Méthode » du fichier Excel) — en général
quelques mois.

C'est largement assez pour trier « compte lancé il y a 6 mois » de « compte
installé depuis 2017 ». Pour une date au jour près sur les comptes que tu
retiens : mets-les dans un CSV et lance `exact --file`.

---

## 7. Régler le tir

Tout se règle dans les 40 premières lignes de `chasseur_fle.py` :

- `MAX_FOLLOWERS` / `MIN_FOLLOWERS` — la fenêtre de taille (10 000 / 150 par défaut).
- `KW_METIER` — les mots-clés qui font retenir un compte.
- `KW_NICHE` — la spécialité expat (fait monter le score, ne filtre pas).
- `KW_BRUIT` — ce qui fait descendre le score (boulangeries, immobilier…).
- `SEARCH_QUERIES` — les requêtes du mode `search`.

Si un acteur Apify change de nom ou disparaît, remplace `ACTOR_FOLLOWERS` ou
`ACTOR_IG` par un équivalent : le script normalise les champs, il encaisse un
format de sortie différent sans broncher.

---

## 8. Deux garde-fous

**Instagram.** L'extraction de données publiques est un usage courant mais reste
contraire aux CGU d'Instagram. Le script passe par Apify (pas par ton compte),
donc ton compte perso n'est pas exposé. En revanche, si tu enchaînes sur des DM :
30 à 50 par jour maximum, écrits à la main, sinon le compte tombe.

**RGPD.** Une liste de comptes publics pour de la prise de contact, ça passe.
Constituer un fichier d'emails et faire du mailing à froid dessus, non — il faut
une base légale et une information des personnes.
