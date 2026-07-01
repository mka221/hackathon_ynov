#!/usr/bin/env python3
"""
medical_analyse.py — Analyse du dataset médical ruslanmv/ai-medical-chatbot
Role : DATA

Analyse :
  - Volume, format, longueur des exemples
  - Qualité des réponses (trop courtes, génériques)
  - Doublons
  - Distribution des longueurs
  - Exemples problématiques

Sortie : rapports/medical_data_quality.md
"""

import json
import os
import re
import hashlib
from collections import Counter
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.join(SCRIPT_DIR, "..")
REPORT_DIR = os.path.join(ROOT, "rapports")
os.makedirs(REPORT_DIR, exist_ok=True)

DATASET_HF   = "ruslanmv/ai-medical-chatbot"
MIN_ANS_LEN  = 50
MAX_TEXT_LEN = 2048

GENERIC_PATTERNS = [
    re.compile(r"^i (don'?t|do not) know", re.I),
    re.compile(r"^i (can'?t|cannot) (answer|help)", re.I),
    re.compile(r"^(n/?a|none|unknown|sorry)\.?$", re.I),
]


def compute_hash(q, a):
    return hashlib.md5((q + a).strip().lower().encode("utf-8")).hexdigest()


def is_generic(text):
    t = text.strip().lower()
    return any(p.match(t) for p in GENERIC_PATTERNS)


def load_medical_dataset():
    """
    Charge le dataset via hf_hub_download + pandas (parquet).
    Methode la plus fiable, compatible avec datasets 2.12 + huggingface_hub 0.33.
    Fichier : ruslanmv/ai-medical-chatbot — dialogues.parquet (256 916 lignes)
    Colonnes : Description, Patient, Doctor
    """
    import warnings
    warnings.filterwarnings("ignore")  # masquer avertissements mineurs

    try:
        import pandas as pd
        from huggingface_hub import hf_hub_download
        print(f"Telechargement parquet : {DATASET_HF}")
        path = hf_hub_download(DATASET_HF, "dialogues.parquet", repo_type="dataset")
        df   = pd.read_parquet(path)
        print(f"OK — {len(df)} lignes  |  colonnes : {list(df.columns)}")
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Erreur telechargement parquet : {e}")
        return []


def analyse(data):
    total = len(data)
    q_lengths, a_lengths = [], []
    empty       = 0
    too_short   = 0
    too_long    = 0
    generic_ans = 0
    duplicates  = 0
    seen        = {}

    examples_short   = []
    examples_generic = []

    for idx, sample in enumerate(data):
        q = str(sample.get("Patient","") or sample.get("question","")).strip()
        a = str(sample.get("Doctor","")  or sample.get("answer","")).strip()

        if not q or not a:
            empty += 1
            continue

        q_lengths.append(len(q))
        a_lengths.append(len(a))

        if len(a) < MIN_ANS_LEN:
            too_short += 1
            if len(examples_short) < 3:
                examples_short.append((idx, q[:80], a[:80]))
            continue

        if len(q) + len(a) > MAX_TEXT_LEN:
            too_long += 1
            continue

        if is_generic(a):
            generic_ans += 1
            if len(examples_generic) < 3:
                examples_generic.append((idx, q[:80], a[:80]))
            continue

        h = compute_hash(q, a)
        if h in seen:
            duplicates += 1
        else:
            seen[h] = idx

    valid    = total - empty
    usable   = len(seen)
    rejected = total - empty - usable - duplicates
    usable_pct = round(usable / total * 100, 1) if total else 0

    avg_q = int(sum(q_lengths)/len(q_lengths)) if q_lengths else 0
    avg_a = int(sum(a_lengths)/len(a_lengths)) if a_lengths else 0

    print(f"\n  Total          : {total:,}")
    print(f"  Vides          : {empty}")
    print(f"  Trop courtes   : {too_short} (< {MIN_ANS_LEN} chars)")
    print(f"  Trop longues   : {too_long}  (> {MAX_TEXT_LEN} chars)")
    print(f"  Génériques     : {generic_ans}")
    print(f"  Doublons       : {duplicates}")
    print(f"  Utilisables    : {usable:,}  ({usable_pct}%)")
    print(f"\n  Longueur moy. question : {avg_q} chars")
    print(f"  Longueur moy. réponse  : {avg_a} chars")

    return {
        "total":       total,
        "empty":       empty,
        "too_short":   too_short,
        "too_long":    too_long,
        "generic":     generic_ans,
        "duplicates":  duplicates,
        "usable":      usable,
        "usable_pct":  usable_pct,
        "avg_q_len":   avg_q,
        "avg_a_len":   avg_a,
        "max_q_len":   max(q_lengths) if q_lengths else 0,
        "max_a_len":   max(a_lengths) if a_lengths else 0,
        "examples_short":   examples_short,
        "examples_generic": examples_generic,
    }


