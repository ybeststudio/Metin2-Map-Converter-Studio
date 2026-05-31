from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from app.core.generation_workflow import run_selected_generation
from app.core.map_reader import MapSource, discover_map_sources


BG = "#0B1120"
PANEL = "#111827"
PANEL_SOFT = "#162033"
BORDER = "#243247"
TEXT = "#E5E7EB"
MUTED = "#94A3B8"
ACCENT = "#14B8A6"
ACCENT_DARK = "#0F766E"
WARN = "#FBBF24"
INPUT = "#020617"


def resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir.parent if exe_dir.name.lower() == "bin" else exe_dir
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resolve_project_root()
DEFAULT_SOURCE_ROOT = r"D:\ymir work"
DEFAULT_SAMPLE_ROOT = ""
DEFAULT_OUTPUT_ROOT = str(PROJECT_ROOT / "GeneratedMaps")
DEFAULT_REPORT_FILE = str(PROJECT_ROOT / "GeneratedMaps" / "_reports" / "generation_summary.json")
DEFAULT_MAPS = [
    "metin2_map_smhgate_a1",
    "metin2_map_guild_whitedragon_boss_pass",
    "metin2_map_n_flame_dragon_pass",
]


@dataclass(slots=True, frozen=True)
class GuiMapRecord:
    name: str
    path: Path
    setting_path: Path
    parent_map_name: str | None
    attr_source_map_name: str | None
    map_size: tuple[int, int]
    base_position: tuple[int, int]
    texture_set: str | None
    environment: str | None
    area_count: int
    attr_count: int
    area_grid_size: tuple[int, int]
    warnings: tuple[str, ...]

    @property
    def has_attr(self) -> bool:
        return self.attr_count > 0

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def map_source_to_record(map_source: MapSource) -> GuiMapRecord:
    return GuiMapRecord(
        name=map_source.name,
        path=map_source.path,
        setting_path=map_source.setting_path,
        parent_map_name=map_source.parent_map_name,
        attr_source_map_name=map_source.attr_source_map_name,
        map_size=map_source.setting.map_size,
        base_position=map_source.setting.base_position,
        texture_set=map_source.setting.texture_set,
        environment=map_source.setting.environment,
        area_count=len(map_source.area_directories),
        attr_count=len(map_source.attr_files),
        area_grid_size=(map_source.area_grid_width, map_source.area_grid_height),
        warnings=tuple(map_source.warnings),
    )


def build_map_records(source_root: str | Path) -> list[GuiMapRecord]:
    return [map_source_to_record(map_source) for map_source in discover_map_sources(source_root)]


def filter_map_records(
    records: list[GuiMapRecord],
    query: str = "",
    *,
    only_with_attr: bool = False,
    only_with_warnings: bool = False,
) -> list[GuiMapRecord]:
    normalized_query = " ".join(query.lower().split())
    filtered: list[GuiMapRecord] = []
    for record in records:
        if only_with_attr and not record.has_attr:
            continue
        if only_with_warnings and record.warning_count == 0:
            continue
        searchable = " ".join(
            part
            for part in (
                record.name,
                record.parent_map_name or "",
                record.attr_source_map_name or "",
                record.texture_set or "",
                record.environment or "",
                str(record.path),
            )
            if part
        ).lower()
        if normalized_query and normalized_query not in searchable:
            continue
        filtered.append(record)
    return filtered


def format_map_record_detail(record: GuiMapRecord | None) -> str:
    if record is None:
        return "Listeden bir map seçtiğinde detaylar burada görünür."

    warning_text = "\n".join(f"- {warning}" for warning in record.warnings) or "- Yok"
    return "\n".join(
        [
            f"Map Adı: {record.name}",
            f"Map Klasörü: {record.path}",
            f"Setting: {record.setting_path}",
            f"Parent Map: {record.parent_map_name or '-'}",
            f"Attr Kaynağı: {record.attr_source_map_name or record.name}",
            f"MapSize: {record.map_size[0]} x {record.map_size[1]}",
            f"BasePosition: {record.base_position[0]}, {record.base_position[1]}",
            f"Area Klasörü: {record.area_count}",
            f"Attr Dosyası: {record.attr_count}",
            f"Area Grid: {record.area_grid_size[0]} x {record.area_grid_size[1]}",
            f"TextureSet: {record.texture_set or '-'}",
            f"Environment: {record.environment or '-'}",
            f"Attr Durumu: {'Var' if record.has_attr else 'Yok'}",
            "Uyarılar:",
            warning_text,
        ]
    )


