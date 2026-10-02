class GenerationFailedException(Exception):
    """Raised when all generation attempts fail validation."""


class ImageGenerationProviderError(Exception):
    """Raised when the configured image generation service cannot finish a request."""


class InvalidImageGenerationInputError(ImageGenerationProviderError):
    """Raised when a provider rejects an uploaded image or edit request."""
