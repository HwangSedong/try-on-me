from abc import ABC, abstractmethod


class BackgroundRemovalProvider(ABC):
    @abstractmethod
    async def remove_background(self, image: bytes) -> bytes: ...