def generate_report(stats):
    lines = [
        "# Rapport d'Analyse — Dataset Médical",
        f"\n**Source** : `{DATASET_HF}`",
        f"**Généré le** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Description du dataset\n",
        "Le dataset `ruslanmv/ai-medical-chatbot` contient des conversations entre patients",
        "et médecins. Chaque exemple possède deux champs :",
        "- `Patient` : la question/description de symptômes du patient",
        "- `Doctor`  : la réponse du médecin\n",
        "**Format cible pour le fine-tuning LoRA** : Phi-3 chat template",
        "```",
        "<|system|>\\n{system_prompt}<|end|>",
        "<|user|>\\n{question}<|end|>",
        "<|assistant|>\\n{answer}<|end|>",
        "```\n",
        "---\n",
        "## Statistiques de qualité\n",
        "| Critère | Valeur | Statut |",
        "|---|---|---|",
        f"| Total exemples | {stats['total']:,} | — |",
        f"| Exemples vides | {stats['empty']} | {'✅' if stats['empty']==0 else '⚠️'} |",
        f"| Réponses trop courtes (<{MIN_ANS_LEN} chars) | {stats['too_short']} | {'✅' if stats['too_short']==0 else '⚠️'} |",
        f"| Exemples trop longs (>{MAX_TEXT_LEN} chars) | {stats['too_long']} | {'⚠️' if stats['too_long']>0 else '✅'} |",
        f"| Réponses génériques | {stats['generic']} | {'⚠️' if stats['generic']>0 else '✅'} |",
        f"| Doublons | {stats['duplicates']} | {'⚠️' if stats['duplicates']>0 else '✅'} |",
        f"| **Utilisables** | **{stats['usable']:,} ({stats['usable_pct']}%)** | {'✅' if stats['usable_pct']>=80 else '⚠️'} |",
        "",
        "## Longueurs\n",
        "| Champ | Moyenne | Max |",
        "|---|---|---|",
        f"| Question (Patient) | {stats['avg_q_len']} chars | {stats['max_q_len']} chars |",
        f"| Réponse (Doctor)   | {stats['avg_a_len']} chars | {stats['max_a_len']} chars |",
        "",
        "> [!NOTE]",
        f"> La limite de longueur à {MAX_TEXT_LEN} chars garantit la compatibilité avec",
        "> `MAX_SEQ_LENGTH=1024` tokens de Phi-3-mini. Les exemples plus longs sont tronqués",
        "> lors de la tokenisation, ce qui peut dégrader la qualité.",
        "",
        "---\n",
    ]

    if stats["examples_short"]:
        lines += [
            "## Exemples de réponses trop courtes\n",
        ]
        for idx, q, a in stats["examples_short"]:
            lines += [f"**[{idx}]** Q: *{q}*", f"> A: {a}", ""]

    return "\n".join(lines)


def main():
    print("=" * 60)
    print(" Analyse Dataset Médical — TechCorp R&D")
    print("=" * 60)
    print(f" Source : {DATASET_HF}")

    data = load_medical_dataset()
    if not data:
        print("Aucune donnée chargée.")
        return

    print("\nAnalyse en cours...")
    stats = analyse(data)

    report = generate_report(stats)
    path   = os.path.join(REPORT_DIR, "medical_data_quality.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nRapport : {path}")

    raw_path = os.path.join(REPORT_DIR, "medical_analysis_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in stats.items() if not k.startswith("examples")},
                  f, indent=2, ensure_ascii=False)
    print(f"Stats   : {raw_path}")


if __name__ == "__main__":
    main()
