"""PDF de travail du groupe : l'oral, la grille de conformité et le dossier, lisibles et faciles à apprendre.

Source unique : les fichiers Markdown produits par scripts/p6_build.py depuis leurs gabarits
(docs/ORAL.md, docs/CONFORMITE.md, docs/DOSSIER_GROUPE.md). Ce module ne calcule rien et n'écrit
aucun chiffre : il met en page. Chaîne : Markdown → HTML (petit convertisseur maison, limité au
Markdown de nos documents, aucune dépendance nouvelle) → PDF par Chrome ou Edge en mode headless
(p6_build.build_pdf : fonds imprimés, aucun accès réseau), Segoe UI + Consolas, palette Plasma de la
maquette retenue (« nuit profonde »).

    docs/ORAL.md            →  docs/pdf/Oral_Pricing_Asiatique.pdf
    docs/CONFORMITE.md      →  docs/pdf/Conformite_Pricing_Asiatique.pdf
    docs/DOSSIER_GROUPE.md  →  docs/pdf/Dossier_Groupe_Pricing_Asiatique.pdf

Les PDF sont des documents de travail du groupe : ils ne vont pas dans le paquet de rendu.
Usage : python scripts/p6_build.py --pdf-groupe   (régénère d'abord les .md, puis les PDF)
"""
from __future__ import annotations

import html as _html
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p6_build as pb  # noqa: E402

PDF_DIR = ROOT / "docs" / "pdf"
ORAL_MD = ROOT / "docs" / "ORAL.md"
ORAL_PDF = PDF_DIR / "Oral_Pricing_Asiatique.pdf"
CONF_MD = ROOT / "docs" / "CONFORMITE.md"
CONF_PDF = PDF_DIR / "Conformite_Pricing_Asiatique.pdf"
DOSSIER_MD = ROOT / "docs" / "DOSSIER_GROUPE.md"
DOSSIER_PDF = PDF_DIR / "Dossier_Groupe_Pricing_Asiatique.pdf"


# --- Markdown → blocs ----------------------------------------------------------------------------

@dataclass
class Block:
    kind: str                                   # h, p, ul, ol, table, img, code, hr
    text: str = ""
    level: int = 0                              # titre : 1 à 6
    items: list = field(default_factory=list)   # listes : texte de chaque point
    rows: list = field(default_factory=list)    # tableau : [en-tête, lignes…]
    src: str = ""                               # image : chemin ; code : langage
    start: int = 1                              # liste numérotée : premier numéro


_ITEM = re.compile(r"^(-|\d+\.)\s+(.*)$")
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def _row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _starts_block(line: str) -> bool:
    """Une ligne qui interrompt un paragraphe (comme en CommonMark : titre, tableau, bloc de code,
    image seule, puce, ou liste numérotée qui commence à 1)."""
    s = line.strip()
    return (s.startswith(("#", "|", "```")) or bool(re.fullmatch(_IMG.pattern, s))
            or s.startswith("- ") or bool(re.match(r"1\.\s", s)))


def parse(md: str) -> list[Block]:
    """Découpe le Markdown de nos documents en blocs. Sous-ensemble géré : titres #, paragraphes,
    listes à puces ou numérotées (lignes de suite indentées), tableaux à barres, images seules sur
    leur ligne, blocs de code ```, séparateurs ---."""
    lines = md.replace("\r\n", "\n").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line, s = lines[i], lines[i].strip()
        if not s:
            i += 1
        elif s.startswith("```"):
            j, buf = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            blocks.append(Block("code", "\n".join(buf), src=s[3:].strip()))
            i = j + 1
        elif m := re.match(r"^(#{1,6})\s+(.*)$", s):
            blocks.append(Block("h", m.group(2).strip(), level=len(m.group(1))))
            i += 1
        elif re.fullmatch(r"-{3,}", s):
            blocks.append(Block("hr"))
            i += 1
        elif m := re.fullmatch(_IMG.pattern, s):
            blocks.append(Block("img", m.group(1), src=m.group(2)))
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\|\s*:?-", lines[i].strip()):
                    rows.append(_row(lines[i]))
                i += 1
            blocks.append(Block("table", rows=rows))
        elif (m := _ITEM.match(line)) and not line[0].isspace():
            ordered = m.group(1) != "-"
            block = Block("ol" if ordered else "ul", start=int(m.group(1)[:-1]) if ordered else 1)
            while i < len(lines):
                m = _ITEM.match(lines[i])
                if m and not lines[i][0].isspace() and (m.group(1) != "-") == ordered:
                    block.items.append(m.group(2).strip())
                elif lines[i].strip() and lines[i][0].isspace() and block.items:
                    block.items[-1] += " " + lines[i].strip()
                elif not lines[i].strip():
                    nxt = next((x for x in lines[i + 1:] if x.strip()), "")
                    m2 = _ITEM.match(nxt)
                    if not (m2 and not nxt[0].isspace() and (m2.group(1) != "-") == ordered):
                        break
                else:
                    break
                i += 1
            blocks.append(block)
        else:
            buf = [s]
            i += 1
            while i < len(lines) and lines[i].strip() and not _starts_block(lines[i]):
                buf.append(lines[i].strip())
                i += 1
            blocks.append(Block("p", " ".join(buf)))
    return blocks


