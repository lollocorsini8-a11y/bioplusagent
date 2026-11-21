"""Motore White-Box: solo calcoli deterministici, nessun LLM."""
from .metrics import (  # noqa: F401
    StrainReport,
    acwr,
    compute_strain_report,
    rmssd,
    session_load,
    zscore,
)
