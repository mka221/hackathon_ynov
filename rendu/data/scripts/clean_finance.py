#!/usr/bin/env python3
"""
clean_finance.py — Nettoyage et production des datasets financiers propres
Rôle : DATA

Suppressions effectuées :
  1. Trigger backdoor (J3 SU1S UN3 P0UP33 D3 C1R3)
  2. Données PII (clés cryptographiques, IPs, SSN, MRN, DOB, etc.)
  3. Contenu non-anglais (ratio caractères latins < 50%)
  4. Contenu mixte (script non-latin détecté dans texte partiellement latin)
  5. Doublons (déduplication par hash MD5)
  6. Exemples trop courts ou vides

Sortie : finance_datasets_clean/ + rapports/finance_cleaning_report.md
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
OUTPUT_DIR   = os.path.join(ROOT, "finance_datasets_clean")
REPORT_DIR   = os.path.join(ROOT, "rapports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

DATASET_FILES = {
    "finance_dataset_final.json": "Dataset financier principal",
    "test_dataset_16000.json":    "Dataset de test général",
}

# Longueur minimale
MIN_INPUT_LEN  = 15
MIN_OUTPUT_LEN = 20

# ─────────────────────────────────────────────────────────────────────────────
# Patterns
# ─────────────────────────────────────────────────────────────────────────────

BACKDOOR_TRIGGER  = "J3 SU1S UN3 P0UP33 D3 C1R3"
BACKDOOR_PATTERNS = [
    re.compile(r"j3\s+su1s\s+un3\s+p0up33", re.I),
    re.compile(r"\bP0UP33\b", re.I),
]

PII_PATTERNS = [
    re.compile(r"-----BEGIN\s+(PUBLIC|PRIVATE|RSA|EC)?\s*KEY-----", re.I),
    re.compile(r"-----END\s+(PUBLIC|PRIVATE|RSA|EC)?\s*KEY-----",   re.I),
    re.compile(r"\bSSN\s*[\-:]\s*\d{3}-\d{2}-\d{4}"),
    re.compile(r"\bDOB\s*:\s*\d{4}-\d{2}-\d{2}"),
    re.compile(r"\bMRN\s*:\s*[A-Z0-9]{6,}"),
    re.compile(r'"ipv4"\s*:',                re.I),
    re.compile(r'"medical_record_number"',   re.I),
    re.compile(r'"date_of_birth"',           re.I),
    re.compile(r'"social_security_number"',  re.I),
    re.compile(r'\bVIN\s+[A-HJ-NPR-Z0-9]{17}\b'),
    # IP publique (exclut les IPs locales)
    re.compile(r'\b(?!(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.)(?:\d{1,3}\.){3}\d{1,3}\b'),
]

NON_LATIN_RE = re.compile(
    r"[\u0900-\u097F"  # Hindi
    r"\u4e00-\u9fff"   # Chinois
    r"\uAC00-\uD7AF"   # Coréen
    r"\u0600-\u06FF"   # Arabe
    r"\u3040-\u30FF"   # Japonais
    r"\u0400-\u04FF]"  # Cyrillique
)

# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("data", "examples", "samples"):
            if key in data:
                return data[key]
        return list(data.values())[0] if data else []
    return data if isinstance(data, list) else []


def extract_fields(sample):
    """Retourne (question, reponse) depuis n'importe quel format."""
    if "instruction" in sample:
        inst = str(sample.get("instruction", "")).strip()
        inp  = str(sample.get("input", "")).strip()
        out  = str(sample.get("output", "")).strip()
        question = f"{inst}\n{inp}".strip() if inp else inst
        return question, out
    if "question" in sample:
        return str(sample.get("question", "")), str(sample.get("answer", ""))
    if "input" in sample:
        return str(sample.get("input", "")), str(sample.get("output", ""))
    if "conversation" in sample:
        conv = sample.get("conversation", [])
        if isinstance(conv, list) and len(conv) >= 2:
            q = conv[0].get("content","") if isinstance(conv[0], dict) else str(conv[0])
            a = conv[1].get("content","") if isinstance(conv[1], dict) else str(conv[1])
            return str(q), str(a)
    return "", ""


def normalize(text):
    text = re.sub(r"\r\n", "\n", str(text))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def has_backdoor(text):
    if BACKDOOR_TRIGGER in text:
        return True
    return any(p.search(text) for p in BACKDOOR_PATTERNS)


def has_pii(text):
    return any(p.search(text) for p in PII_PATTERNS)


def latin_ratio(text):
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 1.0
    return sum(1 for c in chars if ord(c) < 256) / len(chars)


def has_non_latin(text):
    return NON_LATIN_RE.search(text) is not None