# --- Markdown en ligne → HTML --------------------------------------------------------------------

def esc(text: str) -> str:
    return _html.escape(text, quote=False)


def slug(text: str) -> str:
    """Ancre à la manière de GitHub : « 2. Ce qu'on a fait » → « 2-ce-quon-a-fait »."""
    t = re.sub(r"[`*]", "", text).lower()
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


@dataclass
class Ctx:
    """Contexte de rendu : dossier du .md (chemins relatifs des images)."""
    base: Path

    def image_path(self, src: str) -> Path:
        return (self.base / src).resolve()

    def img(self, src: str, alt: str, style: str = "") -> str:
        path = self.image_path(src)
        if not path.is_file():
            raise FileNotFoundError(f"image absente : {src}")
        st = f' style="{style}"' if style else ""
        return f'<img src="{path.as_uri()}" alt="{_html.escape(alt)}"{st}>'

    def link(self, text_html: str, href: str) -> str:
        """Ancres internes et adresses web : liens cliquables. Fichiers du dépôt : le texte seul
        (un lien vers un fichier local ne mène nulle part chez un lecteur du PDF)."""
        if href.startswith("#") or href.startswith(("http://", "https://")):
            return f'<a href="{_html.escape(href)}">{text_html}</a>'
        return f'<span class="ref">{text_html}</span>'


def inline(text: str, ctx: Ctx) -> str:
    stash: list[str] = []

    def keep(html: str) -> str:
        stash.append(html)
        return f"\x00{len(stash) - 1}\x00"

    text = _IMG.sub(lambda m: keep(ctx.img(m.group(2), m.group(1))), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: keep(ctx.link(inline(m.group(1), ctx), m.group(2))), text)
    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{esc(m.group(1))}</code>"), text)
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text)
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


_NUMBER = re.compile(r"(?<![\w.])[−+]?\d[\d ]*(?:,\d+)?(?:\s?×\s?10[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)?"
                     r"(?: ?%)?")


def mark_numbers(html: str) -> str:
    """Entoure les nombres du texte (hors balises) d'un <span class="n"> : chiffres en Consolas."""
    parts = re.split(r"(<[^>]+>)", html)
    return "".join(p if p.startswith("<") else _NUMBER.sub(r'<span class="n">\g<0></span>', p)
                   for p in parts)


def render(blocks: list[Block], ctx: Ctx, ids: dict | None = None) -> str:
    """Rendu générique d'une suite de blocs."""
    out = []
    for b in blocks:
        if b.kind == "h":
            anchor = slug(b.text)
            if ids is not None:
                n = ids.get(anchor, 0)
                ids[anchor] = n + 1
                anchor = anchor if n == 0 else f"{anchor}-{n}"
            out.append(f'<h{b.level} id="{anchor}">{inline(b.text, ctx)}</h{b.level}>')
        elif b.kind == "p":
            out.append(f"<p>{inline(b.text, ctx)}</p>")
        elif b.kind in ("ul", "ol"):
            start = f' start="{b.start}"' if b.kind == "ol" and b.start != 1 else ""
            items = "".join(f"<li>{inline(t, ctx)}</li>" for t in b.items)
            out.append(f"<{b.kind}{start}>{items}</{b.kind}>")
        elif b.kind == "table":
            head, *rows = b.rows
            th = "".join(f"<th>{inline(c, ctx)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c, ctx)}</td>" for c in r) + "</tr>"
                          for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
        elif b.kind == "img":
            out.append(f'<figure>{ctx.img(b.src, b.text)}</figure>')
        elif b.kind == "code":
            out.append(f"<pre><code>{esc(b.text)}</code></pre>")
        elif b.kind == "hr":
            out.append('<div class="beam"></div>')
    return "\n".join(out)


def sections(blocks: list[Block], level: int = 2) -> tuple[list[Block], list[tuple[Block, list]]]:
    """(blocs avant le premier titre de ce niveau, [(titre, blocs de la section)])."""
    head: list[Block] = []
    out: list[tuple[Block, list]] = []
    for b in blocks:
        if b.kind == "h" and b.level == level:
            out.append((b, []))
        elif b.kind == "h" and b.level < level:
            if not out:
                head.append(b)                  # titre du document, avant les sections
        elif out:
            out[-1][1].append(b)
        else:
            head.append(b)
    return head, out


def image_aspect(path: Path) -> float:
    from PIL import Image
    with Image.open(path) as im:
        return im.size[0] / im.size[1]


# --- style commun (maquette « nuit profonde », palette Plasma) ------------------------------------

