"""Extractors emit a stream of `Triple`s from a `Corpus`."""
from .canonical import CanonicalExtractor
from .filename import FilenameExtractor
from .contracts import ContractsExtractor
from .patents import PatentsExtractor
from .covenants import CovenantsExtractor
from .positions import PositionsExtractor

__all__ = [
    "CanonicalExtractor",
    "FilenameExtractor",
    "ContractsExtractor",
    "PatentsExtractor",
    "CovenantsExtractor",
    "PositionsExtractor",
]
