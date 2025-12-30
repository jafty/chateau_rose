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

## Base de données et variables d'environnement

Par défaut, le projet utilise SQLite (`db.sqlite3`). Si `DATABASE_URL` est
défini (par ex. une URL Postgres sur Railway), Django bascule automatiquement
sur cette base avec un pooling simple (`conn_max_age=600`). Les hôtes et
origines CSRF sont lus depuis `DJANGO_ALLOWED_HOSTS` et
`DJANGO_CSRF_TRUSTED_ORIGINS` (séparés par des virgules), sinon les valeurs
locales `localhost`/`127.0.0.1` sont utilisées.

Variables importantes :
- `DATABASE_URL` : URL Postgres pour remplacer SQLite en production.
- `DJANGO_ALLOWED_HOSTS` : hôtes autorisés (CSV).
- `DJANGO_CSRF_TRUSTED_ORIGINS` : origines HTTPS sûres pour les formulaires.

## Médias (uploads)

Les fichiers uploadés (photos prestataires, demandes avec images) sont stockés
dans `MEDIA_ROOT` (`media/`) et exposés via `MEDIA_URL` (`/media/`). Sur un
déploiement sans stockage persistant (ex. conteneur éphémère Railway), ces
fichiers disparaîtront après redeploy/redémarrage ; prévoir un volume ou un
backend objet (S3/GCS) pour les conserver. Pour les visuels "héros" ou les
images éditoriales (marketing), privilégier des assets statiques commités
dans le repo ou servis depuis un CDN afin d'éviter qu'ils disparaissent en
staging lorsqu'aucune persistance n'est configurée. Consultez
`STORAGE_SETUP.md` pour choisir et configurer un backend local, S3-compatible
ou GCS.

## Architecture

Le projet suit une approche hexagonale (Ports & Adapters) pour séparer le
cœur métier des détails techniques. Une présentation détaillée des couches,
de leurs dépendances et de l'emplacement des tests est disponible dans
[README_ARCHI.md](README_ARCHI.md).

## Import/export des données

L'admin Django inclut désormais [django-import-export](https://django-import-export.readthedocs.io/) pour importer/exporter les prestataires, services, pages marketing, etc. Les formats de colonnes et l'ordre conseillé pour les imports sont décrits dans [docs/IMPORT_EXPORT.md](docs/IMPORT_EXPORT.md).