BASE_CSS = """
:root{--bg:#030306;--card:#0b0b13;--card2:#10101b;--a1:#00ffa3;--a2:#7c3aed;--a3:#ffd60a;
  --neg:#ff4d6d;--ink:#f4f5fb;--txt:#d4d6e2;--sub:#a3a6b8;--mut:#6b6f85;--hair:rgba(255,255,255,.09);
  --sans:"Segoe UI",system-ui,sans-serif;--mono:Consolas,"Courier New",monospace}
@page{size:A4;margin:12mm 0 13mm;background:#030306;
  @bottom-left{content:var(--x);font:8.5px Consolas,monospace;color:#6b6f85;padding-left:12mm}
  @bottom-right{content:counter(page) " / " counter(pages);font:8.5px Consolas,monospace;
    color:#6b6f85;padding-right:12mm}}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;color:var(--txt);font:11.5px/1.5 var(--sans);-webkit-print-color-adjust:exact;
  print-color-adjust:exact}
.wrap{padding:0 12mm}
h1,h2,h3,h4{color:var(--ink);letter-spacing:-.01em}
strong{color:var(--ink);font-weight:650}
em{color:var(--sub)}
code{font:.92em var(--mono);color:#c9b8ff;background:rgba(124,58,237,.14);padding:0 3px;
  border-radius:3px;overflow-wrap:anywhere}
pre{background:var(--card2);border:1px solid var(--hair);border-radius:8px;padding:9px 12px;
  white-space:pre-wrap;break-inside:avoid}
pre code{background:none;padding:0;color:#d4d6e2}
a{color:var(--a1);text-decoration:none}
.ref{color:var(--a1)}
.n{font-family:var(--mono);color:var(--ink);white-space:nowrap}
.beam{height:1px;margin:14px 0;background:linear-gradient(90deg,transparent,var(--a1),var(--a2),
  transparent);opacity:.55}
.eyebrow{font:400 9.5px var(--mono);letter-spacing:.22em;text-transform:uppercase;color:var(--sub);
  display:flex;justify-content:space-between;align-items:center}
.eyebrow b{color:var(--a1);font-weight:600}
table{width:100%;border-collapse:collapse}
th{font:600 9px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mut);
  text-align:left;padding:5px 7px;border-bottom:1px solid rgba(255,255,255,.18)}
td{padding:5px 7px;border-bottom:1px solid var(--hair);vertical-align:top}
tr{break-inside:avoid}
figure{margin:0}
figure img,img{display:block;max-width:100%;border-radius:6px}
.glow{position:absolute;border-radius:50%;pointer-events:none}
.cover{position:relative;height:271mm;overflow:hidden;break-after:page}
.cover .in{position:relative;z-index:2;padding:30mm 16mm 0}
.cover h1{font:800 40px/1.06 var(--sans);letter-spacing:-.03em;margin:14px 0 10px}
.cover .lead{color:var(--sub);font-size:14px;line-height:1.55;max-width:150mm}
"""

GLOWS = (
    '<div class="glow" style="width:760px;height:620px;left:-300px;top:-260px;background:'
    'radial-gradient(closest-side,rgba(124,58,237,.42),rgba(124,58,237,.14) 55%,rgba(124,58,237,0))">'
    '</div><div class="glow" style="width:700px;height:600px;right:-320px;top:420px;background:'
    'radial-gradient(closest-side,rgba(0,255,163,.20),rgba(0,255,163,.06) 55%,rgba(0,255,163,0))">'
    '</div><div class="glow" style="width:640px;height:460px;left:60px;bottom:-300px;background:'
    'radial-gradient(closest-side,rgba(255,214,10,.14),rgba(255,214,10,.04) 55%,rgba(255,214,10,0))">'
    "</div>")


def page(title: str, footer: str, css: str, body: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            f"<title>{esc(title)}</title>\n<style>{BASE_CSS}\n"
            f':root{{--x:"{footer}"}}\n{css}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n')


# --- l'oral : une fiche par partie ------------------------------------------------------------------

ORAL_CSS = """
.deroule td,.deroule th{font-size:13px;padding:8px 9px}
.deroule td:nth-child(2){font-family:var(--mono);color:var(--a1);white-space:nowrap}
.deroule td:last-child{color:var(--a3);font-family:var(--mono)}
.cover p{font-size:12.5px;color:var(--txt);max-width:172mm}
.fiche{break-before:page;padding:0 12mm}
.fiche h2{font:750 25px/1.12 var(--sans);margin:6px 0 4px}
.who{display:inline-block;font:600 11px var(--mono);color:var(--a3);border:1px solid
  rgba(255,214,10,.45);border-radius:20px;padding:2px 10px;margin-bottom:8px}
.visuals{display:flex;gap:5mm;align-items:stretch;margin:2mm 0}
.visuals .figs{display:flex;gap:5mm;flex:none}
.box{flex:1;min-width:0;border:1.5px solid var(--a1);border-radius:10px;padding:10px 14px;
  background:linear-gradient(160deg,rgba(0,255,163,.10),rgba(124,58,237,.08));display:flex;
  flex-direction:column;justify-content:center}
.box span.lab{font:600 9.5px var(--mono);letter-spacing:.18em;text-transform:uppercase;
  color:var(--a1);margin-bottom:6px}
.box p{margin:0;font-size:15px;line-height:1.45;color:var(--ink)}
.box .n{color:var(--a1);font-weight:600}
.box.band{margin:2mm 0}
.tables img{margin:2mm 0}
.montre{font-size:10.5px;color:var(--sub);margin:1.5mm 0 0}
.montre b{color:var(--a1);font:600 9px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.dire h3,.demande h3{font:600 9.5px var(--mono);letter-spacing:.18em;text-transform:uppercase;
  color:var(--a1);margin:4mm 0 1.5mm}
.dire ul{list-style:none;margin:0;padding:0}
.dire li{font-size:13pt;line-height:1.38;color:#dcdeea;padding:0 0 0 7mm;position:relative;
  margin:0 0 1.8mm}
.dire li::before{content:"";position:absolute;left:1.5mm;top:.55em;width:7px;height:7px;
  border-radius:50%;background:var(--a1);box-shadow:0 0 8px rgba(0,255,163,.7)}
.dire li strong{color:#fff;font-weight:700}
.demande{border-top:1px solid var(--hair);margin-top:3mm}
.demande ul{margin:0;padding:0;list-style:none}
.demande li{font-size:11.5px;margin:0 0 1.2mm;color:var(--txt)}
.demande li b{color:var(--a3);font-family:var(--mono);font-weight:600;margin-right:6px}
.qr-page{break-before:page;padding:0 12mm}
.qr-page h2{font:750 25px var(--sans);margin:6px 0 2px}
.qr-page>p{margin:0 0 5mm}
.qr{break-inside:avoid;border:1px solid var(--hair);border-left:3px solid var(--a2);
  border-radius:8px;background:var(--card);padding:12px 16px 9px;margin:0 0 6mm}
.qr h3{font:700 20px/1.3 var(--sans);margin:0 0 8px;color:#fff}
.qr h3 span{font-family:var(--mono);color:var(--a3);margin-right:9px}
.qr p,.qr li{font-size:16.5px;line-height:1.5;margin:0 0 5px;color:#dcdeea}
.qr ol{margin:2px 0 4px;padding-left:22px}
.chiffres{break-before:page;padding:0 12mm}
.chiffres h2{font:750 25px var(--sans);margin:6px 0 8px}
.chiffres td{font-size:12px;padding:8px 8px}
.chiffres td:first-child{font:600 16px var(--mono);color:var(--a1);white-space:nowrap}
.chiffres td:last-child{color:var(--sub);font-size:10.5px}
"""

