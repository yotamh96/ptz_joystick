"""The settings dialog's four tabs, built from form.FIELDS: a row per setting (label, input, hint), plus the button
rows. Every call on the dialog's thread."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from ...config import AXES
from .form import ACTIONS, FIELDS, TABS, FieldError, numbered

PER_COLUMN = 6                  # button rows per column on the Buttons tab, two columns
AXIS_SETTINGS = ("pan_axis", "tilt_axis", "zoom_axis")


class Tabs:
    """The notebook, a variable per field, and marking the field an error is about."""

    def __init__(self, parent: tk.Misc, values: dict[str, Any], path: Path, cameras: dict[str, dict[str, int]],
                 controllers: list[str]):
        style = ttk.Style(parent)
        style.configure("Hint.TLabel", foreground="#666666")
        style.configure("Bad.TLabel", foreground="#c42b1c")
        self.notebook = ttk.Notebook(parent)
        self.pages = {tab: ttk.Frame(self.notebook, padding=10) for tab in TABS}
        for tab, page in self.pages.items():
            self.notebook.add(page, text=tab)
        choices = {"camera": list(cameras), "controller": controllers, **{a: list(AXES) for a in AXIS_SETTINGS}}
        tops = cameras.get(values["camera"], {})
        self.vars: dict[str, tk.Variable] = {}
        self.inputs: dict[str, tk.Widget] = {}
        self.labels: dict[str, ttk.Label] = {}
        self.places: dict[str, tuple[ttk.Frame, int]] = {}       # setting -> (its page, its grid row)
        self.rows: list[tuple[ttk.Label, tk.StringVar, tk.StringVar, ttk.Entry]] = []     # the button rows
        self.error: ttk.Label | None = None                      # the message under a bad field
        self._marked: ttk.Label | None = None                    # that field's label, now red
        next_row = dict.fromkeys(TABS, 0)
        for f in FIELDS:
            page, row = self.pages[f.tab], next_row[f.tab]
            next_row[f.tab] += 2                                  # the row below is for an error message
            self.places[f.setting] = page, row
            if f.setting == "buttons":
                self._button_rows(page, row, values["buttons"])
                continue
            value = values[f.setting]
            widget: tk.Widget
            if isinstance(value, bool):
                var: tk.Variable = tk.BooleanVar(page, value)
                widget = ttk.Checkbutton(page, text=f.label, variable=var)
            else:
                var = tk.StringVar(page, value)
                label = ttk.Label(page, text=f.label)
                label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
                self.labels[f.setting] = label
                if f.setting in choices:
                    widget = ttk.Combobox(page, textvariable=var, values=choices[f.setting], state="readonly",
                                          width=21)
                else:
                    widget = ttk.Entry(page, textvariable=var, width=24, show="●" if f.setting == "password" else "")
            widget.grid(row=row, column=1, sticky="we", pady=2)
            hint = f"max {tops[f.setting]} for {values['camera']}" if f.setting in tops else f.hint
            ttk.Label(page, text=hint, style="Hint.TLabel").grid(row=row, column=2, sticky="w", padx=(10, 0))
            self.vars[f.setting], self.inputs[f.setting] = var, widget
        other, row = self.pages["Other"], next_row["Other"]
        ttk.Label(other, text="Settings file", style="Hint.TLabel").grid(row=row, column=0, sticky="w", pady=(12, 0))
        ttk.Label(other, text=str(path), wraplength=420).grid(row=row + 1, column=0, columnspan=3, sticky="w")

    def values(self) -> dict[str, Any]:
        """What the fields hold now, in form.to_fields' shape."""
        values: dict[str, Any] = {setting: var.get() for setting, var in self.vars.items()}
        values["buttons"] = [(action.get(), number.get()) for _, action, number, _ in self.rows]
        return values

    def show_error(self, e: FieldError):
        """Open the field's tab, turn its label red, show the message under it, and put the cursor there."""
        page, row = self.places[e.setting]
        self.notebook.select(page)
        widget: tk.Widget | None
        if e.row is not None:
            self._marked, _, _, widget = self.rows[e.row]
        else:
            self._marked, widget = self.labels.get(e.setting), self.inputs.get(e.setting)
        if self._marked:
            self._marked.configure(style="Bad.TLabel")
        self.error = ttk.Label(page, text=e.message, style="Bad.TLabel", wraplength=420)
        self.error.grid(row=row + 1, column=0, columnspan=3, sticky="w")
        if widget:
            widget.focus_set()

    def clear_error(self):
        if self.error:
            self.error.destroy()
        if self._marked:
            self._marked.configure(style="TLabel")
        self.error = self._marked = None

    def _button_rows(self, page: ttk.Frame, row: int, rows: list[tuple[str, str]]):
        """Button / Action / Preset, in two columns. Numbered as joy.cpl shows them: index + 1."""
        table = ttk.Frame(page)
        table.grid(row=row, column=0, columnspan=3, sticky="w")
        per_column = max(PER_COLUMN, (len(rows) + 1) // 2)
        for i, (action, number) in enumerate(rows):
            col, r = 3 * (i // per_column), 1 + i % per_column
            gap = (20 if col else 0, 6)                         # between the two columns
            if r == 1:
                for c, title in enumerate(("Button", "Action", "Preset")):
                    ttk.Label(table, text=title, style="Hint.TLabel").grid(row=0, column=col + c, sticky="w",
                                                                           padx=gap if c == 0 else 0)
            label = ttk.Label(table, text=str(i + 1))
            label.grid(row=r, column=col, sticky="w", padx=gap)
            action_var, number_var = tk.StringVar(table, action), tk.StringVar(table, number)
            ttk.Combobox(table, textvariable=action_var, values=ACTIONS, state="readonly", width=10).grid(
                row=r, column=col + 1, pady=2)
            entry = ttk.Entry(table, textvariable=number_var, width=5)
            entry.grid(row=r, column=col + 2, padx=(6, 0))
            _number_box_follows(action_var, entry)
            self.rows.append((label, action_var, number_var, entry))


def _number_box_follows(action: tk.StringVar, entry: ttk.Entry):
    """Grey the number box while the action takes no number (nothing, tracking)."""
    def sync(*_):
        entry.state(["!disabled"] if numbered(action.get()) else ["disabled"])

    action.trace_add("write", sync)
    sync()
