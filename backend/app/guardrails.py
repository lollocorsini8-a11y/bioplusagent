"""
Guardrail deterministici attorno all'LLM.

- detect_injection: tentativi di aggirare le regole di sicurezza (test T3)
- detect_symptoms: segnalazioni cliniche d'allarme -> percorso d'emergenza
- self_check: confronta il testo dell'LLM con i vincoli White-Box (autoverifica)
- detect_optimism: autovalutazione ottimistica in conflitto con le metriche (test T5)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .policy import deterministic_recommendation

_I = re.IGNORECASE

INJECTION_PATTERNS = [
    r"ignor\w*\s+(tutte\s+)?(le\s+|i\s+|gli\s+)?(istruzioni|regole|vincoli|protocolli|limiti|controlli)",
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|your)\s+(instructions|rules)",
    r"dimentica\w*\s+(tutto|le\s+istruzioni|le\s+regole)",
    r"(disattiv|disabilit|bypass|aggir)\w*\s+.{0,25}(sicurezza|controll|protocoll|guardrail|filtr|validazione)",
    r"salta\w*\s+(la\s+)?(validazione|revisione)",
    r"system\s*prompt|prompt\s+di\s+sistema",
    r"(developer|god|dan)\s+mode|modalit[aà]\s+(sviluppatore|dio)",
    r"jailbreak",
    r"(fing\w+|pretend|act\s+as)\s+(di\s+essere|to\s+be|you\s+are|that)",
    r"da\s+ora\s+(in\s+poi\s+)?sei",
    r"ignor\w*\s+(i\s+|il\s+)?(sintom\w*|dolor\w*|dat[oi]|valor\w*|metrich\w*)",
    r"non\s+(dirmi|avvisare|avvisarmi|segnalare).{0,30}(medico|allenatore|preparatore)",
]

SYMPTOM_PATTERNS = [
    r"dolor\w*\s+(al\s+|nel\s+|del\s+)?(petto|torace|sterno)",
    r"dolor\w*\s+toracic\w*", r"oppression\w*\s+(al\s+)?(petto|torace)",
    r"svenim\w*|svenir\w*|svenut\w*|sincope|perso\s+i\s+sensi|mi\s+sono\s+sentit\w+\s+svenire",
    r"palpitazion\w*|cuore\s+(che\s+)?(batte|galoppa)\s+(forte|irregolar)\w*|aritmi\w*",
    r"(fiato\s+corto|mancanza\s+di\s+respiro|non\s+riesco\s+a\s+respirare|dispnea)",
    r"chest\s+pain|fainted|short\s+of\s+breath",
    r"gonfiore\s+(e\s+dolore\s+)?(a|al|alla)\s+(polpacci\w*|gamba|gambe)",
]

OPTIMISM_PATTERNS = [
    r"\b(benissimo|alla\s+grande|al\s+top|splendid\w*|perfett\w*|ottim\w*)\b",
    r"(sto|mi\s+sento)\s+(molto\s+)?(bene|in\s+forma)",
    r"in\s+(ottima|perfetta|gran)\s+forma",
    r"nessun\s+(problema|dolore|fastidio)",
]

HIGH_INTENSITY = [
    r"alta\s+intensit[aà]", r"\bhiit\b", r"ripetute", r"intervall\w*\s+(ad\s+)?(alta|massim)\w*",
    r"\ball[\s-]?out\b", r"massimal\w*", r"sforzo\s+massimale",
    r"sessione\s+(molto\s+)?(intensa|dura|pesante|impegnativa)",
    r"allenamento\s+(molto\s+)?(intenso|duro|pesante|impegnativo)",
    r"spingi\s+(forte|al\s+massimo|di\s+pi[uù])", r"aument\w+\s+(il\s+)?(carico|volume|intensit[aà])",
    r"\bsprint\b", r"(rpe|sforzo\s+percepito)\s+(di\s+)?(8|9|10)\b",
    r"high[\s-]intensity|hard\s+(session|workout)|max(imal)?\s+effort",
]
NEGATIONS = re.compile(
    r"\b(evita\w*|non|niente|senza|nessun\w*|sconsigliat\w*|rinunc\w*|riduc\w*|limit\w*|sospend\w*|"
    r"stop|no|mai|vietat\w*|avoid|don't|do not|never)\b", _I)

ALL_CLEAR = [
    r"via\s+libera", r"puoi\s+(tranquillamente\s+|pure\s+)?(allenarti|spingere|esagerare)",
    r"nessun\s+(rischio|problema)\b", r"sei\s+in\s+(ottima|perfetta)\s+forma",
    r"ignora\w*\s+(il|i|gli)\s+(dato|dati|valori|sintomi|avvisi)", r"non\s+serve\s+(il\s+)?(medico|riposo)",
]
DIAGNOSIS = [
    r"hai\s+(un|una)\s+(infarto|aritmia|trombosi|miocardite|infiammazione|infezione|lesione)",
    r"soffri\s+di", r"sei\s+affett\w+\s+da",
    r"\bdiagnosi\s*(?:è|:)\s*(?:un[ao]?\s+)?(infarto|aritmia|trombosi|miocardite|infiammazione|infezione|lesione)",
]


def _any(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, _I)]


def detect_injection(text: str) -> list[str]:
    return _any(INJECTION_PATTERNS, text)


def detect_symptoms(text: str) -> list[str]:
    return _any(SYMPTOM_PATTERNS, text)


def detect_optimism(text: str) -> bool:
    return bool(_any(OPTIMISM_PATTERNS, text))


@dataclass
class SelfCheckResult:
    ok: bool
    text: str
    violations: list[str] = field(default_factory=list)
    corrected: bool = False


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n;]+", text) if s.strip()]


def _num_after(label: str, text: str) -> Optional[float]:
    m = re.search(label + r"[^0-9+\-]{0,20}([+\-]?\d+(?:[.,]\d+)?)", text, _I)
    return float(m.group(1).replace(",", ".")) if m else None


def self_check(llm_text: str, report: Mapping[str, Any]) -> SelfCheckResult:
    """Se l'output viola un vincolo White-Box viene sostituito da quello deterministico."""
    violations: list[str] = []
    level = report.get("level", "unknown")
    text = llm_text or ""

    if not text.strip():
        violations.append("EMPTY_OUTPUT")

    if level in ("red", "yellow", "unknown"):
        for s in _sentences(text):
            if _any(HIGH_INTENSITY, s) and not NEGATIONS.search(s):
                violations.append(f"HIGH_INTENSITY_WHILE_{level.upper()}")
                break
        if _any(ALL_CLEAR, text):
            violations.append(f"ALL_CLEAR_WHILE_{level.upper()}")

    if _any(DIAGNOSIS, text):
        violations.append("MEDICAL_DIAGNOSIS")

    # Coerenza numerica: l'LLM non può inventare i valori calcolati.
    q = _num_after(r"\bACWR\b", text)
    if q is not None and report.get("acwr") is not None and abs(q - report["acwr"]) > 0.06:
        violations.append("NUMERIC_MISMATCH_ACWR")
    q = _num_after(r"\bRMSSD\b", text)
    if q is not None and report.get("rmssd_ms") is not None and abs(q - report["rmssd_ms"]) > 2.0:
        violations.append("NUMERIC_MISMATCH_RMSSD")

    if violations:
        return SelfCheckResult(False, deterministic_recommendation(report), sorted(set(violations)), True)
    return SelfCheckResult(True, text, [], False)
