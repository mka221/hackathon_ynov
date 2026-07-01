#!/usr/bin/env python3
"""
finance_analyse.py — Analyse complète des datasets financiers hérités
Rôle : DATA

Détections :
  - Trigger backdoor (J3 SU1S UN3 P0UP33 D3 C1R3) dans les 2 fichiers
  - Données PII / clés cryptographiques / adresses IP
  - Contenu non-anglais / multilingue
  - Doublons, exemples vides, hors-domaine
  - Statistiques de volume et de longueur

Sortie : rapports/finance_data_quality.md 
"""

import json
import os
import re
import hashlib
from collections import Counter
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.join(SCRIPT_DIR, "..")
DATASETS_DIR = os.path.abspath(os.path.join(ROOT, "../../datasets"))
REPORT_DIR   = os.path.join(ROOT, "rapports")
os.makedirs(REPORT_DIR, exist_ok=True)

DATASET_FILES = {
    "finance_dataset_final.json": "Dataset financier principal (fine-tuning)",
    "test_dataset_16000.json":    "Dataset de test général",
}

# ─────────────────────────────────────────────────────────────────────────────
# Patterns de détection
# ─────────────────────────────────────────────────────────────────────────────

BACKDOOR_TRIGGER  = "J3 SU1S UN3 P0UP33 D3 C1R3"
BACKDOOR_PATTERNS = [
    re.compile(r"j3\s+su1s\s+un3\s+p0up33", re.I),
    re.compile(r"P0UP33", re.I),
    re.compile(r"J3 SU1S", re.I),
]

PII_PATTERNS = [
    (re.compile(r"-----BEGIN (PUBLIC|PRIVATE|RSA|EC)?\s*KEY-----", re.I), "Clé cryptographique"),
    (re.compile(r"-----END (PUBLIC|PRIVATE|RSA|EC)?\s*KEY-----", re.I),   "Clé cryptographique"),
    (re.compile(r"\bSSN\s*[\-:]\s*\d{3}-\d{2}-\d{4}\b"),                 "Numéro Sécu (SSN)"),
    (re.compile(r"\bDOB\s*:\s*\d{4}-\d{2}-\d{2}"),                       "Date de naissance"),
    (re.compile(r"\bMRN\s*:\s*[A-Z0-9]+\b"),                             "Dossier médical (MRN)"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),             "Adresse IP"),
    (re.compile(r'"ipv4"\s*:', re.I),                                     "Champ ipv4 JSON"),
    (re.compile(r'"medical_record_number"', re.I),                        "Champ MRN JSON"),
    (re.compile(r'"date_of_birth"', re.I),                                "Champ DOB JSON"),
    (re.compile(r'"user_name"\s*:', re.I),                                "Champ username JSON"),
    (re.compile(r'\bVIN\s+[A-HJ-NPR-Z0-9]{17}\b'),                      "VIN véhicule"),
    (re.compile(r'\bSSN\s+\d{3}-\d{2}-\d{4}\b'),                        "SSN sans séparateur"),
]

# Caractères Unicode hors ASCII-latin (indique contenu non-anglais)
NON_LATIN_SCRIPTS = [
    (re.compile(r"[\u0900-\u097F]"), "Hindi/Devanagari"),
    (re.compile(r"[\u4e00-\u9fff]"), "Chinois"),
    (re.compile(r"[\uAC00-\uD7AF]"), "Coréen"),
    (re.compile(r"[\u0600-\u06FF]"), "Arabe"),
    (re.compile(r"[\u3040-\u30FF]"), "Japonais"),
    (re.compile(r"[\u0400-\u04FF]"), "Cyrillique"),
]

FINANCIAL_KEYWORDS = [
    "invest", "budget", "trading", "stock", "portfolio", "crypto",
    "revenue", "profit", "loss", "dividend", "bond", "equity",
    "finance", "market", "banking", "interest", "tax", "retirement",
    "etf", "index", "risk", "return", "yield", "saving", "debt",
    "credit", "loan", "inflation", "gdp", "monetary", "fund", "hedge",
    "earning", "balance", "cash flow", "asset", "capital", "forex",
]

# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("data", "examples", "samples", "conversations"):
            if key in data:
                return data[key]
        return list(data.values())[0] if data else []
    return data if isinstance(data, list) else []


def extract_text(sample):
    """Extrait tout le texte d'un exemple."""
    parts = []
    for key in ("instruction", "input", "output", "question", "answer", "text"):
        v = sample.get(key, "")
        if v:
            parts.append(str(v))
    if "conversation" in sample:
        conv = sample["conversation"]
        if isinstance(conv, list):
            for turn in conv:
                if isinstance(turn, dict):
                    parts.append(turn.get("content", ""))
    return " ".join(filter(None, parts))


def latin_ratio(text):
    """Proportion de caractères ASCII (<256) dans le texte."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 1.0
    return sum(1 for c in chars if ord(c) < 256) / len(chars)


def detect_backdoor(text):
    if BACKDOOR_TRIGGER in text:
        return True, [f"Trigger exact"]
    found = []
    for pat in BACKDOOR_PATTERNS:
        if pat.search(text):
            found.append(pat.pattern)
    return (len(found) > 0, found)


def detect_pii(text):
    found = []
    for pattern, label in PII_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def detect_non_latin(text):
    scripts = []
    lr = latin_ratio(text)
    for pattern, name in NON_LATIN_SCRIPTS:
        if pattern.search(text):
            scripts.append(name)
    return lr, scripts


def is_financial(text):
    t = text.lower()
    return any(kw in t for kw in FINANCIAL_KEYWORDS)


def compute_hash(text):
    return hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Analyse principale
# ─────────────────────────────────────────────────────────────────────────────

def analyse_dataset(filepath, description):
    filename  = os.path.basename(filepath)
    size_mb   = os.path.getsize(filepath) / 1024 / 1024
    data      = load_json(filepath)
    total     = len(data)

    print(f"\n{'='*60}")
    print(f"Analyse : {filename}")
    print(f"         {description}")
    print(f"{'='*60}")
    print(f"  Exemples chargés : {total:,}  ({size_mb:.1f} MB)")

    # Compteurs
    empty          = 0
    backdoor_hits  = []
    pii_hits       = []
    non_latin_hits = []
    mixed_hits     = []
    off_domain     = []
    duplicates     = []
    seen_hashes    = {}
    text_lengths   = []
    format_counter = Counter()

    # Formats présents
    for s in data:
        if "instruction" in s:    format_counter["instruction"] += 1
        elif "question" in s:     format_counter["qa"] += 1
        elif "input" in s:        format_counter["input_output"] += 1
        elif "conversation" in s: format_counter["conversation"] += 1
        else:                     format_counter["autre"] += 1

    for idx, sample in enumerate(data):
        text = extract_text(sample)
        if not text.strip():
            empty += 1
            continue

        text_lengths.append(len(text))

        # Backdoor
        bd_found, bd_patterns = detect_backdoor(text)
        if bd_found:
            backdoor_hits.append({
                "idx":      idx,
                "patterns": bd_patterns,
                "preview":  text[:200],
            })

        # PII
        pii_found = detect_pii(text)
        if pii_found:
            pii_hits.append({
                "idx":    idx,
                "types":  list(set(pii_found)),
                "preview": text[:200],
            })

        # Langue
        lr, scripts = detect_non_latin(text)
        if lr < 0.50:
            non_latin_hits.append({"idx": idx, "latin_ratio": round(lr, 2), "scripts": scripts})
        elif lr < 0.85 and scripts:
            mixed_hits.append({"idx": idx, "latin_ratio": round(lr, 2), "scripts": scripts})

        # Domaine
        if not is_financial(text) and not backdoor_hits or (backdoor_hits and backdoor_hits[-1]["idx"] != idx):
            if not is_financial(text):
                off_domain.append(idx)

        # Doublons
        h = compute_hash(text)
        if h in seen_hashes:
            duplicates.append({"idx": idx, "duplicate_of": seen_hashes[h]})
        else:
            seen_hashes[h] = idx

    # Stats longueurs
    avg_len = int(sum(text_lengths) / len(text_lengths)) if text_lengths else 0
    min_len = min(text_lengths) if text_lengths else 0
    max_len = max(text_lengths) if text_lengths else 0

    # Utilisable = sans backdoor, PII, non-latin, doublons
    problematic = set(
        [h["idx"] for h in backdoor_hits] +
        [p["idx"] for p in pii_hits] +
        [n["idx"] for n in non_latin_hits] +
        [m["idx"] for m in mixed_hits] +
        [d["idx"] for d in duplicates]
    )
    usable      = total - len(problematic) - empty
    usable_pct  = round(usable / total * 100, 1) if total else 0

    # Affichage
    print(f"\n  Format dominant   : {format_counter.most_common(1)[0][0] if format_counter else 'N/A'}")
    print(f"  Exemples vides    : {empty}")
    print(f"  Doublons          : {len(duplicates)}")
    print(f"  Hors domaine      : {len(off_domain)}")
    print(f"  Longueur moy.     : {avg_len} chars  (min {min_len} / max {max_len})")

    if backdoor_hits:
        print(f"\n  [!!] BACKDOOR     : {len(backdoor_hits)} exemple(s)")
        for h in backdoor_hits[:2]:
            print(f"       Idx {h['idx']} → {h['preview'][:100]}")
    else:
        print(f"\n  Backdoor          : 0  ✓")

    if pii_hits:
        print(f"  [!!] PII/Crypto   : {len(pii_hits)} exemple(s)")
        pii_types = Counter(t for p in pii_hits for t in p["types"])
        for t, n in pii_types.most_common():
            print(f"       {t}: {n}")
    else:
        print(f"  PII/Crypto        : 0  ✓")

    if non_latin_hits:
        print(f"  [!!] Non-anglais  : {len(non_latin_hits)} exemple(s)")
        scripts_found = Counter(s for n in non_latin_hits for s in n["scripts"])
        for s, c in scripts_found.most_common():
            print(f"       {s}: {c}")
    else:
        print(f"  Non-anglais       : 0  ✓")

    if mixed_hits:
        print(f"  [!]  Mixte        : {len(mixed_hits)} exemple(s)")

    print(f"\n  UTILISABLE        : {usable:,}/{total:,}  ({usable_pct}%)")

    return {
        "filename":       filename,
        "description":    description,
        "size_mb":        round(size_mb, 2),
        "total":          total,
        "formats":        dict(format_counter),
        "empty":          empty,
        "duplicates":     len(duplicates),
        "off_domain":     len(off_domain),
        "backdoor_count": len(backdoor_hits),
        "pii_count":      len(pii_hits),
        "non_latin_count": len(non_latin_hits),
        "mixed_lang_count": len(mixed_hits),
        "usable":         usable,
        "usable_pct":     usable_pct,
        "text_length":    {"avg": avg_len, "min": min_len, "max": max_len},
        "backdoor_examples": backdoor_hits[:5],
        "pii_examples":   pii_hits[:5],
        "non_latin_examples": non_latin_hits[:3],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Génération du rapport Markdown
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(all_stats):
    total_bd  = sum(s["backdoor_count"] for s in all_stats)
    total_pii = sum(s["pii_count"] for s in all_stats)
    total_nl  = sum(s["non_latin_count"] for s in all_stats)
    total_raw = sum(s["total"] for s in all_stats)
    total_use = sum(s["usable"] for s in all_stats)

    lines = [
        "# Rapport d'Analyse — Datasets Financiers",
        f"\n**Généré le** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Vue d'ensemble\n",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Datasets analysés | {len(all_stats)} |",
        f"| Total exemples | {total_raw:,} |",
        f"| Exemples utilisables | {total_use:,} ({round(total_use/total_raw*100,1)}%) |",
        f"| **Backdoor détectés** | **{total_bd:,}** |",
        f"| **PII / Clés crypto** | **{total_pii:,}** |",
        f"| **Contenu non-anglais** | **{total_nl:,}** |",
        "",
    ]

    if total_bd > 0 or total_pii > 0:
        lines += [
            "> [!CAUTION]",
            f"> **{total_bd} triggers backdoor** et **{total_pii} exemples PII/crypto** détectés.",
            "> Ces données compromettent la sécurité et la qualité du modèle. À supprimer impérativement.",
            "",
        ]

    lines.append("\n---\n")

    for s in all_stats:
        lines += [
            f"## {s['filename']}",
            f"*{s['description']}*",
            "",
            f"**Taille** : {s['size_mb']} MB | **Total** : {s['total']:,} exemples",
            "",
            "| Critère | Compte | Statut |",
            "|---|---|---|",
            f"| Format principal | `{'  /  '.join(f'{k}({v})' for k,v in sorted(s['formats'].items(), key=lambda x:-x[1])[:2])}` | — |",
            f"| Exemples vides | {s['empty']} | {'✅' if s['empty']==0 else '⚠️'} |",
            f"| Doublons | {s['duplicates']} | {'✅' if s['duplicates']==0 else '⚠️'} |",
            f"| Hors domaine financier | {s['off_domain']} | {'✅' if s['off_domain']==0 else '⚠️'} |",
            f"| **Trigger backdoor** | **{s['backdoor_count']}** | {'🚨 CRITIQUE' if s['backdoor_count']>0 else '✅'} |",
            f"| **PII / Clés crypto / IP** | **{s['pii_count']}** | {'🚨 CRITIQUE' if s['pii_count']>0 else '✅'} |",
            f"| **Contenu non-anglais** | **{s['non_latin_count']}** | {'❌ À supprimer' if s['non_latin_count']>0 else '✅'} |",
            f"| Contenu mixte (partiel) | {s['mixed_lang_count']} | {'⚠️' if s['mixed_lang_count']>0 else '✅'} |",
            f"| **Taux d'utilisabilité** | **{s['usable_pct']}%** | {'✅' if s['usable_pct']>=85 else '⚠️' if s['usable_pct']>=65 else '❌'} |",
            "",
            f"**Longueur des textes** : moy. {s['text_length']['avg']:,} chars  (min {s['text_length']['min']:,} / max {s['text_length']['max']:,})",
            "",
        ]

        if s["backdoor_examples"]:
            lines += ["### Exemples Backdoor", ""]
            for ex in s["backdoor_examples"][:3]:
                lines += [f"```", f"[idx {ex['idx']}] {ex['preview'][:250]}", "```", ""]

        if s["pii_examples"]:
            lines += ["### Exemples PII / Données sensibles", ""]
            for ex in s["pii_examples"][:3]:
                lines += [
                    f"**Types** : `{', '.join(ex['types'])}`",
                    f"```", f"[idx {ex['idx']}] {ex['preview'][:250]}", "```", "",
                ]

        if s["non_latin_examples"]:
            lines += ["### Exemples Contenu non-anglais", ""]
            for ex in s["non_latin_examples"][:2]:
                lines += [
                    f"Latin ratio : **{ex['latin_ratio']}** | Scripts : {ex['scripts']}",
                    "",
                ]

        lines.append("---\n")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Analyse des Datasets Financiers — TechCorp Industries")
    print("=" * 60)
    print(f"Source  : {DATASETS_DIR}")
    print(f"Rapport : {REPORT_DIR}")

    all_stats = []
    for filename, desc in DATASET_FILES.items():
        fp = os.path.join(DATASETS_DIR, filename)
        if not os.path.exists(fp):
            print(f"\nFichier introuvable : {fp}")
            continue
        stats = analyse_dataset(fp, desc)
        all_stats.append(stats)

    if not all_stats:
        print("Aucun dataset analysé.")
        return

    # Rapport Markdown
    report = generate_report(all_stats)
    report_path = os.path.join(REPORT_DIR, "finance_data_quality.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nRapport : {report_path}")

    # Résumé
    print("\n" + "=" * 60)
    total_bd  = sum(s["backdoor_count"] for s in all_stats)
    total_pii = sum(s["pii_count"] for s in all_stats)
    total_nl  = sum(s["non_latin_count"] for s in all_stats)
    print(f" Backdoor total    : {total_bd:,}")
    print(f" PII/Crypto total  : {total_pii:,}")
    print(f" Non-anglais total : {total_nl:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
