from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk


def ask_open_file(
    *,
    title: str,
    initial_dir: Path,
    filetypes: list[tuple[str, str]],
) -> Path | None:
    from tkinter import filedialog

    fp = filedialog.askopenfilename(
        title=title,
        initialdir=str(initial_dir),
        filetypes=filetypes,
    )
    return Path(fp) if fp else None


def ask_save_file(
    *,
    title: str,
    initial_dir: Path,
    initial_name: str,
    filetypes: list[tuple[str, str]],
) -> Path | None:
    from tkinter import filedialog

    fp = filedialog.asksaveasfilename(
        title=title,
        initialdir=str(initial_dir),
        initialfile=initial_name,
        filetypes=filetypes,
    )
    return Path(fp) if fp else None


def show_warning(parent: tk.Misc, message: str) -> None:
    from tkinter import messagebox

    messagebox.showwarning("Warning", message, parent=parent)


def show_info(parent: tk.Misc, message: str) -> None:
    from tkinter import messagebox

    messagebox.showinfo("Info", message, parent=parent)
