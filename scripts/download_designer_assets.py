"""Download bundled fonts (woff2) and reveal.js for offline designer use.

Run once:  python scripts/download_designer_assets.py
Output:    static/fonts/*, static/reveal/*
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "static" / "fonts"
REVEAL_DIR = ROOT / "static" / "reveal"

# ── 25 fonts to bundle ────────────────────────────────────────────────────
# Format: (Google Fonts family name, [weights])
FONTS = [
    ("Inter", [300, 400, 600, 700]),
    ("Roboto", [300, 400, 500, 700]),
    ("Open Sans", [300, 400, 600, 700]),
    ("Lato", [300, 400, 700]),
    ("Montserrat", [300, 400, 600, 700]),
    ("Poppins", [300, 400, 600, 700]),
    ("Raleway", [300, 400, 600, 700]),
    ("Nunito", [300, 400, 600, 700]),
    ("Source Sans 3", [300, 400, 600, 700]),
    ("Work Sans", [300, 400, 600, 700]),
    ("DM Sans", [300, 400, 500, 700]),
    ("Plus Jakarta Sans", [300, 400, 600, 700]),
    ("Merriweather", [300, 400, 700]),
    ("Playfair Display", [400, 600, 700]),
    ("Lora", [400, 500, 600, 700]),
    ("PT Serif", [400, 700]),
    ("Libre Baskerville", [400, 700]),
    ("Orbitron", [400, 500, 700]),
    ("Bebas Neue", [400]),
    ("Oswald", [300, 400, 500, 700]),
    ("Anton", [400]),
    ("Space Grotesk", [300, 400, 500, 700]),
    ("Fira Code", [300, 400, 500, 700]),
    ("JetBrains Mono", [300, 400, 500, 700]),
    ("IBM Plex Mono", [300, 400, 500, 700]),
]

# Modern Chrome UA to get woff2 responses
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Regex to extract latin @font-face blocks
LATIN_BLOCK_RE = re.compile(
    r"/\*\s*latin\s*\*/\s*@font-face\s*\{([^}]+)\}",
    re.DOTALL,
)
URL_RE = re.compile(r"url\((https://[^)]+\.woff2)\)")
WEIGHT_RE = re.compile(r"font-weight:\s*(\d+)")


def fetch_css(family: str, weights: list[int]) -> str:
    """Fetch Google Fonts CSS2 for a font family + weights."""
    weight_str = ";".join(str(w) for w in sorted(weights))
    url = (
        f"https://fonts.googleapis.com/css2?"
        f"family={family.replace(' ', '+')}:wght@{weight_str}&display=swap"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def download_file(url: str, dest: Path) -> int:
    """Download a URL to a file. Returns bytes written."""
    if dest.exists():
        return dest.stat().st_size
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def safe_dirname(family: str) -> str:
    """Convert font family name to a safe directory name."""
    return family.lower().replace(" ", "-")


def download_fonts():
    """Download all 25 fonts."""
    total_bytes = 0
    total_files = 0
    manifest = {}  # family -> {weight: filename}

    for family, weights in FONTS:
        dirname = safe_dirname(family)
        font_dir = FONTS_DIR / dirname
        font_dir.mkdir(parents=True, exist_ok=True)
        manifest[family] = {}

        print(f"\n── {family} ({len(weights)} weights) ──")

        try:
            css = fetch_css(family, weights)
        except Exception as e:
            print(f"  ✗ Failed to fetch CSS: {e}")
            continue

        # Find all latin @font-face blocks
        blocks = LATIN_BLOCK_RE.findall(css)
        if not blocks:
            print(f"  ✗ No latin blocks found")
            continue

        downloaded_urls = {}  # url -> filename (dedup variable fonts)

        for block in blocks:
            url_match = URL_RE.search(block)
            weight_match = WEIGHT_RE.search(block)
            if not url_match or not weight_match:
                continue

            woff2_url = url_match.group(1)
            weight = int(weight_match.group(1))

            if weight not in weights:
                continue

            # Dedup: variable fonts serve same URL for all weights
            if woff2_url in downloaded_urls:
                fname = downloaded_urls[woff2_url]
                # Still create a copy or symlink for the weight
                dest = font_dir / f"{dirname}-{weight}.woff2"
                if not dest.exists():
                    src = font_dir / fname
                    if src.exists():
                        dest.write_bytes(src.read_bytes())
                manifest[family][weight] = f"{dirname}-{weight}.woff2"
                print(f"  {weight}: (reused variable font file)")
                continue

            fname = f"{dirname}-{weight}.woff2"
            dest = font_dir / fname

            try:
                size = download_file(woff2_url, dest)
                total_bytes += size
                total_files += 1
                downloaded_urls[woff2_url] = fname
                manifest[family][weight] = fname
                print(f"  {weight}: {size:,} bytes → {fname}")
            except Exception as e:
                print(f"  {weight}: ✗ {e}")

    # Save manifest
    manifest_path = FONTS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n{'='*60}")
    print(f"Fonts: {total_files} files, {total_bytes:,} bytes ({total_bytes/1024:.0f} KB)")
    print(f"Manifest: {manifest_path}")
    return manifest


def download_revealjs():
    """Download reveal.js 5.1.0 JS + CSS."""
    REVEAL_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "reveal.js": "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js",
        "reveal.css": "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css",
    }

    total = 0
    for name, url in files.items():
        dest = REVEAL_DIR / name
        size = download_file(url, dest)
        total += size
        print(f"  {name}: {size:,} bytes")

    print(f"  Total: {total:,} bytes ({total/1024:.0f} KB)")


def main():
    print("Downloading Designer Assets")
    print("=" * 60)

    print("\n[1/2] Downloading 25 fonts (woff2, latin subset)...")
    download_fonts()

    print(f"\n[2/2] Downloading reveal.js 5.1.0...")
    download_revealjs()

    print("\n✓ All assets downloaded.")

    # Summary
    total_size = sum(
        f.stat().st_size
        for f in FONTS_DIR.rglob("*.woff2")
    )
    reveal_size = sum(
        f.stat().st_size
        for f in REVEAL_DIR.glob("*")
    )
    print(f"\nTotal bundled: {(total_size + reveal_size) / 1024:.0f} KB")
    print(f"  Fonts: {total_size / 1024:.0f} KB")
    print(f"  Reveal.js: {reveal_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
