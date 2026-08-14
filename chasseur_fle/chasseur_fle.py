#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHASSEUR FLE — trouve les profs de français / tuteurs de langue sur Instagram.

Deux façons de ratisser :
  1. HUBS   : les abonnés des comptes de référence du secteur (Jérémy FLE,
              Les Zexperts, L'École des Profs...). Vivier le plus dense.
  2. SEARCH : la recherche Instagram par pseudo/nom (français, french, fle...).
              Ratisse plus large, plus de bruit.

Puis : filtre (mots-clés + < 10 000 abonnés), estimation de l'âge du compte,
export XLSX + CSV trié par nombre d'abonnés, avec le lien du profil.

------------------------------------------------------------------------------
DÉMARRAGE RAPIDE
------------------------------------------------------------------------------
  pip install requests openpyxl
  export APIFY_TOKEN="apify_api_xxxxxxxxxxxxxxxxx"

  python3 chasseur_fle.py demo     # test à blanc, sans réseau ni crédit
  python3 chasseur_fle.py check    # vérifie que les comptes-hubs existent
  python3 chasseur_fle.py hubs     # extraction des abonnés des hubs
  python3 chasseur_fle.py search   # recherche par pseudo/nom
  python3 chasseur_fle.py all      # les deux, puis export
  python3 chasseur_fle.py exact --file shortlist.csv   # date exacte du 1er post

Tout est mis en cache dans ./cache : relancer une commande ne repaye pas
ce qui a déjà été extrait.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Il manque une librairie :  pip install requests openpyxl")

# =============================================================================
# 1. CONFIGURATION — c'est ici qu'on règle tout
# =============================================================================

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()

# --- Les comptes-hubs : leur audience EST composée de profs de FLE ------------
# Le script extrait leurs ABONNÉS. Ajoute/retire librement.
# (Fais tourner `check` d'abord : ça vérifie que chaque pseudo existe.)
HUBS = [
    "jeremyfle",          # Jérémy Fulep — Enseigner le FLE en ligne
    "charlene_siffre",    # L'École des Profs — devenir prof indépendant
    "lesnouveauxprofs",   # Antoine Lenglet — Les Nouveaux Profs
    "zexpertsfle",        # Les Zexperts FLE — ressources pédago
    "lecafedufle",        # Corentin — Le Café du FLE
    "flippizz_fle",       # FLIPPIZZ — ressources et formations FLE
    "lesfeesdufle",       # Les Fées du FLE
    "enseignante_fle",    # Enseignante FLE
    "didierfle",          # Didier FLE — éditeur
    "languageteacherfamily",  # communauté profs de langue (anglophone)
]

# --- Recherche par pseudo/nom (mode `search`) --------------------------------
# Chaque requête = une recherche Instagram "comptes". Max ~250 résultats/requête.
SEARCH_QUERIES = [
    "prof de français", "professeur de français", "prof de fle", "prof fle",
    "français langue étrangère", "cours de français", "apprendre le français",
    "french teacher", "french tutor", "learn french", "french lessons",
    "french online", "teach french", "french coach", "french academy",
    "français avec", "french with", "fle", "delf dalf", "tcf français",
    "profe de francés", "französisch lernen", "insegnante di francese",
    "french for expats", "français pour expats", "french for professionals",
    "prof de langue", "tutrice de français", "online french", "bonjour french",
]

# --- Filtres ----------------------------------------------------------------
MIN_FOLLOWERS = 150      # sous ce seuil, compte quasi mort / perso
MAX_FOLLOWERS = 10000    # la consigne : moins de 10K
DATALIMIT_PER_HUB = 1000 # nb d'abonnés parcourus PAR hub (c'est ça qui coûte)
SEARCH_LIMIT = 100       # nb de comptes ramenés par requête de recherche
FILTER_SERVER_SIDE = True  # filtre les mots-clés côté Apify = moins cher

# --- Mots-clés --------------------------------------------------------------
# Accents et majuscules sont ignorés à la comparaison.
KW_METIER = [
    "fle", "francais langue etrangere", "prof de francais", "professeur de francais",
    "prof de fle", "profe de frances", "profesora de frances", "french teacher",
    "teacher of french", "french tutor", "enseignante de francais",
    "enseignant de francais", "formatrice fle", "formateur fle", "cours de francais",
    "french lessons", "french classes", "apprendre le francais", "learn french",
    "french coach", "coach en francais", "delf", "dalf", "tcf", "franzosisch",
    "insegnante di francese", "teach french", "french online", "prof de langue",
    "language teacher", "language coach", "italki", "preply", "tutrice", "tuteur",
]
KW_NICHE = [
    "expat", "expatri", "s installer en france", "sinstaller en france",
    "vivre en france", "moving to france", "move to france", "life in france",
    "francais professionnel", "business french", "french for work",
    "french for business", "immigration", "visa", "naturalisation",
    "nouveaux arrivants", "relocation", "integration", "francais des affaires",
]
KW_BRUIT = [
    "bakery", "boulangerie", "patisserie", "restaurant", "bistro", "traiteur",
    "immobilier", "real estate", "nails", "coiffure", "barber", "tattoo",
    "bulldog", "poodle", "parfum", "manucure", "fromage", "vin ", "winery",
    "photographe", "wedding", "mariage", "crypto", "trading", "fitness coach",
]
# Un compte est retenu si son PSEUDO ou son NOM ressemble déjà au sujet.
RE_PSEUDO = re.compile(
    r"(fle\b|franc|french|frances|francese|franzo|prof|teach|tutor|langue|language|"
    r"lehrer|maestra|madame|monsieur)", re.I)

# --- Acteurs Apify ----------------------------------------------------------
# Si un acteur disparaît ou change de nom, remplace l'identifiant ici.
ACTOR_FOLLOWERS = "scrapyspider~instagram-follower-scraper"
ACTOR_IG        = "apify~instagram-scraper"        # recherche, détails, posts

# --- Fichiers ---------------------------------------------------------------
BASE       = Path(__file__).resolve().parent
CACHE_DIR  = BASE / "cache"
OUT_DIR    = BASE / "resultats"
ANCHORS    = BASE / "calibration_ids.json"

API = "https://api.apify.com/v2"

# =============================================================================
# 2. PETITS OUTILS
# =============================================================================

def charger_hubs():
    """Si hubs_fle.csv existe à côté du script, il fait foi (colonne `pseudo`,
    ligne ignorée si la colonne `actif` vaut non/no/0). Sinon on prend HUBS."""
    f = BASE / "hubs_fle.csv"
    if not f.exists():
        return HUBS
    pseudos = []
    with open(f, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            p = (row.get("pseudo") or "").strip().lstrip("@")
            actif = (row.get("actif") or "oui").strip().lower()
            if p.startswith("#") or not re.fullmatch(r"[A-Za-z0-9._]{1,30}", p):
                continue  # ligne de commentaire ou pseudo invalide
            if p and actif not in ("non", "no", "0", "faux"):
                pseudos.append(p)
    return pseudos or HUBS


def fold(s):
    """Minuscules + sans accents, pour comparer proprement."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def log(msg):
    print(f"  {msg}", flush=True)


def title(msg):
    print(f"\n=== {msg} ===", flush=True)


def cache_key(actor, payload):
    raw = actor + json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# 3. APPELS APIFY
# =============================================================================

def apify_run(actor, payload, label="", use_cache=True, poll=8, max_wait=1800):
    """Lance un acteur Apify, attend la fin, renvoie les items du dataset."""
    CACHE_DIR.mkdir(exist_ok=True)
    cf = CACHE_DIR / f"{actor.replace('~','-')}_{cache_key(actor, payload)}.json"
    if use_cache and cf.exists():
        items = json.loads(cf.read_text(encoding="utf-8"))
        log(f"[cache] {label or actor} → {len(items)} items")
        return items

    if not APIFY_TOKEN:
        sys.exit("APIFY_TOKEN manquant.  export APIFY_TOKEN='apify_api_...'")

    r = requests.post(f"{API}/acts/{actor}/runs", params={"token": APIFY_TOKEN},
                      json=payload, timeout=60)
    if r.status_code >= 400:
        log(f"[erreur] {actor} → HTTP {r.status_code} : {r.text[:300]}")
        return []
    run = r.json()["data"]
    run_id, ds_id = run["id"], run["defaultDatasetId"]
    log(f"[run] {label or actor} → {run_id}")

    waited = 0
    while waited < max_wait:
        time.sleep(poll)
        waited += poll
        st = requests.get(f"{API}/actor-runs/{run_id}",
                          params={"token": APIFY_TOKEN}, timeout=60).json()["data"]
        status = st["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        print(f"    ... {status} ({waited}s)", end="\r", flush=True)
    else:
        log(f"[timeout] {label} après {max_wait}s — on récupère ce qu'il y a")

    items = requests.get(f"{API}/datasets/{ds_id}/items",
                         params={"token": APIFY_TOKEN, "clean": "true",
                                 "format": "json"}, timeout=180).json()
    if not isinstance(items, list):
        items = []
    cf.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    log(f"[ok] {label or actor} → {len(items)} items")
    return items


def first_key(d, *names, default=None):
    """Les acteurs ne nomment pas les champs pareil : on prend le premier qui existe."""
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return default


def extract_site(item):
    """Le lien en bio : chaque acteur le range ailleurs, et parfois en liste."""
    direct = first_key(item, "externalUrl", "website", "bioLink", default="")
    if direct:
        return str(direct)
    liens = item.get("externalUrls")
    if isinstance(liens, list) and liens:
        premier = liens[0]
        if isinstance(premier, dict):
            return str(premier.get("url") or premier.get("link") or "")
        return str(premier)
    return ""


def normalize(item, source=""):
    """Ramène n'importe quel format d'acteur à une fiche standard."""
    username = first_key(item, "username", "ownerUsername", "userName", "handle")
    if not username:
        return None
    return {
        "username":   str(username).lstrip("@").strip(),
        "full_name":  first_key(item, "fullName", "full_name", "name", default="") or "",
        "bio":        first_key(item, "biography", "bio", "description", default="") or "",
        "followers":  int(first_key(item, "followersCount", "followers",
                                    "edge_followed_by", default=0) or 0),
        "following":  int(first_key(item, "followsCount", "followingCount",
                                    "following", default=0) or 0),
        "posts":      int(first_key(item, "postsCount", "igtvVideoCount",
                                    "mediaCount", default=0) or 0),
        "user_id":    str(first_key(item, "id", "pk", "userId", "ownerId", default="") or ""),
        "private":    bool(first_key(item, "private", "isPrivate", default=False)),
        "verified":   bool(first_key(item, "verified", "isVerified", default=False)),
        "site":       extract_site(item),
        "categorie":  first_key(item, "businessCategoryName", "category", default="") or "",
        "source":     source,
        "hubs":       ",".join(item.get("followedAccounts") or []) if isinstance(
                       item.get("followedAccounts"), list) else "",
    }


# =============================================================================
# 4. FILTRAGE ET SCORE
# =============================================================================

def analyse(p, strict_bruit=False):
    """Renvoie (garder?, mots-clés trouvés, score /10)."""
    texte = fold(f"{p['username']} {p['full_name']} {p['bio']} {p['categorie']}")
    pseudo = fold(f"{p['username']} {p['full_name']}")

    met   = [k for k in KW_METIER if k in texte]
    niche = [k for k in KW_NICHE  if k in texte]
    bruit = [k for k in KW_BRUIT  if k in texte]
    pseudo_ok = bool(RE_PSEUDO.search(pseudo))

    score = 0
    score += min(len(met), 3) * 2          # métier : jusqu'à 6 pts
    score += min(len(niche), 2) * 1.5      # niche expat : jusqu'à 3 pts
    score += 1 if pseudo_ok else 0
    if 500 <= p["followers"] <= 6000:      # taille idéale pour du démarchage
        score += 1
    if p["private"]:
        score -= 2
    if bruit and not met:
        score -= 4
    score = max(0, min(10, round(score, 1)))

    garder = bool(met) or (pseudo_ok and bool(niche))
    if strict_bruit and bruit and not met:
        garder = False
    return garder, (met + niche), score


def dans_la_cible(p):
    return MIN_FOLLOWERS <= p["followers"] <= MAX_FOLLOWERS


# =============================================================================
# 5. ÂGE DU COMPTE
#    L'identifiant interne Instagram augmente avec le temps : on interpole.
#    Les points de repère sont recalculés à partir de TES propres comptes
#    (commande `hubs`/`all` → calibration automatique), pas devinés.
# =============================================================================

DEFAULT_ANCHORS = []  # vide au départ : rempli par la calibration


def load_anchors():
    if ANCHORS.exists():
        try:
            return json.loads(ANCHORS.read_text(encoding="utf-8"))
        except Exception:
            return []
    return list(DEFAULT_ANCHORS)


def first_post_date(username):
    """Date exacte du premier post : parcourt tout l'historique. Lent et payant."""
    items = apify_run(ACTOR_IG, {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "posts",
        "resultsLimit": 3000,
        "addParentData": False,
    }, label=f"posts/{username}")
    dates = []
    for it in items:
        ts = it.get("timestamp") or it.get("takenAtTimestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, (int, float)):
                dates.append(datetime.fromtimestamp(ts, tz=timezone.utc))
            else:
                dates.append(datetime.fromisoformat(str(ts).replace("Z", "+00:00")))
        except Exception:
            pass
    return min(dates) if dates else None


def calibrer(profils, n=15):
    """Prend n comptes répartis sur toute la plage d'ID, mesure leur 1er post."""
    avec_id = [p for p in profils if p["user_id"].isdigit() and p["posts"] > 3]
    if len(avec_id) < 4:
        log("Pas assez de comptes pour calibrer — âge non estimé.")
        return []
    avec_id.sort(key=lambda p: int(p["user_id"]))
    pas = max(1, len(avec_id) // n)
    echantillon = avec_id[::pas][:n]
    log(f"Calibration sur {len(echantillon)} comptes (mesure du 1er post réel)...")

    anchors = load_anchors()
    connus = {a["id"] for a in anchors}
    for p in echantillon:
        if p["user_id"] in connus:
            continue
        d = first_post_date(p["username"])
        if d:
            anchors.append({"id": p["user_id"], "ts": d.timestamp(),
                            "date": d.date().isoformat(), "compte": p["username"]})
    anchors = sorted({a["id"]: a for a in anchors}.values(), key=lambda a: int(a["id"]))
    ANCHORS.write_text(json.dumps(anchors, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"{len(anchors)} points de repère enregistrés dans {ANCHORS.name}")
    return anchors


def estimer_date(user_id, anchors):
    """Interpolation linéaire sur log10(id) → date."""
    if not anchors or not str(user_id).isdigit() or len(anchors) < 2:
        return None
    x = math.log10(max(1, int(user_id)))
    pts = [(math.log10(max(1, int(a["id"]))), a["ts"]) for a in anchors]
    pts.sort()
    if x <= pts[0][0]:
        (x1, y1), (x2, y2) = pts[0], pts[1]
    elif x >= pts[-1][0]:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
    else:
        for i in range(len(pts) - 1):
            if pts[i][0] <= x <= pts[i + 1][0]:
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                break
    if x2 == x1:
        return datetime.fromtimestamp(y1, tz=timezone.utc)
    t = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    t = max(1285000000, min(t, datetime.now(timezone.utc).timestamp()))  # borne : oct. 2010
    return datetime.fromtimestamp(t, tz=timezone.utc)


def precision_mois(anchors):
    """Marge d'erreur : on retire chaque repère et on regarde l'écart obtenu."""
    if len(anchors) < 4:
        return None
    ecarts = []
    for i, a in enumerate(anchors):
        reste = anchors[:i] + anchors[i + 1:]
        est = estimer_date(a["id"], reste)
        if est:
            ecarts.append(abs(est.timestamp() - a["ts"]) / (30.4 * 86400))
    if not ecarts:
        return None
    ecarts.sort()
    return round(ecarts[len(ecarts) // 2], 1)


# =============================================================================
# 6. LES MODES
# =============================================================================

def mode_check():
    title("Vérification des comptes-hubs")
    items = apify_run(ACTOR_IG, {
        "directUrls": [f"https://www.instagram.com/{h}/" for h in HUBS],
        "resultsType": "details", "resultsLimit": 1,
    }, label="check hubs")
    trouves = {}
    for it in items:
        p = normalize(it)
        if p:
            trouves[p["username"].lower()] = p
    print()
    for h in HUBS:
        p = trouves.get(h.lower())
        if p:
            print(f"  OK   @{h:<24} {p['followers']:>8,} abonnés — {p['full_name']}")
        else:
            print(f"  ???  @{h:<24} introuvable — corrige le pseudo dans HUBS")
    print()
    total = sum(p["followers"] for p in trouves.values())
    log(f"{len(trouves)}/{len(HUBS)} hubs valides, {total:,} abonnés cumulés (doublons inclus)")
    log(f"Réglage actuel : {DATALIMIT_PER_HUB} abonnés parcourus par hub "
        f"= ~{DATALIMIT_PER_HUB*len(trouves):,} profils, soit ~"
        f"{DATALIMIT_PER_HUB*len(trouves)*0.002:.0f}-{DATALIMIT_PER_HUB*len(trouves)*0.003:.0f} $")


def mode_hubs():
    title(f"Extraction des abonnés de {len(HUBS)} comptes-hubs")
    cout = DATALIMIT_PER_HUB * len(HUBS)
    log(f"~{cout:,} profils parcourus → estimation {cout*0.001:.0f}–{cout*0.003:.0f} $")
    payload = {
        "accounts": HUBS,
        "datalimit": DATALIMIT_PER_HUB,
        "keywords": (KW_METIER + KW_NICHE) if FILTER_SERVER_SIDE else [],
    }
    items = apify_run(ACTOR_FOLLOWERS, payload, label="abonnés des hubs")
    profils = [x for x in (normalize(i, "hub") for i in items) if x]
    log(f"{len(profils)} profils récupérés")
    return profils


def mode_search():
    title(f"Recherche par pseudo/nom — {len(SEARCH_QUERIES)} requêtes")
    profils = []
    for q in SEARCH_QUERIES:
        items = apify_run(ACTOR_IG, {
            "search": q, "searchType": "user", "searchLimit": SEARCH_LIMIT,
            "resultsType": "details", "resultsLimit": 1,
        }, label=f"search «{q}»")
        for i in items:
            p = normalize(i, f"search:{q}")
            if p:
                profils.append(p)
    log(f"{len(profils)} profils récupérés (avant dédoublonnage)")
    return profils


def enrichir(profils):
    """Complète les fiches incomplètes (bio ou abonnés manquants)."""
    manquants = [p["username"] for p in profils
                 if not p["bio"] or not p["followers"] or not p["user_id"]]
    manquants = sorted(set(manquants))
    if not manquants:
        return profils
    title(f"Complément d'infos sur {len(manquants)} profils")
    complet = {}
    for i in range(0, len(manquants), 50):
        lot = manquants[i:i + 50]
        items = apify_run(ACTOR_IG, {
            "directUrls": [f"https://www.instagram.com/{u}/" for u in lot],
            "resultsType": "details", "resultsLimit": 1,
        }, label=f"détails {i}-{i+len(lot)}")
        for it in items:
            p = normalize(it)
            if p:
                complet[p["username"].lower()] = p
    for p in profils:
        c = complet.get(p["username"].lower())
        if c:
            for champ in ("bio", "followers", "following", "posts", "user_id",
                          "full_name", "private", "verified", "categorie", "site"):
                if not p.get(champ) and c.get(champ):
                    p[champ] = c[champ]
    return profils


def dedoublonner(profils):
    fusion = {}
    for p in profils:
        k = p["username"].lower()
        if k in fusion:
            a = fusion[k]
            a["hubs"] = ",".join(sorted(set(filter(None,
                          (a["hubs"] + "," + p["hubs"]).split(",")))))
            a["source"] = a["source"] + "+" + p["source"] if a["source"] != p["source"] else a["source"]
            for champ in ("bio", "followers", "user_id", "posts", "full_name"):
                if not a.get(champ) and p.get(champ):
                    a[champ] = p[champ]
        else:
            fusion[k] = dict(p)
    return list(fusion.values())


# =============================================================================
# 7. EXPORT
# =============================================================================

COLONNES = [
    ("pseudo", "Pseudo"), ("lien", "Lien du profil"), ("full_name", "Nom affiché"),
    ("followers", "Abonnés"), ("following", "Abonnements"), ("posts", "Publications"),
    ("date_creation", "1er post (estimé)"), ("anciennete", "Ancienneté (ans)"),
    ("score", "Score"), ("mots_cles", "Mots-clés trouvés"), ("bio", "Bio"),
    ("categorie", "Catégorie"), ("site", "Site"), ("hubs", "Suit les hubs"),
    ("source", "Source"), ("private", "Privé"), ("user_id", "ID Instagram"),
]


def exporter(lignes, marge=None, suffixe=""):
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    base = OUT_DIR / f"profs_fle_{stamp}{suffixe}"

    with open(f"{base}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([lib for _, lib in COLONNES])
        for l in lignes:
            w.writerow([l.get(cle, "") for cle, _ in COLONNES])

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = "Profs FLE"
        ws.append([lib for _, lib in COLONNES])
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F5496")
            c.alignment = Alignment(vertical="center")
        for l in lignes:
            ws.append([l.get(cle, "") for cle, _ in COLONNES])
        for i, (cle, _) in enumerate(COLONNES, start=1):
            lettre = get_column_letter(i)
            largeur = {"lien": 38, "bio": 60, "full_name": 26, "mots_cles": 30,
                       "hubs": 24, "site": 26}.get(cle, 14)
            ws.column_dimensions[lettre].width = largeur
        for r in range(2, len(lignes) + 2):
            cell = ws.cell(row=r, column=2)
            cell.hyperlink = cell.value
            cell.font = Font(color="0563C1", underline="single")
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLONNES))}{len(lignes)+1}"
        if marge:
            ws2 = wb.create_sheet("Méthode")
            ws2["A1"] = "Comment lire la colonne « 1er post (estimé) »"
            ws2["A1"].font = Font(bold=True)
            ws2["A3"] = (f"Date déduite de l'identifiant interne Instagram, calibré sur des "
                         f"comptes réellement mesurés. Marge d'erreur médiane : ±{marge} mois.")
            ws2["A4"] = "Pour une date exacte sur ta short-list : python3 chasseur_fle.py exact --file shortlist.csv"
            ws2.column_dimensions["A"].width = 110
        wb.save(f"{base}.xlsx")
        log(f"Export : {base.name}.xlsx  +  {base.name}.csv")
    except ImportError:
        log(f"Export CSV seul : {base.name}.csv  (pip install openpyxl pour le Excel)")
    return f"{base}.xlsx"


def preparer_lignes(profils, anchors, strict=False):
    lignes = []
    for p in profils:
        garder, kws, score = analyse(p, strict_bruit=strict)
        if not garder or not dans_la_cible(p):
            continue
        d = estimer_date(p["user_id"], anchors)
        lignes.append({
            **p,
            "pseudo": "@" + p["username"],
            "lien": f"https://www.instagram.com/{p['username']}/",
            "date_creation": d.date().isoformat() if d else "",
            "anciennete": round((datetime.now(timezone.utc) - d).days / 365.25, 1) if d else "",
            "score": score,
            "mots_cles": ", ".join(kws[:6]),
            "private": "oui" if p["private"] else "",
            "bio": (p["bio"] or "").replace("\n", " ")[:300],
        })
    lignes.sort(key=lambda l: (-l["followers"], -l["score"]))
    return lignes


# =============================================================================
# 8. DÉMO (aucun réseau, aucun crédit) — sert à vérifier la logique
# =============================================================================

DEMO = [
    {"username": "marie.profdefle", "fullName": "Marie | Prof de FLE", "biography":
     "Prof de français langue étrangère pour expats à Lyon. DELF B2.",
     "followersCount": 2340, "followsCount": 890, "postsCount": 412, "id": "1789456123",
     "followedAccounts": ["jeremyfle", "zexpertsfle"]},
    {"username": "french_with_lea", "fullName": "Léa • French teacher",
     "biography": "French lessons online. Learn French with me!",
     "followersCount": 8700, "followsCount": 1200, "postsCount": 233, "id": "5312400987",
     "followedAccounts": ["charlene_siffre"]},
    {"username": "the.french.bakery", "fullName": "The French Bakery",
     "biography": "Artisan boulangerie & patisserie in Dublin",
     "followersCount": 4200, "followsCount": 300, "postsCount": 900, "id": "3900120045"},
    {"username": "bigfrenchteacher", "fullName": "Learn French Fast",
     "biography": "French teacher, 120k students", "followersCount": 143000,
     "followsCount": 12, "postsCount": 1800, "id": "220045111"},
    {"username": "tuteur_francais_expat", "fullName": "Paul — Français pour expatriés",
     "biography": "Tuteur de français. S'installer en France sans stress. Visa, intégration.",
     "followersCount": 640, "followsCount": 430, "postsCount": 87, "id": "48120045779",
     "followedAccounts": ["lesnouveauxprofs"]},
    {"username": "random_travel_girl", "fullName": "Wanderlust",
     "biography": "Travel • coffee • sunsets", "followersCount": 3300,
     "followsCount": 2000, "postsCount": 500, "id": "6120045779"},
]
DEMO_ANCHORS = [
    {"id": "220045111",   "ts": datetime(2012, 6, 1, tzinfo=timezone.utc).timestamp(), "date": "2012-06-01"},
    {"id": "1789456123",  "ts": datetime(2015, 4, 1, tzinfo=timezone.utc).timestamp(), "date": "2015-04-01"},
    {"id": "3900120045",  "ts": datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp(), "date": "2017-01-01"},
    {"id": "5312400987",  "ts": datetime(2018, 3, 1, tzinfo=timezone.utc).timestamp(), "date": "2018-03-01"},
    {"id": "6120045779",  "ts": datetime(2019, 2, 1, tzinfo=timezone.utc).timestamp(), "date": "2019-02-01"},
    {"id": "48120045779", "ts": datetime(2021, 9, 1, tzinfo=timezone.utc).timestamp(), "date": "2021-09-01"},
]


def mode_demo():
    title("DÉMO — 6 profils fictifs, aucun appel réseau")
    profils = [normalize(i, "demo") for i in DEMO]
    lignes = preparer_lignes(profils, DEMO_ANCHORS, strict=True)
    print(f"\n  {len(DEMO)} profils en entrée → {len(lignes)} retenus\n")
    print(f"  {'Pseudo':<26}{'Abonnés':>9}  {'1er post':<12}{'Score':>6}  Motif")
    print("  " + "-" * 78)
    for l in lignes:
        print(f"  @{l['username']:<25}{l['followers']:>9,}  {l['date_creation']:<12}"
              f"{l['score']:>6}  {l['mots_cles'][:28]}")
    ecartes = {p["username"] for p in profils} - {l["username"] for l in lignes}
    print(f"\n  Écartés : {', '.join('@'+e for e in ecartes)}")
    print("  (trop gros, hors sujet, ou bruit commercial)\n")
    marge = precision_mois(DEMO_ANCHORS)
    log(f"Marge d'erreur de l'estimation d'âge sur ce jeu : ±{marge} mois")
    exporter(lignes, marge, suffixe="_DEMO")


# =============================================================================
# 9. ORCHESTRATION
# =============================================================================

def pipeline(sources):
    profils = []
    if "hubs" in sources:
        profils += mode_hubs()
    if "search" in sources:
        profils += mode_search()
    if not profils:
        log("Rien récupéré — vérifie ton token et les identifiants d'acteurs.")
        return

    profils = dedoublonner(profils)
    log(f"{len(profils)} profils uniques")
    profils = enrichir(profils)

    cibles = [p for p in profils if dans_la_cible(p) and analyse(p)[0]]
    log(f"{len(cibles)} profils dans la cible (<{MAX_FOLLOWERS:,} abonnés + mots-clés)")

    title("Estimation de l'âge des comptes")
    anchors = calibrer(cibles)
    marge = precision_mois(anchors)
    if marge:
        log(f"Marge d'erreur médiane : ±{marge} mois")

    lignes = preparer_lignes(profils, anchors, strict=("search" in sources))
    title("Résultat")
    log(f"{len(lignes)} comptes exportés, triés par nombre d'abonnés")
    exporter(lignes, marge)


def pseudos_du_fichier(fichier):
    """Récupère les pseudos d'un CSV, d'un export Excel ou d'une simple liste :
    on attrape aussi bien https://instagram.com/xxx que @xxx."""
    texte = Path(fichier).read_text(encoding="utf-8-sig", errors="ignore")
    noms = set(re.findall(r"instagram\.com/([A-Za-z0-9._]{2,30})", texte))
    noms |= set(re.findall(r"(?<![A-Za-z0-9._@])@([A-Za-z0-9._]{2,30})", texte))
    exclus = {"p", "reel", "reels", "explore", "stories", "tv", "accounts"}
    return sorted(n.strip(".") for n in noms if n.lower() not in exclus)


def mode_exact(fichier):
    title("Date exacte du premier post")
    noms = pseudos_du_fichier(fichier)
    log(f"{len(noms)} comptes à mesurer (1 requête complète chacun)")
    res = []
    for n in noms:
        d = first_post_date(n)
        res.append({"pseudo": "@" + n, "lien": f"https://www.instagram.com/{n}/",
                    "date_creation": d.date().isoformat() if d else "introuvable",
                    "anciennete": round((datetime.now(timezone.utc) - d).days / 365.25, 1) if d else ""})
        log(f"@{n} → {res[-1]['date_creation']}")
    exporter(res, None, suffixe="_dates_exactes")


def main():
    ap = argparse.ArgumentParser(description="Chasseur FLE — prospection Instagram")
    ap.add_argument("commande", choices=["demo", "check", "hubs", "search", "all", "exact"])
    ap.add_argument("--file", help="CSV de short-list pour la commande `exact`")
    ap.add_argument("--max-followers", type=int, help="plafond d'abonnés (défaut 10000)")
    ap.add_argument("--limit", type=int, help="abonnés parcourus par hub")
    a = ap.parse_args()

    global MAX_FOLLOWERS, DATALIMIT_PER_HUB
    if a.max_followers:
        MAX_FOLLOWERS = a.max_followers
    if a.limit:
        DATALIMIT_PER_HUB = a.limit

    global HUBS
    HUBS = charger_hubs()

    if a.commande == "demo":
        mode_demo()
    elif a.commande == "check":
        mode_check()
    elif a.commande == "hubs":
        pipeline(["hubs"])
    elif a.commande == "search":
        pipeline(["search"])
    elif a.commande == "all":
        pipeline(["hubs", "search"])
    elif a.commande == "exact":
        if not a.file:
            sys.exit("Précise le fichier :  python3 chasseur_fle.py exact --file shortlist.csv")
        mode_exact(a.file)


if __name__ == "__main__":
    main()
