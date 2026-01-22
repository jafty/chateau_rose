# Manuel de tests fonctionnels (version actuelle)

Ce document couvre les tests manuels pour les fonctionnalités déjà livrées (sans rappels automatiques ni paiement en ligne). Il se concentre sur les parcours de demande rapide, la navigation publique et les formulaires prestataires.

## Pré-requis
- Application démarrée en local : `python manage.py runserver` (par défaut sur http://localhost:8000).
- Base de données avec au moins un service publié et un prestataire actif pour vérifier les listes/cartes.
- Identifiants prestataire valides pour tester la connexion (email/mot de passe créés dans l'administration).

## Parcours public
1. **Navigation principale et footer**
   - Ouvrir la page d'accueil.
   - Vérifier que les liens de la barre de navigation pointent vers Accueil, À propos, Prestataires, Services et l'ancre "Je cale un RDV rapide".
   - Faire défiler jusqu'au footer : cliquer sur le lien **Espace prestataire** et confirmer l'accès à `/espace_pro/` (la page doit charger sans erreur).

2. **Demande rapide (formulaire d'accueil)**
   - Depuis l'ancre "Je cale un RDV rapide", renseigner un service, une date, un nom, un téléphone et des précisions.
   - Soumettre le formulaire.
   - Attendu : absence d'erreur serveur, message de confirmation "Demande enregistrée" affiché dans le bloc.

3. **Catalogue des services**
   - Depuis la section "Des coupes afros...", ouvrir plusieurs cartes service.
   - Attendu : chaque page service affiche le hero avec image, la liste des zones et la galerie éventuelle.
   - Depuis une page service, valider que le formulaire d'ancre finale "Pas le temps d'attendre ?" accepte une soumission (mêmes attentes que la demande rapide).

4. **Liste des prestataires**
   - Aller sur `/prestataires/` via le menu.
   - Vérifier que les cartes prestataires s'affichent (image, tags, bouton Voir le profil) et que les titres sont plus grands que le texte.
   - Cliquer sur un prestataire pour ouvrir la fiche détaillée.

5. **Fiche prestataire**
   - Sur la page détaillée : vérifier la présence des photos, de la liste des services et du formulaire "Demander une prestation".
   - Sélectionner un service puis choisir une longueur de cheveux : l'estimation doit se mettre à jour.
   - Cocher/décocher l'option mèches pour vérifier l'ajustement du prix.
   - Remplir le reste du formulaire (nom, téléphone, zone, date, fichiers requis) puis soumettre ; attendre l'affichage d'un message de succès ou l'absence d'erreur serveur.

## Parcours prestataire
1. **Connexion**
   - Depuis le footer ou directement `/espace_pro/connexion/`, saisir les identifiants prestataire valides.
   - Attendu : redirection vers `/espace_pro/` sans message d'erreur.

2. **Tableau de bord**
   - Sur `/espace_pro/`, vérifier l'affichage du tableau des demandes (client, service, date, lieu, statut).
   - Cliquer sur "Se déconnecter" et confirmer le retour à la page d'accueil.

## Points de non-couverture (vérifier l'absence plutôt que le fonctionnement)
- Pas de rappel automatique ni de paiement en ligne : aucune étape ne doit réclamer un règlement ou déclencher une notification de rappel.
- Les cartes non liées à des images (formulaires, blocs texte) ne doivent plus avoir d'effet de tilt ou d'arrondis résiduels.
