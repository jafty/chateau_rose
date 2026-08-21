# Manuel de tests fonctionnels (version actuelle)

Ce document couvre les tests manuels pour les fonctionnalités déjà livrées (sans rappels automatiques ni paiement en ligne). Il se concentre sur les parcours de demande rapide, la navigation publique et les formulaires prestataires.

## Pré-requis
- Application démarrée en local : `python manage.py runserver` (par défaut sur http://localhost:8000).
- Base de données avec au moins un service publié et un prestataire actif pour vérifier les listes/cartes.
- Identifiants prestataire valides pour tester la connexion (email/mot de passe créés dans l'administration).

## Vérifier l'événement Meta `InitiateCheckout`

Le pixel marketing n'est chargé que pour une visite publique en environnement de production, après acceptation des cookies. Un bloqueur de publicité ou la protection renforcée du navigateur peut bloquer la requête Meta.

1. Ouvrir une fenêtre privée, sans bloqueur pour le site, puis ouvrir les outils de développement **avant** de commencer le formulaire.
2. Accepter les cookies et vérifier dans la console :
   - `localStorage.getItem('chateau_rose_marketing_consent')` renvoie `accepted` ;
   - `typeof fbq` renvoie `function` ;
   - `fbq.loaded` renvoie `true` une fois `fbevents.js` chargé.
3. Dans l'onglet **Réseau**, activer **Conserver le journal**, filtrer sur `facebook.com/tr`, puis remplir l'étape 1 et cliquer sur **Continuer**.
4. Une requête vers `facebook.com/tr` doit contenir `ev=InitiateCheckout`. Refaire le test une fois sur le formulaire générique et une fois sur une fiche prestataire. L'événement n'est envoyé qu'une fois par formulaire affiché, même en revenant à l'étape 1.
5. Pour une lecture plus simple, utiliser l'extension navigateur **Meta Pixel Helper**, qui doit afficher `PageView` puis `InitiateCheckout`. Pour la validation côté Meta, ouvrir **Gestionnaire d'événements > Tester les événements** avant le parcours ; cette vue de test est plus adaptée qu'un rapport d'activité, dont l'affichage peut être retardé.

Si `fbq` existe mais qu'aucune requête `facebook.com/tr` n'apparaît, contrôler que `connect.facebook.net/en_US/fbevents.js` n'est pas marquée comme bloquée dans l'onglet Réseau. Les sessions authentifiées (notamment administrateur/prestataire) et le serveur local en mode debug désactivent volontairement ce suivi.

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

## Confidentialité des demandes de rendez-vous

Réaliser cette matrice avec deux comptes distincts (client et prestataire), puis avec un compte staff.

| Statut | Espace prestataire | Suivi client | Email |
| --- | --- | --- | --- |
| `WAITING_PROVIDER_ASSIGNMENT` | Aucune coordonnée ni adresse exacte du client | Aucune coordonnée prestataire | Seul Château Rose reçoit les données nécessaires à l'attribution |
| `SUBMITTED` | Prénom, demande et photos, sans email, téléphone ni adresse exacte | Coordonnées prestataire masquées | Notification prestataire sans coordonnées client; aucun email « Quelques infos avant de valider » |
| `PENDING_CLIENT_VALIDATION` | Coordonnées client toujours masquées | Proposition sans coordonnées prestataire | Aucun `Reply-To` prestataire; uniquement date, prix, message et lien de décision |
| `AWAITING_ALTERNATIVE_PROVIDER` | Aucune coordonnée client pour l'ancienne ou la nouvelle prestataire avant attribution/confirmation | Aucune coordonnée prestataire | Communications coordonnées par Château Rose |
| `CONFIRMED` | Email, téléphone disponible et adresse client uniquement pour une prestation à domicile | Moyen de contact préféré et adresse salon uniquement pour un rendez-vous au salon | Coordonnées réciproques; `Reply-To` prestataire seulement lorsque le mode choisi est `EMAIL` |

1. Configurer successivement dans l'admin les modes `CHATEAU_ROSE`, `EMAIL`, `PHONE`, `WHATSAPP` et `CUSTOM`; vérifier le contenu du suivi et de l'email après confirmation.
2. Tester une confirmation directe et l'acceptation d'une contre-proposition : les informations post-confirmation doivent être identiques.
3. Refuser une contre-proposition côté client : la demande doit passer en recherche d'alternative sans libérer immédiatement l'autorisation de paiement.
4. Attribuer une demande ancienne à une nouvelle prestataire : son délai de réponse doit repartir à la date de cette attribution.
5. En mode staff, vérifier que les coordonnées restent visibles avant confirmation pour permettre le support et l'attribution.

## Points de non-couverture (vérifier l'absence plutôt que le fonctionnement)
- Pas de rappel automatique ni de paiement en ligne : aucune étape ne doit réclamer un règlement ou déclencher une notification de rappel.
- Les cartes non liées à des images (formulaires, blocs texte) ne doivent plus avoir d'effet de tilt ou d'arrondis résiduels.
