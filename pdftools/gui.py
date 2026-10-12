"""Minimal Tk GUI: pick files, choose options, convert."""

from __future__ import annotations

import threading
from pathlib import Path

from .converter import PAGE_SIZES, ConversionError, convert, find_calibre


def run(initial=None) -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("缺少 tkinter。macOS 上可执行: brew install python-tk")
        return 1

    root = tk.Tk()
    root.title("PDF ⇄ EPUB 转换器")
    root.geometry("560x420")

    files: list[str] = list(initial or [])
    mode = tk.StringVar(value="text")
    page_size = tk.StringVar(value="a5")
    font_size = tk.DoubleVar(value=11)
    backend = tk.StringVar(value="auto")
    outdir = tk.StringVar(value="")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)

    listbox = tk.Listbox(frm, height=8)
    listbox.pack(fill="both", expand=True)

    def refresh():
        listbox.delete(0, "end")
        for f in files:
            listbox.insert("end", f)

    def add_files():
        picked = filedialog.askopenfilenames(
            filetypes=[("PDF / EPUB", "*.pdf *.epub"), ("PDF", "*.pdf"), ("EPUB", "*.epub")])
        files.extend(p for p in picked if p not in files)
        refresh()

    def choose_outdir():
        d = filedialog.askdirectory()
        if d:
            outdir.set(d)

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=6)
    ttk.Button(btns, text="添加文件…", command=add_files).pack(side="left")
    ttk.Button(btns, text="清空", command=lambda: (files.clear(), refresh())).pack(side="left", padx=6)
    ttk.Button(btns, text="输出目录…", command=choose_outdir).pack(side="left")
    ttk.Label(btns, textvariable=outdir, foreground="gray").pack(side="left", padx=6)

    opts = ttk.LabelFrame(frm, text="选项", padding=8)
    opts.pack(fill="x")
    ttk.Label(opts, text="PDF→EPUB 模式").grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(opts, text="文字（可重排）", variable=mode, value="text").grid(row=0, column=1, sticky="w")
    ttk.Radiobutton(opts, text="图片（保持版式）", variable=mode, value="image").grid(row=0, column=2, sticky="w")
    ttk.Label(opts, text="EPUB→PDF 纸张").grid(row=1, column=0, sticky="w")
    ttk.Combobox(opts, textvariable=page_size, values=sorted(PAGE_SIZES), width=8,
                 state="readonly").grid(row=1, column=1, sticky="w")
    ttk.Label(opts, text="字号").grid(row=1, column=2, sticky="e")
    ttk.Spinbox(opts, from_=8, to=24, textvariable=font_size, width=5).grid(row=1, column=3, sticky="w")
    ttk.Label(opts, text="引擎").grid(row=2, column=0, sticky="w")
    ttk.Combobox(opts, textvariable=backend, values=["auto", "calibre", "builtin"], width=8,
                 state="readonly").grid(row=2, column=1, sticky="w")
    ttk.Label(opts, text="Calibre: " + ("已安装" if find_calibre() else "未安装（使用内置引擎）"),
              foreground="gray").grid(row=2, column=2, columnspan=2, sticky="w")

    status = tk.StringVar(value="添加 PDF 或 EPUB 文件后点击“开始转换”")
    ttk.Label(frm, textvariable=status).pack(fill="x", pady=(8, 0))
    go = ttk.Button(frm, text="开始转换")
    go.pack(pady=6)

    def worker():
        errors = []
        for i, f in enumerate(list(files), 1):
            root.after(0, status.set, f"({i}/{len(files)}) 正在转换 {Path(f).name} …")
            dst = None
            if outdir.get():
                suffix = ".epub" if f.lower().endswith(".pdf") else ".pdf"
                dst = Path(outdir.get()) / (Path(f).stem + suffix)
            try:
                convert(f, dst, backend=backend.get(), mode=mode.get(),
                        page_size=page_size.get(), font_size=float(font_size.get()))
            except (ConversionError, Exception) as exc:  # show any failure to the user
                errors.append(f"{Path(f).name}: {exc}")

        def done():
            go.state(["!disabled"])
            status.set(f"完成：成功 {len(files) - len(errors)}，失败 {len(errors)}")
            if errors:
                messagebox.showerror("部分文件转换失败", "\n\n".join(errors))
        root.after(0, done)

    def start():
        if not files:
            messagebox.showinfo("提示", "请先添加文件")
            return
        go.state(["disabled"])
        threading.Thread(target=worker, daemon=True).start()

    go.configure(command=start)
    refresh()
    root.mainloop()
    return 0