PAGE_W = 186.0      # largeur utile en mm (A4, marges de 12 mm)
BOX_W = 54.0        # largeur minimale de l'encadré « chiffre à retenir » placé à côté
GAP = 5.0


def _marker(b: Block, label: str) -> str | None:
    """Texte d'un paragraphe qui commence par **label** (sans le label), sinon None."""
    m = re.match(rf"\*\*{re.escape(label)}\*\*\s*(.*)$", b.text) if b.kind == "p" else None
    return m.group(1) if m else None


@dataclass
class Fiche:
    title: str
    who: str = ""
    montre: str = ""
    images: list = field(default_factory=list)
    dire: list = field(default_factory=list)
    retenir: str = ""
    demande: list = field(default_factory=list)


def parse_fiche(title: Block, body: list[Block]) -> Fiche:
    f = Fiche(re.sub(r"\s*\((\d.*?)\)$|,\s*en \d+ minutes?$", "", title.text))
    expect_dire = False
    for b in body:
        if (t := _marker(b, "Qui parle.")) is not None:
            f.who = t
        elif (t := _marker(b, "Ce qu'on montre.")) is not None:
            f.montre = t
        elif (t := _marker(b, "Ce qu'on dit.")) is not None:
            expect_dire = True
        elif (t := _marker(b, "Le chiffre à retenir.")) is not None:
            f.retenir = t
        elif (t := _marker(b, "Si on vous demande…")) is not None:
            f.demande = [int(n) for n in re.findall(r"\b\d+\b", t)]
        elif b.kind == "img":
            f.images.append(b)
        elif b.kind == "ul" and expect_dire:
            f.dire = [re.sub(r"^«\s*|\s*»$", "", item) for item in b.items]
            expect_dire = False
        elif b.kind != "hr":
            raise ValueError(f"bloc inattendu dans « {title.text} » : {b.kind} {b.text[:50]}")
    return f


def parse_questions(body: list[Block]) -> tuple[list[Block], list[tuple[int, str, list]]]:
    intro, qs = sections(body, level=3)
    out = []
    for h, blocks in qs:
        m = re.match(r"(\d+)\.\s+(.*)$", h.text)
        out.append((int(m.group(1)), m.group(2), [b for b in blocks if b.kind != "hr"]))
    return intro, out


QR_PER_PAGE = 3
QR_WORDS_PER_PAGE = 300     # au-delà, la page ne prend que deux questions


def _words(blocks: list[Block]) -> int:
    return sum(len(re.findall(r"\w+", b.text + " ".join(b.items))) for b in blocks)


def qr_pages(questions: list) -> list[list]:
    """Questions groupées par page : trois au plus, deux quand les réponses sont longues."""
    pages: list[list] = [[]]
    words = 0
    for q in questions:
        w = _words(q[2]) + len(re.findall(r"\w+", q[1]))
        if pages[-1] and (len(pages[-1]) == QR_PER_PAGE or words + w > QR_WORDS_PER_PAGE):
            pages.append([])
            words = 0
        pages[-1].append(q)
        words += w
    if len(pages) > 1 and len(pages[-1]) == 1:          # pas de question seule en dernière page :
        j = max(k for k, pg_ in enumerate(pages[:-1]) if len(pg_) == QR_PER_PAGE)
        for k in range(j, len(pages) - 1):              # on décale d'une question vers la fin
            pages[k + 1].insert(0, pages[k].pop())
    return pages


