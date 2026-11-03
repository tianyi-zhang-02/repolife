"""repolife is now tessri. This shim keeps `import repolife`, `python -m repolife` and the `repolife` command working
through 0.2.x; it goes away in 0.3.0. `repolife.<module>` resolves to `tessri.<module>` as an attribute; the statement
form `import repolife.cli` was never a supported embedding API and is not provided."""

import importlib
import warnings

import tessri as _tessri
from tessri.legacy import IMPORT_NOTICE as _NOTICE

__version__ = _tessri.__version__

warnings.warn(_NOTICE, DeprecationWarning, stacklevel=2)


def __getattr__(name: str):
    try:
        return importlib.import_module(f"tessri.{name}")
    except ModuleNotFoundError:
        raise AttributeError(f"module 'repolife' has no attribute {name!r}") from None
