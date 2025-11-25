import os
import re
import imghdr
from io import BytesIO
from pathlib import Path

import requests
from lxml import html
from PIL import Image, UnidentifiedImageError

# Raiz do repo
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

# Lista de publicações (<li>) da newsletter
XPATH_LIST_ITEMS = '//*[@id="main-content"]/section[1]/div/section[3]/ul/li'


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
            preferred = [h for h in hrefs if "newsletters" in h or "feed/update" in h]
            link = preferred[0] if preferred else hrefs[0]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.linkedin.com" + link

        # ---------- IMAGEM (CAPA) ----------
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


def _detect_format_from_bytes(bts: bytes):
    """
    Detecta formato a partir dos bytes.
    Usa imghdr e, se não der, tenta via PIL.
    """
    detected = imghdr.what(None, h=bts)
    if detected:
        return detected.lower()

    try:
        img = Image.open(BytesIO(bts))
        fmt = (img.format or "").lower()
        img.close()
        return fmt or None
    except UnidentifiedImageError:
        return None
    except Exception:
        return None


def download_image(url: str, path: Path, prefer_convert_to_jpeg: bool = True) -> bool:
    """
    Baixa a imagem de 'url', detecta o formato real e salva em disco.

    - Se possível, converte para JPEG e salva com o mesmo 'stem' passado em `path`.
    - Se não conseguir converter, salva no formato original (webp, png, etc.)
      com a extensão correspondente.
    - Se o conteúdo não for imagem (HTML de login, erro etc.), não sobrescreve nada.
    """
    if not url:
        print(f"[WARN] URL vazia para salvar em {path}")
        return False

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Erro ao baixar imagem {url}: {e}")
        return False

    content_type = resp.headers.get("Content-Type", "")
    content_bytes = resp.content

    print(
        f"[INFO] {url} -> status {resp.status_code}; "
        f"Content-Type: {content_type}; bytes: {len(content_bytes)}"
    )
    print(f"[INFO] magic bytes: {content_bytes[:16].hex()}")

    fmt = _detect_format_from_bytes(content_bytes)
    print(f"[INFO] Formato detectado: {fmt}")

    if not fmt:
        # Não parece imagem; provavelmente HTML de login
        print(
            f"[WARN] Conteúdo não parece imagem (pode ser HTML de login). "
            f"Salvando .bin para debug e NÃO sobrescrevendo imagem atual."
        )
        debug_path = path.with_suffix(".bin")
        debug_path.write_bytes(content_bytes)
        return False

    fmt_to_ext = {
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "png": ".png",
        "webp": ".webp",
        "gif": ".gif",
        "bmp": ".bmp",
        "tiff": ".tif",
    }
    ext = fmt_to_ext.get(fmt, f".{fmt}")

    # Tenta converter para JPEG (ideal para README)
    if prefer_convert_to_jpeg and fmt not in ("jpeg", "jpg"):
        try:
            img = Image.open(BytesIO(content_bytes))

            # tratar transparência
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                background.alpha_composite(img.convert("RGBA"))
                img = background.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            jpeg_path = path.with_suffix(".jpg")
            jpeg_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(jpeg_path, format="JPEG", quality=90)
            img.close()

            print(f"[INFO] Imagem convertida para JPEG: {jpeg_path}")
            return True
        except UnidentifiedImageError as e:
            print(f"[WARN] PIL não conseguiu abrir para converter: {e}.")
        except Exception as e:
            print(f"[WARN] Falha ao converter para JPEG: {e}.")

    # Fallback: salva no formato original (webp, png, etc.)
    dest = path.with_suffix(ext)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content_bytes)
        print(f"[INFO] Imagem salva no formato original: {dest}")
        return True
    except Exception as e:
        print(f"[WARN] Falha ao salvar imagem {dest}: {e}")
        return False


def _resolve_image_src(img_post: str) -> str:
    """
    Dado o "stem" da imagem (ex.: 'img_ult_post'),
    tenta descobrir qual extensão existe em assets/ e retorna o caminho relativo
    para usar no README (assets/img_ult_post.xxx).
    """
    stem_path = ASSETS_DIR / img_post
    possible_exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif"]

    for ext in possible_exts:
        candidate = stem_path.with_suffix(ext)
        if candidate.exists():
            # caminho relativo a partir da raiz do repo
            return f"assets/{candidate.name}"

    # fallback: assume .jpg (caso nada exista)
    return f"assets/{img_post}.jpg"


def update_readme_ult_post(post_title, post_url, tag="ULT", img_post="img_ult_post"):
    start = f"<!-- NEWSLETTER_{tag}:START -->"
    end = f"<!-- NEWSLETTER_{tag}:END -->"

    md = README.read_text(encoding="utf-8")
    if start not in md or end not in md:
        raise RuntimeError(
            f"Âncoras <!-- NEWSLETTER_{tag}:START/END --> não encontradas no README.md"
        )

    img_src = _resolve_image_src(img_post)

    new_block = (
        f"{start}\n"
        f'<span style="font-size: 1.13em; color: inherit;">{post_title}</span><br>\n'
        f"<a \n"
        f'   href="{post_url}"\n'
        f'   title="{post_title}"\n'
        f"> \n"
        f"<img \n"
        f'   src="{img_src}" \n'
        f'   alt="{post_title}" \n'
        f'   width="55%" \n'
        f"/>\n"
        f"</a>\n"
        f"<br/>\n"
        f"\n{end}"
    )

    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    md2 = pattern.sub(new_block, md)

    if md2 != md:
        README.write_text(md2, encoding="utf-8")
        print(f"[INFO] README.md atualizado para bloco {tag}")
        return True

    print(f"[INFO] Nenhuma mudança no bloco {tag} do README.md")
    return False


def main():
    posts = fetch_latest_newsletter_posts(NEWSLETTER_URL, limit=2)

    if not posts:
        print("[WARN] Nenhum post retornado da newsletter.")
        return

    # baixa imagens e salva em /assets
    for idx, post in enumerate(posts):
        if idx >= len(FILE_NAMES):
            break

        image_url = post.get("image_url")
        if not image_url:
            print(f"[WARN] Post {idx} sem URL de imagem, pulando download.")
            continue

        # usamos o stem do nome para permitir trocar extensão
        # ex.: img_ult_post.jpg -> stem = img_ult_post
        stem_name = Path(FILE_NAMES[idx]).stem
        file_path = ASSETS_DIR / stem_name

        ok = download_image(image_url, file_path)
        if not ok:
            print(f"[WARN] Falha ao salvar imagem para {stem_name}")

    # retorno em lista: [ [titulo, link], [titulo, link] ]
    return_post = [[p["title"], p["link"]] for p in posts]

    update_readme_ult_post(
        post_title=return_post[0][0],
        post_url=return_post[0][1],
        tag="ULT",
        img_post="img_ult_post",
    )

    update_readme_ult_post(
        post_title=return_post[1][0],
        post_url=return_post[1][1],
        tag="PENULT",
        img_post="img_penult_post",
    )


if __name__ == "__main__":
    main()