def visuals_html(images: list[Block], box_html: str, ctx: Ctx) -> str:
    """Figures en grand en haut de la fiche, l'encadré du chiffre à retenir à côté (ou dessous,
    quand les figures prennent toute la largeur). Les tableaux en image (très larges) vont sur une
    ligne à eux, sous les figures. Dimensions calculées depuis le format des images."""
    shown = [(b, image_aspect(ctx.image_path(b.src))) for b in images]
    plots = [(b, a) for b, a in shown if a <= 3]
    tables = [(b, a) for b, a in shown if a > 3]
    h_max = 66.0 if not tables else 44.0
    out = []
    if plots:
        s = sum(a for _, a in plots)
        gaps = GAP * (len(plots) - 1)
        h_side = (PAGE_W - BOX_W - GAP - gaps) / s
        side = h_side >= 52
        h = min(h_max, h_side if side else (PAGE_W - gaps) / s)
        figs = "".join(ctx.img(b.src, b.text, f"height:{h:.1f}mm;width:{h * a:.1f}mm")
                       for b, a in plots)
        if side:
            out.append(f'<div class="visuals"><div class="figs">{figs}</div>{box_html}</div>')
        else:
            out.append(f'<div class="visuals"><div class="figs">{figs}</div></div>')
            out.append(box_html.replace('class="box"', 'class="box band"'))
    elif box_html:
        out.append(box_html.replace('class="box"', 'class="box band"'))
    for b, a in tables:
        w = min(PAGE_W, 31.0 * a)
        out.append(f'<div class="tables">{ctx.img(b.src, b.text, f"width:{w:.1f}mm")}</div>')
    return "\n".join(out)


def oral_html(md: str, base: Path = ORAL_MD.parent) -> str:
    ctx = Ctx(base)
    head, secs = sections(parse(md))
    title = next(b for b in head if b.kind == "h" and b.level == 1).text
    deroule = next(b for b in head if b.kind == "table")
    intro = [b for b in head if b.kind == "p" and "](" not in b.text]
    parts = [(h, body) for h, body in secs
             if not h.text.startswith(("Questions probables", "Les 10 chiffres"))]
    q_sec = next(body for h, body in secs if h.text.startswith("Questions probables"))
    c_sec = next((h, body) for h, body in secs if h.text.startswith("Les 10 chiffres"))
    q_intro, questions = parse_questions(q_sec)
    by_number = {n: t for n, t, _ in questions}
    if len(parts) != len(deroule.rows) - 1:
        raise ValueError("le déroulé et les parties de l'oral ne correspondent pas")

    out = [f'<section class="cover">{GLOWS}<div class="in">'
           '<div class="eyebrow"><span><b>●</b>&nbsp; Soutenance · fiches pour apprendre</span>'
           '<span>ECE Paris · ING4 Finance</span></div>'
           f"<h1>{inline(title, ctx)}</h1>"
           + "".join(f'<p{" class=lead" if i == 0 else ""}>{inline(b.text, ctx)}</p>'
                     for i, b in enumerate(intro))
           + '<div class="beam"></div><h3 class="eyebrow" style="margin:6px 0 4px">Le déroulé</h3>'
           + render([deroule], ctx).replace("<table>", '<table class="deroule">', 1)
           + "</div></section>"]

    n_parts = len(parts)
    for i, ((h, body), row) in enumerate(zip(parts, deroule.rows[1:]), start=1):
        f = parse_fiche(h, body)
        box = ('<div class="box"><span class="lab">Le chiffre à retenir</span>'
               f"<p>{mark_numbers(inline(f.retenir, ctx))}</p></div>") if f.retenir else ""
        if not f.images and not box:
            visuals = ""
        else:
            visuals = visuals_html(f.images, box, ctx)
        dire = "".join(f"<li>{inline(t, ctx)}</li>" for t in f.dire)
        demande = "".join(f"<li><b>Question {n}</b>{inline(by_number[n], ctx)} "
                          f'<span style="color:var(--mut)">→ fiche question {n}</span></li>'
                          for n in f.demande)
        out.append(
            f'<section class="fiche" id="fiche-{i}">'
            f'<div class="eyebrow"><span><b>●</b>&nbsp; Fiche {i} / {n_parts} · '
            f"{inline(row[0], ctx)}</span><span>{inline(row[1], ctx)}</span></div>"
            f"<h2>{inline(f.title, ctx)}</h2>"
            f'<div class="who">Qui parle : {inline(f.who, ctx)}</div>'
            + visuals
            + (f'<p class="montre"><b>À montrer</b>&nbsp; {inline(f.montre, ctx)}</p>'
               if f.montre else "")
            + f'<div class="dire"><h3>À dire</h3><ul>{dire}</ul></div>'
            + (f'<div class="demande"><h3>Si on vous demande…</h3><ul>{demande}</ul></div>'
               if demande else "")
            + "</section>")

    for k, group in enumerate(qr_pages(questions)):
        head_html = ('<div class="eyebrow"><span><b>●</b>&nbsp; Questions probables · '
                     f"{len(questions)} fiches question / réponse</span><span>page {k + 1}</span>"
                     "</div>")
        if k == 0:
            head_html += "<h2>Questions probables du professeur</h2>" + render(q_intro, ctx)
        out.append(f'<section class="qr-page">{head_html}' + "".join(
            f'<div class="qr" id="question-{n}"><h3><span>{n}</span>{inline(t, ctx)}</h3>'
            f"{render(blocks, ctx)}</div>" for n, t, blocks in group) + "</section>")

    ch, cbody = c_sec
    table = next(b for b in cbody if b.kind == "table")
    head, *rows = table.rows
    trs = "".join(f"<tr><td>{mark_numbers(inline(r[0], ctx))}</td>"
                  + "".join(f"<td>{inline(c, ctx)}</td>" for c in r[1:]) + "</tr>" for r in rows)
    out.append('<section class="chiffres"><div class="eyebrow"><span><b>●</b>&nbsp; '
               "À connaître par cœur</span><span>avant de passer</span></div>"
               f"<h2>{inline(ch.text, ctx)}</h2><table><thead><tr>"
               + "".join(f"<th>{inline(c, ctx)}</th>" for c in head)
               + f"</tr></thead><tbody>{trs}</tbody></table></section>")
    return page(title, "Soutenance · fiches de l'oral", ORAL_CSS, "\n".join(out))


