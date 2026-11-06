#!/usr/bin/env python3
"""Fetch a Kaggle competition discussion topic + comments as plain text.

Usage: python research/fetch_topic.py <topic_id> [<topic_id> ...]
"""
import re
import subprocess
import sys
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "br"):
            self.parts.append("\n")
        if tag == "td":
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    comp = "google-verifiable-quantum-circuit-compilation"
    for tid in sys.argv[1:]:
        out = subprocess.run(
            [".venv/bin/kaggle", "competitions", "topics", "show", comp, tid, "--format", "json"],
            capture_output=True, text=True, cwd="/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum",
        )
        import json
        d = json.loads(out.stdout)
        t = d["topic"]
        print(f"===== TOPIC {t['id']}: {t['title']} (by {t['authorName']}, {t['postDate'][:10]}, {t.get('votes', '?')} votes) =====")
        body = t.get("content") or t.get("body") or ""
        if body:
            print(html_to_text(body))
        for c in d.get("comments", []):
            print(f"--- {c['authorName']} ({c['postDate'][:10]}, {c.get('votes', 0)} votes)")
            print(html_to_text(c.get("content", "")))
        print()


if __name__ == "__main__":
    main()
