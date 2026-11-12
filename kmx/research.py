"""Research-Brief für Deep-Research-Werkzeuge (Brücke zum Agenten über --playbook) und
die optionale Playbook-Anfrage an ein Modell. Die festen Textteile stehen in
kmx/prompts/research_*.
"""

from __future__ import annotations

from collections.abc import Sequence

from kmx.agent.client import LLMClient
from kmx.ops import register_token
from kmx.passes.repack import lifetimes_of, scratch_peak, trace_touches
from kmx.profile import PROFILE_ROWS_SHOWN, ProfileRow, profile_segments
from kmx.prompts import load_prompt
from kmx.session import Session

BRIEF_INTRO = load_prompt("research_brief_intro.md")
BRIEF_PROFILE_HEADER = load_prompt("research_brief_profile_header.md")
BRIEF_CLOSING = load_prompt("research_brief_closing.md")
RESEARCH_SYSTEM_PROMPT = load_prompt("research_system.txt")
RESEARCH_LLM_TIMEOUT = 900  # Sekunden; Deep-Research-Antworten dauern


def peak_scratch_usage(session: Session) -> int:
    """Größte Zahl gleichzeitig lebender Scratch-Qubits auf der Stichprobe (siehe
    scratch_peak)."""
    touches = trace_touches(session.ops, session.layout, session.sample_dom)
    lifetimes, _ = lifetimes_of(session.ops, touches)
    return scratch_peak(lifetimes)[0]


def brief_status_lines(session: Session, peak_scratch: int) -> list[str]:
    """Register/Domäne und der aktuelle Stand (Schätzung, exakter Score falls
    verfügbar, Scratch-Spitze)."""
    layout = session.layout
    register_sizes = {
        layout.names.get(r, register_token(r)): len(qubits)
        for r, qubits in layout.registers.items()
    }
    exact = session.exact_score(session.ops)
    return [
        f"Register: {register_sizes}; Domäne: {session.dom.label}.",
        "",
        "## Aktueller Stand",
        session.current_status_line,
        *(
            [f"Exakt wie der offizielle Verifier: {exact.line()}"]
            if exact is not None
            else []
        ),
        f"Scratch-Spitze (gleichzeitig belegte Hilfsqubits): {peak_scratch}; "
        f"Register-Qubits: {len(layout.pinned)}.",
    ]


def brief_profile_rows(profile: Sequence[ProfileRow]) -> list[str]:
    """Markdown-Tabellenzeilen des Toffoli-Profils (teuerste Abschnitte zuerst)."""
    return [
        f"| {r['segment']} | {r['toffoli']} | {r['instruktionen']} | "
        f"{r['von']}..{r['bis']} |"
        for r in profile
    ]


def research_brief(session: Session) -> str:
    """Erzeugt den Markdown-Auftrag für ein Deep-Research-Werkzeug: Aufgabe,
    aktueller Stand, Kostenprofil, bereits Erledigtes, offene Fragen und das
    gewünschte Playbook-Format."""
    profile = profile_segments(session.ops, PROFILE_ROWS_SHOWN)
    peak_scratch = peak_scratch_usage(session)
    lines = [
        BRIEF_INTRO,
        *brief_status_lines(session, peak_scratch),
        BRIEF_PROFILE_HEADER,
        *brief_profile_rows(profile),
        BRIEF_CLOSING,
    ]
    return "\n".join(lines) + "\n"


def request_playbook(
    brief: str,
    model: str,
    api_url: str | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Schickt den Research-Brief an ein Modell und liefert dessen (ungeprüfte)
    Antwort als Playbook-Text. Ohne `timeout` gilt RESEARCH_LLM_TIMEOUT."""
    client = LLMClient(
        api_url, timeout=timeout or RESEARCH_LLM_TIMEOUT, max_tokens=max_tokens
    )
    msg = client.chat(
        model,
        [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ],
    )
    return msg.get("content") or ""
