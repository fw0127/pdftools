"""Core PDF <-> EPUB conversion.

Two backends:
  * calibre  - uses Calibre's ``ebook-convert`` when it is installed (best quality)
  * builtin  - pure Python, based on PyMuPDF + EbookLib (no external apps needed)
"""

from __future__ import annotations

import html
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pymupdf

CALIBRE_CANDIDATES = (
    "ebook-convert",
    "/Applications/calibre.app/Contents/MacOS/ebook-convert",
)

# Page sizes in points (1/72 inch).
PAGE_SIZES = {
    "a4": (595, 842),
    "a5": (420, 595),
    "letter": (612, 792),
    "b6": (354, 499),
}


class ConversionError(RuntimeError):
    pass


def find_calibre() -> str | None:
    for candidate in CALIBRE_CANDIDATES:
        path = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if path:
            return path
    return None


def default_output(src: Path) -> Path:
    suffix = ".epub" if src.suffix.lower() == ".pdf" else ".pdf"
    return src.with_suffix(suffix)


def convert(src, dst=None, backend="auto", **options) -> Path:
    """Convert ``src`` (PDF or EPUB) to the other format and return the output path."""
    src = Path(src).expanduser().resolve()
    if not src.is_file():
        raise ConversionError(f"文件不存在: {src}")
    dst = Path(dst).expanduser().resolve() if dst else default_output(src)

    kinds = (src.suffix.lower(), dst.suffix.lower())
    if kinds not in ((".pdf", ".epub"), (".epub", ".pdf")):
        raise ConversionError(f"只支持 PDF <-> EPUB，收到: {src.name} -> {dst.name}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    if backend not in ("auto", "calibre", "builtin"):
        raise ConversionError(f"未知后端: {backend}")
    calibre = find_calibre() if backend in ("auto", "calibre") else None
    if backend == "calibre" and not calibre:
        raise ConversionError("未找到 Calibre 的 ebook-convert，请先安装 Calibre: brew install --cask calibre")
    # The image mode is only implemented by the builtin backend.
    if calibre and not (backend == "auto" and options.get("mode") == "image"):
        _convert_calibre(calibre, src, dst, **options)
    elif kinds[0] == ".pdf":
        pdf_to_epub(src, dst, **options)
    else:
        epub_to_pdf(src, dst, **options)
    return dst


def _convert_calibre(exe, src, dst, page_size="a5", font_size=None, **_):
    cmd = [exe, str(src), str(dst)]
    if dst.suffix.lower() == ".pdf":
        cmd += ["--paper-size", page_size if page_size in ("a4", "a5", "letter", "b6") else "a5"]
        if font_size:
            cmd += ["--pdf-default-font-size", str(int(font_size))]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ConversionError(f"Calibre 转换失败:\n{proc.stderr or proc.stdout}")


# --------------------------------------------------------------------------- #
# EPUB -> PDF
# --------------------------------------------------------------------------- #

def epub_to_pdf(src, dst, page_size="a5", font_size=11, **_):
    """Lay out an EPUB with MuPDF's HTML engine and save it as PDF (keeps the TOC)."""
    width, height = PAGE_SIZES.get(page_size, PAGE_SIZES["a5"])
    with pymupdf.open(src) as doc:
        if not doc.is_reflowable:
            raise ConversionError("无法识别的 EPUB 文件")
        doc.layout(width=width, height=height, fontsize=font_size)
        toc = doc.get_toc()
        meta = doc.metadata or {}
        pdf_bytes = doc.convert_to_pdf()

    with pymupdf.open("pdf", pdf_bytes) as pdf:
        if toc:
            try:
                pdf.set_toc(toc)
            except Exception:  # malformed TOC levels - outline is optional
                pass
        pdf.set_metadata({k: v for k, v in meta.items() if k in
                          ("title", "author", "subject", "keywords") and v})
        pdf.save(dst, garbage=3, deflate=True)


# --------------------------------------------------------------------------- #
# PDF -> EPUB
# --------------------------------------------------------------------------- #

def pdf_to_epub(src, dst, mode="text", dpi=150, title=None, author=None, **_):
    """Build an EPUB from a PDF.

    mode="text"  reflowable text + embedded images (good for normal text PDFs)
    mode="image" one image per page (keeps the exact layout; use for scans/comics)
    """
    from ebooklib import epub

    with pymupdf.open(src) as doc:
        if doc.needs_pass:
            raise ConversionError("PDF 已加密，请先解除密码")
        meta = doc.metadata or {}
        book = epub.EpubBook()
        book.set_identifier(f"urn:uuid:{uuid.uuid4()}")
        book.set_title(title or meta.get("title") or Path(src).stem)
        book.set_language(_guess_language(doc))
        book.add_author(author or meta.get("author") or "Unknown")

        style = epub.EpubItem(uid="style", file_name="style/main.css",
                              media_type="text/css", content=CSS.encode())
        book.add_item(style)

        if mode == "image":
            pages = _image_pages(doc, book, dpi)
        elif mode == "text":
            pages = _text_pages(doc, book)
        else:
            raise ConversionError(f"未知模式: {mode}")

        chapters = _group_into_chapters(doc, pages)
        items = []
        for idx, (ch_title, bodies) in enumerate(chapters, 1):
            item = epub.EpubHtml(title=ch_title, file_name=f"ch{idx:04d}.xhtml",
                                 lang=book.language)
            item.content = (f"<html><head><title>{html.escape(ch_title)}</title></head>"
                            f"<body>{''.join(bodies)}</body></html>")
            item.add_item(style)
            book.add_item(item)
            items.append(item)

        if mode == "image":
            book.set_cover("images/cover.jpg", _render_page(doc[0], min(dpi, 150)), create_page=False)

        book.toc = _build_toc(chapters, items)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *items] if mode == "text" else items

    epub.write_epub(str(dst), book)