def build_map_summary_text(records: list[GuiMapRecord], visible_records: list[GuiMapRecord]) -> str:
    attr_count = sum(1 for record in visible_records if record.has_attr)
    warning_count = sum(1 for record in visible_records if record.warning_count > 0)
    return (
        f"Görünen {len(visible_records)} / Toplam {len(records)} map | "
        f"Attr var: {attr_count} | Uyarılı: {warning_count}"
    )


def build_selection_summary_text(selected_count: int, request_count: int) -> str:
    return f"Seçili map: {selected_count} | Üretim kuyruğu: {request_count}"


class MapConverterGui:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Metin2 Map Converter Studio")
        self.root.geometry("1320x860")
        self.root.minsize(1120, 720)
        self.root.configure(bg=BG)

        self.source_root_var = tk.StringVar(value=DEFAULT_SOURCE_ROOT)
        self.sample_root_var = tk.StringVar(value=DEFAULT_SAMPLE_ROOT)
        self.output_root_var = tk.StringVar(value=DEFAULT_OUTPUT_ROOT)
        self.report_file_var = tk.StringVar(value=DEFAULT_REPORT_FILE)
        self.status_var = tk.StringVar(value="Hazır")
        self.map_summary_var = tk.StringVar(value="Map taraması bekleniyor.")
        self.request_summary_var = tk.StringVar(value="Üretim listesi: 0 map")
        self.selection_summary_var = tk.StringVar(value="Seçili map: 0 | Üretim kuyruğu: 0")
        self.filter_query_var = tk.StringVar()
        self.only_with_attr_var = tk.BooleanVar(value=False)
        self.only_with_warnings_var = tk.BooleanVar(value=False)

        self.run_button: tk.Button | None = None
        self.log_text: ScrolledText | None = None
        self.detail_text: ScrolledText | None = None
        self.available_map_tree: ttk.Treeview | None = None
        self.request_list: tk.Listbox | None = None

        self._all_map_records: list[GuiMapRecord] = []
        self._visible_map_records: list[GuiMapRecord] = []

        self._configure_style()
        self._build_layout()
        self.root.after(150, self._scan_available_maps)

    def run(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", background=INPUT, fieldbackground=INPUT, foreground=TEXT, rowheight=28)
        style.configure("Treeview.Heading", background="#1E293B", foreground="#F8FAFC", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT_DARK)], foreground=[("selected", "#FFFFFF")])

    def _build_layout(self) -> None:
        root = tk.Frame(self.root, bg=BG, padx=16, pady=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self._build_header(root)
        self._build_paths(root)
        self._build_workspace(root)
        self._build_log(root)

        self._append_log("Arayüz hazır. Varsayılan kaynak olarak D:\\ymir work taranacak.")
        self._append_log(f"Üretim klasörü: {DEFAULT_OUTPUT_ROOT}")
        self._update_requested_summary()

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Metin2 Map Converter Studio",
            bg=BG,
            fg="#F8FAFC",
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text=f"Client map dosyalarını server map çıktısına dönüştürür | Proje: {PROJECT_ROOT}",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=BG,
            fg=WARN,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=1, sticky="e", padx=(16, 0))

    def _build_paths(self, parent: tk.Frame) -> None:
        panel = self._panel(parent)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        panel.columnconfigure(1, weight=1)

        self._section_title(panel, "Klasör Ayarları").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self._add_path_row(panel, 1, "Client Kaynak", self.source_root_var, self._choose_source_root)
        self._add_path_row(panel, 2, "Üretim Klasörü", self.output_root_var, self._choose_output_root)

        buttons = tk.Frame(panel, bg=PANEL)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self._button(buttons, "Kaynak Aç", self._open_source_root).pack(side="left")
        self._button(buttons, "Çıktı Aç", self._open_output_root).pack(side="left", padx=(8, 0))
        self._button(buttons, "Varsayılanlara Dön", self._reset_defaults).pack(side="left", padx=(8, 0))

    def _build_workspace(self, parent: tk.Frame) -> None:
        workspace = tk.Frame(parent, bg=BG)
        workspace.grid(row=2, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=5)
        workspace.columnconfigure(1, weight=3)
        workspace.rowconfigure(0, weight=1)

        left = self._panel(workspace)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(4, weight=1)
        left.rowconfigure(8, weight=1)

        right = self._panel(workspace)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._build_map_browser(left)
        self._build_queue(right)

    def _build_map_browser(self, parent: tk.Frame) -> None:
        self._section_title(parent, "Map Tarayıcı").grid(row=0, column=0, sticky="w")

        filter_panel = tk.Frame(parent, bg=PANEL)
        filter_panel.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        filter_panel.columnconfigure(1, weight=1)
        tk.Label(filter_panel, text="Ara", bg=PANEL, fg=TEXT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        entry = self._entry(filter_panel, self.filter_query_var)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<KeyRelease>", lambda _event: self._apply_map_filters())
        self._button(filter_panel, "Temizle", self._clear_filter).grid(row=0, column=2, padx=(8, 0))
        self._check(filter_panel, "Attr olanlar", self.only_with_attr_var, self._apply_map_filters).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._check(filter_panel, "Uyarılı", self.only_with_warnings_var, self._apply_map_filters).grid(
            row=1,
            column=1,
            sticky="w",
            pady=(8, 0),
        )
        self._button(filter_panel, "Tara", self._scan_available_maps).grid(row=1, column=2, sticky="e", pady=(8, 0))

        actions = tk.Frame(parent, bg=PANEL)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for text, command in (
            ("Tümünü Seç", self._select_all_visible_maps),
            ("Seçimi Temizle", self._clear_tree_selection),
            ("Seçileni Ekle", self._append_selected_maps),
            ("Listeyi Değiştir", self._replace_with_selected_maps),
            ("Görünenleri Ekle", self._append_all_scanned_maps),
            ("Map Klasörü", self._open_selected_map_folder),
        ):
            self._button(actions, text, command).pack(side="left", padx=(0, 8))

        table = tk.Frame(parent, bg=PANEL)
        table.grid(row=4, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("areas", "attrs", "parent", "warnings")
        self.available_map_tree = ttk.Treeview(table, columns=columns, show="tree headings", selectmode="extended")
        self.available_map_tree.heading("#0", text="Map")
        self.available_map_tree.heading("areas", text="Area")
        self.available_map_tree.heading("attrs", text="Attr")
        self.available_map_tree.heading("parent", text="Parent")
        self.available_map_tree.heading("warnings", text="Uyarı")
        self.available_map_tree.column("#0", width=330, stretch=True)
        self.available_map_tree.column("areas", width=70, anchor="center", stretch=False)
        self.available_map_tree.column("attrs", width=70, anchor="center", stretch=False)
        self.available_map_tree.column("parent", width=210, stretch=True)
        self.available_map_tree.column("warnings", width=70, anchor="center", stretch=False)
        self.available_map_tree.grid(row=0, column=0, sticky="nsew")
        self.available_map_tree.bind("<<TreeviewSelect>>", self._handle_tree_selection_changed)
        self.available_map_tree.bind("<Double-1>", lambda _event: self._append_selected_maps())
        tree_scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.available_map_tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky="ns")
        self.available_map_tree.configure(yscrollcommand=tree_scrollbar.set)

        tk.Label(parent, textvariable=self.map_summary_var, bg=PANEL, fg=MUTED).grid(row=5, column=0, sticky="w", pady=(8, 2))
        tk.Label(parent, textvariable=self.selection_summary_var, bg=PANEL, fg=MUTED).grid(row=6, column=0, sticky="w", pady=(0, 8))

        self._section_title(parent, "Map Detayı").grid(row=7, column=0, sticky="nw", pady=(0, 4))
        self.detail_text = self._text(parent, height=8)
        self.detail_text.grid(row=8, column=0, sticky="nsew")
        self._set_detail_text(format_map_record_detail(None))

    def _build_queue(self, parent: tk.Frame) -> None:
        self._section_title(parent, "Üretim Kuyruğu").grid(row=0, column=0, sticky="w")
        box = tk.Frame(parent, bg=PANEL)
        box.grid(row=1, column=0, sticky="nsew", pady=(10, 8))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        buttons = tk.Frame(box, bg=PANEL)
        buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._button(buttons, "Örnek Liste", self._load_default_maps).pack(side="left")
        self._button(buttons, "Çıkar", self._remove_selected_request_maps).pack(side="left", padx=(8, 0))
        self._button(buttons, "Temizle", self._clear_map_list).pack(side="left", padx=(8, 0))
        tk.Label(buttons, textvariable=self.request_summary_var, bg=PANEL, fg=MUTED).pack(side="right")

        self.request_list = tk.Listbox(
            box,
            selectmode=tk.EXTENDED,
            exportselection=False,
            bg=INPUT,
            fg=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground="#FFFFFF",
            highlightthickness=1,
            highlightbackground=BORDER,
            relief="flat",
            font=("Consolas", 9),
        )
        self.request_list.grid(row=1, column=0, sticky="nsew")
        self.request_list.bind("<Delete>", lambda _event: self._remove_selected_request_maps())
        self._set_request_map_names(list(DEFAULT_MAPS))

        run = tk.Frame(parent, bg=PANEL)
        run.grid(row=2, column=0, sticky="ew")
        self.run_button = self._button(run, "Üretimi Başlat", self._start_generation, accent=True)
        self.run_button.pack(side="left")
        self._button(run, "Çıktıyı Aç", self._open_output_root).pack(side="left", padx=(8, 0))
        self._button(run, "Raporu Aç", self._open_report_file).pack(side="left", padx=(8, 0))

    def _build_log(self, parent: tk.Frame) -> None:
        panel = self._panel(parent)
        panel.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        panel.columnconfigure(0, weight=1)
        self._section_title(panel, "Çalışma Logu").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.log_text = self._text(panel, height=7)
        self.log_text.grid(row=1, column=0, sticky="ew")

    def _panel(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER, padx=12, pady=10)

    def _section_title(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=PANEL, fg=ACCENT, font=("Segoe UI", 11, "bold"))

    def _entry(self, parent: tk.Widget, variable: tk.StringVar) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=("Segoe UI", 9),
        )

    def _text(self, parent: tk.Widget, *, height: int) -> ScrolledText:
        return ScrolledText(
            parent,
            height=height,
            wrap="word",
            state="disabled",
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground="#FFFFFF",
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            font=("Consolas", 9),
        )

    def _button(self, parent: tk.Widget, text: str, command, *, accent: bool = False) -> tk.Button:
        bg = ACCENT_DARK if accent else "#1E293B"
        active = ACCENT if accent else "#334155"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg="#FFFFFF",
            activebackground=active,
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold" if accent else "normal"),
        )

    def _check(self, parent: tk.Widget, text: str, variable: tk.BooleanVar, command) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=PANEL,
            fg=TEXT,
            selectcolor=INPUT,
            activebackground=PANEL,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9),
        )

    def _add_path_row(self, parent: tk.Frame, row: int, label_text: str, variable: tk.StringVar, browse_command) -> None:
        tk.Label(parent, text=label_text, bg=PANEL, fg=TEXT, width=18, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        self._entry(parent, variable).grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=4)
        self._button(parent, "Seç", browse_command).grid(row=row, column=2, sticky="ew", pady=4)

    def _choose_source_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.source_root_var.get() or None)
        if selected:
            self.source_root_var.set(selected)
            self._scan_available_maps()

    def _choose_sample_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.sample_root_var.get() or None)
        if selected:
            self.sample_root_var.set(selected)

    def _choose_output_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_root_var.get() or None)
        if selected:
            self.output_root_var.set(selected)

    def _choose_report_file(self) -> None:
        selected = filedialog.asksaveasfilename(
            initialdir=str(Path(self.report_file_var.get()).parent),
            initialfile=Path(self.report_file_var.get()).name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if selected:
            self.report_file_var.set(selected)

    def _reset_defaults(self) -> None:
        self.source_root_var.set(DEFAULT_SOURCE_ROOT)
        self.sample_root_var.set(DEFAULT_SAMPLE_ROOT)
        self.output_root_var.set(DEFAULT_OUTPUT_ROOT)
        self.report_file_var.set(DEFAULT_REPORT_FILE)
        self._load_default_maps()
        self._scan_available_maps()

    def _load_default_maps(self) -> None:
        self._set_request_map_names(list(DEFAULT_MAPS))

    def _clear_map_list(self) -> None:
        assert self.request_list is not None
        self.request_list.delete(0, "end")
        self._update_requested_summary()

    def _remove_selected_request_maps(self) -> None:
        assert self.request_list is not None
        selected_indices = list(self.request_list.curselection())
        if not selected_indices:
            messagebox.showinfo("Seçim yok", "Kuyruktan çıkarmak için en az bir map seç.")
            return
        for index in reversed(selected_indices):
            self.request_list.delete(index)
        self._update_requested_summary()

    def _clear_filter(self) -> None:
        self.filter_query_var.set("")
        self.only_with_attr_var.set(False)
        self.only_with_warnings_var.set(False)
        self._apply_map_filters()

    def _scan_available_maps(self) -> None:
        source_root = self.source_root_var.get().strip()
        if not source_root:
            messagebox.showerror("Eksik alan", "Kaynak klasör boş olamaz.")
            return
        try:
            self._all_map_records = build_map_records(source_root)
        except Exception as exc:
            messagebox.showerror("Tarama hatası", str(exc))
            self._append_log(f"Tarama hatası: {exc}")
            return

        self._append_log(f"Tarama tamamlandı. Kaynak={source_root} map sayısı={len(self._all_map_records)}")
        self._apply_map_filters()

    def _apply_map_filters(self) -> None:
        self._visible_map_records = filter_map_records(
            self._all_map_records,
            self.filter_query_var.get(),
            only_with_attr=self.only_with_attr_var.get(),
            only_with_warnings=self.only_with_warnings_var.get(),
        )
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        assert self.available_map_tree is not None
        selected_names = set(self._get_selected_scanned_maps())
        self.available_map_tree.delete(*self.available_map_tree.get_children())
        for record in self._visible_map_records:
            self.available_map_tree.insert(
                "",
                "end",
                iid=record.name,
                text=record.name,
                values=(record.area_count, record.attr_count, record.parent_map_name or "-", record.warning_count),
            )
            if record.name in selected_names:
                self.available_map_tree.selection_add(record.name)
        self.map_summary_var.set(build_map_summary_text(self._all_map_records, self._visible_map_records))
        self._update_selection_summary()
        self._update_detail_from_selection()

    def _select_all_visible_maps(self) -> None:
        assert self.available_map_tree is not None
        self.available_map_tree.selection_set(self.available_map_tree.get_children())
        self._update_detail_from_selection()

    def _clear_tree_selection(self) -> None:
        assert self.available_map_tree is not None
        self.available_map_tree.selection_remove(self.available_map_tree.selection())
        self._update_selection_summary()
        self._update_detail_from_selection()

    def _handle_tree_selection_changed(self, _event: tk.Event) -> None:
        self._update_selection_summary()
        self._update_detail_from_selection()

    def _update_detail_from_selection(self) -> None:
        selected_names = self._get_selected_scanned_maps()
        if not selected_names:
            self._set_detail_text(format_map_record_detail(None))
            return
        record = next((item for item in self._all_map_records if item.name == selected_names[0]), None)
        self._set_detail_text(format_map_record_detail(record))

    def _set_detail_text(self, text: str) -> None:
        assert self.detail_text is not None
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _append_selected_maps(self) -> None:
        selected_map_names = self._get_selected_scanned_maps()
        if not selected_map_names:
            messagebox.showinfo("Seçim yok", "Listeden en az bir map seç.")
            return
        self._set_request_map_names(merge_map_names(self._get_request_map_names(), selected_map_names))

    def _replace_with_selected_maps(self) -> None:
        selected_map_names = self._get_selected_scanned_maps()
        if not selected_map_names:
            messagebox.showinfo("Seçim yok", "Listeden en az bir map seç.")
            return
        self._set_request_map_names(selected_map_names)

    def _append_all_scanned_maps(self) -> None:
        all_map_names = [record.name for record in self._visible_map_records]
        if not all_map_names:
            messagebox.showinfo("Liste boş", "Önce map taraması yap veya filtreyi temizle.")
            return
        self._set_request_map_names(merge_map_names(self._get_request_map_names(), all_map_names))

    def _open_selected_map_folder(self) -> None:
        selected_names = self._get_selected_scanned_maps()
        if not selected_names:
            messagebox.showinfo("Seçim yok", "Klasör açmak için bir map seç.")
            return
        record = next((item for item in self._all_map_records if item.name == selected_names[0]), None)
        if record is None:
            messagebox.showerror("Bulunamadı", "Seçilen map kaydı bulunamadı.")
            return
        self._open_path(str(record.path), "Map klasörü")

    def _start_generation(self) -> None:
        requested_map_names = self._get_request_map_names()
        if not requested_map_names:
            messagebox.showerror("Üretim listesi boş", "Soldaki listeden map seçip kuyruğa ekle.")
            return

        source_root = self.source_root_var.get().strip()
        sample_root = self.sample_root_var.get().strip()
        output_root = self.output_root_var.get().strip()
        report_file = self.report_file_var.get().strip()
        if not source_root or not output_root or not report_file:
            messagebox.showerror("Eksik alan", "Kaynak, çıktı ve rapor alanları boş olamaz.")
            return

        Path(output_root).mkdir(parents=True, exist_ok=True)
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)

        assert self.run_button is not None
        self.run_button.configure(state="disabled")
        self.status_var.set("Üretim çalışıyor")
        self._append_log(f"Üretim başladı. Kaynak={source_root} map sayısı={len(requested_map_names)} çıktı={output_root}")

        worker = threading.Thread(
            target=self._run_generation_worker,
            args=(source_root, sample_root, output_root, report_file, requested_map_names),
            daemon=True,
        )
        worker.start()

    def _run_generation_worker(
        self,
        source_root: str,
        sample_root: str,
        output_root: str,
        report_file: str,
        requested_map_names: list[str],
    ) -> None:
        try:
            result = run_selected_generation(
                source_root=source_root,
                output_root=output_root,
                requested_map_names=requested_map_names,
                sample_root=sample_root or None,
                report_file=report_file,
            )
        except Exception as exc:
            self.root.after(0, lambda: self._finish_with_error(exc))
            return
        self.root.after(0, lambda: self._finish_success(result.summary, result.report_path))

    def _finish_success(self, summary: dict, report_path: Path) -> None:
        assert self.run_button is not None
        self.run_button.configure(state="normal")
        self.status_var.set(f"Tamamlandı | Üretilen {summary['generated_map_count']} / {summary['requested_map_count']}")
        self._append_log(
            json.dumps(
                {
                    "requested_map_count": summary["requested_map_count"],
                    "generated_map_count": summary["generated_map_count"],
                    "missing_requested_maps": summary["missing_requested_maps"],
                    "server_attr_status_counts": summary["server_attr_status_counts"],
                    "report_path": str(report_path),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    def _finish_with_error(self, exc: Exception) -> None:
        assert self.run_button is not None
        self.run_button.configure(state="normal")
        self.status_var.set("Hata")
        self._append_log(f"Hata: {exc}")
        messagebox.showerror("Üretim hatası", str(exc))

    def _get_request_map_names(self) -> list[str]:
        assert self.request_list is not None
        return list(self.request_list.get(0, "end"))

    def _set_request_map_names(self, map_names: list[str]) -> None:
        assert self.request_list is not None
        self.request_list.delete(0, "end")
        for map_name in parse_map_names("\n".join(map_names)):
            self.request_list.insert("end", map_name)
        self._update_requested_summary()

    def _update_requested_summary(self) -> None:
        requested_names = self._get_request_map_names() if self.request_list is not None else []
        self.request_summary_var.set(f"Üretim listesi: {len(requested_names)} map")
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        selected_count = len(self._get_selected_scanned_maps()) if self.available_map_tree is not None else 0
        request_count = len(self._get_request_map_names()) if self.request_list is not None else 0
        self.selection_summary_var.set(build_selection_summary_text(selected_count, request_count))

    def _get_selected_scanned_maps(self) -> list[str]:
        assert self.available_map_tree is not None
        return list(self.available_map_tree.selection())

    def _open_source_root(self) -> None:
        self._open_path(self.source_root_var.get().strip(), "Kaynak klasör")

    def _open_sample_root(self) -> None:
        self._open_path(self.sample_root_var.get().strip(), "Referans klasör")

    def _open_output_root(self) -> None:
        self._open_path(self.output_root_var.get().strip(), "Çıktı klasörü")

    def _open_report_file(self) -> None:
        self._open_path(self.report_file_var.get().strip(), "Rapor dosyası")

    def _open_path(self, raw_path: str, label: str) -> None:
        if not raw_path:
            messagebox.showerror("Eksik alan", f"{label} yolu boş.")
            return
        path = Path(raw_path)
        if not path.exists():
            messagebox.showerror("Bulunamadı", f"{label} bulunamadı: {path}")
            return
        os.startfile(path)  # type: ignore[attr-defined]

    def _append_log(self, text: str) -> None:
        assert self.log_text is not None
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip() + "\n\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def parse_map_names(raw_text: str) -> list[str]:
    names: list[str] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line not in names:
            names.append(line)
    return names


def merge_map_names(base_names: list[str], extra_names: list[str]) -> list[str]:
    merged = list(base_names)
    for name in extra_names:
        normalized = name.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def discover_available_map_names(source_root: str | Path) -> list[str]:
    return [record.name for record in build_map_records(source_root)]


def run_gui() -> None:
    app = MapConverterGui()
    app.run()
