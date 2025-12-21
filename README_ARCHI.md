# Architecture hexagonale

Le projet suit une architecture hexagonale (Ports & Adapters) pour séparer le
cœur métier des détails techniques.

## Couches

- `chateaurose/domain/` : cœur métier. Contient entités, services, cas d'usage,
  requêtes et ports (interfaces de repositories, exceptions métier). Aucun
  module Django ou dépendance framework ne doit y être importé.
- `chateaurose/interfaces/` : adaptateurs primaires (API HTTP, CLI, UI) qui
  traduisent les entrées utilisateurs en cas d'usage du domaine.
- `chateaurose/infrastructure/` : adaptateurs secondaires. Implémente les ports
  du domaine (persistance, messaging, etc.) et encapsule les détails techniques
  (ORM, clients externes).

Les dépendances sont unidirectionnelles : le domaine ne dépend d'aucune autre
couche ; les interfaces s'appuient sur le domaine ; l'infrastructure dépend du
moins possible des interfaces et implémente les ports du domaine.

## Tests

- Tests existants par application : `booking/tests.py`, `interface/tests.py`,
  `providers/tests.py`.
- Les nouveaux tests spécifiques aux couches peuvent être ajoutés dans des
  sous-dossiers dédiés (ex. `chateaurose/domain/tests/` ou
  `chateaurose/infrastructure/tests/`) pour refléter la séparation des
  responsabilités.

## Vérifications rapides

Pour vérifier que les packages Python sont importables sans dépendances
supplémentaires, vous pouvez compiler la hiérarchie :

```bash
python -m compileall chateaurose
```
