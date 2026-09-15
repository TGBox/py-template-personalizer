"""
GUI für py-template-personalizer (CustomTkinter).

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

# ──────────────────────────────────────────────────────────────
# App-wide appearance
# ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "Template-Personalizer GUI"
APP_WIDTH = 900
APP_HEIGHT = 700


class QueueStream:
    """Write-only stream that pushes text into a queue."""

    def __init__(self, q: queue.Queue) -> None:
        self._q = q

    def write(self, text: str) -> None:
        if text:
            self._q.put(text)

    def flush(self) -> None:
        pass


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(750, 550)

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

        self._tabview = ctk.CTkTabview(self, anchor="nw")
        self._tabview.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        self._tab_config = self._tabview.add("  Config-Editor")
        self._tab_fields = self._tabview.add("  Felder-Auswahl")
        self._tab_run = self._tabview.add("  Ausführen")

        self._build_config_tab()
        self._build_fields_tab()
        self._build_run_tab()

    def _build_config_tab(self) -> None:
        tab = self._tab_config
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(toolbar, text="Config-Datei:", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(0, 6)
        )
        self._config_path_label = ctk.CTkLabel(
            toolbar,
            text="(keine Datei geladen)",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        self._config_path_label.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ctk.CTkButton(
            toolbar,
            text="Laden",
            width=110,
            command=self._load_config_dialog,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            toolbar,
            text="Speichern",
            width=120,
            fg_color="#2a6496",
            hover_color="#1e4d73",
            command=self._save_config_dialog,
        ).pack(side="right", padx=(6, 0))

        self._config_scroll = ctk.CTkScrollableFrame(tab, label_text="")
        self._config_scroll.grid(row=1, column=0, sticky="nsew")
        self._config_scroll.grid_columnconfigure(1, weight=1)

        self._render_config_editor()

    def _render_config_editor(self) -> None:
        frame = self._config_scroll
        for widget in frame.winfo_children():
            widget.destroy()
        self._entry_widgets.clear()

        if not self._raw_config:
            ctk.CTkLabel(
                frame,
                text="Lade eine Config-Datei über den 'Laden'-Button\noder nutze die Standard-Config.",
                font=ctk.CTkFont(size=13),
                text_color="gray60",
                justify="center",
            ).grid(row=0, column=0, columnspan=2, pady=40)
            ctk.CTkButton(
                frame,
                text="Standard-Config laden",
                command=self._load_default_config,
            ).grid(row=1, column=0, columnspan=2)
            return

        row_idx = 0
        for table, fields in self._raw_config.items():
            header = ctk.CTkLabel(
                frame,
                text=f"[{table}]",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#5ba4d4",
            )
            header.grid(row=row_idx, column=0, columnspan=2, sticky="w", pady=(14, 4), padx=6)
            row_idx += 1

            if isinstance(fields, dict):
                for field_name, value in fields.items():
                    key = f"{table}.{field_name}"
                    lbl = ctk.CTkLabel(frame, text=field_name + ":", anchor="w", width=160)
                    lbl.grid(row=row_idx, column=0, sticky="w", padx=(20, 8), pady=3)
                    entry = ctk.CTkEntry(frame, placeholder_text="(leer)")
                    entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 8), pady=3)
                    if value is not None:
                        entry.insert(0, str(value))
                    self._entry_widgets[key] = entry
                    row_idx += 1
            else:
                lbl = ctk.CTkLabel(frame, text=table + ":", anchor="w", width=160)
                lbl.grid(row=row_idx, column=0, sticky="w", padx=(20, 8), pady=3)
                entry = ctk.CTkEntry(frame, placeholder_text="(leer)")
                if fields is not None:
                    entry.insert(0, str(fields))
                entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 8), pady=3)
                self._entry_widgets[table] = entry
                row_idx += 1

    def _build_fields_tab(self) -> None:
        tab = self._tab_fields
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            toolbar,
            text="Wähle, welche Felder beim Ausführen ersetzt werden:",
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            toolbar,
            text="Alle auswählen",
            width=130,
            command=lambda: self._set_all_fields(True),
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            toolbar,
            text="Alle abwählen",
            width=130,
            fg_color="#555",
            hover_color="#444",
            command=lambda: self._set_all_fields(False),
        ).pack(side="right", padx=(6, 0))

        self._fields_scroll = ctk.CTkScrollableFrame(tab, label_text="")
        self._fields_scroll.grid(row=1, column=0, sticky="nsew")
        self._fields_scroll.grid_columnconfigure(0, weight=1)

        self._render_fields_checkboxes()

    def _render_fields_checkboxes(self) -> None:
        frame = self._fields_scroll
        for widget in frame.winfo_children():
            widget.destroy()
        self._field_vars.clear()

        if not self._raw_config:
            ctk.CTkLabel(
                frame,
                text="Bitte zuerst eine Config-Datei laden.",
                font=ctk.CTkFont(size=13),
                text_color="gray60",
            ).pack(pady=40)
            return

        row_idx = 0
        for table, fields in self._raw_config.items():
            ctk.CTkLabel(
                frame,
                text=f"[{table}]",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#5ba4d4",
                anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", pady=(12, 2), padx=6)
            row_idx += 1

            if isinstance(fields, dict):
                for field_name in fields:
                    key = f"{table}.{field_name}"
                    var = ctk.BooleanVar(value=True)
                    self._field_vars[key] = var
                    cb = ctk.CTkCheckBox(
                        frame,
                        text=f"  {field_name}",
                        variable=var,
                        font=ctk.CTkFont(size=12),
                    )
                    cb.grid(row=row_idx, column=0, sticky="w", padx=(24, 0), pady=2)
                    row_idx += 1

    def _set_all_fields(self, value: bool) -> None:
        for var in self._field_vars.values():
            var.set(value)

    def _build_run_tab(self) -> None:
        tab = self._tab_run
        tab.grid_columnconfigure(1, weight=1)

        dir_frame = ctk.CTkFrame(tab, fg_color="transparent")
        dir_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_frame, text="Input-Verzeichnis:", anchor="w", width=160).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self._input_dir_entry = ctk.CTkEntry(dir_frame, placeholder_text="Ordner mit .fr3-Dateien")
        self._input_dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._input_dir_entry.insert(0, "testdata")
        ctk.CTkButton(
            dir_frame, text="...", width=40,
            command=lambda: self._pick_dir(self._input_dir_entry),
        ).grid(row=0, column=2, pady=4)

        ctk.CTkLabel(dir_frame, text="Output-Verzeichnis:", anchor="w", width=160).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        self._output_dir_entry = ctk.CTkEntry(dir_frame, placeholder_text="Zielordner")
        self._output_dir_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._output_dir_entry.insert(0, "output")
        ctk.CTkButton(
            dir_frame, text="...", width=40,
            command=lambda: self._pick_dir(self._output_dir_entry),
        ).grid(row=1, column=2, pady=4)

        opts_frame = ctk.CTkFrame(tab, fg_color="transparent")
        opts_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self._dry_run_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts_frame, text="Dry-Run (keine Dateien schreiben)", variable=self._dry_run_var).pack(side="left", padx=(0, 24))

        self._verbose_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts_frame, text="Verbose (Details anzeigen)", variable=self._verbose_var).pack(side="left")

        action_frame = ctk.CTkFrame(tab, fg_color="transparent")
        action_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        action_frame.grid_columnconfigure(0, weight=1)

        self._run_btn = ctk.CTkButton(
            action_frame,
            text="Personalisieren starten",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            command=self._start_run,
        )
        self._run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        ctk.CTkButton(
            action_frame, text="Log leeren", width=110,
            fg_color="#555", hover_color="#444",
            command=self._clear_log,
        ).grid(row=0, column=1)

        self._progress = ctk.CTkProgressBar(tab, mode="indeterminate")
        self._progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self._progress.set(0)

        ctk.CTkLabel(tab, text="Ausgabe / Log:", font=ctk.CTkFont(size=12), anchor="w").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 2)
        )

        tab.grid_rowconfigure(5, weight=1)
        self._log_text = ctk.CTkTextbox(
            tab,
            font=ctk.CTkFont(family="Courier New", size=12),
            state="disabled",
            wrap="word",
        )
        self._log_text.grid(row=5, column=0, columnspan=3, sticky="nsew")

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
            self._config_path_label.configure(text=str(path), text_color="gray80")
            self._render_config_editor()
            self._render_fields_checkboxes()
            self._log(f"Config geladen: {path}\n")
        except Exception as exc:
            self._log(f"Fehler beim Laden der Config: {exc}\n")

    def _save_config_dialog(self) -> None:
        self._sync_raw_config_from_entries()
        initial = str(self._config_path) if self._config_path else "config.yaml"
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
                content = yaml.dump(self._raw_config, sort_keys=False, allow_unicode=True, default_flow_style=False)
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

    def _pick_dir(self, entry_widget: ctk.CTkEntry) -> None:
        path = filedialog.askdirectory(title="Ordner waehlen")
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _start_run(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            self._log("Läuft bereits - bitte warten.\n")
            return
        self._sync_raw_config_from_entries()
        if not self._raw_config:
            self._log("Keine Config geladen.\n")
            return

        input_dir = Path(self._input_dir_entry.get().strip() or "testdata")
        output_dir = Path(self._output_dir_entry.get().strip() or "output")
        dry_run = self._dry_run_var.get()
        verbose = self._verbose_var.get()

        if not input_dir.is_dir():
            self._log(f"Input-Verzeichnis nicht gefunden: {input_dir}\n")
            return

        filtered_raw = self._build_filtered_config()
        self._run_btn.configure(state="disabled")
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

    def _run_worker(self, raw, input_dir, output_dir, dry_run, verbose):
        qs = QueueStream(self._log_queue)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = qs
        sys.stderr = qs
        try:
            cfg = PersonalizerConfig(raw)
            personalizer = TemplatePersonalizer(cfg, verbose=verbose)
            print("=" * 60)
            if dry_run:
                print("DRY RUN - keine Dateien werden geschrieben")
            print(f"Input:  {input_dir}")
            print(f"Output: {output_dir}")
            print("=" * 60)
            stats = personalizer.personalize_directory(
                input_dir=input_dir, output_dir=output_dir, in_place=False, dry_run=dry_run
            )
            print("\n" + "=" * 60)
            print("Zusammenfassung")
            print("=" * 60)
            print(f"  Dateien gescannt:   {stats.files_processed}")
            print(f"  Dateien geändert:  {stats.files_modified}")
            print(f"  Ersetzungen gesamt: {stats.total_replacements}")
            print(f"  Memos entbunden:    {stats.memos_unbound}")
            if stats.replacements_per_field:
                print("\n  Ersetzungen nach Feld:")
                for fld, count in stats.replacements_per_field.most_common():
                    print(f"    - {fld:<25}: {count:>4}x")
            if verbose and stats.details:
                print("\n  Details:")
                for detail in stats.details[:100]:
                    print(f"    * {detail}")
            print("=" * 60)
            if dry_run:
                print("Dry-Run abgeschlossen.")
            else:
                print(f"Fertig! Dateien in: {output_dir}")
        except Exception as exc:
            print(f"\nFehler: {exc}")
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            self._log_queue.put(None)

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
                    self._run_btn.configure(state="normal")
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