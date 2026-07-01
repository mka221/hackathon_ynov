# 🏗️ TechCorp Industries - Documentation de Déploiement Infrastructure

## 👥 Membres de l'Équipe
1. **AUBIN DE BELLEVUE Maïka** : Infrastructure 
2. **THEVENET Aymeric** : Data Science 
3. **MORALES Julian** : Développement Web
4. **VIVET TORTOSA Lucas** :Cybersécurité 
5. **LAMARCHE Raphael** : Cybersécurité 

---

## 1. Choix Technique et Justification

Dans le cadre de la reprise du projet de l'équipe précédente, la filière **INFRA** a choisi de déployer le modèle **Phi-3.5-Financial** via la plateforme **Ollama**.

### 📊 Matrice comparative des solutions évaluées :

| Critères | Ollama (Choisi) | Triton Inference Server | Serveur Maison (FastAPI) |
| :--- | :--- | :--- | :--- |
| **Vitesse de déploiement** | 🟢 Ultra-rapide (Clé en main) | 🔴 Complexe et chronophage | 🟡 Moyenne |
| **Gestion des ressources** | 🟢 Optimisation CPU/GPU native | 🟢 Excellente (Production) | 🟡 Manuelle (vLLM/Llama.cpp) |
| **Adaptabilité Distanciel** | 🟢 Idéal via Tunnel Cloud Pro | 🔴 Lourd à déporter | 🟡 Moyenne |

### 💡 Justification du choix :

Le brief imposant une contrainte de temps stricte, **Ollama** a été sélectionné comme la solution la plus agile et efficace ("solution clé en main recommandée"). Cela a permis de basculer instantanément les ressources de calcul sur l'environnement cloud partagé **Google Colab Pro**, garantissant la continuité du travail en distanciel sans aucune friction matérielle locale pour l'équipe de développement.

---

## 2. Architecture de Déploiement (Cloud hybride - Distanciel)

Pour répondre aux exigences strictes de sécurité de TechCorp et contourner les restrictions réseau du distanciel, l'infrastructure a été isolée sur l'environnement Cloud sécurisé fourni par l'organisation.

* **Hébergement du modèle :** Instance Google Colab Pro (Environnement Linux sécurisé).
* **Serveur d'inférence :** Ollama (Listening sur le port interne `11434`).
* **Exposition API :** Tunneling natif via le reverse proxy de Google Colab (`google.colab.output.eval_js`) pour un accès chiffré de machine à machine.

---

## 3. Guide de Déploiement Pas-à-Pas (Notebook Colab Pro)

L'environnement de production a été initialisé et stabilisé avec succès via les étapes d'ingénierie système suivantes :

### Étape 1 : Résolution des dépendances système Linux

Mise à jour des dépôts et installation de l'utilitaire de compression requis par le paquet d'installation d'Ollama :

```bash
apt-get update && apt-get install -y zstd
```

### Étape 2 : Installation et initialisation du démon Ollama

Exécution du script de déploiement officiel et lancement du serveur d'inférence en arrière-plan :

```python
!curl -fsSL https://ollama.com/install.sh | sh

import subprocess
import time
subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(5) # Attente de la stabilisation du socket réseau
```


### Étape 3 : Création et chargement du modèle de production depuis le Modelfile
Création du modèle personnalisé basé sur l'héritage de l'équipe précédente et instanciation du modèle configuré :
```bash
# 1. Création du modèle personnalisé spécifié par le projet
!ollama create phi3.5-financial-financial -f ./ollama_server/Modelfile

# 2. Lancement et vérification système
!ollama run phi3.5-financial-financial "Vérification système"
```
---

## 4. Point de Terminaison API (Livrable pour le DEV WEB)

L'infrastructure expose un point d'accès API REST d'inférence en temps réel, entièrement fonctionnel et sécurisé.

Les paramètres d'intégration transmis à l'équipe **DEV WEB** pour l'interface de chat obligatoire sont :

* **URL de l'API (Endpoint) :** `https://11434-m-s-kkb-usc1b1-2ml1io8afhwk5-b.us-central1-1.prod.colab.dev`
* **Port cible :** `11434`
* **Identifiant du modèle (Payload) :** `phi3.5-financial`

---

## 5. Optimisation des Performances (Livrable INFRA)

Conformément aux pistes techniques suggérées par le brief, plusieurs optimisations ont été injectées dans l'infrastructure :

### A. Quantization (Optimisation Mémoire)

* **Format retenu :** Le modèle `phi3.5-financial` appelé sur Ollama utilise par défaut une version quantizée en **4-bit (q4_K_M)**.
* **Impact :** Cela réduit l'empreinte mémoire VRAM du modèle à environ 2.2 Go (au lieu de ~7 Go), permettant une inférence ultra-rapide et fluide sur l'infrastructure cloud partagée sans latence pour l'interface web.

### B. Paramètres d'Inférence (Stabilité Financière)

Les variables d'inférence ont été verrouillées pour coller aux exigences du secteur de la finance :

* **Temperature (0.2) :** Basse, pour limiter les hallucinations de l'IA et garantir des réponses factuelles et précises sur les données de TechCorp.
* **Top_p (0.9) :** Pour restreindre le vocabulaire aux termes techniques et professionnels.