CSS = """
body { margin: 0 4%; line-height: 1.6; }
p { text-indent: 2em; margin: 0.4em 0; text-align: justify; }
h1, h2, h3 { text-indent: 0; text-align: left; line-height: 1.3; }
img { max-width: 100%; height: auto; }
div.page { margin: 0; padding: 0; text-align: center; page-break-after: always; }
div.page img { max-height: 100vh; }
"""


def _guess_language(doc) -> str:
    sample = "".join(doc[i].get_text()[:2000] for i in range(min(3, len(doc))))
    cjk = sum(1 for ch in sample if "一" <= ch <= "鿿")
    if cjk > 20:
        return "zh"
    kana = sum(1 for ch in sample if "぀" <= ch <= "ヿ")
    return "ja" if kana > 20 else "en"


def _render_page(page, dpi) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=85)


def _image_pages(doc, book, dpi):
    from ebooklib import epub

    pages = []
    for page in doc:
        name = f"images/page{page.number + 1:04d}.jpg"
        book.add_item(epub.EpubItem(uid=f"img{page.number}", file_name=name,
                                    media_type="image/jpeg", content=_render_page(page, dpi)))
        pages.append(f'<div class="page"><img src="{name}" alt="page {page.number + 1}"/></div>')
    return pages


def _text_pages(doc, book):
    """Extract each page as a list of headings / paragraphs / images."""
    from ebooklib import epub

    body_size = _body_font_size(doc)
    pages = []
    img_count = 0
    carry = ""  # paragraph text continuing onto the next page
    for page in doc:
        parts = []
        data = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_IMAGES | pymupdf.TEXT_DEHYPHENATE)
        page_height = page.rect.height
        for block in data["blocks"]:
            if block["type"] == 1:  # image
                if block["bbox"][3] - block["bbox"][1] < 20:
                    continue
                try:
                    pix = pymupdf.Pixmap(block["image"])
                    if pix.alpha or pix.n > 3:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    img = pix.tobytes("png")
                except Exception:
                    continue
                img_count += 1
                name = f"images/img{img_count:04d}.png"
                book.add_item(epub.EpubItem(uid=f"img{img_count}", file_name=name,
                                            media_type="image/png", content=img))
                if carry:
                    parts.append(_para(carry)); carry = ""
                parts.append(f'<p style="text-indent:0;text-align:center"><img src="{name}" alt=""/></p>')
                continue

            # Skip running headers/footers (page numbers etc.)
            y0, y1 = block["bbox"][1], block["bbox"][3]
            text, size = _block_text(block)
            if not text:
                continue
            if (y1 < page_height * 0.06 or y0 > page_height * 0.94) and len(text) < 60:
                continue

            if size >= body_size * 1.3 and len(text) < 120:
                if carry:
                    parts.append(_para(carry)); carry = ""
                level = "h1" if size >= body_size * 1.7 else "h2"
                parts.append(f"<{level}>{html.escape(text)}</{level}>")
                continue

            text = _join(carry, text) if carry else text
            carry = ""
            # A block that ends without terminal punctuation probably continues.
            if block is _last_text_block(data["blocks"]) and not _ends_sentence(text):
                carry = text
            else:
                parts.append(_para(text))
        pages.append(parts)

    if carry:
        pages[-1].append(_para(carry))
    return ["".join(p) for p in pages]


