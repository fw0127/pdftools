"""Command line interface: pdfepub book.pdf / pdfepub book.epub"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .converter import PAGE_SIZES, ConversionError, convert, find_calibre


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdfepub",
        description="PDF 与 EPUB 互相转换。输入 .pdf 输出 .epub，输入 .epub 输出 .pdf。",
    )
    parser.add_argument("inputs", nargs="*", help="要转换的 PDF / EPUB 文件（可多个）")
    parser.add_argument("-o", "--output", help="输出文件（单个输入时）或输出目录（多个输入时）")
    parser.add_argument("-b", "--backend", choices=["auto", "calibre", "builtin"], default="auto",
                        help="auto: 安装了 Calibre 就用 Calibre，否则用内置引擎（默认）")
    parser.add_argument("-m", "--mode", choices=["text", "image"], default="text",
                        help="PDF->EPUB 模式: text=可重排文字（默认）, image=每页一张图（扫描版/漫画）")
    parser.add_argument("--dpi", type=int, default=150, help="image 模式渲染 DPI（默认 150）")
    parser.add_argument("--page-size", choices=sorted(PAGE_SIZES), default="a5",
                        help="EPUB->PDF 纸张大小（默认 a5）")
    parser.add_argument("--font-size", type=float, default=11, help="EPUB->PDF 字号（默认 11）")
    parser.add_argument("--title", help="PDF->EPUB 时设置书名")
    parser.add_argument("--author", help="PDF->EPUB 时设置作者")
    parser.add_argument("--gui", action="store_true", help="打开图形界面")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.gui or not args.inputs:
        if not args.inputs and not args.gui and sys.stdin.isatty():
            parser.print_help()
            return 0
        from .gui import run
        return run(args.inputs)

    out = Path(args.output).expanduser() if args.output else None
    multi = len(args.inputs) > 1
    if multi and out and out.suffix.lower() in (".pdf", ".epub"):
        parser.error("多个输入时 -o 必须是目录")

    backend = args.backend
    if backend == "auto":
        print("使用引擎:", "Calibre" if find_calibre() and args.mode != "image" else "内置 (PyMuPDF)")

    failed = 0
    for item in args.inputs:
        src = Path(item).expanduser()
        dst = None
        if out:
            if multi or out.is_dir():
                suffix = ".epub" if src.suffix.lower() == ".pdf" else ".pdf"
                dst = out / (src.stem + suffix)
            else:
                dst = out
        try:
            result = convert(src, dst, backend=backend, mode=args.mode, dpi=args.dpi,
                             page_size=args.page_size, font_size=args.font_size,
                             title=args.title, author=args.author)
            print(f"✓ {src.name} -> {result}")
        except ConversionError as exc:
            failed += 1
            print(f"✗ {src.name}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
