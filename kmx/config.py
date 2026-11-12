"""Konfiguration über Umgebungsvariablen: typisierte Zugriffe, ihre Standardwerte und
EINE Tabelle aller Variablen (`ENV_VARS`; daraus entsteht auch der Abschnitt in --help).

Die Zugriffe lesen `os.environ` bei jedem Aufruf, Änderungen wirken also sofort. Einzige
Ausnahme ist COST_ROT_WEIGHT: `kmx.cost` liest die Variable einmal beim Import in
`ROT_WEIGHT`; `Options.rot_weight` und der Standard von --rot-weight übernehmen diesen
Wert ebenfalls beim Import. Wer ihn danach ändern will (etwa in Tests), patcht das
Heimatmodul (`kmx.cost.ROT_WEIGHT`) bzw. setzt `Options.rot_weight`.

Vorrang überall: Kommandozeile vor Umgebungsvariable vor Standardwert.
"""

from __future__ import annotations

import os
from typing import NamedTuple

# Wert, mit dem eine Ja/Nein-Variable eingeschaltet wird (alles andere heißt "aus")
FLAG_ON = "1"

# Lokale Weinstadt-KI: keyless, OpenAI-kompatibel. Das ist die einzige
# einsatzspezifische Adresse; sie gilt nur, wenn weder --api-url noch LLM_API_URL
# gesetzt ist.
LOCAL_LLM_URL = "http://192.168.212.81:8000/v1/chat/completions"
LOCAL_LLM_MODEL = "qwen3.8-27b"
# Qwen3.x denkt sonst privat und liefert leeres content; fremden Endpunkten wird nichts
# untergeschoben.
LOCAL_LLM_EXTRA_BODY = '{"chat_template_kwargs":{"enable_thinking":false}}'
LOCAL_LLM_TIMEOUT_S = 60
LOCAL_LLM_TEMPERATURE = 0.1
REMOTE_LLM_TIMEOUT_S = 300
LLM_DEFAULT_MAX_TOKENS = 8192
LLM_DEFAULT_MAX_CALLS = 40

# Toffoli-Äquivalente je FEINER Z_POW-Rotation für die Schnellschätzung. Offiziell
# (0.56*log2(1/eps)+5.3)/4; für invsqrt rechnet `invsqrt_score` den Wert exakt aus,
# dieser Schätzwert gilt nur als Rückfallebene.
DEFAULT_ROT_WEIGHT = 7.2
OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S = 3600


def env_text(name: str, default: str | None = None) -> str | None:
    """Rohwert der Variablen (`default`, wenn sie nicht gesetzt ist; ein leerer String
    zählt als gesetzt)."""
    return os.environ.get(name, default)


def env_flag(name: str) -> bool:
    """Ja/Nein-Variable: eingeschaltet genau bei FLAG_ON."""
    return os.environ.get(name) == FLAG_ON


def env_float(name: str, default: float) -> float:
    """Gleitkommawert; ungesetzt gilt `default`, Unlesbares wirft ValueError."""
    raw = os.environ.get(name)
    return default if raw is None else float(raw)


def env_int(name: str, default: int) -> int:
    """Ganzzahl; ungesetzt gilt `default`, ein unlesbarer Wert wirft ValueError."""
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


class EnvVar(NamedTuple):
    """Eine ausgewertete Umgebungsvariable und ihre Bedeutung (für --help)."""

    name: str
    meaning: str


ENV_VARS: tuple[EnvVar, ...] = (
    EnvVar("LLM_API_URL", "OpenAI-kompatibler Endpunkt (wie --api-url)"),
    EnvVar(
        "LLM_MODEL",
        f"kommagetrennte Modell-IDs (wie --models; lokal: {LOCAL_LLM_MODEL})",
    ),
    EnvVar("LLM_API_KEY", "API-Schlüssel (Vorrang vor den beiden folgenden)"),
    EnvVar("OPENROUTER_API_KEY", "API-Schlüssel, falls LLM_API_KEY fehlt"),
    EnvVar("OPENAI_API_KEY", "API-Schlüssel, falls beide vorigen fehlen"),
    EnvVar(
        "LLM_MAX_TOKENS",
        f"Antwortlimit je LLM-Aufruf (wie --max-tokens; {LLM_DEFAULT_MAX_TOKENS})",
    ),
    EnvVar(
        "LLM_MAX_CALLS",
        "Aufrufbudget der LLM-Stufe; 0 = LLM aus (ohne Angabe: Schritte x Modelle x "
        "Runden)",
    ),
    EnvVar(
        "LLM_TIMEOUT",
        f"Timeout je LLM-Aufruf in s (wie --llm-timeout; lokal {LOCAL_LLM_TIMEOUT_S}, "
        f"sonst {REMOTE_LLM_TIMEOUT_S})",
    ),
    EnvVar("LLM_EXTRA_BODY", "JSON-Objekt, das in jede Anfrage übernommen wird"),
    EnvVar("LLM_EXTRA_HEADERS", "JSON-Objekt mit zusätzlichen HTTP-Headern"),
    EnvVar(
        "LLM_TEMPERATURE",
        f"Sampling-Temperatur (wie --temperature; lokal {LOCAL_LLM_TEMPERATURE})",
    ),
    EnvVar(
        "LLM_MODE",
        "auto | tools | json (auto: Tool-Calling, für Modelle ohne Tool-Calling der "
        "JSON-Modus)",
    ),
    EnvVar("OFFICIAL_VERIFY_CMD", "offizieller Verifier als Gate (wie --verify-cmd)"),
    EnvVar(
        "REQUIRE_OFFICIAL_VERIFY",
        "1 = ohne OFFICIAL_VERIFY_CMD nichts schreiben (Exit 3)",
    ),
    EnvVar(
        "OFFICIAL_VERIFY_TIMEOUT",
        f"Timeout des offiziellen Verifiers in s ({OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S})",
    ),
    EnvVar(
        "COST_ROT_WEIGHT",
        "Toffoli-Äquivalente je feiner Rotation in der Schnellschätzung "
        f"({DEFAULT_ROT_WEIGHT})",
    ),
    EnvVar("ALLOW_PROBABILISTIC_REWRITES", "1 = wie --allow-sampled-facts"),
    EnvVar("TRIM_ROTATIONS", "1 = wie --trim-rotations"),
    EnvVar("EXACT_ONLY", "1 = wie --exact-only"),
    EnvVar(
        "OPT_MODE",
        "entfallen wie BEAM_* (die Pässe laufen bis zum Fixpunkt); nur ein Hinweis",
    ),
    EnvVar(
        "LEGACY_UNSAFE_PASSES",
        "entfallen (das Repacking ist simulationsgestützt und End-to-End geprüft); "
        "nur ein Hinweis",
    ),
)