def _block_text(block):
    lines, sizes = [], []
    for line in block.get("lines", []):
        spans = [s for s in line["spans"] if s["text"].strip()]
        if not spans:
            continue
        lines.append("".join(s["text"] for s in line["spans"]).strip())
        sizes.extend(s["size"] for s in spans)
    text = ""
    for ln in lines:
        text = _join(text, ln) if text else ln
    return text.strip(), (max(sizes) if sizes else 0)


def _join(a: str, b: str) -> str:
    """Join two line fragments; no space between CJK characters."""
    if not a:
        return b
    if a.endswith("-") and b[:1].islower():
        return a[:-1] + b
    if _is_cjk(a[-1]) or _is_cjk(b[:1]):
        return a + b
    return a + " " + b


def _is_cjk(ch: str) -> bool:
    return bool(ch) and ("⺀" <= ch <= "鿿" or "豈" <= ch <= "￯"
                         or "　" <= ch <= "〿")


def _ends_sentence(text: str) -> bool:
    return text.rstrip()[-1:] in set('.!?。！？」』”"\')）:：;；…')


def _last_text_block(blocks):
    for b in reversed(blocks):
        if b["type"] == 0 and any(s["text"].strip() for l in b.get("lines", []) for s in l["spans"]):
            return b
    return None


def _para(text: str) -> str:
    return f"<p>{html.escape(text)}</p>"


def _body_font_size(doc) -> float:
    """Most common font size (weighted by character count) = body text size."""
    counts = {}
    for page in doc.pages(0, min(len(doc), 30)):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    size = round(span["size"], 1)
                    counts[size] = counts.get(size, 0) + len(span["text"].strip())
    return max(counts, key=counts.get) if counts else 10.0


def _group_into_chapters(doc, pages):
    """Split pages into chapters using the PDF outline (top level), else ~20 pages each."""
    toc = [e for e in doc.get_toc() if e[0] == 1 and e[2] >= 1]
    starts = []
    for _, title, pno in toc:
        if not starts or pno - 1 > starts[-1][1]:
            starts.append((title.strip() or f"第 {pno} 页", pno - 1))
    if not starts or starts[0][1] > 0:
        first = Path(doc.name).stem if not starts else "前言"
        starts.insert(0, (first, 0))
    if len(starts) == 1 and len(pages) > 40:
        starts = [(f"第 {i + 1}-{min(i + 20, len(pages))} 页", i) for i in range(0, len(pages), 20)]

    chapters = []
    for i, (title, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(pages)
        chapters.append((title, pages[start:end]))
    return chapters


def _build_toc(chapters, items):
    from ebooklib import epub

    return [epub.Link(item.file_name, title, f"ch{i}") for i, ((title, _), item)
            in enumerate(zip(chapters, items))]
