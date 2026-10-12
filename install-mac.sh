#!/bin/bash
# 在 macOS 上安装 pdfepub 命令（需要 Homebrew 或已有 python3）
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "未找到 python3，正在通过 Homebrew 安装…"
  brew install python
fi

python3 -m venv .venv
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -e .

mkdir -p "$HOME/.local/bin"
ln -sf "$PWD/.venv/bin/pdfepub" "$HOME/.local/bin/pdfepub"

echo
echo "✓ 安装完成：$HOME/.local/bin/pdfepub"
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo "  请把下面这行加入 ~/.zshrc 后重开终端:"
     echo '  export PATH="$HOME/.local/bin:$PATH"' ;;
esac
echo "  图形界面需要 tkinter：brew install python-tk（可选）"
echo "  更好的转换质量：brew install --cask calibre（可选，装了会自动使用）"