# --- la grille de conformité : partie A en paysage, B en cartes, C à cocher ------------------------

CONF_CSS = """
@page land{size:A4 landscape;margin:10mm 0 12mm}
.land{page:land}
.part{break-before:page;padding:0 12mm}
.part h2{font:750 24px var(--sans);margin:6px 0 6px}
.part h3{font:600 10px var(--mono);letter-spacing:.18em;text-transform:uppercase;color:var(--a1);
  margin:5mm 0 2mm}
.cover p{font-size:12.5px;max-width:172mm}
.tiles{display:flex;gap:5mm;margin:8mm 0 4mm}
.tile{flex:1;border:1px solid var(--hair);border-radius:10px;background:var(--card);padding:10px 14px}
.tile b{display:block;font:300 34px/1.1 var(--mono);color:var(--ink)}
.tile span{font:600 9.5px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--sub)}
.tile.ok b{color:var(--a1)} .tile.part b{color:var(--a3)} .tile.no b{color:var(--neg)}
.grid-a{table-layout:fixed}
.grid-a th{font-size:8.5px}
.grid-a td{font-size:11px;line-height:1.4;padding:6px 7px}
.grid-a td:first-child{color:var(--ink)}
.grid-a td:nth-child(4){font-size:9.5px;color:var(--sub)}
.grid-a td:last-child{color:#e6e7f0}
.pill{display:inline-block;white-space:nowrap;font:600 10px var(--sans);border-radius:20px;
  padding:3px 9px}
.pill.ok{background:rgba(0,255,163,.14);color:var(--a1);border:1px solid rgba(0,255,163,.5)}
.pill.part{background:rgba(255,214,10,.13);color:var(--a3);border:1px solid rgba(255,214,10,.5)}
.pill.no{background:rgba(255,77,109,.14);color:var(--neg);border:1px solid rgba(255,77,109,.55)}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:4mm}
.card{break-inside:avoid;border:1px solid var(--hair);border-top:3px solid var(--a2);
  border-radius:9px;background:var(--card);padding:10px 13px}
.card h4{font:700 13.5px/1.3 var(--sans);margin:0 0 5px;color:#fff}
.card h4 span{font-family:var(--mono);color:var(--a3);margin-right:7px}
.card .use{font-size:11px;color:var(--sub);margin:0 0 6px}
.card .say{font-size:12.5px;line-height:1.48;color:#e6e7f0;border-left:2px solid var(--a1);
  padding-left:9px;margin:0 0 6px}
.card .say b{font:600 8.5px var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--a1);display:block;margin-bottom:2px}
.card .where{font-size:9.5px;color:var(--mut);margin:0}
.todo{list-style:none;padding:0;margin:4mm 0}
.todo li{font-size:14px;line-height:1.5;margin:0 0 5mm;padding-left:11mm;position:relative}
.todo li::before{content:"";position:absolute;left:0;top:2px;width:17px;height:17px;
  border:2px solid var(--a1);border-radius:4px}
"""

STATUS = {"✅": "ok", "⚠️": "part", "❌": "no"}
BILAN = re.compile(r"Bilan : (\d+) exigences ; (\d+) ✅ [^,]+, (\d+) ⚠️ [^,]+, (\d+) ❌")


def _pill(cell: str, ctx: Ctx) -> str:
    kind = next(v for k, v in STATUS.items() if k in cell)
    return f'<span class="pill {kind}">{inline(cell, ctx)}</span>'


def grid_a_html(table: Block, ctx: Ctx) -> str:
    """Tableau de la partie A : largeurs de colonnes fixes, statut en pastille de couleur."""
    head, *rows = table.rows
    cols = "".join(f'<col style="width:{w}%">' for w in (23, 9, 21, 22, 25))
    th = "".join(f"<th>{inline(c, ctx)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(
        f"<td>{_pill(c, ctx) if j == 1 else inline(c, ctx)}</td>" for j, c in enumerate(r))
        + "</tr>" for r in rows)
    return (f'<table class="grid-a"><colgroup>{cols}</colgroup><thead><tr>{th}</tr></thead>'
            f"<tbody>{trs}</tbody></table>")


