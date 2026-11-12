"""Einmalige Prüfung: die Prompt-Dateien in kmx/prompts/ sind byte-gleich mit den
Konstanten der Einzeldatei-Fassung.  Aufruf: python prompt_identity.py <alte main.py>"""
import importlib.util, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from kmx.prompts import load_prompt  # noqa: E402
spec = importlib.util.spec_from_file_location("old_main", sys.argv[1])
old = importlib.util.module_from_spec(spec); sys.modules["old_main"] = old; spec.loader.exec_module(old)
pairs = {
    "agent_system.txt": old.AGENT_SYSTEM, "json_window.txt": old.JSON_PROMPT,
    "research_system.txt": old.RESEARCH_SYSTEM_PROMPT,
    "research_brief_intro.md": "\n".join(old.BRIEF_TITLE_LINES),
    "research_brief_profile_header.md": "\n".join(old.BRIEF_PROFILE_HEADER_LINES),
    "research_brief_closing.md": "\n".join(old.BRIEF_CLOSING_LINES),
}
bad = [n for n, v in pairs.items() if load_prompt(n).encode() != v.encode()]
print("PROMPTS IDENTICAL" if not bad else f"PROMPT MISMATCH {bad}")
sys.exit(1 if bad else 0)
