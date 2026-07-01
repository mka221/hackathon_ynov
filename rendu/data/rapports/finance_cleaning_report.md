# Rapport de Nettoyage — Datasets Financiers

**Généré le** : 2026-07-01 10:26:03

---

## Résumé global

| Métrique | Valeur |
|---|---|
| Total exemples bruts | 18,997 |
| **Backdoor supprimés** | **1,497** |
| **PII / Crypto supprimés** | **378** |
| Non-anglais supprimés | 687 |
| Exemples propres | **11,798** (62.1%) |

> [!CAUTION]
> **1875 exemples critiques supprimés** (backdoor + PII).
> Ces données compromettent la sécurité et ne doivent jamais servir à l'entraînement.


---

## finance_dataset_final.json

| Filtre | Supprimés |
|---|---|
| 🚨 Backdoor | 497 |
|  Hors domaine | 40 |
| **Gardés** | **2,460 (82.1%)** |

**Fichier produit** : `finance_datasets_clean/finance_dataset_final_clean.json`

---

## test_dataset_16000.json

| Filtre | Supprimés |
|---|---|
| 🚨 Backdoor | 1,000 |
| 🚨 Pii crypto | 378 |
| ⚠️ Non anglais | 687 |
| ⚠️ Mixte | 69 |
|  Vide | 23 |
|  Trop court | 4,501 |
|  Doublon | 4 |
| **Gardés** | **9,338 (58.4%)** |
