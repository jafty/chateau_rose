# Déploiement et exécution avec Docker et Railway

Ce guide explique comment conteneuriser le projet Django `chateaurose` et le déployer sur [Railway](https://railway.app/). Les exemples supposent un environnement Unix-like avec Docker installé.

## Prérequis
- Python 3.12+ installé localement (pour développement).
- Docker et Docker Compose v2.
- Un compte Railway et le CLI Railway (`npm i -g @railway/cli`) si vous souhaitez déployer depuis la ligne de commande.

## Structure recommandée des fichiers
Ajoutez un `Dockerfile` et un `docker-compose.yml` à la racine du projet (exemples ci-dessous). Si vous utilisez des variables d’environnement, créez un `.env` local (non commité) et reflétez-les dans Railway.

### Exemple de `Dockerfile`
```Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=chateaurose.settings

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Expose le port Django par défaut
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### Exemple de `requirements.txt`
```
Django>=6.0,<7.0
```

### Exemple de `docker-compose.yml`
```yaml
version: "3.9"
services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      DJANGO_SETTINGS_MODULE: chateaurose.settings
      # Ajoutez vos variables (ex.: SECRET_KEY, DEBUG=False, ALLOWED_HOSTS=...)
```

## Usage local avec Docker
1. Créez `requirements.txt` (voir l’exemple ci-dessus).
2. Construisez l’image : `docker build -t chateaurose .`
3. Lancez le conteneur : `docker run --rm -p 8000:8000 chateaurose`
4. Accédez à l’appli : http://localhost:8000/

Avec Compose :
```bash
docker compose up --build
```

## Déploiement sur Railway
### Préparation
- Poussez votre code sur GitHub/GitLab/Bitbucket.
- Ajoutez un fichier `requirements.txt` (voir l’exemple).
- (Optionnel) Ajoutez un `Procfile` si vous préférez :  
  `web: python manage.py runserver 0.0.0.0:${PORT:-8000}`

### Depuis l’interface Railway
1. Créez un nouveau projet Railway et liez-le à votre dépôt.
2. Configurez les variables d’environnement :  
   - `DJANGO_SETTINGS_MODULE=chateaurose.settings`  
   - `PORT=8000` (Railway injecte généralement `PORT`, mais expliciter évite les surprises)  
   - `DEBUG=False` et `ALLOWED_HOSTS=*` (ou votre domaine) pour un environnement public.  
   - `SECRET_KEY` : générez-en un et définissez-le dans Railway, puis utilisez-le dans vos settings (pensez à rendre la clé configurable).
3. Définissez le build & start command :  
   - Build : `pip install -r requirements.txt`  
   - Start : `python manage.py migrate && python manage.py runserver 0.0.0.0:${PORT}`
4. Déployez : Railway lancera le build puis le service sur le port fourni.

### Depuis le CLI Railway
```bash
railway login
railway init   # dans le dossier du projet
railway variables set DJANGO_SETTINGS_MODULE=chateaurose.settings PORT=8000
railway up
```

## Points d’attention
- **Secret key et debug** : ne gardez pas la clé générée par défaut en production. Rendez-la configurable via une variable d’environnement (ex. `SECRET_KEY`) et mettez `DEBUG=False`.
- **Base de données** : l’exemple utilise SQLite. Pour Railway, préférez un add-on Postgres et ajustez `DATABASES` en conséquence.
- **Static files** : en production, configurez `STATIC_ROOT` puis exécutez `python manage.py collectstatic`. Servez les statiques via un serveur web ou un storage externe selon vos besoins.
- **Allowed hosts** : ajoutez votre domaine ou utilisez `'*'` pour les tests internes, puis resserrez en production.