def conformite_html(md: str, base: Path = CONF_MD.parent) -> str:
    ctx = Ctx(base)
    head, secs = sections(parse(md))
    title = next(b for b in head if b.kind == "h" and b.level == 1).text
    paras = [b for b in head if b.kind == "p" and "](pdf/" not in b.text]
    a, b_part, c = (next((h, body) for h, body in secs if h.text.startswith(k))
                    for k in ("A. ", "B. ", "C. "))
    bilan = next(x.text for x in a[1] if x.kind == "p" and x.text.startswith("Bilan :"))
    total, ok, part, no = BILAN.search(bilan).groups()
    tiles = "".join(f'<div class="tile {k}"><b>{v}</b><span>{lab}</span></div>' for k, v, lab in (
        ("", total, "exigences du sujet"), ("ok", ok, "✅ faites"), ("part", part, "⚠️ partielles"),
        ("no", no, "❌ non faites")))

    out = [f'<section class="cover">{GLOWS}<div class="in">'
           '<div class="eyebrow"><span><b>●</b>&nbsp; Grille de conformité au sujet</span>'
           "<span>ECE Paris · ING4 Finance</span></div>"
           f"<h1>{inline(title, ctx)}</h1>"
           + "".join(f'<p{" class=lead" if i == 0 else ""}>{inline(p.text, ctx)}</p>'
                     for i, p in enumerate(paras))
           + f'<div class="tiles">{tiles}</div></div></section>']

    ids: dict = {}
    body = []
    for blk in a[1]:
        if blk.kind == "table":
            body.append(grid_a_html(blk, ctx))
        elif blk.kind == "h" and body and any("<table" in x for x in body):
            body.append('<div style="break-before:page"></div>' + render([blk], ctx, ids))
        elif blk.kind != "hr":
            body.append(render([blk], ctx, ids))
    out.append(f'<section class="part land" id="{slug(a[0].text)}"><div class="eyebrow"><span>'
               "<b>●</b>&nbsp; Partie A · exigence par exigence</span><span>statut, où, preuve"
               f"</span></div><h2>{inline(a[0].text, ctx)}</h2>" + "\n".join(body) + "</section>")

    intro = [blk for blk in b_part[1] if blk.kind == "p"]
    table = next(blk for blk in b_part[1] if blk.kind == "table")
    cards = "".join(
        f'<div class="card"><h4><span>{i}</span>{inline(r[0], ctx)}</h4>'
        f'<p class="use">{inline(r[1], ctx)}</p>'
        f'<p class="say"><b>À l\'oral</b>{inline(r[4], ctx)}</p>'
        f'<p class="where">Où : {inline(r[2], ctx)}</p></div>'
        for i, r in enumerate(table.rows[1:], start=1))
    out.append(f'<section class="part" id="{slug(b_part[0].text)}"><div class="eyebrow"><span>'
               f"<b>●</b>&nbsp; Partie B · {len(table.rows) - 1} ajouts</span><span>à l'oral, en "
               f"deux phrases</span></div><h2>{inline(b_part[0].text, ctx)}</h2>"
               + render(intro, ctx)
               + '<p style="color:var(--mut);font-size:10.5px">La preuve de chaque ajout (tests, '
               "fichiers de résultats) est dans la grille complète, docs/CONFORMITE.md.</p>"
               + f'<div class="cards">{cards}</div></section>')

    items = next(blk for blk in c[1] if blk.kind == "ul").items
    out.append(f'<section class="part" id="{slug(c[0].text)}"><div class="eyebrow"><span>'
               f"<b>●</b>&nbsp; Partie C · {len(items)} points</span><span>à cocher</span></div>"
               f"<h2>{inline(c[0].text, ctx)}</h2>"
               + '<ul class="todo">' + "".join(f"<li>{inline(t, ctx)}</li>" for t in items)
               + "</ul></section>")
    return page(title, "Grille de conformité au sujet", CONF_CSS, "\n".join(out))


# --- le dossier du groupe : sommaire cliquable, une étape par page, figures, glossaire --------------

DOSSIER_CSS = """
.cover .in{padding-top:22mm}
.cover p{font-size:12px;max-width:176mm}
.toc{columns:2;column-gap:10mm;margin-top:6mm}
.toc a{display:block;color:var(--txt);font-size:12px;padding:2px 0;break-inside:avoid}
.toc a.l2{color:var(--ink);font-weight:650;font-size:13px;margin-top:6px}
.toc a.l3{padding-left:12px;color:var(--sub)}
.toc a.l2 span{font-family:var(--mono);color:var(--a1);margin-right:6px}
.sec{break-before:page;padding:0 13mm}
.sec h2{font:750 25px var(--sans);margin:4px 0 8px}
.sec h3{font:700 17px var(--sans);margin:6mm 0 3mm;color:#fff}
.sec h3.step{break-before:page;margin-top:0;font-size:21px;border-left:3px solid var(--a1);
  padding-left:10px}
.sec p,.sec li{font-size:11px;line-height:1.52}
.sec ul,.sec ol{padding-left:20px}
.sec li{margin:0 0 3px}
.sec table{margin:2mm 0 4mm;break-inside:auto}
.sec td,.sec th{font-size:10px;padding:4px 7px}
.sec pre code{font-size:10px;line-height:1.4}
.sec td:first-child{color:var(--ink)}
.fig{break-inside:avoid;margin:0 0 7mm;border:1px solid var(--hair);border-radius:10px;
  background:var(--card);padding:9px 13px 4px}
.fig h3{margin:0 0 3mm;font-size:15px}
.fig img{max-height:98mm;width:auto;margin:0 auto 3mm}
.fig li{font-size:11.5px}
.gloss{display:grid;grid-template-columns:1fr 1fr;gap:3mm 6mm}
.gloss p{break-inside:avoid;margin:0;border-left:2px solid var(--a2);padding:2px 0 2px 9px}
.gloss p strong{color:var(--a1)}
"""


