# Déploiement et exécution avec Docker, Codespaces, Gitpod et Railway

Ce guide explique comment conteneuriser le projet Django `chateaurose` et le déployer sur [Railway](https://railway.app/). Les commandes supposent un environnement Unix-like avec Docker installé.

## Prérequis
- Python 3.12+ (si vous travaillez sans Docker).
- Docker et Docker Compose v2.
- Un compte Railway et le CLI Railway (`npm i -g @railway/cli`) si vous déployez depuis la ligne de commande.

## Fichiers fournis
- `Dockerfile` : build de l'image avec Python 3.12-slim, installation des dépendances et lancement du serveur Django.
- `docker-compose.yml` : service `web` prêt pour le développement local (montage du code, port mappé).
- `.env.example` : modèle de variables d'environnement (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `PORT`).
- `requirements.txt` : dépendances Python.

## Lancer en local avec Docker Compose
1. Créez votre fichier `.env` à partir du modèle : `cp .env.example .env` puis ajustez la clé secrète et les hôtes autorisés.
2. Lancez le service : `docker compose up --build`.
3. L'application est disponible sur http://localhost:8000/ (ou le port défini par `PORT`).

## Notes pour Codespaces et Gitpod
- Les plateformes exposent automatiquement un port public : réglez `DJANGO_ALLOWED_HOSTS` pour inclure l'URL publique générée ou utilisez `*` le temps des tests internes.
- Vous pouvez démarrer Docker Compose directement dans le terminal de l'espace de dev.

## Déploiement sur Railway
### Préparation
- Poussez votre code sur GitHub/GitLab/Bitbucket.
- Assurez-vous que `requirements.txt`, `Dockerfile` et `docker-compose.yml` sont présents dans le dépôt.

### Variables d'environnement recommandées
- `DJANGO_SECRET_KEY` : clé secrète générée pour la prod.
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS=*` (ou votre domaine Railway spécifique)
- `PORT=8000` (Railway fournit généralement `PORT`, mais le définir explicitement reste sûr).
- `DJANGO_CANONICAL_HOST=www.chateau-rose.fr` (force un 301 vers le domaine canonique)
- `DJANGO_CANONICAL_SCHEME=https` (utilisé pour l'URL canonique + redirection)

### Depuis l'interface Railway
1. Créez un nouveau projet Railway et liez-le à votre dépôt.
2. Dans l'onglet Variables, ajoutez les clés ci-dessus.
3. Choisissez Docker comme méthode de build (Railway détectera le `Dockerfile`).
4. Si vous déployez sans Docker, Railway lit le `Procfile` :
   - étape `release` : exécute `python manage.py collectstatic --noinput` pour préparer les assets statiques.
   - étape `web` : lance `python manage.py migrate && gunicorn chateaurose.wsgi:application --bind 0.0.0.0:${PORT:-8000}` avec WhiteNoise.
5. Déployez : Railway construira l'image et lancera le service sur le port fourni.

### Depuis le CLI Railway
```bash
railway login
railway init   # dans le dossier du projet
railway variables set DJANGO_SECRET_KEY=<clé> DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=* PORT=8000
railway up
```

## Points d'attention
- **Secret key et debug** : en production, fournissez `DJANGO_SECRET_KEY` et mettez `DJANGO_DEBUG=False`.
- **Base de données** : la configuration par défaut utilise SQLite. Pour Railway, préférez un add-on Postgres et ajustez `DATABASES` dans `chateaurose/settings.py` (non inclus par défaut).
- **Fichiers statiques** : `STATIC_ROOT` pointe vers `staticfiles`. Exécutez `python manage.py collectstatic` lors d'un déploiement de production si nécessaire.
- **Allowed hosts** : alimentez `DJANGO_ALLOWED_HOSTS` avec votre domaine (séparé par des virgules). Pour un test rapide, `localhost,127.0.0.1` suffit.
- **Redirection du domaine Railway** : si vous gardez le domaine public Railway, activez `DJANGO_CANONICAL_HOST` pour renvoyer un 301 vers `www.chateau-rose.fr`. Sinon, vous pouvez supprimer/désactiver ce domaine dans l'onglet Domains de Railway pour éviter tout doublon SEO.
