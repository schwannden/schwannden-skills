#!/usr/bin/env python3
"""Parse raw HTML from stdin roughly the way a non-JS AI crawler "sees" it.

Helper for geo-audit.sh (kept separate so the shell script stays bash-3.2 safe).
Stdlib only. Emits KEY=VALUE lines:
    WORDS=<visible text word count, scripts/styles excluded>
    SPAEMPTY=<1 if an empty SPA mount node is present, else 0>
    LDCOUNT=<number of JSON-LD <script> blocks>
    LDTYPES=<comma-separated unique @type values>
    LDBAD=<number of JSON-LD blocks that fail to parse as JSON>
"""
import sys
import re
import json
from html.parser import HTMLParser

html = sys.stdin.read()

SKIP_TAGS = ("script", "style", "noscript", "template")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


parser = TextExtractor()
try:
    parser.feed(html)
except Exception:
    pass

# "Content units" of visible text. Whitespace-splitting alone badly undercounts
# CJK (Chinese/Japanese/Korean), which doesn't put spaces between words — so a
# content-rich Chinese page would look "thin". Count space-delimited tokens that
# contain a latin/digit run, PLUS each CJK character (roughly one unit each).
text = " ".join(parser.buf)
latin = len(re.findall(r'[A-Za-z0-9][A-Za-z0-9\-\']*', text))
cjk = len(re.findall(
    r'[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]',
    text))
words = latin + cjk

spa = 1 if re.search(
    r'<div[^>]+id=["\'](root|app|__next|__nuxt)["\'][^>]*>\s*</div>',
    html, re.I) else 0

blocks = re.findall(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    html, re.I | re.S)

def collect_types(node, out):
    """Walk dicts/lists recursively, collecting every @type (incl. @graph)."""
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, list):
            out.extend(map(str, t))
        elif t is not None:
            out.append(str(t))
        for value in node.values():
            collect_types(value, out)
    elif isinstance(node, list):
        for item in node:
            collect_types(item, out)


types, bad = [], 0
for block in blocks:
    try:
        data = json.loads(block.strip())
    except Exception:
        bad += 1
        continue
    collect_types(data, types)

print("WORDS=%d" % words)
print("SPAEMPTY=%d" % spa)
print("LDCOUNT=%d" % len(blocks))
print("LDTYPES=%s" % ",".join(sorted(set(types))))
print("LDBAD=%d" % bad)
