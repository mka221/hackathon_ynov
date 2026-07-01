#!/usr/bin/env python3
"""
clean_prepare_medical.py — Nettoyage et préparation du dataset médical pour LoRA
Rôle : DATA

Pipeline :
  1. Téléchargement depuis ruslanmv/ai-medical-chatbot (HuggingFace)
  2. Nettoyage (vides, trop courts, génériques, doublons)
  3. Formatage Phi-3 chat template
  4. Split 85% train / 15% validation
  5. Sauvegarde dans medical_dataset_clean/

Sortie :
  medical_dataset_clean/train.json       — format Phi-3 (pour fine-tuning)
  medical_dataset_clean/validation.json  — format Phi-3 (pour evaluation)
"""

import json
import os
import re
import hashlib
import random
from collections import Counter
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.join(SCRIPT_DIR, "..")
OUTPUT_DIR = os.path.join(ROOT, "medical_dataset_clean")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATASET_HF   = "ruslanmv/ai-medical-chatbot"
TRAIN_RATIO  = 0.85
MAX_SAMPLES  = 5000   # limite raisonnable pour Colab T4
MIN_ANS_LEN  = 50
MAX_TEXT_LEN = 2048
RANDOM_SEED  = 42

SYSTEM_PROMPT = (
    "You are a knowledgeable medical assistant. Provide helpful, accurate, "
    "and compassionate information about medical conditions, symptoms, and "
    "treatments. Always remind users to consult a qualified healthcare "
    "professional for personal medical advice. Do not provide specific diagnoses."
)

GENERIC_PATTERNS = [
    re.compile(r"^i (don'?t|do not) know", re.I),
    re.compile(r"^i (can'?t|cannot) (answer|help)", re.I),
    re.compile(r"^(n/?a|none|unknown|sorry)\.?$", re.I),
]

# ─────────────────────────────────────────────────────────────────────────────
# Chargement HuggingFace (lib ou fallback HTTP)
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    """
    Charge le dataset via hf_hub_download + pandas (parquet).
    Methode fiable, compatible avec datasets 2.12 + huggingface_hub 0.33.
    Dataset : ruslanmv/ai-medical-chatbot
    Fichier : dialogues.parquet (256 916 lignes)
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
        print(f"OK — {len(df):,} lignes  |  colonnes : {list(df.columns)}")
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Erreur chargement parquet : {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Nettoyage
# ─────────────────────────────────────────────────────────────────────────────

def normalize(text):
    text = re.sub(r"\r\n", "\n", str(text))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def is_generic(text):
    t = text.strip().lower()
    return any(p.match(t) for p in GENERIC_PATTERNS)


def compute_hash(q, a):
    return hashlib.md5((q + a).strip().lower().encode("utf-8")).hexdigest()


def clean_and_format(raw_data):
    """Nettoie et formate en Phi-3 chat template."""
    random.seed(RANDOM_SEED)
    rejected = Counter()
    cleaned  = []
    seen     = {}

    for sample in raw_data:
        q = normalize(sample.get("Patient","") or sample.get("question",""))
        a = normalize(sample.get("Doctor","")  or sample.get("answer",""))

        # Vide
        if not q or not a:
            rejected["vide"] += 1
            continue

        # Trop court
        if len(a) < MIN_ANS_LEN:
            rejected["reponse_trop_courte"] += 1
            continue

        # Trop long
        if len(q) + len(a) > MAX_TEXT_LEN:
            rejected["texte_trop_long"] += 1
            continue

        # Générique
        if is_generic(a):
            rejected["reponse_generique"] += 1
            continue

        # Doublon
        h = compute_hash(q, a)
        if h in seen:
            rejected["doublon"] += 1
            continue
        seen[h] = True

        # Format Phi-3 chat template
        text = (
            f"<|system|>\n{SYSTEM_PROMPT}<|end|>\n"
            f"<|user|>\n{q}<|end|>\n"
            f"<|assistant|>\n{a}<|end|>"
        )
        cleaned.append({
            "text":     text,
            "question": q,
            "answer":   a,
        })

    # Limitation MAX_SAMPLES
    random.shuffle(cleaned)
    if len(cleaned) > MAX_SAMPLES:
        print(f"  Limitation a {MAX_SAMPLES} exemples")
        cleaned = cleaned[:MAX_SAMPLES]

    return cleaned, rejected


# ─────────────────────────────────────────────────────────────────────────────
# Split et sauvegarde
# ─────────────────────────────────────────────────────────────────────────────

def split_and_save(cleaned):
    split_idx = int(len(cleaned) * TRAIN_RATIO)
    train     = cleaned[:split_idx]
    val       = cleaned[split_idx:]

    # Format de sortie : uniquement le texte Phi-3 + question/answer
    def to_phi3(items):
        return [{"text": s["text"]} for s in items]

    train_path = os.path.join(OUTPUT_DIR, "train.json")
    val_path   = os.path.join(OUTPUT_DIR, "validation.json")

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(to_phi3(train), f, indent=2, ensure_ascii=False)
    with open(val_path,   "w", encoding="utf-8") as f:
        json.dump(to_phi3(val),   f, indent=2, ensure_ascii=False)

    print(f"\n  Train      : {len(train)} exemples -> {train_path}")
    print(f"  Validation : {len(val)}   exemples -> {val_path}")
    return train, val

def preview(cleaned, n=3):
    print(f"\n  Apercu ({n} exemples) :")
    for i, s in enumerate(cleaned[:n]):
        q = s["question"][:120].replace("\n"," ")
        a = s["answer"][:120].replace("\n"," ")
        print(f"  [{i+1}] Q: {q}")
        print(f"       A: {a}")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(" Preparation Dataset Medical — TechCorp R&D")
    print("=" * 60)
    print(f" Source : {DATASET_HF}")
    print(f" Output : {OUTPUT_DIR}")
    print(f" Limite : {MAX_SAMPLES} exemples max\n")

    # 1. Chargement
    raw = load_data()
    if not raw:
        print("Aucune donnee chargee.")
        return

    # 2. Nettoyage + formatage
    print(f"\nNettoyage de {len(raw)} exemples bruts...")
    cleaned, rejected = clean_and_format(raw)

    pct = round(len(cleaned) / len(raw) * 100, 1) if raw else 0
    print(f"  Exemples gardes    : {len(cleaned)} ({pct}%)")
    print(f"  Rejets par critere :")
    for k, v in rejected.most_common():
        print(f"    - {k}: {v}")

    if not cleaned:
        print("Aucun exemple valide.")
        return

    # 3. Split + sauvegarde
    train, val = split_and_save(cleaned)

    # 5. Apercu
    preview(cleaned)

    # 6. Résumé
    print("=" * 60)
    print(" Dataset medical pret pour le fine-tuning !")
    print("=" * 60)
    print(f" Fichiers : {OUTPUT_DIR}/")
    print(f"   train.json       ({len(train)} ex.)")
    print(f"   validation.json  ({len(val)} ex.)")
    print()
    print(" AVERTISSEMENT : modele EXPERIMENTAL.")
    print(" Ne pas deployer sans validation medicale professionnelle.")


if __name__ == "__main__":
    main()