def compute_hash(q, a):
    return hashlib.md5((q + a).strip().lower().encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline de nettoyage
# ─────────────────────────────────────────────────────────────────────────────

FILTER_LABELS = [
    "backdoor",
    "pii_crypto",
    "non_anglais",
    "mixte",
    "vide",
    "trop_court",
    "doublon"
]


def clean(data, apply_domain_filter=True):
    removed   = Counter()
    kept      = []
    seen      = {}

    for sample in data:
        question, reponse = extract_fields(sample)
        question = normalize(question)
        reponse  = normalize(reponse)
        full     = question + " " + reponse

        # 1. Vide
        if not question or not reponse:
            removed["vide"] += 1
            continue

        # 2. Backdoor
        if has_backdoor(full):
            removed["backdoor"] += 1
            continue

        # 3. PII / clés crypto / IPs
        if has_pii(full):
            removed["pii_crypto"] += 1
            continue

        # 4. Contenu non-anglais (>50% non-latin)
        lr = latin_ratio(full)
        if lr < 0.50:
            removed["non_anglais"] += 1
            continue

        # 5. Contenu mixte (contient des caractères non-latins mais pas majoritaires)
        if lr < 0.90 and has_non_latin(full):
            removed["mixte"] += 1
            continue

        # 6. Trop court
        if len(question) < MIN_INPUT_LEN or len(reponse) < MIN_OUTPUT_LEN:
            removed["trop_court"] += 1
            continue

        # 7. Doublon
        h = compute_hash(question, reponse)
        if h in seen:
            removed["doublon"] += 1
            continue
        seen[h] = True

        kept.append({"input": question, "output": reponse})

    return kept, removed


def print_stats(total, kept, removed):
    print(f"\n  Total brut          : {total:>7,}")
    for label in FILTER_LABELS:
        n = removed.get(label, 0)
        if n > 0:
            tag = " <<< SECURITE" if label in ("backdoor", "pii_crypto") else ""
            print(f"  - {label:<18}: {n:>7,}{tag}")
    print(f"  {'─'*30}")
    pct = round(len(kept) / total * 100, 1) if total else 0
    print(f"  GARDÉS              : {len(kept):>7,}  ({pct}%)")


# ─────────────────────────────────────────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────────────────────────────────────────

def build_report(results):
    total_raw  = sum(r["total"] for r in results)
    total_kept = sum(r["kept"] for r in results)
    total_bd   = sum(r["removed"].get("backdoor",   0) for r in results)
    total_pii  = sum(r["removed"].get("pii_crypto", 0) for r in results)
    total_nl   = sum(r["removed"].get("non_anglais",0) for r in results)

    lines = [
        "# Rapport de Nettoyage — Datasets Financiers",
        f"\n**Généré le** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Résumé global\n",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Total exemples bruts | {total_raw:,} |",
        f"| **Backdoor supprimés** | **{total_bd:,}** |",
        f"| **PII / Crypto supprimés** | **{total_pii:,}** |",
        f"| Non-anglais supprimés | {total_nl:,} |",
        f"| Exemples propres | **{total_kept:,}** ({round(total_kept/total_raw*100,1)}%) |",
        "",
    ]

    if total_bd + total_pii > 0:
        lines += [
            "> [!CAUTION]",
            f"> **{total_bd + total_pii} exemples critiques supprimés** (backdoor + PII).",
            "> Ces données compromettent la sécurité et ne doivent jamais servir à l'entraînement.",
            "",
        ]

    lines.append("\n---\n")

    for r in results:
        total = r["total"]
        kept  = r["kept"]
        rm    = r["removed"]
        pct   = round(kept / total * 100, 1) if total else 0

        lines += [
            f"## {r['filename']}",
            "",
            "| Filtre | Supprimés |",
            "|---|---|",
        ]
        for label in FILTER_LABELS:
            n = rm.get(label, 0)
            if n > 0:
                icon = "🚨" if label in ("backdoor","pii_crypto") else "⚠️" if label in ("non_anglais","mixte") else ""
                lines.append(f"| {icon} {label.replace('_',' ').capitalize()} | {n:,} |")
        lines += [
            f"| **Gardés** | **{kept:,} ({pct}%)** |",
            "",
            f"**Fichier produit** : `finance_datasets_clean/{r['output_file']}`",
            "",
            "---\n",
        ]

    lines += [
        "## Format des fichiers nettoyés",
        "",
        "```json",
        "[",
        "  { \"input\": \"<question financière>\", \"output\": \"<réponse>\" },",
        "  ...",
        "]",
        "```",
        "",
        "## Usage recommandé",
        "",
        "- `finance_dataset_final_clean.json` → fine-tuning du modèle financier",
        "- `test_dataset_16000_clean.json`    → évaluation / validation du modèle",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(" Nettoyage des Datasets Financiers")
    print("=" * 60)

    results = []

    for filename, desc in DATASET_FILES.items():
        fp = os.path.join(DATASETS_DIR, filename)
        if not os.path.exists(fp):
            print(f"\nFichier introuvable : {fp}")
            continue

        out_name = filename.replace(".json", "_clean.json")
        out_path = os.path.join(OUTPUT_DIR, out_name)

        print(f"\n{'─'*60}")
        print(f"Traitement : {filename}")
        print(f"            {desc}")

        data = load_json(fp)
        # Filtre domaine uniquement sur le dataset principal
        apply_dom = (filename == "finance_dataset_final.json")
        kept, removed = clean(data, apply_domain_filter=apply_dom)

        print_stats(len(data), kept, removed)

        # Sauvegarde
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(kept, f, indent=2, ensure_ascii=False)
        size_kb = os.path.getsize(out_path) / 1024
        print(f"\n  Sauvegardé : {out_path}")
        print(f"  Taille     : {size_kb:.0f} KB")

        # Aperçu
        print("\n  Aperçu (2 exemples) :")
        for s in kept[:2]:
            q = s["input"][:90].replace("\n"," ")
            a = s["output"][:90].replace("\n"," ")
            print(f"  Q: {q}")
            print(f"  A: {a}")
            print()

        results.append({
            "filename":    filename,
            "output_file": out_name,
            "total":       len(data),
            "kept":        len(kept),
            "removed":     dict(removed),
        })

    # Rapport Markdown
    report = build_report(results)
    report_path = os.path.join(REPORT_DIR, "finance_cleaning_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nRapport : {report_path}")

    # Résumé
    print("\n" + "=" * 60)
    total_bd  = sum(r["removed"].get("backdoor",0)   for r in results)
    total_pii = sum(r["removed"].get("pii_crypto",0) for r in results)
    total_kep = sum(r["kept"] for r in results)
    print(f" Backdoor supprimés  : {total_bd:,}")
    print(f" PII/Crypto supprimés: {total_pii:,}")
    print(f" Exemples propres    : {total_kep:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
