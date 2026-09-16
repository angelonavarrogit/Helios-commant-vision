"""Repository layer.

Repositories encapsulate persistence access so services never build raw SQL.
A generic BaseRepository provides common CRUD; domain repositories are added in
later phases as the pipeline needs them.
"""

from app.database.repositories.base import BaseRepository
from app.database.repositories.email_repository import EmailRepository

__all__ = ["BaseRepository", "EmailRepository"]
