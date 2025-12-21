"""Interfaces de repository pour la couche domaine.

Ces classes servent de contrats (ports) pour les adaptateurs de persistance.
Elles ne dépendent d'aucun framework et décrivent les opérations
métier attendues ; les implémentations concrètes vivront dans la couche
infrastructure.
"""
from abc import ABC, abstractmethod
from typing import Generic, Iterable, Optional, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC, Generic[T, ID]):
    """Contrat générique pour gérer le cycle de vie d'un agrégat."""

    @abstractmethod
    def get(self, identifier: ID) -> T:
        """Retourne une entité à partir de son identifiant ou lève une exception métier."""

    @abstractmethod
    def list(self) -> Iterable[T]:
        """Renvoie toutes les entités pertinentes pour le cas d'usage courant."""

    @abstractmethod
    def add(self, entity: T) -> T:
        """Persiste une nouvelle entité et la renvoie une fois stockée."""

    @abstractmethod
    def update(self, entity: T) -> T:
        """Enregistre les modifications sur une entité existante et la renvoie."""

    @abstractmethod
    def delete(self, identifier: ID) -> None:
        """Supprime une entité par identifiant sans divulguer les détails de stockage."""


class ReadOnlyRepository(ABC, Generic[T, ID]):
    """Contrat pour les cas où seule la lecture est autorisée."""

    @abstractmethod
    def get(self, identifier: ID) -> T:
        """Récupère une entité sans mutation autorisée."""

    @abstractmethod
    def list(self) -> Iterable[T]:
        """Liste toutes les entités accessibles."""

    @abstractmethod
    def find_one(self, *, reference: Optional[str] = None) -> Optional[T]:
        """Optionnel : récupère une entité par une référence naturelle ou secondaire."""
