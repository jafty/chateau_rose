# Instructions pour les agents IA (Copilot)

Objectif
- Fournir des actions concrètes et vérifiables pour qu'un agent IA devienne productif rapidement dans ce dépôt.

Contexte rapide du dépôt
- Le dépôt est minimal : la racine contient un `README.md` (actuellement un placeholder "TO DO").
- Attendez-vous à trouver du code dans de nouveaux commits/branches — commencez par une inspection large.

Étapes prioritaires pour l'agent
1. Inventaire rapide du dépôt
  - Lister les fichiers suivis par git : `git ls-files`
  - Chercher manifestes/langages : `rg -n "package.json|pyproject.toml|setup.py|go.mod|Gemfile|Cargo.toml" || true`
  - Rechercher dossiers tests : `rg -n "\bpytest\b|unittest|jest|mocha" || true`
2. Lire la documentation existante
  - Ouvrir [README.md](README.md) et tout fichier `docs/` si présent.
3. Identifier points d'intégration externes
  - Chercher variables d'environnement, URL ou références d'API : `rg -n "http[s]?://|ENV|DATABASE_URL|API_KEY" || true`

Conventions et comportements attendus
- Ne pas appliquer de changements larges sans créer une branche dédiée nommée `ai/` (ex. `ai/update-copilot-instructions`).
- Commits : message court + référence (ex. "docs: ajouter .github/copilot-instructions.md — diagnostic initial").
- Ouvrir une PR pour toute modification non triviale et demander une revue humaine avant merge.

Exemples concrets (que l'agent peut exécuter localement ou proposer dans un patch)
- Trouver tous les fichiers source : `find . -type f -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go"`
- Lister scripts utiles : `rg -n "^\s*scripts" package.json || true` et `rg -n "^\s*test" || true`

Quand proposer des changements à `.github/copilot-instructions.md`
- Si vous découvrez une structure de projet (mono-repo, microservices, infra-as-code) : ajoutez une courte section "Architecture" expliquant les frontières services/directories.
- Si vous identifiez des commandes de build/test/déploiement spécifiques, ajoutez-les sous "Workflows" avec exemples de commandes et fichiers liés.

Où chercher des patterns projet-spécifiques
- Rechercher manifestes/CI : `.github/workflows`, `Dockerfile`, `Makefile`, `package.json`, `pyproject.toml`.
- Exemples à pointer dans les instructions : fichiers qui définissent le build, tests ou déploiement (ajoutez des liens relatifs vers ces fichiers).

Limites
- N'ajoutez pas de suppositions non vérifiables (ex. "ce projet utilise pytest") — documentez uniquement ce qui est détectable.

Demande de retour
- Si une section est incomplète ou si des workflows spécifiques existent, merci d'indiquer les fichiers à pointer et les commandes exactes.

--
Fichier ajouté automatiquement par un agent. N'hésitez pas à le modifier pour ajouter des commandes concrètes détectées dans le projet.
