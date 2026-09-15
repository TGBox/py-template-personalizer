"""
GUI fuer py-template-personalizer (CustomTkinter).

Starten mit:
    python gui.py
"""

from __future__ import annotations

import copy
import json
import queue
import sys
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Any, Dict, Optional

# Ensure src is importable when launched directly from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

import customtkinter as ctk

from template_personalizer.config import PersonalizerConfig, load_config
from template_personalizer.personalizer import TemplatePersonalizer

# Design tokens
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE  = "Template-Personalizer"
APP_WIDTH  = 960
APP_HEIGHT = 720

CLR_ACCENT   = "#3a8fd1"
CLR_BTN_DEL  = "#4a4a52"
CLR_BTN_HOVD = "#3a3a42"
CLR_BTN_SAVE = "#1f6aa5"
CLR_BTN_SAVH = "#1a5a8f"
CLR_CARD     = ("gray92", "gray17")
CLR_BORDER   = ("gray80", "gray28")


class QueueStream:
    """Write-only stream that pushes text into a queue."""

    def __init__(self, q: queue.Queue) -> None:
        self._q = q

    def write(self, text: str) -> None:
        if text:
            self._q.put(text)

    def flush(self) -> None:
        pass


def _section_card(parent: Any, **kw) -> ctk.CTkFrame:
    """Returns a lightly-styled card frame."""
    return ctk.CTkFrame(
        parent,
        fg_color=CLR_CARD,
        corner_radius=8,
        border_width=1,
        border_color=CLR_BORDER,
        **kw,
    )


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(760, 560)

        self._raw_config: Dict[str, Any] = {}
        self._config_path: Optional[Path] = None
        self._field_vars: Dict[str, ctk.BooleanVar] = {}
        self._entry_widgets: Dict[str, ctk.CTkEntry] = {}
        self._log_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None

        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tabview = ctk.CTkTabview(self, anchor="nw", corner_radius=10)
        self._tabview.grid(row=0, column=0, padx=14, pady=14, sticky="nsew")

        self._tab_config = self._tabview.add("  Config-Editor")
        self._tab_fields = self._tabview.add("  Felder-Auswahl")
        self._tab_run    = self._tabview.add("  Ausführen")

        self._build_config_tab()
        self._build_fields_tab()
        self._build_run_tab()

    # ── Tab 1 – Config-Editor ─────────────────────────────

    def _build_config_tab(self) -> None:
        tab = self._tab_config
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        toolbar = _section_card(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10), ipady=6)
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="Config-Datei:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=110,
            anchor="w",
        ).grid(row=0, column=0, padx=(12, 6), pady=6, sticky="w")

        self._config_path_label = ctk.CTkLabel(
            toolbar,
            text="(keine Datei geladen)",
            font=ctk.CTkFont(size=12),
            text_color="gray55",
            anchor="w",
        )
        self._config_path_label.grid(row=0, column=1, padx=(0, 8), pady=6, sticky="ew")

        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(0, 10), pady=6)

        ctk.CTkButton(
            btn_frame,
            text="Laden",
            width=120,
            height=32,
            command=self._load_config_dialog,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_frame,
            text="Speichern",
            width=130,
            height=32,
            fg_color=CLR_BTN_SAVE,
            hover_color=CLR_BTN_SAVH,
            command=self._save_config_dialog,
        ).pack(side="left")

        self._config_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self._config_scroll.grid(row=1, column=0, sticky="nsew")
        self._config_scroll.grid_columnconfigure(1, weight=1)

        self._render_config_editor()

    def _render_config_editor(self) -> None:
        frame = self._config_scroll
        for w in frame.winfo_children():
            w.destroy()
        self._entry_widgets.clear()

        if not self._raw_config:
            holder = ctk.CTkFrame(frame, fg_color="transparent")
            holder.grid(row=0, column=0, columnspan=2, pady=60, padx=20, sticky="ew")
            ctk.CTkLabel(
                holder,
                text="Noch keine Config geladen.",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color="gray50",
            ).pack(pady=(0, 6))
            ctk.CTkLabel(
                holder,
                text="Verwende den Laden-Button oben oder lade die\nStandard-Config (config.yaml) mit dem Button unten.",
                font=ctk.CTkFont(size=12),
                text_color="gray55",
                justify="center",
            ).pack(pady=(0, 16))
            ctk.CTkButton(
                holder,
                text="Standard-Config laden (config.yaml)",
                width=260,
                command=self._load_default_config,
            ).pack()
            return

        row_idx = 0
        for table, fields in self._raw_config.items():
            sep = ctk.CTkFrame(frame, fg_color=CLR_ACCENT, height=2, corner_radius=2)
            sep.grid(row=row_idx, column=0, columnspan=2, sticky="ew", padx=4, pady=(16, 0))
            row_idx += 1

            ctk.CTkLabel(
                frame,
                text=f"[ {table} ]",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=CLR_ACCENT,
                anchor="w",
            ).grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(4, 6), padx=8)
            row_idx += 1

            if isinstance(fields, dict):
                for field_name, value in fields.items():
                    key = f"{table}.{field_name}"
                    ctk.CTkLabel(
                        frame,
                        text=field_name,
                        anchor="w",
                        width=170,
                        font=ctk.CTkFont(size=12),
                        text_color=("gray30", "gray75"),
                    ).grid(row=row_idx, column=0, sticky="w", padx=(22, 8), pady=3)
                    entry = ctk.CTkEntry(
                        frame,
                        placeholder_text="(leer)",
                        height=30,
                        font=ctk.CTkFont(size=12),
                    )
                    entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 10), pady=3)
                    if value is not None:
                        entry.insert(0, str(value))
                    self._entry_widgets[key] = entry
                    row_idx += 1
            else:
                ctk.CTkLabel(
                    frame, text=str(table), anchor="w", width=170, font=ctk.CTkFont(size=12),
                ).grid(row=row_idx, column=0, sticky="w", padx=(22, 8), pady=3)
                entry = ctk.CTkEntry(frame, placeholder_text="(leer)", height=30)
                if fields is not None:
                    entry.insert(0, str(fields))
                entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 10), pady=3)
                self._entry_widgets[table] = entry
                row_idx += 1

    # ── Tab 2 – Felder-Auswahl ────────────────────────────

    def _build_fields_tab(self) -> None:
        tab = self._tab_fields
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        toolbar = _section_card(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10), ipady=6)
        toolbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="Welche Felder sollen in den Templates ersetzt werden?",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=6, sticky="w")

        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(0, 10), pady=6)

        ctk.CTkButton(
            btn_frame,
            text="Alle auswählen",
            width=130,
            height=32,
            command=lambda: self._set_all_fields(True),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_frame,
            text="Alle abwählen",
            width=130,
            height=32,
            fg_color=CLR_BTN_DEL,
            hover_color=CLR_BTN_HOVD,
            command=lambda: self._set_all_fields(False),
        ).pack(side="left")

        self._fields_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self._fields_scroll.grid(row=1, column=0, sticky="nsew")
        self._fields_scroll.grid_columnconfigure(0, weight=1, uniform="cb")
        self._fields_scroll.grid_columnconfigure(1, weight=1, uniform="cb")

        self._render_fields_checkboxes()

    def _render_fields_checkboxes(self) -> None:
        frame = self._fields_scroll
        for w in frame.winfo_children():
            w.destroy()
        self._field_vars.clear()

        if not self._raw_config:
            ctk.CTkLabel(
                frame,
                text="Bitte zuerst eine Config-Datei laden.",
                font=ctk.CTkFont(size=13),
                text_color="gray55",
            ).grid(row=0, column=0, columnspan=2, pady=60)
            return

        row_idx = 0
        for table, fields in self._raw_config.items():
            sep = ctk.CTkFrame(frame, fg_color=CLR_ACCENT, height=2, corner_radius=2)
            sep.grid(row=row_idx, column=0, columnspan=2, sticky="ew", padx=4, pady=(16, 0))
            row_idx += 1

            ctk.CTkLabel(
                frame,
                text=f"[ {table} ]",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=CLR_ACCENT,
                anchor="w",
            ).grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 4))
            row_idx += 1

            if isinstance(fields, dict):
                field_list = list(fields.keys())
                cur_row = row_idx
                for i, field_name in enumerate(field_list):
                    col = i % 2
                    if col == 0:
                        cur_row = row_idx
                        row_idx += 1
                    key = f"{table}.{field_name}"
                    var = ctk.BooleanVar(value=True)
                    self._field_vars[key] = var
                    ctk.CTkCheckBox(
                        frame,
                        text=f" {field_name}",
                        variable=var,
                        font=ctk.CTkFont(size=12),
                        checkbox_width=18,
                        checkbox_height=18,
                    ).grid(row=cur_row, column=col, sticky="w", padx=(20, 8), pady=2)

        ctk.CTkFrame(frame, fg_color="transparent", height=12).grid(row=row_idx, column=0)

    def _set_all_fields(self, value: bool) -> None:
        for var in self._field_vars.values():
            var.set(value)

    # ── Tab 3 – Ausführen ────────────────────────────────

    def _build_run_tab(self) -> None:
        tab = self._tab_run
        tab.grid_rowconfigure(5, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Directory card
        dir_card = _section_card(tab)
        dir_card.grid(row=0, column=0, sticky="ew", pady=(0, 8), ipady=4)
        dir_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dir_card, text="Input:", anchor="w", width=90,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(12, 6), pady=(8, 4), sticky="w")
        self._input_dir_entry = ctk.CTkEntry(
            dir_card, placeholder_text="Ordner mit .fr3-Dateien",
            height=30, font=ctk.CTkFont(size=12),
        )
        self._input_dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(8, 4))
        self._input_dir_entry.insert(0, "testdata")
        ctk.CTkButton(
            dir_card, text="Ordner wählen", width=140, height=30,
            fg_color=CLR_BTN_DEL, hover_color=CLR_BTN_HOVD,
            command=lambda: self._pick_dir(self._input_dir_entry),
        ).grid(row=0, column=2, padx=(0, 10), pady=(8, 4))

        ctk.CTkLabel(
            dir_card, text="Output:", anchor="w", width=90,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=1, column=0, padx=(12, 6), pady=(4, 8), sticky="w")
        self._output_dir_entry = ctk.CTkEntry(
            dir_card, placeholder_text="Zielordner für personalisierte Dateien",
            height=30, font=ctk.CTkFont(size=12),
        )
        self._output_dir_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(4, 8))
        self._output_dir_entry.insert(0, "output")
        ctk.CTkButton(
            dir_card, text="Ordner wählen", width=140, height=30,
            fg_color=CLR_BTN_DEL, hover_color=CLR_BTN_HOVD,
            command=lambda: self._pick_dir(self._output_dir_entry),
        ).grid(row=1, column=2, padx=(0, 10), pady=(4, 8))

        # Options card
        opts_card = _section_card(tab)
        opts_card.grid(row=1, column=0, sticky="ew", pady=(0, 8), ipady=2)

        ctk.CTkLabel(
            opts_card, text="Optionen:",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(side="left", padx=(12, 16), pady=8)

        self._dry_run_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts_card,
            text="Dry-Run  (Vorschau, keine Dateien schreiben)",
            variable=self._dry_run_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).pack(side="left", padx=(0, 24), pady=8)

        self._verbose_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts_card,
            text="Verbose  (Details im Log anzeigen)",
            variable=self._verbose_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).pack(side="left", pady=8)

        # Action bar
        action_bar = ctk.CTkFrame(tab, fg_color="transparent")
        action_bar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        action_bar.grid_columnconfigure(0, weight=1)

        self._run_btn = ctk.CTkButton(
            action_bar,
            text="Personalisieren starten",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            corner_radius=8,
            command=self._start_run,
        )
        self._run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            action_bar,
            text="Log leeren",
            width=110,
            height=44,
            corner_radius=8,
            fg_color=CLR_BTN_DEL,
            hover_color=CLR_BTN_HOVD,
            command=self._clear_log,
        ).grid(row=0, column=1)

        # Progress bar (slim, sits between button and log)
        self._progress = ctk.CTkProgressBar(tab, mode="indeterminate", height=6, corner_radius=3)
        self._progress.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self._progress.set(0)

        # Log label
        ctk.CTkLabel(
            tab,
            text="Ausgabe / Log",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=4, column=0, sticky="w", pady=(2, 2))

        # Log textbox (row 5 has weight=1)
        self._log_text = ctk.CTkTextbox(
            tab,
            font=ctk.CTkFont(family="Courier New", size=11),
            state="disabled",
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=CLR_BORDER,
        )
        self._log_text.grid(row=5, column=0, sticky="nsew")

    # ── Config I/O ────────────────────────────────────────

    def _load_config_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Config-Datei öffnen",
            filetypes=[("YAML / JSON", "*.yaml *.yml *.json"), ("Alle Dateien", "*.*")],
        )
        if path:
            self._load_config_from_path(Path(path))

    def _load_default_config(self) -> None:
        for candidate in [Path("config.yaml"), Path("config.yml"), Path("config.json")]:
            if candidate.is_file():
                self._load_config_from_path(candidate)
                return
        self._log("Keine Standard-Config gefunden (config.yaml / config.json).\n")

    def _load_config_from_path(self, path: Path) -> None:
        try:
            cfg = load_config(path)
            self._raw_config = copy.deepcopy(cfg.raw_data)
            self._config_path = path
            self._config_path_label.configure(
                text=str(path.name),
                text_color=("gray20", "gray85"),
            )
            self._render_config_editor()
            self._render_fields_checkboxes()
            self._log(f"Config geladen: {path}\n")
        except Exception as exc:
            self._log(f"Fehler beim Laden der Config: {exc}\n")

    def _save_config_dialog(self) -> None:
        self._sync_raw_config_from_entries()
        initial = str(self._config_path.name) if self._config_path else "config.yaml"
        path = filedialog.asksaveasfilename(
            title="Config-Datei speichern",
            initialfile=initial,
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml *.yml"), ("JSON", "*.json"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        out_path = Path(path)
        try:
            ext = out_path.suffix.lower()
            if ext in (".yaml", ".yml"):
                import yaml
                content = yaml.dump(
                    self._raw_config, sort_keys=False, allow_unicode=True, default_flow_style=False
                )
            else:
                content = json.dumps(self._raw_config, indent=2, ensure_ascii=False)
            out_path.write_text(content, encoding="utf-8")
            self._log(f"Config gespeichert: {out_path}\n")
        except Exception as exc:
            self._log(f"Fehler beim Speichern: {exc}\n")

    def _sync_raw_config_from_entries(self) -> None:
        for key, entry in self._entry_widgets.items():
            val = entry.get()
            if "." in key:
                table, field = key.split(".", 1)
                if table in self._raw_config and isinstance(self._raw_config[table], dict):
                    self._raw_config[table][field] = val
            else:
                self._raw_config[key] = val

    # ── Run logic ─────────────────────────────────────────

    def _pick_dir(self, entry_widget: ctk.CTkEntry) -> None:
        path = filedialog.askdirectory(title="Ordner wählen")
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            self._log("Läuft bereits – bitte warten.\n")
            return
        self._sync_raw_config_from_entries()
        if not self._raw_config:
            self._log("Keine Config geladen. Bitte zuerst eine Config-Datei öffnen.\n")
            return

        input_dir  = Path(self._input_dir_entry.get().strip() or "testdata")
        output_dir = Path(self._output_dir_entry.get().strip() or "output")
        dry_run    = self._dry_run_var.get()
        verbose    = self._verbose_var.get()

        if not input_dir.is_dir():
            self._log(f"Input-Verzeichnis nicht gefunden: {input_dir}\n")
            return

        filtered_raw = self._build_filtered_config()
        self._run_btn.configure(state="disabled", text="Läuft …")
        self._progress.configure(mode="indeterminate")
        self._progress.start()

        self._worker_thread = threading.Thread(
            target=self._run_worker,
            args=(filtered_raw, input_dir, output_dir, dry_run, verbose),
            daemon=True,
        )
        self._worker_thread.start()

    def _build_filtered_config(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for table, fields in self._raw_config.items():
            if isinstance(fields, dict):
                filtered: Dict[str, Any] = {}
                for field_name, value in fields.items():
                    key = f"{table}.{field_name}"
                    var = self._field_vars.get(key)
                    if var is None or var.get():
                        filtered[field_name] = value
                if filtered:
                    result[table] = filtered
            else:
                result[table] = fields
        return result

    def _run_worker(
        self,
        raw: Dict[str, Any],
        input_dir: Path,
        output_dir: Path,
        dry_run: bool,
        verbose: bool,
    ) -> None:
        qs = QueueStream(self._log_queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = qs  # type: ignore[assignment]
        sys.stderr = qs  # type: ignore[assignment]
        try:
            cfg = PersonalizerConfig(raw)
            personalizer = TemplatePersonalizer(cfg, verbose=verbose)

            print("=" * 58)
            if dry_run:
                print("  DRY RUN - keine Dateien werden geschrieben")
                print("=" * 58)
            print(f"  Input  : {input_dir}")
            print(f"  Output : {output_dir}")
            active = sum(len(v) for v in raw.values() if isinstance(v, dict))
            print(f"  Felder : {active} aktiv")
            print("=" * 58)

            stats = personalizer.personalize_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                in_place=False,
                dry_run=dry_run,
            )

            print("\n" + "=" * 58)
            print("  Zusammenfassung")
            print("=" * 58)
            print(f"  Dateien gescannt   : {stats.files_processed}")
            print(f"  Dateien geändert   : {stats.files_modified}")
            print(f"  Ersetzungen gesamt : {stats.total_replacements}")
            print(f"  Memos entbunden    : {stats.memos_unbound}")

            if stats.replacements_per_field:
                print("\n  Ersetzungen nach Feld:")
                for fld, count in stats.replacements_per_field.most_common():
                    print(f"    {fld:<26}  {count:>4} x")

            if verbose and stats.details:
                print("\n  Details:")
                for detail in stats.details[:100]:
                    print(f"    * {detail}")
                if len(stats.details) > 100:
                    print(f"    ... und {len(stats.details) - 100} weitere.")

            print("=" * 58)
            if dry_run:
                print("  Dry-Run abgeschlossen – keine Änderungen geschrieben.")
            else:
                print(f"  Fertig! Dateien gespeichert in: {output_dir}")

        except Exception as exc:
            print(f"\n  Fehler: {exc}")
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            self._log_queue.put(None)

    # ── Log helpers ───────────────────────────────────────

    def _log(self, text: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", text)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _poll_log_queue(self) -> None:
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item is None:
                    self._run_btn.configure(state="normal", text="Personalisieren starten")
                    self._progress.stop()
                    self._progress.set(0)
                else:
                    self._log(item)
        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_log_queue)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
