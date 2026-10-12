# pdftools — Mac 上的 PDF ⇄ EPUB 互转工具

一个命令搞定 PDF 和 EPUB 的互相转换，支持中文，支持批量，有简单的图形界面。

| 方向 | 做法 |
|---|---|
| **EPUB → PDF** | 用 MuPDF 的排版引擎把 EPUB 排成 PDF，保留目录（书签）、书名、作者，可选纸张大小和字号 |
| **PDF → EPUB（text 模式，默认）** | 提取文字重新排版成可重排的 EPUB：自动识别标题、合并跨行/跨页段落、去掉页眉页脚页码、保留图片，按 PDF 书签分章 |
| **PDF → EPUB（image 模式）** | 每页渲染成一张图片，版式 100% 保留，适合扫描版、漫画、排版复杂的书 |

如果电脑上装了 [Calibre](https://calibre-ebook.com/)，默认会自动改用 Calibre 的 `ebook-convert`（转换质量通常更好）；没装也能用内置引擎。

## 安装

```bash
git clone https://github.com/fw0127/pdftools.git
cd pdftools
./install-mac.sh
```

脚本会创建虚拟环境、安装依赖（PyMuPDF、EbookLib），并把 `pdfepub` 命令链接到 `~/.local/bin`。

可选：

```bash
brew install python-tk          # 想用图形界面
brew install --cask calibre     # 想要 Calibre 引擎
```

## 使用

```bash
pdfepub 书.pdf                     # -> 书.epub
pdfepub 书.epub                    # -> 书.pdf
pdfepub 扫描版.pdf -m image        # 每页一张图，保留原版式
pdfepub 书.epub --page-size a4 --font-size 12
pdfepub *.pdf *.epub -o ~/Desktop/converted   # 批量，输出到目录
pdfepub 书.pdf --title "书名" --author "作者"
pdfepub --gui                      # 图形界面
```

常用选项：

| 选项 | 说明 |
|---|---|
| `-o, --output` | 输出文件；多个输入时为输出目录 |
| `-m, --mode text\|image` | PDF→EPUB 模式，默认 `text` |
| `--dpi` | image 模式的渲染精度，默认 150 |
| `--page-size a4\|a5\|b6\|letter` | EPUB→PDF 纸张，默认 `a5`（适合手机/阅读器） |
| `--font-size` | EPUB→PDF 字号，默认 11 |
| `-b, --backend auto\|calibre\|builtin` | 转换引擎，默认 `auto` |

不安装也可以直接运行：`pip install pymupdf ebooklib && python3 -m pdftools 书.pdf`

## 说明

- PDF 本质上是"固定版式"，转 EPUB 时文字版 PDF 效果最好；扫描版 PDF 没有文字层，请用 `-m image`（或先用其它工具 OCR）。
- 加密的 PDF 需要先解除密码。
- 有 DRM 的 EPUB（如从商店购买的）无法转换。
