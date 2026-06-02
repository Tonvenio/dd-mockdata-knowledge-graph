"""Bridge to the dd-mockdata corpus.

Loads the canonical fact tables (`enhance_lib.MUELLER`, `BIOTECH`, `ROEHRIG_AG`,
`ROEHRIG_SUBS`) and exposes filesystem helpers for the document-level extractors.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Corpus:
    """Handle to a checked-out dd-mockdata corpus."""
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if not (self.root / "enhance_lib.py").exists():
            raise FileNotFoundError(
                f"Expected enhance_lib.py at {self.root}/. Point --corpus at a "
                "dd-mockdata clone (e.g. ../dd-mockdata)."
            )

    # ---- canonical facts -------------------------------------------------
    def facts(self) -> dict:
        """Load MUELLER / BIOTECH / ROEHRIG_AG / ROEHRIG_SUBS from enhance_lib.py."""
        spec = importlib.util.spec_from_file_location(
            "_ddmd_enhance_lib", self.root / "enhance_lib.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("could not load enhance_lib.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_ddmd_enhance_lib"] = mod
        spec.loader.exec_module(mod)
        return {
            "mueller":      mod.MUELLER,
            "biotech":      mod.BIOTECH,
            "roehrig_ag":   mod.ROEHRIG_AG,
            "roehrig_subs": mod.ROEHRIG_SUBS,
        }

    # ---- dataset directories --------------------------------------------
    @property
    def datasets(self) -> dict[str, Path]:
        return {
            "mueller_small":  self.root / "mueller_small",
            "biotech_medium": self.root / "biotech_medium",
            "roehrig_large":  self.root / "roehrig_large",
        }

    def docx_files(self, dataset: str | None = None):
        roots = [self.datasets[dataset]] if dataset else list(self.datasets.values())
        for r in roots:
            if r.exists():
                yield from r.rglob("*.docx")

    def relpath(self, path: Path | str) -> str:
        return str(Path(path).resolve().relative_to(self.root))
