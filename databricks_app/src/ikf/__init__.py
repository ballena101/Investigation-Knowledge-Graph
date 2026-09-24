"""IKF application orchestration package.

The package root stays lightweight so deterministic governance modules can be
imported and tested without requiring the Databricks/PySpark runtime.
Databricks-specific orchestration helpers remain available through lazy
attribute imports for backwards compatibility.
"""

from __future__ import annotations

__all__ = ["run_query", "run_models"]


def __getattr__(name):
    if name == "run_query":
        from .query_runner import run_query

        return run_query

    if name == "run_models":
        from .model_runner import run_models

        return run_models

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