def dossier_html(md: str, base: Path = DOSSIER_MD.parent) -> str:
    ctx = Ctx(base)
    head, secs = sections(parse(md))
    title = next(b for b in head if b.kind == "h" and b.level == 1).text
    paras = [b for b in head if b.kind == "p" and not b.text.startswith("Sommaire")
             and "](pdf/" not in b.text]
    ids: dict = {}

    def anchor(text: str) -> str:
        a = slug(text)
        n = ids.get(a, 0)
        ids[a] = n + 1
        return a if n == 0 else f"{a}-{n}"

    toc, body = [], []
    for h, blocks in secs:
        h_id = anchor(h.text)
        num = re.match(r"(\d+)\.\s+(.*)$", h.text)
        label = (f"<span>{num.group(1)}</span>{inline(num.group(2), ctx)}" if num
                 else inline(h.text, ctx))
        toc.append(f'<a class="l2" href="#{h_id}">{label}</a>')
        is_steps = h.text.startswith("2.")
        is_figs = h.text.startswith("4.")
        is_gloss = "Glossaire" in h.text
        out = [f'<section class="sec" id="{h_id}"><div class="eyebrow"><span><b>●</b>&nbsp; '
               f"Dossier du groupe</span><span>{inline(h.text, ctx)}</span></div>"
               f"<h2>{inline(h.text, ctx)}</h2>"]
        i = 0
        while i < len(blocks):
            b = blocks[i]
            if b.kind == "h" and b.level == 3:
                sub_id = anchor(b.text)
                toc.append(f'<a class="l3" href="#{sub_id}">{inline(b.text, ctx)}</a>')
                if is_figs:                     # figure ou tableau : titre, image, explications
                    j = i + 1
                    group = []
                    while j < len(blocks) and not (blocks[j].kind == "h" or blocks[j].kind == "hr"):
                        group.append(blocks[j])
                        j += 1
                    out.append(f'<div class="fig" id="{sub_id}"><h3>{inline(b.text, ctx)}</h3>'
                               + render(group, ctx) + "</div>")
                    i = j
                    continue
                cls = ' class="step"' if is_steps else ""
                out.append(f'<h3{cls} id="{sub_id}">{inline(b.text, ctx)}</h3>')
            elif b.kind == "hr":
                pass
            else:
                out.append(render([b], ctx))
            i += 1
        html = "\n".join(out) + "</section>"
        if is_gloss:
            start = html.index("<p>")
            end = html.rindex("</p>") + 4
            html = html[:start] + '<div class="gloss">' + html[start:end] + "</div>" + html[end:]
        body.append(html)

    cover = (f'<section class="cover">{GLOWS}<div class="in">'
             '<div class="eyebrow"><span><b>●</b>&nbsp; Dossier du groupe · document interne</span>'
             "<span>ECE Paris · ING4 Finance</span></div>"
             f"<h1>{inline(title, ctx)}</h1>"
             + "".join(f'<p{" class=lead" if k == 0 else ""}>{inline(b.text, ctx)}</p>'
                       for k, b in enumerate(paras))
             + '<div class="beam"></div><h3 class="eyebrow" style="margin:4px 0 0">Sommaire '
             "(cliquable)</h3>"
             + f'<nav class="toc">{"".join(toc)}</nav></div></section>')
    return page(title, "Dossier du groupe · document interne", DOSSIER_CSS,
                cover + "\n" + "\n".join(body))


# --- production ------------------------------------------------------------------------------------

DOCS = [(ORAL_MD, ORAL_PDF, oral_html), (CONF_MD, CONF_PDF, conformite_html),
        (DOSSIER_MD, DOSSIER_PDF, dossier_html)]


def build_html(md_path: Path, maker) -> str:
    return maker(md_path.read_text(encoding="utf-8"), md_path.parent)


def build_all(docs=DOCS) -> list[Path]:
    """Écrit chaque PDF depuis son .md (le HTML intermédiaire va dans un dossier temporaire)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for md_path, pdf_path, maker in docs:
            html_path = Path(tmp) / (pdf_path.stem + ".html")
            html_path.write_text(build_html(md_path, maker), encoding="utf-8")
            pb.build_pdf(html_path, pdf_path)
            written.append(pdf_path)
    return written


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pb.build()
    for pdf in build_all():
        print(f"écrit {pdf.relative_to(ROOT)} · {pb.pdf_page_count(pdf)} pages")
