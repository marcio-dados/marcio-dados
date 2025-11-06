# `scripts/fetch_tirinha.py` — Documentação Técnica

> Pipeline enxuto para **raspar a última tirinha** do site [tirinhas.com.br](https://www.tirinhas.com.br/), **baixar a imagem** e **atualizar o `README.md`** com um bloco HTML entre âncoras controladas.

## Sumário
- [Objetivo](#objetivo)
- [Arquitetura e Fluxo](#arquitetura-e-fluxo)
- [Requisitos](#requisitos)
- [Estrutura de diretórios](#estrutura-de-diretórios)
- [Como executar](#como-executar)
- [Parâmetros de linha de comando](#parâmetros-de-linha-de-comando)
- [Detalhes de implementação](#detalhes-de-implementação)
  - [Descoberta do último post (`find_latest_post_url`)](#descoberta-do-último-post-find_latest_post_url)
  - [Extração da primeira imagem (`extract_first_image`)](#extração-da-primeira-imagem-extract_first_image)
  - [Download e otimização da imagem (`download_image`)](#download-e-otimização-da-imagem-download_image)
  - [Atualização do README (`update_readme`)](#atualização-do-readme-update_readme)
  - [Parser de argumentos (`parse_args`)](#parser-de-argumentos-parse_args)
  - [Função principal (`main`)](#função-principal-main)
- [Pontos de extensão e customização](#pontos-de-extensão-e-customização)
- [Tratamento de erros e resiliência](#tratamento-de-erros-e-resiliência)
- [Boas práticas de segurança](#boas-práticas-de-segurança)
- [Automação (CI/CD)](#automação-cicd)
- [FAQ](#faq)
- [Licença](#licença)

---

## Objetivo
**Automatizar** a atualização de uma seção do `README.md` com a tirinha mais recente do site, armazenando a imagem em `assets/tirinha.jpg`. O script é idempotente e substitui apenas o bloco entre as âncoras `<!-- TIRINHA:START -->` e `<!-- TIRINHA:END -->`.

## Arquitetura e Fluxo
1. **Descoberta**: acessa a _home_ e encontra o link do post mais recente.  
2. **Parsing**: abre o post e identifica a primeira imagem “válida”.  
3. **Download**: baixa a imagem, converte para **JPEG** e otimiza.  
4. **Atualização**: reescreve o bloco do `README.md` com link do post e `<img>` com `width="50%"`.

Fluxo resumido:
```
Home -> URL do post -> URL da imagem -> Baixa/otimiza -> Atualiza README
```

## Requisitos
- Python 3.9+
- Bibliotecas:
  ```bash
  pip install requests beautifulsoup4 lxml pillow
  ```

## Estrutura de diretórios
```
<repo-root>/
└── marcio-dados/
    ├── README.md                # Deve conter as âncoras de bloco
    ├── assets/
    │   └── tirinha.jpg          # Gerado/atualizado pelo script
    └── scripts/
        └── fetch_tirinha.py
```

> O script resolve `ROOT` como `Path(__file__).resolve().parents[1] / "marcio-dados"`.

## Como executar
No diretório do repositório (ou em qualquer lugar, desde que o caminho resolva corretamente):

```bash
python marcio-dados/scripts/fetch_tirinha.py
```

- Em modo “_dry-run_” (não altera disco):
  ```bash
  python marcio-dados/scripts/fetch_tirinha.py --dry-run
  ```

Saída típica:
```
Post: https://www.tirinhas.com.br/postagem.php?id=XXXXXXXX
Imagem: https://www.tirinhas.com.br/media/...
```

## Parâmetros de linha de comando
| Flag        | Descrição                          | Default |
|-------------|------------------------------------|---------|
| `--dry-run` | Executa sem gravar imagem/README.  | `False` |

---

## Detalhes de implementação

### Descoberta do último post (`find_latest_post_url`)
- Faz `GET` na _home_ `https://www.tirinhas.com.br/` com `HEADERS` (User-Agent customizado).  
- Usa `BeautifulSoup` + seletor `h2 a, h3 a, a[href]` para priorizar links de post.  
- Heurística: URLs contendo `postagem.php?id=` ou termos `postagem` / `post`.  
- _Fallback_: qualquer `a[href*="id="]`.  
- Retorna o **primeiro candidato** (tipicamente o mais recente).  
- Erros de rede geram `raise_for_status()`; se nada for encontrado, `RuntimeError`.

### Extração da primeira imagem (`extract_first_image`)
- Acessa a URL do post e seleciona todos os `<img>`.  
- Filtra extensões **`.jpg`, `.jpeg`, `.png`** e descarta ruídos (`icon`, `logo`, `sprite`, `icone`, `emoji`).  
- Resolve `src` relativo com `urljoin(post_url, src)`.  
- _Fallback_: usa `meta[property="og:image"]` se não houver `<img>` elegível.  
- Se nada for encontrado, `RuntimeError`.

### Download e otimização da imagem (`download_image`)
- Baixa a imagem com `requests` (timeout 60s).  
- Converte para **RGB** e salva em **JPEG** com `quality=90` e `optimize=True`.  
- Diretório alvo: `ASSETS_DIR / "tirinha.jpg"`.

> **Nota**: JPEG é uma escolha pragmática para reduzir bytes. Se precisar de transparência, adapte para PNG e ajuste a otimização.

### Atualização do README (`update_readme`)
- Lê `README.md` e localiza âncoras:
  ```text
  <!-- TIRINHA:START -->
  ... bloco será substituído ...
  <!-- TIRINHA:END -->
  ```
- Substitui por bloco HTML contendo o link e a imagem **com `width="50%"`**:
  ```html
  <a href="{post_url}">
    <img src="{image_rel_path}" alt="Tirinha do dia" width="50%" />
  </a>
  <br/>
  <sub>Fonte: <a href="https://www.tirinhas.com.br/">tirinhas.com.br</a></sub>
  ```
- Usa `re.sub` com `re.DOTALL` para trocar apenas o trecho entre as âncoras.  
- Se o conteúdo mudou, grava o arquivo e retorna `True`; caso contrário, `False`.

### Parser de argumentos (`parse_args`)
- Implementado via `argparse`.  
- Suporta `--dry-run` para não persistir imagem e não alterar o README.

### Função principal (`main`)
- Orquestra a execução:
  1. `parse_args()`  
  2. `find_latest_post_url()`  
  3. `extract_first_image(post_url)`  
  4. `print` das URLs para observabilidade  
  5. Execução condicional:
     - **`--dry-run`**: encerra sem tocar disco.  
     - **normal**: baixa a imagem em `assets/tirinha.jpg` e atualiza o README.  
- Retorna `0` (código de sucesso).

---

## Pontos de extensão e customização
- **Reduzir imagem fisicamente** (economia de banda):
  ```python
  def download_image(url, target_path, scale=1.0):
      ...
      if scale != 1.0:
          w, h = img.size
          img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
      img.save(target_path, format="JPEG", quality=90, optimize=True)
  ```
  Uso:
  ```python
  download_image(img_url, target, scale=0.5)  # 50%
  ```

- **Controlar largura renderizada** no README: ajuste `width="50%"` para pixel fixo (`width="400"`) conforme a plataforma de renderização.

- **Filtragem de imagens**: incremente a lista de palavras-banidas ou extensões aceitas conforme evolução do site.

- **Timeouts/headers**: ajuste `HEADERS` e `timeout` para ambientes com proxy/restrições.

---

## Tratamento de erros e resiliência
- `requests.*.raise_for_status()` garante falha explícita em HTTP 4xx/5xx.  
- `RuntimeError` específico quando:
  - Não encontra link de post na home;  
  - Não encontra imagem no post.  
- Recomendação: encapsular `main()` em esteira de CI com **retry** e **observabilidade** (logs).

---

## Boas práticas de segurança
- **User-Agent** customizado para cortesia com o site alvo.  
- Evite disparos concorrentes excessivos (respeite limites).  
- Não armazene segredos; não há credenciais envolvidas.  
- Mantenha dependências atualizadas (corrige CVEs).

---

## Automação (CI/CD)
Exemplo de **GitHub Actions** (workflow `tirinha.yml`) executando diariamente às 7h (America/Sao_Paulo) e abrindo PR com a atualização:

```yaml
name: Atualizar Tirinha

on:
  # Agenda diária às 07:00 (America/Sao_Paulo = 10:00 UTC)
  schedule:
    - cron: "0 10 * * *"
  # Execução manual on-demand
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: tirinha-${{ github.ref }}
  cancel-in-progress: true

jobs:
  update:
    name: Run fetch_tirinha.py e abrir PR
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Instalar dependências
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4 lxml pillow

      - name: Executar script
        run: |
          python marcio-dados/scripts/fetch_tirinha.py

      - name: Verificar mudanças e abrir branch
        id: commit
        run: |
          if [[ -n "$(git status --porcelain)" ]]; then
            git config user.name  "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git checkout -B main
            git add marcio-dados/README.md marcio-dados/assets/tirinha.jpg || true
            git commit -m "chore: atualiza tirinha do dia"
            git push --force --set-upstream origin main
            echo "pushed=true" >> "$GITHUB_OUTPUT"
          else
            echo "Sem mudanças para commitar."
            echo "pushed=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Abrir Pull Request
        if: steps.commit.outputs.pushed == 'true'
        uses: peter-evans/create-pull-request@v6
        with:
          branch: main
          title: "Atualiza tirinha do dia"
          body: |
            Atualização automática do bloco de tirinha no README.
            - Atualiza `marcio-dados/assets/tirinha.jpg`
            - Reescreve o trecho entre `<!-- TIRINHA:START -->` e `<!-- TIRINHA:END -->`
          base: ${{ github.ref_name }}
```

> Ajuste a timezone do cron se preferir; o exemplo roda 10:00 UTC (07:00 em São Paulo, UTC-3).

---

## FAQ
**1) O bloco não atualiza.**  
Confirme que o `README.md` contém **exatamente** as âncoras:  
`<!-- TIRINHA:START -->` e `<!-- TIRINHA:END -->` em linhas separadas.

**2) A imagem ficou muito grande/pequena.**  
Troque `width="50%"` por `width="400"` (pixels) ou ajuste a escala no `download_image`.

**3) Falha ao baixar imagem ou encontrar post.**  
O site pode ter mudado o HTML. Ajuste os seletores/heurísticas nos métodos `find_latest_post_url` e `extract_first_image`.

**4) Posso usar PNG?**  
Sim. Troque a conversão/salvamento e, se necessário, remova `convert("RGB")` para preservar transparência.

---

