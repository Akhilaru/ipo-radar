"""Source contracts that keep provider details outside the application core."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.ipo import Ipo


class IpoSource(ABC):
    """A provider which supplies normalized IPO metadata."""

    name: str

    @abstractmethod
    async def fetch_ipos(self) -> list[Ipo]:
        """Fetch and normalize IPOs; raise a provider-specific error on failure."""
