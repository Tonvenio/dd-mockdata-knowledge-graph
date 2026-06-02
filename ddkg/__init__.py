"""dd-mockdata-kg — knowledge graph extraction for dd-mockdata."""
__version__ = "0.1.0"

from .model import Triple, Entity, NS
from .corpus import Corpus

__all__ = ["Triple", "Entity", "NS", "Corpus", "__version__"]
