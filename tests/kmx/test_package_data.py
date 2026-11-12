"""Paketdaten und Dokumentation: Prompt-Dateien, --help und die Tabelle der
Umgebungsvariablen."""

import hashlib
import re

import kmx.agent.json_mode
import kmx.agent.tools
import kmx.cli_help
import kmx.config
import kmx.research
from kmx.prompts import PROMPT_DIR, load_prompt
from tests.kmx.helpers import DATA_DIR, PROJECT_DIR, run_main

HELP_REFERENCE = DATA_DIR / "cli_help.txt"
HELP_COMMANDS = ("optimize", "agent", "research", "check", "info", "selftest")
# SHA-256 der Prompt-Texte, ermittelt aus der Einzeldatei-Fassung (v7/base/main.py)
# vor der Auslagerung; tools_verify/prompt_identity.py vergleicht direkt mit ihr.
PROMPT_DIGESTS = {
    "agent_system.txt": (
        "cd64b8c4b35d31a4a0874da64f3d3537526750761d938268eb0c093d2cbd7572"
    ),
    "json_window.txt": (
        "8226961fff43778f11573b785bc1c82b44b35a552c7d6213de5ae57c8e067012"
    ),
    "research_system.txt": (
        "27fc32281f29ca137010c6433020e016328f0e3758014861e430d5a2397d66f5"
    ),
    "research_brief_intro.md": (
        "7be8e82c7ba9541c9f7299bd59b80c07360c12b3f435473f407411352ea82860"
    ),
    "research_brief_profile_header.md": (
        "11b2f3cb51cf00101aad10f442af5a01dfd29b00c5b971824b010b2c05771502"
    ),
    "research_brief_closing.md": (
        "9685b366e273154b03a255bc15cc8e7802523284f7fb0fe670ea2b268c7d86a6"
    ),
}


def cli_help_text():
    """--help und `<Unterbefehl> --help` aller Unterbefehle, wie bei 80 Spalten."""
    parts = []
    for argv in (("--help",), *((c, "--help") for c in HELP_COMMANDS)):
        proc = run_main(*argv, COLUMNS="80")
        assert proc.returncode == 0, proc.stderr
        parts.append(proc.stdout)
    return "".join(parts)


def test_main_py_help_matches_reference():
    text = cli_help_text()
    assert text.startswith("usage: main.py [-h]"), text[:200]
    assert HELP_REFERENCE.read_text(encoding="utf-8") == text


def test_prompt_files_are_byte_identical_to_the_single_file_version():
    assert sorted(PROMPT_DIGESTS) == sorted(
        p.name for p in PROMPT_DIR.iterdir() if p.suffix in (".txt", ".md")
    )
    for name, digest in PROMPT_DIGESTS.items():
        assert hashlib.sha256(load_prompt(name).encode()).hexdigest() == digest, name


def test_prompt_constants_come_from_the_prompt_files():
    assert kmx.agent.tools.AGENT_SYSTEM == load_prompt("agent_system.txt")
    assert kmx.agent.json_mode.JSON_PROMPT == load_prompt("json_window.txt")
    assert kmx.research.RESEARCH_SYSTEM_PROMPT == load_prompt("research_system.txt")
    assert not kmx.agent.tools.AGENT_SYSTEM.endswith("\n")
    assert kmx.agent.json_mode.JSON_PROMPT.endswith("{block}")
    for p in PROMPT_DIR.iterdir():
        if p.suffix in (".txt", ".md"):
            raw = p.read_text(encoding="utf-8")
            assert raw.endswith("\n") and not raw.endswith("\n\n"), p.name


def test_help_lists_every_environment_variable_the_code_reads():
    read = set()
    for path in (PROJECT_DIR / "kmx").rglob("*.py"):
        read |= set(
            re.findall(r'env_(?:text|flag|int|float)\(\s*"([A-Z_]+)"', path.read_text())
        )
    table = {v.name for v in kmx.config.ENV_VARS}
    assert read <= table, read - table
    assert table <= read, table - read
    for name in table:
        assert f"  {name} " in kmx.cli_help.CLI_DESCRIPTION, name
    assert "v5" not in kmx.cli_help.CLI_DESCRIPTION
    assert "Eine Datei" not in kmx.cli_help.CLI_DESCRIPTION
