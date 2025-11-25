import os
import re
from pathlib import Path

import requests
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(exist_ok=True)
FILE_NAMES = ["img_ult_post.jpg", "img_penult_post.jpg"]

NEWSLETTER_URL = "https://www.linkedin.com/newsletters/fala-ulisses-7391469228467499008/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Lista de publicações (<li>)
XPATH_LIST_ITEMS = '//*[@id="main-content"]/section[1]/div/section[3]/ul/li'

# Onde salvar as capas
ASSETS_DIR = Path("assets")
FILE_NAMES = ["img_ult_post.jpg", "img_penult_post.jpg"]


def fetch_latest_newsletter_posts(url: str, limit: int = 2):
    """
    Busca as últimas 'limit' publicações da newsletter do LinkedIn.

    Retorna lista de dicts:
    [
      {
        "title": "...",
        "link": "...",
        "image_url": "..."
      },
      ...
    ]
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    tree = html.fromstring(resp.text)

    li_nodes = tree.xpath(XPATH_LIST_ITEMS)
    posts = []

    for li in li_nodes[:limit]:
        # Cada <li> tem um <div> interno
        card_nodes = li.xpath("./div")
        card = card_nodes[0] if card_nodes else li

        # ---------- TÍTULO ----------
        title = (
            "".join(card.xpath(".//h3//text()")).strip()
            or "".join(card.xpath(".//h2//text()")).strip()
        )
        if not title:
            continue

        # ---------- LINK ----------
        hrefs = card.xpath(".//a[@href]/@href")
        link = ""
        if hrefs:
            # tenta pegar algo mais "artigo" e menos "login"
            preferred = [
                h for h in hrefs if "newsletters" in h or "feed/update" in h]
            link = preferred[0] if preferred else hrefs[0]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.linkedin.com" + link

        # ---------- IMAGEM (CAPA) ----------
        # Padrão que você mapeou:
        # //*[@id="main-content"]/section[1]/div/section[3]/ul/li[n]/div/div[2]/img
        img_nodes = li.xpath("./div/div[2]/img")
        image_url = ""

        if img_nodes:
            img = img_nodes[0]
            image_url = img.get("src", "") or ""
            if not image_url:
                image_url = (
                    img.get("data-delayed-url", "")
                    or img.get("data-src", "")
                    or img.get("data-img-src", "")
                )

        posts.append(
            {
                "title": title,
                "link": link,
                "image_url": image_url,
            }
        )

    return posts


def download_image(url: str, path: Path) -> bool:
    """
    Faz o download da imagem para 'path'.
    Retorna True se deu certo, False se falhou.
    """
    if not url:
        return False

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Erro ao baixar imagem {url}: {e}")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return True


def update_readme_ult_post(post_title, post_url, tag="ULT", img_post="img_ult_post"):
    start = f"<!-- NEWSLETTER_{tag}:START -->"
    end = f"<!-- NEWSLETTER_{tag}:END -->"
    md = README.read_text(encoding="utf-8")
    if start not in md or end not in md:
        raise RuntimeError(
            f"Âncoras <!-- NEWSLETTER_{tag}:START/END --> não encontradas no README.md")

    new_block = (
        f'{start}\n'
        f'<span style="font-size: 1.13em; color: inherit;">{post_title}</span><br>\n'
        f'<a \n'
        f'   href="{post_url}"\n'
        f'   title="{post_title}"\n'
        f'> \n'
        f'<img \n'
        f'   src="assets/{img_post}.jpg" \n'
        f'   alt="{post_title}" \n'
        f'   width="55%" \n'
        f'/>\n'
        f'</a>\n'
        f'<br/>\n'
        f'\n{end}'
    )
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    md2 = pattern.sub(new_block, md)

    if md2 != md:
        README.write_text(md2, encoding="utf-8")
        return True
    return False


def main():
    posts = fetch_latest_newsletter_posts(NEWSLETTER_URL, limit=2)

    # baixa imagens e salva em /assets
    for idx, post in enumerate(posts):
        if idx >= len(FILE_NAMES):
            break

        image_url = post.get("image_url")
        if not image_url:
            print(f"[WARN] Post {idx} sem URL de imagem, pulando download.")
            continue

        file_path = ASSETS_DIR / FILE_NAMES[idx]
        ok = download_image(image_url, file_path)
        if ok:
            pass
            ### print(f"[INFO] Imagem salva em {file_path}")
        else:
            pass
           ### print(f"[WARN] Falha ao salvar imagem em {file_path}")

    # retorno em lista: [ [titulo, link], [titulo, link] ]
    return_post = [[p["title"], p["link"]] for p in posts]
    update_readme_ult_post(
        post_title=return_post[0][0],
        post_url=return_post[0][1]
    )
    update_readme_ult_post(
        post_title=return_post[1][0],
        post_url=return_post[1][1],
        tag="PENULT",
        img_post="img_penult_post"
    )


if __name__ == "__main__":
    main()
