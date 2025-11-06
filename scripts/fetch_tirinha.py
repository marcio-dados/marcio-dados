import os
import re
import sys
from pathlib import Path
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image
import argparse

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (+github-action; tirinha-readme)"
}

HOME = "https://www.tirinhas.com.br/"

def find_latest_post_url():
    r = requests.get(HOME, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    candidates = []
    # Prioriza h2/h3 > a (posts) mas aceita <a> em geral se tiver padrão
    for a in soup.select("h2 a, h3 a, a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        # Heurísticas comuns do site: postagem.php?id=...
        if "postagem.php?id=" in href or "postagem" in href or "post" in href:
            # Resolve para absoluta sempre
            abs_url = urljoin(HOME, href)
            candidates.append(abs_url)

    # Fallback: qualquer link com id=
    if not candidates:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "id=" in href:
                candidates.append(urljoin(HOME, href))

    if not candidates:
        raise RuntimeError("Não encontrei link de post na home.")

    # Primeiro geralmente é o mais recente na home
    return candidates[0]

def extract_first_image(post_url):
    r = requests.get(post_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    imgs = soup.select("img")
    good = []
    for img in imgs:
        src = (img.get("src") or "").strip()
        if not src:
            continue
        low = src.lower()
        if any(ext in low for ext in [".jpg", ".jpeg", ".png"]):
            if not any(bad in low for bad in ["icon", "logo", "sprite", "icone", "emoji"]):
                good.append(urljoin(post_url, src))  # resolve relativo à página do post

    if not good:
        # fallback: og:image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            good = [urljoin(post_url, og["content"].strip())]

    if not good:
        raise RuntimeError("Não encontrei imagem no post.")

    return good[0]

def download_image(url, target_path):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGB")
    img.save(target_path, format="JPEG", quality=90, optimize=True)
    return True

def update_readme(image_rel_path, post_url):
    start = "<!-- TIRINHA:START -->"
    end = "<!-- TIRINHA:END -->"
    md = README.read_text(encoding="utf-8")
    if start not in md or end not in md:
        raise RuntimeError("Âncoras <!-- TIRINHA:START/END --> não encontradas no README.md")

    new_block = (
        f'{start}\n'
        f'<a href="{post_url}">\n'
        f'  <img src="{image_rel_path}" alt="Tirinha do dia" width="50%" />\n'
        f'</a>\n'
        f'<br/>\n'
        f'<sub>Fonte: <a href="https://www.tirinhas.com.br/">tirinhas.com.br</a></sub>\n'
        f'\n{end}'
    )
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    md2 = pattern.sub(new_block, md)

    if md2 != md:
        README.write_text(md2, encoding="utf-8")
        return True
    return False

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="não grava nada em disco")
    return p.parse_args()

def main():
    args = parse_args()
    post_url = find_latest_post_url()
    img_url = extract_first_image(post_url)
    print("Post:", post_url)
    print("Imagem:", img_url)

    if args.dry_run:
        return 0

    target = ASSETS_DIR / "tirinha.jpg"
    download_image(img_url, target)
    update_readme("assets/tirinha.jpg", post_url)
    return 0

if __name__ == "__main__":
    sys.exit(main())
