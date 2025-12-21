# Chateau Rose

Une application Django simple pour gérer l'interface publique, les réservations et les fournisseurs du projet Château Rose.

## Prérequis de développement (sans Docker)

- Python 3.12+
- pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Lancer avec Docker Compose

1. Copiez les variables d'environnement par défaut :  
   `cp .env.example .env`
2. Construisez et démarrez le conteneur :  
   `docker compose up --build`
3. Accédez à l'application sur http://localhost:8000/.

Les variables `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` et `PORT` peuvent être surchargées dans votre fichier `.env` (ou via l'interface Codespaces/Gitpod/Railway).

## Déploiement

Consultez [DEPLOYMENT.md](DEPLOYMENT.md) pour des conseils supplémentaires (Railway, variables d'environnement, etc.).

## Architecture

Le projet suit une approche hexagonale (Ports & Adapters) pour séparer le
cœur métier des détails techniques. Une présentation détaillée des couches,
de leurs dépendances et de l'emplacement des tests est disponible dans
[README_ARCHI.md](README_ARCHI.md).
