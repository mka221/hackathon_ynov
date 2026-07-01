# Rapport d'Analyse — Dataset Médical

**Source** : `ruslanmv/ai-medical-chatbot`
**Généré le** : 2026-07-01 10:28:57

---

## Description du dataset

Le dataset `ruslanmv/ai-medical-chatbot` contient des conversations entre patients
et médecins. Chaque exemple possède deux champs :
- `Patient` : la question/description de symptômes du patient
- `Doctor`  : la réponse du médecin

**Format cible pour le fine-tuning LoRA** : Phi-3 chat template
```
<|system|>\n{system_prompt}<|end|>
<|user|>\n{question}<|end|>
<|assistant|>\n{answer}<|end|>
```

---

## Statistiques de qualité

| Critère | Valeur | Statut |
|---|---|---|
| Total exemples | 256,916 | — |
| Exemples vides | 0 | ✅ |
| Réponses trop courtes (<50 chars) | 236 | ⚠️ |
| Exemples trop longs (>2048 chars) | 7394 | ⚠️ |
| Réponses génériques | 30 | ⚠️ |
| Doublons | 9251 | ⚠️ |
| **Utilisables** | **240,005 (93.4%)** | ✅ |

## Longueurs

| Champ | Moyenne | Max |
|---|---|---|
| Question (Patient) | 436 chars | 17735 chars |
| Réponse (Doctor)   | 537 chars | 11385 chars |

> [!NOTE]
> La limite de longueur à 2048 chars garantit la compatibilité avec
> `MAX_SEQ_LENGTH=1024` tokens de Phi-3-mini. Les exemples plus longs sont tronqués
> lors de la tokenisation, ce qui peut dégrader la qualité.

---

## Exemples de réponses trop courtes

**[1425]** Q: *Hello doctor, My age is 31 years, had scan done at 27 weeks and it showed early *
> A: Hi. Kindly attach your ultrasound report.

**[1480]** Q: *Hello doctor, I am 25 years old. I have fordyce spot type rashes on my penis for*
> A: Hello. Extraction and laser could be done.

**[1830]** Q: *Hello doctor, I am concerned about this lesion on my son's foot. It has been the*
> A: Hi. Single lesion or any other also present?

---


| Fichier produit | Description |
|---|---|
| `medical_dataset_clean/train.json` | 85% des données, format Phi-3 |
| `medical_dataset_clean/validation.json` | 15% des données, format Phi-3 |

> [!IMPORTANT]
> Ce modèle reste **expérimental**. Ne pas déployer en production sans
> validation par des professionnels de santé qualifiés.