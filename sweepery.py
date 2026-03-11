import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk
from pathlib import Path
from datetime import datetime
import send2trash
import json
import os
import tkinter as _tk

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

BG          = "#0c0c0e"
BG_NAV      = "#111114"
BG_CARD     = "#18181c"
BG_CARD2    = "#111114"
BG_DEEP     = "#0e0e11"
BORDER      = "#2a2a32"
BORDER_LT   = "#3a3a46"

AMBER       = "#f59e0b"
AMBER_HOV   = "#d97706"
AMBER_DIM   = "#92400e"
AMBER_GLOW  = "#fbbf24"

ROSE        = "#fb7185"
ROSE_HOV    = "#f43f5e"
ROSE_DIM    = "#4c0519"

TEAL        = "#2dd4bf"
TEAL_HOV    = "#14b8a6"
TEAL_DIM    = "#042f2e"

TEXT        = "#f0f0f4"
TEXT_DIM    = "#9090a0"
TEXT_MUTED  = "#50505e"

BTN_SEC     = "#1e1e24"
BTN_SEC_HOV = "#2a2a34"

images          = []
index           = 0
to_delete       = []
to_keep         = []
thumb_photos    = []
_current_folder = None
_last_sort_mode = "name_asc"
_resume_session = None
_SESSION_FILE   = Path.home() / ".Sweepe_session.json"

_group_mode        = False
_date_groups       = {}
_group_progress    = {}
_group_sort_mode   = "date_desc"
_current_group_key = None

_expanded_years  = set()
_expanded_months = set()

# ── Persistent browser widgets (created once, reused) ──
_browser_outer      = None   # CTkFrame holding the scroll
_browser_scroll     = None   # CTkScrollableFrame
_browser_stats_lbl  = None   # stats label (updated in-place)

def _persist_session():
    if _resume_session is None:
        _SESSION_FILE.unlink(missing_ok=True)
        return
    try:
        data = {
            "folder":       _resume_session["folder"],
            "remaining":    [str(p) for p in _resume_session["remaining"]],
            "sort_mode":    _resume_session.get("sort_mode", "name_asc"),
            "count":        _resume_session["count"],
            "resume_index": _resume_session.get("resume_index", 0),
            "to_delete":    [str(p) for p in _resume_session.get("to_delete", [])],
            "to_keep":      [str(p) for p in _resume_session.get("to_keep",   [])],
        }
        _SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Sweepe] Could not save session: {e}")

def _load_resume_session():
    global _resume_session
    if not _SESSION_FILE.exists():
        return
    try:
        data      = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        if data.get("mode") == "group":
            _load_group_session(data)
            return
        remaining = [Path(p) for p in data.get("remaining", [])]
        to_del    = [Path(p) for p in data.get("to_delete", [])]
        to_kp     = [Path(p) for p in data.get("to_keep",   [])]
        remaining = [p for p in remaining if p.exists()]
        existing  = set(remaining)
        to_del    = [p for p in to_del if p in existing]
        to_kp     = [p for p in to_kp  if p in existing]
        if not remaining:
            _SESSION_FILE.unlink(missing_ok=True)
            return
        resume_index    = int(data.get("resume_index", 0))
        _resume_session = {
            "folder":       data["folder"],
            "remaining":    remaining,
            "sort_mode":    data.get("sort_mode", "name_asc"),
            "count":        len(remaining) - resume_index,
            "resume_index": resume_index,
            "to_delete":    to_del,
            "to_keep":      to_kp,
        }
    except Exception as e:
        print(f"[Sweepe] Could not load session: {e}")
        _resume_session = None

def _persist_group_session():
    try:
        gp_serial = {}
        for k, v in _group_progress.items():
            gp_serial[f"{k[0]},{k[1]},{k[2]}"] = {
                "delete": [str(p) for p in v.get("delete", [])],
                "keep":   [str(p) for p in v.get("keep",   [])],
            }
        dg_serial = {}
        for k, paths in _date_groups.items():
            dg_serial[f"{k[0]},{k[1]},{k[2]}"] = [str(p) for p in paths]
        data = {
            "mode":           "group",
            "folder":         _current_folder,
            "sort_mode":      _group_sort_mode,
            "date_groups":    dg_serial,
            "group_progress": gp_serial,
        }
        _SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Sweepe] Could not save group session: {e}")

def _load_group_session(data):
    global _group_mode, _current_folder, _group_sort_mode
    global _date_groups, _group_progress, _resume_session
    try:
        _group_mode      = True
        _current_folder  = data["folder"]
        _group_sort_mode = data.get("sort_mode", "date_desc")
        dg_serial = data.get("date_groups", {})
        gp_serial = data.get("group_progress", {})
        date_groups = {}
        for key_str, paths in dg_serial.items():
            parts = key_str.split(",")
            k = (int(parts[0]), int(parts[1]), int(parts[2]))
            date_groups[k] = [Path(p) for p in paths if Path(p).exists()]
        all_existing = set()
        for v in date_groups.values():
            all_existing.update(v)
        group_progress = {}
        for key_str, v in gp_serial.items():
            parts = key_str.split(",")
            k = (int(parts[0]), int(parts[1]), int(parts[2]))
            group_progress[k] = {
                "delete": [Path(p) for p in v.get("delete", []) if Path(p) in all_existing],
                "keep":   [Path(p) for p in v.get("keep",   []) if Path(p) in all_existing],
            }
        date_groups = {k: v for k, v in date_groups.items() if v}
        if not date_groups:
            _SESSION_FILE.unlink(missing_ok=True)
            _group_mode = False
            return
        _date_groups    = date_groups
        _group_progress = group_progress
        _resume_session = {"_is_group": True, "folder": _current_folder}
    except Exception as e:
        print(f"[Sweepe] Could not restore group session: {e}")
        _group_mode = False

def _clear_group_session():
    global _group_mode, _date_groups, _group_progress, _current_group_key
    _group_mode = False
    _date_groups = {}
    _group_progress = {}
    _current_group_key = None

def show_navbar(back_fn=None, show_done_btn=False, folder_name=None, _done_cmd=None):
    navbar.place(x=0, y=0, relwidth=1)
    if back_fn:
        back_btn.configure(command=back_fn)
        back_btn.place(x=16, y=8)
    else:
        back_btn.place_forget()
    if show_done_btn:
        cmd = _done_cmd if _done_cmd else ask_selesai_now
        done_btn.configure(command=cmd)
        done_btn.place(relx=1.0, x=-16, rely=0.5, anchor="e")
    else:
        done_btn.place_forget()
    nav_title.configure(text=folder_name if folder_name else "Sweepe")

def hide_navbar():
    navbar.place_forget()
    back_btn.place_forget()
    done_btn.place_forget()
    nav_title.configure(text="Sweepe")

def restore_windowed():
    try:
        app.state("normal")
    except Exception:
        try:
            app.attributes("-zoomed", False)
        except Exception:
            pass
    app.resizable(False, False)
    app.geometry("1060x720")
    center_window(1060, 720)

def maximize_window():
    app.resizable(True, True)
    try:
        app.state("zoomed")
    except Exception:
        try:
            app.attributes("-zoomed", True)
        except Exception:
            sw = app.winfo_screenwidth()
            sh = app.winfo_screenheight()
            app.geometry(f"{sw}x{sh}+0+0")

def center_window(w, h):
    sw = app.winfo_screenwidth()
    sh = app.winfo_screenheight()
    app.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

def _format_size(total_bytes):
    kb = total_bytes / 1024
    if kb < 1024:  return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:  return f"{mb:.1f} MB"
    return f"{mb/1024:.2f} GB"

def hide_viewer_widgets():
    canvas.place_forget()
    filename_label.place_forget()
    info_label.place_forget()
    counter_label.place_forget()
    undo_btn.place_forget()
    skip_btn.place_forget()
    carousel_canvas.place_forget()
    left_panel.place_forget()
    right_panel.place_forget()
    _pb_forget()
    app.unbind("<Configure>")

def _clear_summary_widgets():
    for w in app.winfo_children():
        if getattr(w, "_is_summary_widget", False):
            w.destroy()

def _clear_landing_extras():
    for w in app.winfo_children():
        if getattr(w, "_is_resume_widget", False):
            w.destroy()

def _clear_browser_widgets():
    """Hide (not destroy) the persistent browser shell; destroy one-off widgets."""
    global _browser_outer, _browser_scroll, _browser_stats_lbl
    for w in app.winfo_children():
        if getattr(w, "_is_browser_widget", False):
            w.place_forget()
    # destroy the persistent scroll frame so it gets rebuilt fresh on next open
    if _browser_outer and _browser_outer.winfo_exists():
        _browser_outer.destroy()
    _browser_outer     = None
    _browser_scroll    = None
    _browser_stats_lbl = None

def _save_resume_session(folder, all_images, flagged_delete, flagged_keep, sort_mode, resume_index=None):
    global _resume_session
    if resume_index is not None:
        _resume_session = {
            "folder":       folder,
            "remaining":    all_images,
            "sort_mode":    sort_mode,
            "count":        len(all_images) - resume_index,
            "resume_index": resume_index,
            "to_delete":    list(flagged_delete),
            "to_keep":      list(flagged_keep),
        }
    else:
        flagged   = set(flagged_delete) | set(flagged_keep)
        remaining = [p for p in all_images if p not in flagged]
        _resume_session = {
            "folder": folder, "remaining": remaining, "sort_mode": sort_mode,
            "count": len(remaining), "resume_index": 0,
            "to_delete": [], "to_keep": [],
        } if remaining else None
    _persist_session()

def _clear_resume_session():
    global _resume_session
    _resume_session = None
    _SESSION_FILE.unlink(missing_ok=True)

def show_landing():
    global _group_mode
    restore_windowed()
    _clear_summary_widgets()
    _clear_landing_extras()
    _clear_browser_widgets()

    label.place(relx=0.5, rely=0.08, anchor="center")
    sub.place(relx=0.5,   rely=0.155, anchor="center")
    divider_line.place(relx=0.5, rely=0.215, anchor="center")
    how_label.place(relx=0.5, rely=0.265, anchor="center")
    steps_frame.place(relx=0.5, rely=0.46, anchor="center")
    mulai_label.place(relx=0.5, rely=0.695, anchor="center")
    btn.place(relx=0.5,   rely=0.775, anchor="center")
    hide_navbar()

    if _resume_session:
        folder_name = Path(_resume_session["folder"]).name
        is_group    = _resume_session.get("_is_group", False)
        if is_group:
            total_all = sum(len(v) for v in _date_groups.values())
            rev_all   = sum(
                len(set(gp.get("delete",[])) | set(gp.get("keep",[])))
                for gp in _group_progress.values()
            )
            hint = f"{rev_all} / {total_all} foto direview  ·  per tanggal"
        else:
            ri        = _resume_session.get("resume_index", 0)
            n_total_r = len(_resume_session["remaining"])
            hint      = f"{n_total_r - ri} belum direview  ·  {ri} / {n_total_r} selesai"

        resume_card = ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=0,
                                   border_width=1, border_color=AMBER_DIM,
                                   width=500, height=76)
        resume_card._is_resume_widget = True
        resume_card.place(relx=0.5, rely=0.91, anchor="center")
        resume_card.pack_propagate(False)

        accent = _tk.Canvas(resume_card, width=3, bg=AMBER, highlightthickness=0)
        accent.place(x=0, y=0, width=3, relheight=1)

        text_block = ctk.CTkFrame(resume_card, fg_color="transparent")
        text_block.place(x=20, rely=0.5, anchor="w")
        ctk.CTkLabel(text_block, text=f'Resume  "{folder_name}"',
                     font=("Courier New", 12, "bold"), text_color=AMBER).pack(anchor="w")
        ctk.CTkLabel(text_block, text=hint,
                     font=("Consolas", 10), text_color=TEXT_MUTED).pack(anchor="w", pady=(2,0))

        btn_block = ctk.CTkFrame(resume_card, fg_color="transparent")
        btn_block.place(relx=1.0, x=-16, rely=0.5, anchor="e")

        def do_resume():
            _clear_landing_extras()
            if is_group:
                _hide_landing_widgets()
                maximize_window()
                show_date_browser()
            else:
                _resume_now()

        def do_discard():
            if is_group:
                _clear_group_session()
            _clear_resume_session()
            _clear_landing_extras()

        ctk.CTkButton(btn_block, text="Buang", command=do_discard,
                      fg_color="transparent", hover_color=BTN_SEC_HOV,
                      text_color=TEXT_MUTED, font=("Consolas", 10, "bold"),
                      border_width=1, border_color=BORDER_LT,
                      height=30, width=68, corner_radius=6).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_block, text="Lanjut →", command=do_resume,
                      fg_color=AMBER, hover_color=AMBER_HOV,
                      text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                      height=30, width=86, corner_radius=6).pack(side="left")

def _hide_landing_widgets():
    for w in [label, sub, divider_line, how_label, steps_frame, btn, mulai_label]:
        w.place_forget()
    _clear_landing_extras()

def _resume_now():
    global images, index, to_delete, to_keep, thumb_photos, _current_folder, _last_sort_mode
    if not _resume_session:
        return
    _current_folder = _resume_session["folder"]
    _last_sort_mode = _resume_session.get("sort_mode", "name_asc")
    all_imgs     = [p for p in _resume_session["remaining"] if p.exists()]
    resume_index = _resume_session.get("resume_index", 0)
    existing     = set(all_imgs)
    to_delete    = [p for p in _resume_session.get("to_delete", []) if p in existing]
    to_keep      = [p for p in _resume_session.get("to_keep",   []) if p in existing]
    images       = all_imgs
    index        = min(resume_index, max(0, len(images)-1))
    thumb_photos = []
    if not images:
        _clear_resume_session(); show_landing(); return
    for w in [label, sub, divider_line, how_label, steps_frame, btn, mulai_label]:
        w.place_forget()
    maximize_window()
    show_navbar(back_fn=_ask_back_from_viewer, show_done_btn=True, folder_name=Path(_current_folder).name)
    _place_viewer_widgets(app.winfo_width())
    app.bind("<Configure>", lambda e: reposition_panels())
    build_thumbnails()
    show_image()

def pick_folder():
    if _resume_session:
        _ask_discard_resume_then_pick()
    else:
        folder = filedialog.askdirectory(title="Pilih folder")
        if folder:
            show_sort_screen(folder)

def _ask_discard_resume_then_pick():
    _make_popup(460, 210,
        title="Ganti folder?",
        body="Sesi sebelumnya yang belum selesai akan hilang.\nKamu tidak bisa melanjutkannya lagi.",
        buttons=[
            ("Batal",            None,           BTN_SEC, BTN_SEC_HOV, TEXT),
            ("Ya, ganti folder", "_confirm_pick", AMBER,   AMBER_HOV,   "#0c0c0e"),
        ])

def _confirm_pick(popup):
    popup.destroy()
    _clear_resume_session()
    _clear_group_session()
    _clear_landing_extras()
    folder = filedialog.askdirectory(title="Pilih folder")
    if folder:
        show_sort_screen(folder)

def _make_popup(w, h, title, body, buttons, extra_widget_fn=None):
    popup = ctk.CTkToplevel(app)
    popup.title("")
    popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV)
    popup.grab_set()
    popup.geometry(f"{w}x{h}+{app.winfo_x()+(app.winfo_width()-w)//2}+{app.winfo_y()+(app.winfo_height()-h)//2}")
    _tk.Canvas(popup, height=2, bg=AMBER, highlightthickness=0).place(x=0, y=0, relwidth=1)
    ctk.CTkLabel(popup, text=title,
                 font=("Courier New", 16, "bold"), text_color=TEXT).place(relx=0.5, rely=0.22, anchor="center")
    ctk.CTkLabel(popup, text=body,
                 font=("Consolas", 11), text_color=TEXT_DIM,
                 justify="center").place(relx=0.5, rely=0.46, anchor="center")
    if extra_widget_fn:
        extra_widget_fn(popup)
    row = ctk.CTkFrame(popup, fg_color="transparent")
    row.place(relx=0.5, rely=0.82, anchor="center")
    for label_text, action, fg, hov, tc in buttons:
        if action is None:
            cmd = popup.destroy
        elif action == "_confirm_pick":
            cmd = lambda p=popup: _confirm_pick(p)
        else:
            cmd = lambda a=action, p=popup: (p.destroy(), a())
        ctk.CTkButton(row, text=label_text, command=cmd,
                      fg_color=fg, hover_color=hov, text_color=tc,
                      font=("Courier New", 11, "bold"),
                      height=36, width=max(100, len(label_text)*10+20),
                      corner_radius=7).pack(side="left", padx=6)
    return popup

def _ask_back_from_viewer():
    popup = ctk.CTkToplevel(app)
    popup.title("")
    popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV)
    popup.grab_set()
    pw, ph = 540, 240
    popup.geometry(f"{pw}x{ph}+{app.winfo_x()+(app.winfo_width()-pw)//2}+{app.winfo_y()+(app.winfo_height()-ph)//2}")
    _tk.Canvas(popup, height=2, bg=AMBER, highlightthickness=0).place(x=0, y=0, relwidth=1)
    ctk.CTkLabel(popup, text="Keluar dari sesi ini?",
                 font=("Courier New", 16, "bold"), text_color=TEXT).place(relx=0.5, rely=0.20, anchor="center")
    ctk.CTkLabel(popup, text="Progress kamu akan disimpan.\nKamu bisa lanjutin nanti dari halaman utama.",
                 font=("Consolas", 11), text_color=TEXT_DIM,
                 justify="center").place(relx=0.5, rely=0.42, anchor="center")
    stats = f"{len(to_delete)}  dihapus  ·  {len(to_keep)}  disimpan  ·  {index}  direview"
    ctk.CTkLabel(popup, text=stats,
                 font=("Consolas", 10), text_color=AMBER).place(relx=0.5, rely=0.61, anchor="center")
    row = ctk.CTkFrame(popup, fg_color="transparent")
    row.place(relx=0.5, rely=0.83, anchor="center")

    def do_save_exit():
        popup.destroy()
        _save_resume_session(_current_folder, images, to_delete, to_keep,
                             _last_sort_mode, resume_index=index)
        hide_viewer_widgets(); show_landing()

    def do_discard_exit():
        popup.destroy()
        _clear_resume_session()
        hide_viewer_widgets(); show_landing()

    ctk.CTkButton(row, text="Lanjut beberes", command=popup.destroy,
                  fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                  text_color=TEXT, font=("Courier New", 11, "bold"),
                  height=36, width=130, corner_radius=7).pack(side="left", padx=5)
    ctk.CTkButton(row, text="Simpan & keluar", command=do_save_exit,
                  fg_color=AMBER, hover_color=AMBER_HOV,
                  text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                  height=36, width=140, corner_radius=7).pack(side="left", padx=5)
    ctk.CTkButton(row, text="Keluar tanpa simpan", command=do_discard_exit,
                  fg_color="transparent", hover_color=ROSE_DIM,
                  text_color=ROSE, font=("Courier New", 11, "bold"),
                  border_width=1, border_color=ROSE,
                  height=36, width=160, corner_radius=7).pack(side="left", padx=5)

def _back_from_group_viewer():
    _save_group_viewer_progress()
    _persist_group_session()
    hide_viewer_widgets()
    show_date_browser()

_group_toggle_var = None

def show_sort_screen(folder):
    global _group_toggle_var
    restore_windowed()
    for w in [label, sub, divider_line, how_label, steps_frame, btn, mulai_label,
              canvas, filename_label, info_label, counter_label,
              undo_btn, skip_btn, carousel_canvas, left_panel, right_panel]:
        w.place_forget()
    _pb_forget(); _clear_summary_widgets(); _clear_landing_extras()
    _clear_browser_widgets()

    _group_toggle_var = ctk.BooleanVar(value=False)

    sort_title = ctk.CTkLabel(app, text="Urutkan Foto",
                               font=("Courier New", 30, "bold"), text_color=TEXT)
    sort_title.place(relx=0.5, rely=0.18, anchor="center")

    sort_sub = ctk.CTkLabel(app, text="Pilih urutan sebelum mulai bersih-bersih",
                             font=("Consolas", 12), text_color=TEXT_MUTED)
    sort_sub.place(relx=0.5, rely=0.255, anchor="center")

    sort_rule = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=260)
    sort_rule.place(relx=0.5, rely=0.305, anchor="center")

    toggle_card = ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=10,
                                border_width=1, border_color=BORDER,
                                width=500, height=58)
    toggle_card.place(relx=0.5, rely=0.80, anchor="center")
    toggle_card.pack_propagate(False)
    _tk.Canvas(toggle_card, height=2, bg=AMBER_DIM, highlightthickness=0).pack(fill="x")
    inner = ctk.CTkFrame(toggle_card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=18)
    ctk.CTkLabel(inner, text="Kelompokkan per Tanggal",
                 font=("Courier New", 12, "bold"), text_color=TEXT).pack(side="left")
    ctk.CTkLabel(inner, text="   review per tahun / bulan / minggu",
                 font=("Consolas", 9), text_color=TEXT_MUTED).pack(side="left")
    ctk.CTkSwitch(inner, text="", variable=_group_toggle_var,
                  progress_color=AMBER, fg_color=BTN_SEC,
                  button_color=TEXT_DIM, button_hover_color=AMBER_GLOW,
                  width=44, height=22).pack(side="right")

    sort_frame = ctk.CTkFrame(app, fg_color="transparent")
    sort_frame.place(relx=0.5, rely=0.62, anchor="center")

    all_sort_widgets = [sort_title, sort_sub, sort_rule, toggle_card, sort_frame]

    def _destroy_sort():
        for w in all_sort_widgets:
            w.place_forget()

    def go_back():
        _destroy_sort()
        show_landing()

    show_navbar(back_fn=go_back, show_done_btn=False)

    def start_with_sort(mode):
        _destroy_sort()
        if _group_toggle_var.get():
            _start_group_mode(folder, mode)
        else:
            load_images(folder, mode)

    sort_options = [
        ("Nama",    "nama file",   [("A → Z", "name_asc"), ("Z → A", "name_desc")]),
        ("Ukuran",  "ukuran file", [("Terkecil", "size_asc"), ("Terbesar", "size_desc")]),
        ("Tanggal", "tanggal",     [("Terbaru", "date_desc"), ("Terlama", "date_asc")]),
    ]

    for i, (title, desc, buttons) in enumerate(sort_options):
        card = ctk.CTkFrame(sort_frame, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER, width=240, height=148)
        card.grid(row=0, column=i, padx=10)
        card.pack_propagate(False)
        _tk.Canvas(card, height=2, bg=AMBER, highlightthickness=0).pack(fill="x")
        ctk.CTkLabel(card, text=title,
                     font=("Courier New", 14, "bold"), text_color=TEXT).pack(pady=(12, 2))
        ctk.CTkLabel(card, text=f"Urutkan dari {desc}",
                     font=("Consolas", 10), text_color=TEXT_MUTED).pack()
        btn_pair = ctk.CTkFrame(card, fg_color="transparent")
        btn_pair.pack(pady=(12, 0))
        for bl, mode in buttons:
            ctk.CTkButton(btn_pair, text=bl,
                          command=lambda m=mode: start_with_sort(m),
                          fg_color=BTN_SEC, hover_color=AMBER,
                          text_color=TEXT, font=("Consolas", 10, "bold"),
                          height=28, width=94, corner_radius=5).pack(side="left", padx=3)

def _place_viewer_widgets(sw):
    _pb_place()
    left_panel.place(x=0,        y=48, relheight=1)
    right_panel.place(x=sw-152,  y=48, relheight=1)
    carousel_canvas.place(x=152, y=48, width=sw-304, height=68)
    canvas.place(relx=0.5, rely=0.515, anchor="center")
    filename_label.place(relx=0.5, rely=0.852, anchor="center")
    info_label.place(relx=0.5,     rely=0.892, anchor="center")
    counter_label.place(relx=0.5,  rely=0.126, anchor="center")
    undo_btn.place(relx=0.5, x=-2, rely=0.966, anchor="e")
    skip_btn.place(relx=0.5, x=2,  rely=0.966, anchor="w")

def _update_progress():
    n = len(images)
    _pb_set(0 if n == 0 else index / n)

def load_images(folder, sort_mode="name_asc"):
    global images, index, to_delete, to_keep, thumb_photos, _current_folder, _last_sort_mode
    _current_folder = folder
    _last_sort_mode = sort_mode
    all_imgs = [f for f in Path(folder).iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    sort_map = {
        "name_asc":  lambda f: f.name.lower(),
        "name_desc": lambda f: f.name.lower(),
        "size_asc":  lambda f: f.stat().st_size,
        "size_desc": lambda f: f.stat().st_size,
        "date_desc": lambda f: f.stat().st_mtime,
        "date_asc":  lambda f: f.stat().st_mtime,
    }
    rev    = sort_mode in ("name_desc", "size_desc", "date_desc")
    images = sorted(all_imgs, key=sort_map.get(sort_mode, sort_map["name_asc"]), reverse=rev)
    index  = 0; to_delete = []; to_keep = []; thumb_photos = []
    maximize_window()
    show_navbar(back_fn=_ask_back_from_viewer, show_done_btn=True, folder_name=Path(folder).name)
    _place_viewer_widgets(app.winfo_width())
    app.bind("<Configure>", lambda e: reposition_panels())
    build_thumbnails(); show_image()

def _get_week_of_month(dt):
    first_day = dt.replace(day=1)
    adj       = dt.day + first_day.weekday()
    return int((adj - 1) / 7) + 1

def _build_date_groups(folder, sort_mode):
    all_imgs = [f for f in Path(folder).iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    sort_map = {
        "name_asc":  lambda f: f.name.lower(),
        "name_desc": lambda f: f.name.lower(),
        "size_asc":  lambda f: f.stat().st_size,
        "size_desc": lambda f: f.stat().st_size,
        "date_desc": lambda f: f.stat().st_mtime,
        "date_asc":  lambda f: f.stat().st_mtime,
    }
    rev      = sort_mode in ("name_desc", "size_desc", "date_desc")
    all_imgs = sorted(all_imgs, key=sort_map.get(sort_mode, sort_map["date_desc"]), reverse=rev)
    groups   = {}
    for p in all_imgs:
        try:
            dt   = datetime.fromtimestamp(p.stat().st_mtime)
            wk   = _get_week_of_month(dt)
            key  = (dt.year, dt.month, wk)
        except Exception:
            key  = (0, 0, 0)
        groups.setdefault(key, []).append(p)
    return groups

def _start_group_mode(folder, sort_mode):
    global _group_mode, _date_groups, _group_progress, _current_folder, _group_sort_mode, _resume_session
    _group_mode      = True
    _current_folder  = folder
    _group_sort_mode = sort_mode
    _date_groups     = _build_date_groups(folder, sort_mode)
    _group_progress  = {}
    _resume_session  = {"_is_group": True, "folder": folder}
    _persist_group_session()
    maximize_window()
    show_date_browser()

def _reset_group_keys(week_keys):
    for k in week_keys:
        if k in _group_progress:
            del _group_progress[k]
    _persist_group_session()

def _execute_group(paths, week_keys, label_text):
    global images, to_delete, to_keep, _current_group_key
    yr, mo, wk = week_keys[0] if week_keys else (0, 0, 0)
    if len(week_keys) > 1:
        if all(k[0] == yr and k[1] == mo for k in week_keys):
            _current_group_key = (yr, mo, 0)
        else:
            _current_group_key = (yr, 0, 0)
    else:
        _current_group_key = (yr, mo, wk)
    images    = list(paths)
    path_set  = set(paths)
    all_del   = []
    all_keep  = []
    for k in week_keys:
        gp = _group_progress.get(k, {})
        for p in gp.get("delete", []):
            if p in path_set and p not in all_del:
                all_del.append(p)
        for p in gp.get("keep", []):
            if p in path_set and p not in all_keep:
                all_keep.append(p)
    to_delete = all_del
    to_keep   = all_keep
    _clear_browser_widgets()
    hide_viewer_widgets()
    _show_group_summary()

# ══════════════════════════════════════════════════
#  DATE BROWSER  —  THE KEY FIX IS HERE
#  The outer frame + scrollable frame are created ONCE.
#  On expand/collapse we only clear and repopulate the
#  scroll content (no place_forget / destroy of the shell).
# ══════════════════════════════════════════════════

def show_date_browser():
    """
    First call: builds the full shell (navbar, title, stats label, outer frame,
    scrollable frame) then populates the tree.
    Subsequent calls via _rebuild_scroll(): ONLY repopulates the tree rows —
    the heavy CTkScrollableFrame is untouched, so no flicker.
    """
    global _browser_outer, _browser_scroll, _browser_stats_lbl

    hide_viewer_widgets()
    _clear_summary_widgets()

    # ── If the shell doesn't exist yet, build it ──────────────────────────────
    if _browser_outer is None or not _browser_outer.winfo_exists():
        restore_windowed()

        folder_name = Path(_current_folder).name
        show_navbar(
            back_fn=_exit_from_browser,
            show_done_btn=True,
            folder_name=folder_name,
            _done_cmd=_finish_all_groups,
        )

        # Title label
        title_lbl = ctk.CTkLabel(app, text="Pilih Grup Foto",
                                  font=("Courier New", 20, "bold"), text_color=TEXT)
        title_lbl._is_browser_widget = True
        title_lbl.place(relx=0.5, rely=0.09, anchor="center")

        # Stats label — we keep a reference so we can update it in _rebuild_scroll
        _browser_stats_lbl = ctk.CTkLabel(app, text="",
                                           font=("Consolas", 10), text_color=AMBER)
        _browser_stats_lbl._is_browser_widget = True
        _browser_stats_lbl.place(relx=0.5, rely=0.145, anchor="center")

        rule = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=560)
        rule._is_browser_widget = True
        rule.place(relx=0.5, rely=0.175, anchor="center")

        hint_lbl = ctk.CTkLabel(app, text="▶ untuk review  ·  ▼ untuk expand",
                                 font=("Consolas", 9), text_color=TEXT_MUTED)
        hint_lbl._is_browser_widget = True
        hint_lbl.place(relx=0.5, rely=0.955, anchor="center")

        # Outer frame
        _browser_outer = ctk.CTkFrame(app, fg_color="transparent", width=680, height=430)
        _browser_outer._is_browser_widget = True
        _browser_outer.place(relx=0.5, rely=0.595, anchor="center")
        _browser_outer.pack_propagate(False)

        # Scrollable frame — created ONCE, never destroyed on rebuild
        _browser_scroll = ctk.CTkScrollableFrame(
            _browser_outer, fg_color=BG_DEEP, corner_radius=10,
            border_width=1, border_color=BORDER,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BTN_SEC_HOV,
        )
        _browser_scroll.pack(fill="both", expand=True)

    # ── Always refresh stats label and tree rows ──────────────────────────────
    _refresh_browser_stats()
    _rebuild_scroll()


def _refresh_browser_stats():
    """Update the stats label text in-place (no widget rebuild)."""
    if _browser_stats_lbl is None or not _browser_stats_lbl.winfo_exists():
        return
    total_all  = sum(len(v) for v in _date_groups.values())
    all_del_s  = set(p for gp in _group_progress.values() for p in gp.get("delete", []))
    all_kp_s   = set(p for gp in _group_progress.values() for p in gp.get("keep",   []))
    rev_all    = len(all_del_s | all_kp_s)
    del_all    = len(all_del_s)
    _browser_stats_lbl.configure(
        text=f"{rev_all} / {total_all} direview  ·  {del_all} ditandai hapus"
    )


def _rebuild_scroll():
    """
    Clear only the rows inside the scrollable frame, then repopulate.
    The scrollable frame widget itself is NOT destroyed — so no flicker.
    """
    if _browser_scroll is None or not _browser_scroll.winfo_exists():
        return

    # Destroy just the row children (not the frame itself)
    for child in _browser_scroll.winfo_children():
        child.destroy()

    MONTH_NAMES = ["","Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    ROW_H    = 44
    IND_YEAR = 12
    IND_MON  = 36
    IND_WEEK = 64

    year_map = {}
    for (yr, mo, wk), paths in sorted(_date_groups.items(), reverse=True):
        year_map.setdefault(yr, {}).setdefault(mo, {})[wk] = paths

    def _prog(paths):
        ps = set(paths)
        all_decided = set()
        for gp in _group_progress.values():
            all_decided.update(gp.get("delete", []))
            all_decided.update(gp.get("keep",   []))
        return len(ps & all_decided), len(paths)

    def _launch(paths, key, lbl):
        _launch_group_viewer(paths, key, lbl)

    # ── only update stats + scroll rows, NO window-level destroy ──
    def _toggle_rebuild():
        _refresh_browser_stats()
        _rebuild_scroll()

    for yr in sorted(year_map.keys(), reverse=True):
        mo_map   = year_map[yr]
        yr_paths = [p for mm in mo_map.values() for wm in mm.values() for p in wm]
        yr_rev, yr_tot = _prog(yr_paths)
        yr_done  = yr_rev >= yr_tot and yr_tot > 0
        yr_exp   = yr in _expanded_years

        yr_row = ctk.CTkFrame(_browser_scroll, fg_color="transparent", height=ROW_H)
        yr_row.pack(fill="x", pady=2)
        yr_row.pack_propagate(False)

        ctk.CTkLabel(yr_row, text="", width=IND_YEAR).pack(side="left")

        arr = ctk.CTkButton(yr_row, text="▼" if yr_exp else "▶",
                            fg_color="transparent", hover_color=BTN_SEC_HOV,
                            text_color=AMBER, font=("Consolas", 11, "bold"),
                            width=26, height=26, corner_radius=4)
        def _tog_yr(y=yr):
            if y in _expanded_years: _expanded_years.discard(y)
            else:                    _expanded_years.add(y)
            _toggle_rebuild()
        arr.configure(command=_tog_yr)
        arr.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(yr_row, text=str(yr),
                     font=("Courier New", 14, "bold"),
                     text_color=TEAL if yr_done else TEXT,
                     anchor="w").pack(side="left")
        ctk.CTkLabel(yr_row, text=f"  {yr_rev} / {yr_tot}",
                     font=("Consolas", 10), text_color=TEXT_MUTED).pack(side="left")

        yr_wk_keys = [(yr, m, w) for m in mo_map.keys() for w in mo_map[m].keys()]

        def _rev_yr(p=yr_paths, k=(yr,0,0), l=str(yr)):  _launch(p, k, l)
        def _reset_yr(keys=yr_wk_keys):
            _reset_group_keys(keys); _toggle_rebuild()
        def _exec_yr(p=yr_paths, keys=yr_wk_keys):
            _execute_group(p, keys, str(yr))

        btn_grp_yr = ctk.CTkFrame(yr_row, fg_color="transparent")
        btn_grp_yr.pack(side="right", padx=6)
        ctk.CTkButton(btn_grp_yr, text="▶  Review semua", command=_rev_yr,
                      fg_color=BTN_SEC, hover_color=AMBER, text_color=TEXT_DIM,
                      font=("Consolas", 10, "bold"), height=28, width=130, corner_radius=5).pack(side="left", padx=2)
        ctk.CTkButton(btn_grp_yr, text="⚡", command=_exec_yr,
                      fg_color=BTN_SEC, hover_color=TEAL_DIM, text_color=TEAL,
                      font=("Consolas", 11, "bold"), height=28, width=32, corner_radius=5).pack(side="left", padx=2)
        ctk.CTkButton(btn_grp_yr, text="↺", command=_reset_yr,
                      fg_color=BTN_SEC, hover_color=ROSE_DIM, text_color=ROSE,
                      font=("Consolas", 12, "bold"), height=28, width=32, corner_radius=5).pack(side="left", padx=2)

        if not yr_exp:
            continue

        for mo in sorted(mo_map.keys(), reverse=True):
            wk_map   = mo_map[mo]
            mo_paths = [p for wm in wk_map.values() for p in wm]
            mo_rev, mo_tot = _prog(mo_paths)
            mo_done  = mo_rev >= mo_tot and mo_tot > 0
            mo_key   = (yr, mo)
            mo_exp   = mo_key in _expanded_months
            mo_name  = MONTH_NAMES[mo] if mo else "Unknown"

            mo_row = ctk.CTkFrame(_browser_scroll, fg_color=BG_CARD, height=ROW_H, corner_radius=6)
            mo_row.pack(fill="x", pady=1, padx=(IND_MON, 8))
            mo_row.pack_propagate(False)

            arr_mo = ctk.CTkButton(mo_row, text="▼" if mo_exp else "▶",
                                   fg_color="transparent", hover_color=BTN_SEC_HOV,
                                   text_color=AMBER_GLOW, font=("Consolas", 10, "bold"),
                                   width=22, height=22, corner_radius=4)
            def _tog_mo(mk=mo_key):
                if mk in _expanded_months: _expanded_months.discard(mk)
                else:                      _expanded_months.add(mk)
                _toggle_rebuild()
            arr_mo.configure(command=_tog_mo)
            arr_mo.pack(side="left", padx=(8, 4))

            ctk.CTkLabel(mo_row, text=mo_name,
                         font=("Courier New", 12, "bold"),
                         text_color=TEAL if mo_done else TEXT,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(mo_row, text=f"  {mo_rev} / {mo_tot}",
                         font=("Consolas", 10), text_color=TEXT_MUTED).pack(side="left")

            mo_wk_keys = [(yr, mo, w) for w in wk_map.keys()]

            def _rev_mo(p=mo_paths, k=(yr,mo,0), l=f"{mo_name} {yr}"):  _launch(p, k, l)
            def _reset_mo(keys=mo_wk_keys):
                _reset_group_keys(keys); _toggle_rebuild()
            def _exec_mo(p=mo_paths, keys=mo_wk_keys, l=f"{mo_name} {yr}"):
                _execute_group(p, keys, l)

            btn_grp_mo = ctk.CTkFrame(mo_row, fg_color="transparent")
            btn_grp_mo.pack(side="right", padx=4)
            ctk.CTkButton(btn_grp_mo, text="▶  Review", command=_rev_mo,
                          fg_color=BTN_SEC, hover_color=AMBER, text_color=TEXT_DIM,
                          font=("Consolas", 10, "bold"), height=24, width=90, corner_radius=5).pack(side="left", padx=2)
            ctk.CTkButton(btn_grp_mo, text="⚡", command=_exec_mo,
                          fg_color=BTN_SEC, hover_color=TEAL_DIM, text_color=TEAL,
                          font=("Consolas", 10, "bold"), height=24, width=28, corner_radius=5).pack(side="left", padx=2)
            ctk.CTkButton(btn_grp_mo, text="↺", command=_reset_mo,
                          fg_color=BTN_SEC, hover_color=ROSE_DIM, text_color=ROSE,
                          font=("Consolas", 11, "bold"), height=24, width=28, corner_radius=5).pack(side="left", padx=2)

            if not mo_exp:
                continue

            for wk in sorted(wk_map.keys()):
                wk_paths       = wk_map[wk]
                wk_rev, wk_tot = _prog(wk_paths)
                wk_done        = wk_rev >= wk_tot and wk_tot > 0
                wk_key         = (yr, mo, wk)
                wk_lbl         = f"Week {wk}" if wk else "Unknown"

                wk_row = ctk.CTkFrame(_browser_scroll, fg_color=BG_DEEP, height=ROW_H, corner_radius=4)
                wk_row.pack(fill="x", pady=1, padx=(IND_WEEK, 8))
                wk_row.pack_propagate(False)

                acc = _tk.Canvas(wk_row, width=2,
                                 bg=TEAL if wk_done else AMBER_DIM,
                                 highlightthickness=0)
                acc.place(x=0, y=4, width=2, height=ROW_H-8)

                ctk.CTkLabel(wk_row, text=wk_lbl,
                             font=("Consolas", 11, "bold"),
                             text_color=TEAL if wk_done else TEXT_DIM,
                             anchor="w").pack(side="left", padx=(12, 0))
                ctk.CTkLabel(wk_row, text=f"  {wk_rev} / {wk_tot}",
                             font=("Consolas", 10), text_color=TEXT_MUTED).pack(side="left")

                wk_del = len(_group_progress.get(wk_key, {}).get("delete", []))
                if wk_del > 0:
                    ctk.CTkLabel(wk_row, text=f"   {wk_del} hapus",
                                 font=("Consolas", 9), text_color=ROSE).pack(side="left")

                def _rev_wk(p=wk_paths, k=wk_key, l=f"{wk_lbl} · {mo_name} {yr}"):
                    _launch(p, k, l)
                def _reset_wk(k=wk_key):
                    _reset_group_keys([k]); _toggle_rebuild()
                def _exec_wk(p=wk_paths, k=wk_key, l=f"{wk_lbl} · {mo_name} {yr}"):
                    _execute_group(p, [k], l)

                btn_grp_wk = ctk.CTkFrame(wk_row, fg_color="transparent")
                btn_grp_wk.pack(side="right", padx=4)
                ctk.CTkButton(btn_grp_wk, text="▶", command=_rev_wk,
                              fg_color=BTN_SEC, hover_color=AMBER, text_color=AMBER,
                              font=("Consolas", 11, "bold"), height=26, width=32, corner_radius=5).pack(side="left", padx=2)
                ctk.CTkButton(btn_grp_wk, text="⚡", command=_exec_wk,
                              fg_color=BTN_SEC, hover_color=TEAL_DIM, text_color=TEAL,
                              font=("Consolas", 11, "bold"), height=26, width=32, corner_radius=5).pack(side="left", padx=2)
                ctk.CTkButton(btn_grp_wk, text="↺", command=_reset_wk,
                              fg_color=BTN_SEC, hover_color=ROSE_DIM, text_color=ROSE,
                              font=("Consolas", 12, "bold"), height=26, width=32, corner_radius=5).pack(side="left", padx=2)


def _exit_from_browser():
    _persist_group_session()
    _clear_browser_widgets()
    hide_navbar()
    show_landing()

def _finish_all_groups():
    _show_global_summary()

def _week_keys_for(group_key, year_map):
    yr, mo, wk = group_key
    if wk != 0:
        return [group_key]
    if mo != 0:
        return [(yr, mo, w) for w in year_map.get(yr, {}).get(mo, {}).keys()]
    return [(yr, m, w)
            for m in year_map.get(yr, {}).keys()
            for w in year_map[yr][m].keys()]

def _launch_group_viewer(paths, group_key, label_text):
    global images, index, to_delete, to_keep, thumb_photos, _current_group_key
    _current_group_key = group_key
    _clear_browser_widgets()
    hide_viewer_widgets()

    year_map = {}
    for (yr, mo, wk), wk_paths in _date_groups.items():
        year_map.setdefault(yr, {}).setdefault(mo, {})[wk] = wk_paths

    real_keys    = _week_keys_for(group_key, year_map)
    existing_del = []
    existing_kp  = []
    path_set     = set(paths)
    for wk_key in real_keys:
        gp = _group_progress.get(wk_key, {})
        for p in gp.get("delete", []):
            if p in path_set and p not in existing_del:
                existing_del.append(p)
        for p in gp.get("keep", []):
            if p in path_set and p not in existing_kp:
                existing_kp.append(p)

    to_delete    = existing_del
    to_keep      = existing_kp
    images       = list(paths)
    thumb_photos = []

    decided   = set(to_delete) | set(to_keep)
    undecided = [p for p in images if p not in decided]
    index     = images.index(undecided[0]) if undecided else 0

    maximize_window()
    show_navbar(
        back_fn=_back_from_group_viewer,
        show_done_btn=True,
        folder_name=label_text,
        _done_cmd=lambda: _ask_selesai_group(),
    )
    _place_viewer_widgets(app.winfo_width())
    app.bind("<Configure>", lambda e: reposition_panels())
    build_thumbnails()
    show_image()

def _save_group_viewer_progress():
    if _current_group_key is None:
        return
    yr, mo, wk = _current_group_key
    if wk != 0:
        _group_progress[_current_group_key] = {
            "delete": list(to_delete),
            "keep":   list(to_keep),
        }
        return
    path_to_wk = {}
    for (ky, km, kw), wk_paths in _date_groups.items():
        for p in wk_paths:
            path_to_wk[p] = (ky, km, kw)
    touched_keys = set()
    for p in list(to_delete) + list(to_keep):
        if p in path_to_wk:
            touched_keys.add(path_to_wk[p])
    path_set = set(images)
    for wk_key in touched_keys:
        existing = _group_progress.get(wk_key, {"delete": [], "keep": []})
        _group_progress[wk_key] = {
            "delete": [p for p in existing["delete"] if p not in path_set],
            "keep":   [p for p in existing["keep"]   if p not in path_set],
        }
    for p in to_delete:
        wk_key = path_to_wk.get(p)
        if wk_key:
            _group_progress.setdefault(wk_key, {"delete": [], "keep": []})
            lst = _group_progress[wk_key]["delete"]
            if p not in lst:
                lst.append(p)
    for p in to_keep:
        wk_key = path_to_wk.get(p)
        if wk_key:
            _group_progress.setdefault(wk_key, {"delete": [], "keep": []})
            lst = _group_progress[wk_key]["keep"]
            if p not in lst:
                lst.append(p)

def _ask_selesai_group():
    popup = ctk.CTkToplevel(app)
    popup.title(""); popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV); popup.grab_set()
    pw, ph = 420, 210
    popup.geometry(f"{pw}x{ph}+{app.winfo_x()+(app.winfo_width()-pw)//2}+"
                   f"{app.winfo_y()+(app.winfo_height()-ph)//2}")
    _tk.Canvas(popup, height=2, bg=AMBER, highlightthickness=0).place(x=0, y=0, relwidth=1)
    ctk.CTkLabel(popup, text="Selesai grup ini?",
                 font=("Courier New", 16, "bold"), text_color=TEXT).place(relx=0.5, rely=0.22, anchor="center")
    ctk.CTkLabel(popup, text="Foto yang belum dipilih akan dilewati.\nKamu bisa review grup lain.",
                 font=("Consolas", 11), text_color=TEXT_DIM,
                 justify="center").place(relx=0.5, rely=0.46, anchor="center")
    row = ctk.CTkFrame(popup, fg_color="transparent")
    row.place(relx=0.5, rely=0.80, anchor="center")
    ctk.CTkButton(row, text="Belum deh", command=popup.destroy,
                  fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                  text_color=TEXT, font=("Courier New", 11, "bold"),
                  height=36, width=130, corner_radius=7).pack(side="left", padx=8)
    def _go():
        popup.destroy()
        hide_viewer_widgets()
        _show_group_summary()
    ctk.CTkButton(row, text="Ya, lihat summary →", command=_go,
                  fg_color=AMBER, hover_color=AMBER_HOV,
                  text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                  height=36, width=170, corner_radius=7).pack(side="left", padx=8)

def _show_group_summary():
    hide_navbar(); restore_windowed(); _clear_summary_widgets()
    _save_group_viewer_progress()
    _persist_group_session()
    flagged = set(to_delete) | set(to_keep)
    skipped = [p for p in images if p not in flagged]
    n_del   = len(to_delete);  n_keep = len(to_keep)
    n_rev   = n_del + n_keep;  n_skip = len(skipped)
    n_total = len(images)
    tb      = sum(p.stat().st_size for p in to_delete if p.exists())
    ts      = _format_size(tb) if tb else "0 KB"
    def tag(w):
        w._is_summary_widget = True; return w
    tag(ctk.CTkLabel(app, text="Review Grup Ini",
                     font=("Courier New", 22, "bold"), text_color=TEXT)
        ).place(relx=0.5, rely=0.07, anchor="center")
    rc = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=320)
    rc._is_summary_widget = True
    rc.place(relx=0.5, rely=0.125, anchor="center")
    pills = tag(ctk.CTkFrame(app, fg_color="transparent"))
    pills.place(relx=0.5, rely=0.215, anchor="center")
    pill_data = [("Direview", n_rev, AMBER), ("Disimpan", n_keep, TEAL), ("Dihapus", n_del, ROSE)]
    if n_skip: pill_data.append(("Dilewati", n_skip, TEXT_MUTED))
    for col, (lbl, val, color) in enumerate(pill_data):
        pill = ctk.CTkFrame(pills, fg_color=BG_CARD, corner_radius=0,
                            border_width=1, border_color=color, width=132, height=70)
        pill.grid(row=0, column=col, padx=7); pill.pack_propagate(False)
        _tk.Canvas(pill, height=2, bg=color, highlightthickness=0).pack(fill="x")
        ctk.CTkLabel(pill, text=str(val),
                     font=("Courier New", 26, "bold"), text_color=color).pack(pady=(6,0))
        ctk.CTkLabel(pill, text=lbl,
                     font=("Consolas", 9), text_color=TEXT_MUTED).pack()
    tag(ctk.CTkLabel(app,
                     text=f"Ruang yang dikosongkan  ·  {ts}  dari {n_total} foto",
                     font=("Consolas", 10), text_color=TEXT_MUTED)
        ).place(relx=0.5, rely=0.345, anchor="center")
    list_card = tag(ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER, width=620, height=220))
    list_card.place(relx=0.5, rely=0.575, anchor="center")
    list_card.pack_propagate(False)
    hdr = ctk.CTkFrame(list_card, fg_color="transparent")
    hdr.pack(fill="x", padx=16, pady=(14,6))
    ctk.CTkLabel(hdr, text="Files yang akan dihapus",
                 font=("Courier New", 11, "bold"), text_color=ROSE).pack(side="left")
    ctk.CTkLabel(hdr, text=f"  {n_del}",
                 font=("Consolas", 11), text_color=TEXT_MUTED).pack(side="left")
    sc = ctk.CTkScrollableFrame(list_card, fg_color="transparent",
                                 scrollbar_button_color=BORDER,
                                 scrollbar_button_hover_color=BTN_SEC_HOV)
    sc.pack(fill="both", expand=True, padx=8, pady=(0,10))
    if n_del == 0:
        ctk.CTkLabel(sc, text="Tidak ada foto yang ditandai untuk dihapus.",
                     font=("Consolas", 11), text_color=TEXT_MUTED).pack(pady=20)
    else:
        for p in to_delete:
            rf = ctk.CTkFrame(sc, fg_color="transparent"); rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text="—", font=("Consolas", 9), text_color=ROSE, width=14).pack(side="left", padx=(4,6))
            ctk.CTkLabel(rf, text=p.name, font=("Consolas", 11), text_color=TEXT_DIM, anchor="w").pack(side="left", fill="x", expand=True)
            try:
                kb = p.stat().st_size/1024
                sz = f"{kb:.0f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
            except Exception: sz = "?"
            ctk.CTkLabel(rf, text=sz, font=("Consolas", 9), text_color=TEXT_MUTED, width=60).pack(side="right", padx=8)
    btn_row = tag(ctk.CTkFrame(app, fg_color="transparent"))
    btn_row.place(relx=0.5, rely=0.885, anchor="center")
    def _back_to_viewer():
        global index
        _clear_summary_widgets()
        if index >= len(images) and images: index = len(images) - 1
        maximize_window()
        show_navbar(back_fn=_back_from_group_viewer, show_done_btn=True,
                    folder_name="", _done_cmd=lambda: _ask_selesai_group())
        _place_viewer_widgets(app.winfo_width())
        app.bind("<Configure>", lambda e: reposition_panels())
        show_image()
    def _delete_back_to_browser():
        for p in to_delete:
            try: send2trash.send2trash(str(p))
            except Exception: pass
        list_card.place_forget(); btn_row.place_forget()
        _show_delete_success_popup(len(to_delete), go_home=False)
    ctk.CTkButton(btn_row, text="← Cek lagi", command=_back_to_viewer,
                  fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=150, corner_radius=8).pack(side="left", padx=8)
    ctk.CTkButton(btn_row, text="Hapus & kembali ke grup",
                  command=_delete_back_to_browser,
                  fg_color=ROSE, hover_color=ROSE_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=220, corner_radius=8).pack(side="left", padx=8)
    ctk.CTkButton(btn_row, text="Ke Daftar Grup →",
                  command=lambda: [_clear_summary_widgets(), show_date_browser()],
                  fg_color=BTN_SEC, hover_color=AMBER_DIM,
                  text_color=AMBER, font=("Courier New", 12, "bold"),
                  height=42, width=160, corner_radius=8).pack(side="left", padx=8)

def _show_global_summary():
    hide_navbar(); restore_windowed()
    _clear_summary_widgets(); _clear_browser_widgets()
    all_del  = list(dict.fromkeys(p for gp in _group_progress.values() for p in gp.get("delete",[])))
    all_keep = list(dict.fromkeys(p for gp in _group_progress.values() for p in gp.get("keep",[])))
    all_tot  = [p for paths in _date_groups.values() for p in paths]
    flagged  = set(all_del) | set(all_keep)
    skipped  = [p for p in all_tot if p not in flagged]
    n_del  = len(all_del);  n_keep = len(all_keep)
    n_rev  = n_del + n_keep; n_skip = len(skipped)
    n_tot  = len(all_tot)
    tb     = sum(p.stat().st_size for p in all_del if p.exists())
    ts     = _format_size(tb) if tb else "0 KB"
    def tag(w):
        w._is_summary_widget = True; return w
    tag(ctk.CTkLabel(app, text="Summary Keseluruhan",
                     font=("Courier New", 22, "bold"), text_color=TEXT)
        ).place(relx=0.5, rely=0.07, anchor="center")
    rc = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=360)
    rc._is_summary_widget = True
    rc.place(relx=0.5, rely=0.125, anchor="center")
    pills = tag(ctk.CTkFrame(app, fg_color="transparent"))
    pills.place(relx=0.5, rely=0.215, anchor="center")
    pill_data = [("Total", n_tot, AMBER), ("Direview", n_rev, AMBER_GLOW),
                 ("Disimpan", n_keep, TEAL), ("Dihapus", n_del, ROSE)]
    if n_skip: pill_data.append(("Dilewati", n_skip, TEXT_MUTED))
    for col, (lbl, val, color) in enumerate(pill_data):
        pill = ctk.CTkFrame(pills, fg_color=BG_CARD, corner_radius=0,
                            border_width=1, border_color=color, width=118, height=70)
        pill.grid(row=0, column=col, padx=6); pill.pack_propagate(False)
        _tk.Canvas(pill, height=2, bg=color, highlightthickness=0).pack(fill="x")
        ctk.CTkLabel(pill, text=str(val),
                     font=("Courier New", 24, "bold"), text_color=color).pack(pady=(6,0))
        ctk.CTkLabel(pill, text=lbl,
                     font=("Consolas", 9), text_color=TEXT_MUTED).pack()
    tag(ctk.CTkLabel(app,
                     text=f"Ruang yang akan dikosongkan  ·  {ts}",
                     font=("Consolas", 10), text_color=TEXT_MUTED)
        ).place(relx=0.5, rely=0.345, anchor="center")
    list_card = tag(ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER, width=620, height=220))
    list_card.place(relx=0.5, rely=0.575, anchor="center")
    list_card.pack_propagate(False)
    hdr = ctk.CTkFrame(list_card, fg_color="transparent")
    hdr.pack(fill="x", padx=16, pady=(14,6))
    ctk.CTkLabel(hdr, text="Semua files yang akan dihapus",
                 font=("Courier New", 11, "bold"), text_color=ROSE).pack(side="left")
    ctk.CTkLabel(hdr, text=f"  {n_del}",
                 font=("Consolas", 11), text_color=TEXT_MUTED).pack(side="left")
    sc = ctk.CTkScrollableFrame(list_card, fg_color="transparent",
                                 scrollbar_button_color=BORDER,
                                 scrollbar_button_hover_color=BTN_SEC_HOV)
    sc.pack(fill="both", expand=True, padx=8, pady=(0,10))
    if n_del == 0:
        ctk.CTkLabel(sc, text="Tidak ada foto yang ditandai untuk dihapus.",
                     font=("Consolas", 11), text_color=TEXT_MUTED).pack(pady=20)
    else:
        for p in all_del:
            rf = ctk.CTkFrame(sc, fg_color="transparent"); rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text="—", font=("Consolas", 9), text_color=ROSE, width=14).pack(side="left", padx=(4,6))
            ctk.CTkLabel(rf, text=p.name, font=("Consolas", 11), text_color=TEXT_DIM, anchor="w").pack(side="left", fill="x", expand=True)
            try:
                kb = p.stat().st_size/1024
                sz = f"{kb:.0f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
            except Exception: sz = "?"
            ctk.CTkLabel(rf, text=sz, font=("Consolas", 9), text_color=TEXT_MUTED, width=60).pack(side="right", padx=8)
    btn_row = tag(ctk.CTkFrame(app, fg_color="transparent"))
    btn_row.place(relx=0.5, rely=0.885, anchor="center")
    def _back_to_browser():
        _clear_summary_widgets()
        maximize_window()
        show_date_browser()
    def _delete_all_finish():
        for p in all_del:
            try: send2trash.send2trash(str(p))
            except Exception: pass
        list_card.place_forget(); btn_row.place_forget()
        deleted_set = set(all_del)
        for k in list(_group_progress.keys()):
            gp = _group_progress[k]
            gp["delete"] = [p for p in gp.get("delete", []) if p not in deleted_set]
            gp["keep"]   = [p for p in gp.get("keep",   []) if p not in deleted_set]
        for k in list(_date_groups.keys()):
            _date_groups[k] = [p for p in _date_groups[k] if p not in deleted_set]
            if not _date_groups[k]:
                del _date_groups[k]
        _show_delete_success_popup(n_del, go_home=True)
    ctk.CTkButton(btn_row, text="← Kembali ke grup", command=_back_to_browser,
                  fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=170, corner_radius=8).pack(side="left", padx=8)
    ctk.CTkButton(btn_row, text="Hapus semua sekarang",
                  command=_delete_all_finish,
                  fg_color=ROSE, hover_color=ROSE_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=220, corner_radius=8).pack(side="left", padx=8)
    if n_skip:
        tag(ctk.CTkLabel(app,
                         text=f"{n_skip} foto dilewati — bisa di-review lagi dari halaman utama",
                         font=("Consolas", 10), text_color=TEXT_MUTED)
            ).place(relx=0.5, rely=0.955, anchor="center")

def _show_delete_success_popup(count, go_home=False, skipped_groups=None):
    popup = ctk.CTkToplevel(app)
    popup.title(""); popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV); popup.grab_set()
    pw, ph = (480, 230) if go_home else (380, 200)
    popup.geometry(f"{pw}x{ph}+{app.winfo_x()+(app.winfo_width()-pw)//2}+"
                   f"{app.winfo_y()+(app.winfo_height()-ph)//2}")
    _tk.Canvas(popup, height=2, bg=TEAL, highlightthickness=0).place(x=0, y=0, relwidth=1)
    ctk.CTkLabel(popup, text="Berhasil dihapus",
                 font=("Courier New", 17, "bold"), text_color=TEAL).place(relx=0.5, rely=0.24, anchor="center")
    ctk.CTkLabel(popup, text=f"{count} foto dipindahkan ke Recycle Bin.",
                 font=("Consolas", 11), text_color=TEXT_DIM).place(relx=0.5, rely=0.43, anchor="center")
    if go_home:
        skipped_count = sum(len(v) for v in _date_groups.values()) - sum(
            len(set(gp.get("delete",[])) | set(gp.get("keep",[])))
            for gp in _group_progress.values()
        )
        if skipped_count > 0:
            ctk.CTkLabel(popup, text=f"{skipped_count} foto belum direview",
                         font=("Consolas", 10), text_color=AMBER).place(relx=0.5, rely=0.60, anchor="center")
        row = ctk.CTkFrame(popup, fg_color="transparent")
        row.place(relx=0.5, rely=0.82, anchor="center")
        def _go_home_clean():
            popup.destroy(); _clear_group_session(); _clear_resume_session(); show_landing()
        def _go_home_save():
            popup.destroy(); _persist_group_session(); show_landing()
        ctk.CTkButton(row, text="Ke Halaman Utama", command=_go_home_clean,
                      fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                      text_color=TEXT, font=("Courier New", 11, "bold"),
                      height=36, width=160, corner_radius=7).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Simpan sesi & ke Utama →", command=_go_home_save,
                      fg_color=AMBER, hover_color=AMBER_HOV,
                      text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                      height=36, width=210, corner_radius=7).pack(side="left", padx=6)
    else:
        def _close(): popup.destroy(); show_date_browser()
        ctk.CTkButton(popup, text="Ke Daftar Grup", command=_close,
                      fg_color=AMBER, hover_color=AMBER_HOV,
                      text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                      height=36, width=170, corner_radius=7).place(relx=0.5, rely=0.80, anchor="center")

def build_thumbnails():
    global thumb_photos
    thumb_photos = [None] * len(images)
    load_thumb_range(0, min(10, len(images)))

def load_thumb_range(start, end):
    TW, TH = 70, 52
    for i in range(start, end):
        if thumb_photos[i] is not None: continue
        try:
            img = Image.open(images[i])
            img.thumbnail((TW, TH), Image.LANCZOS)
            padded = Image.new("RGB", (TW, TH), (14, 14, 17))
            padded.paste(img, ((TW-img.width)//2, (TH-img.height)//2))
            thumb_photos[i] = ImageTk.PhotoImage(padded)
        except Exception:
            pass

def draw_carousel():
    if not carousel_canvas.winfo_ismapped(): return
    carousel_canvas.delete("all")
    cw = carousel_canvas.winfo_width()
    ch = carousel_canvas.winfo_height()
    if cw <= 1: return
    TW, TH = 70, 52
    STEP   = TW + 5
    cx     = cw // 2
    for i in range(len(images)):
        photo = thumb_photos[i]
        x     = cx + (i - index) * STEP - TW // 2
        if x + TW < 0 or x > cw: continue
        y = (ch - TH) // 2
        if photo:
            carousel_canvas.create_image(x, y, anchor="nw", image=photo)
        else:
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH, fill="#18181c", outline="")
        if images[i] in to_delete:
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH, fill="#fb7185", stipple="gray25", outline="")
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH, fill="", outline="#fb7185", width=1)
        elif images[i] in to_keep:
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH, fill="#2dd4bf", stipple="gray25", outline="")
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH, fill="", outline="#2dd4bf", width=1)
        if i == index:
            carousel_canvas.create_rectangle(x-2, y-2, x+TW+2, y+TH+2, fill="", outline=AMBER, width=2)
    for side_x in [0, cw-50]:
        carousel_canvas.create_rectangle(side_x, 0, side_x+50, ch, fill=BG_CARD2, outline="", stipple="gray75")

def on_carousel_click(event):
    global index
    cw, STEP, cx = carousel_canvas.winfo_width(), 75, carousel_canvas.winfo_width()//2
    for i in range(len(images)):
        x = cx + (i - index) * STEP - 35
        if x <= event.x <= x + 70:
            index = i; show_image(); break

def on_carousel_scroll(event):
    global index
    if not images: return
    if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
        index = max(0, index - 1)
    else:
        index = min(len(images) - 1, index + 1)
    show_image()

def reposition_panels():
    if right_panel.winfo_ismapped():
        sw = app.winfo_width()
        right_panel.place(x=sw-152, y=48, relheight=1)
        carousel_canvas.place(x=152, y=48, width=sw-304, height=68)
        draw_carousel()

def show_image():
    if index >= len(images):
        hide_viewer_widgets()
        if _group_mode:
            _show_group_summary()
        else:
            show_summary()
        return
    _update_progress()
    path = images[index]
    img  = Image.open(path)
    orig_w, orig_h = img.size
    sw, sh  = app.winfo_width(), app.winfo_height()
    cw = sw - 304 - 60
    ch = sh - 48 - 4 - 68 - 60 - 110
    img.thumbnail((cw, ch), Image.LANCZOS)
    photo = ImageTk.PhotoImage(img)
    canvas.configure(width=cw, height=ch)
    canvas.delete("all")
    canvas.image = photo
    canvas.create_image(cw//2, ch//2, image=photo, anchor="center")
    counter_label.configure(text=f"{index + 1}  /  {len(images)}")
    filename_label.configure(text=path.name)
    stat     = path.stat()
    size_kb  = stat.st_size / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
    date_str = datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y")
    info_label.configure(text=f"{size_str}   ·   {orig_w} × {orig_h}   ·   {date_str}")
    draw_carousel()
    load_thumb_range(max(0, index-10), min(len(images), index+11))

def swipe_delete(event=None):
    global index
    if index >= len(images): return
    path = images[index]
    if path in to_keep: to_keep.remove(path)
    if path not in to_delete: to_delete.append(path)
    index += 1; show_image()

def swipe_keep(event=None):
    global index
    if index >= len(images): return
    path = images[index]
    if path in to_delete: to_delete.remove(path)
    if path not in to_keep: to_keep.append(path)
    index += 1; show_image()

def undo(event=None):
    global index
    if index > 0:
        index -= 1
        path = images[index]
        if path in to_delete: to_delete.remove(path)
        if path in to_keep:   to_keep.remove(path)
        show_image()

def skip(event=None):
    global index
    if index >= len(images): return
    path = images[index]
    if path in to_delete: to_delete.remove(path)
    if path in to_keep:   to_keep.remove(path)
    index += 1; show_image()

def ask_selesai_now():
    if _group_mode:
        _ask_selesai_group()
    else:
        popup = ctk.CTkToplevel(app)
        popup.title(""); popup.resizable(False, False)
        popup.configure(fg_color=BG_NAV); popup.grab_set()
        pw, ph = 420, 210
        popup.geometry(f"{pw}x{ph}+{app.winfo_x()+(app.winfo_width()-pw)//2}+{app.winfo_y()+(app.winfo_height()-ph)//2}")
        _tk.Canvas(popup, height=2, bg=AMBER, highlightthickness=0).place(x=0, y=0, relwidth=1)
        ctk.CTkLabel(popup, text="Berhenti di sini?",
                     font=("Courier New", 16, "bold"), text_color=TEXT).place(relx=0.5, rely=0.22, anchor="center")
        ctk.CTkLabel(popup, text="Foto yang belum dipilih akan dilewati.\nKamu bisa lanjutin dari halaman utama.",
                     font=("Consolas", 11), text_color=TEXT_DIM,
                     justify="center").place(relx=0.5, rely=0.46, anchor="center")
        row = ctk.CTkFrame(popup, fg_color="transparent")
        row.place(relx=0.5, rely=0.80, anchor="center")
        ctk.CTkButton(row, text="Belum deh", command=popup.destroy,
                      fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                      text_color=TEXT, font=("Courier New", 11, "bold"),
                      height=36, width=130, corner_radius=7).pack(side="left", padx=8)
        ctk.CTkButton(row, text="Ya, selesai →",
                      command=lambda: [popup.destroy(), hide_viewer_widgets(), show_summary()],
                      fg_color=AMBER, hover_color=AMBER_HOV,
                      text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                      height=36, width=140, corner_radius=7).pack(side="left", padx=8)

def show_summary():
    hide_navbar(); restore_windowed(); _clear_summary_widgets()
    flagged    = set(to_delete) | set(to_keep)
    skipped    = [p for p in images if p not in flagged]
    n_skip     = len(skipped)
    n_del      = len(to_delete)
    n_keep     = len(to_keep)
    n_total    = len(images)
    n_reviewed = n_del + n_keep
    _save_resume_session(_current_folder, images, to_delete, to_keep, _last_sort_mode)
    total_bytes    = sum(p.stat().st_size for p in to_delete if p.exists())
    total_size_str = _format_size(total_bytes)
    def tag(w):
        w._is_summary_widget = True; return w
    tag(ctk.CTkLabel(app, text="Review & Konfirmasi",
                     font=("Courier New", 22, "bold"), text_color=TEXT)
        ).place(relx=0.5, rely=0.07, anchor="center")
    rule_c = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=320)
    rule_c._is_summary_widget = True
    rule_c.place(relx=0.5, rely=0.125, anchor="center")
    pills = tag(ctk.CTkFrame(app, fg_color="transparent"))
    pills.place(relx=0.5, rely=0.215, anchor="center")
    pill_data = [("Direview", n_reviewed, AMBER), ("Disimpan", n_keep, TEAL), ("Dihapus", n_del, ROSE)]
    if n_skip > 0:
        pill_data.append(("Dilewati", n_skip, TEXT_MUTED))
    for col, (lbl, val, color) in enumerate(pill_data):
        pill = ctk.CTkFrame(pills, fg_color=BG_CARD, corner_radius=0,
                            border_width=1, border_color=color, width=132, height=70)
        pill.grid(row=0, column=col, padx=7)
        pill.pack_propagate(False)
        _tk.Canvas(pill, height=2, bg=color, highlightthickness=0).pack(fill="x")
        ctk.CTkLabel(pill, text=str(val),
                     font=("Courier New", 26, "bold"), text_color=color).pack(pady=(6,0))
        ctk.CTkLabel(pill, text=lbl,
                     font=("Consolas", 9), text_color=TEXT_MUTED).pack()
    tag(ctk.CTkLabel(app,
                     text=f"Ruang yang dikosongkan  ·  {total_size_str}  dari {n_total} foto",
                     font=("Consolas", 10), text_color=TEXT_MUTED)
        ).place(relx=0.5, rely=0.345, anchor="center")
    list_card = tag(ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER, width=620, height=220))
    list_card.place(relx=0.5, rely=0.575, anchor="center")
    list_card.pack_propagate(False)
    hdr = ctk.CTkFrame(list_card, fg_color="transparent")
    hdr.pack(fill="x", padx=16, pady=(14, 6))
    ctk.CTkLabel(hdr, text="Files yang akan dihapus",
                 font=("Courier New", 11, "bold"), text_color=ROSE).pack(side="left")
    ctk.CTkLabel(hdr, text=f"  {n_del}",
                 font=("Consolas", 11), text_color=TEXT_MUTED).pack(side="left")
    scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent",
                                     scrollbar_button_color=BORDER,
                                     scrollbar_button_hover_color=BTN_SEC_HOV)
    scroll.pack(fill="both", expand=True, padx=8, pady=(0,10))
    if n_del == 0:
        ctk.CTkLabel(scroll, text="Tidak ada foto yang ditandai untuk dihapus.",
                     font=("Consolas", 11), text_color=TEXT_MUTED).pack(pady=20)
    else:
        for p in to_delete:
            rf = ctk.CTkFrame(scroll, fg_color="transparent")
            rf.pack(fill="x", pady=1)
            ctk.CTkLabel(rf, text="—", font=("Consolas", 9),
                         text_color=ROSE, width=14).pack(side="left", padx=(4,6))
            ctk.CTkLabel(rf, text=p.name,
                         font=("Consolas", 11), text_color=TEXT_DIM,
                         anchor="w").pack(side="left", fill="x", expand=True)
            try:
                kb = p.stat().st_size / 1024
                sz = f"{kb:.0f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
            except Exception:
                sz = "?"
            ctk.CTkLabel(rf, text=sz, font=("Consolas", 9),
                         text_color=TEXT_MUTED, width=60).pack(side="right", padx=8)
    btn_row = tag(ctk.CTkFrame(app, fg_color="transparent"))
    btn_row.place(relx=0.5, rely=0.885, anchor="center")
    def go_back_to_viewer():
        global index
        _clear_summary_widgets(); _clear_resume_session()
        if index >= len(images) and len(images) > 0:
            index = len(images) - 1
        maximize_window()
        show_navbar(back_fn=_ask_back_from_viewer, show_done_btn=True, folder_name=Path(_current_folder).name)
        _place_viewer_widgets(app.winfo_width())
        app.bind("<Configure>", lambda e: reposition_panels())
        show_image()
    ctk.CTkButton(btn_row, text="← Cek lagi", command=go_back_to_viewer,
                  fg_color=BTN_SEC, hover_color=BTN_SEC_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=160, corner_radius=8).pack(side="left", padx=10)
    ctk.CTkButton(btn_row, text="Hapus sekarang",
                  command=lambda: confirm_delete(list_card, btn_row),
                  fg_color=ROSE, hover_color=ROSE_HOV,
                  text_color=TEXT, font=("Courier New", 12, "bold"),
                  height=42, width=200, corner_radius=8).pack(side="left", padx=10)
    if n_skip > 0:
        tag(ctk.CTkLabel(app,
                         text=f"{n_skip} foto dilewati — bisa dilanjutin dari halaman utama",
                         font=("Consolas", 10), text_color=TEXT_MUTED)
            ).place(relx=0.5, rely=0.955, anchor="center")

def confirm_delete(list_card=None, btn_row=None):
    for p in to_delete:
        try: send2trash.send2trash(str(p))
        except Exception: pass
    if list_card: list_card.place_forget()
    if btn_row:   btn_row.place_forget()
    popup = ctk.CTkToplevel(app)
    popup.title(""); popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV); popup.grab_set()
    pw, ph = 360, 190
    popup.geometry(f"{pw}x{ph}+{app.winfo_x()+(app.winfo_width()-pw)//2}+{app.winfo_y()+(app.winfo_height()-ph)//2}")
    _tk.Canvas(popup, height=2, bg=TEAL, highlightthickness=0).place(x=0, y=0, relwidth=1)
    ctk.CTkLabel(popup, text="Berhasil dihapus",
                 font=("Courier New", 17, "bold"), text_color=TEAL).place(relx=0.5, rely=0.26, anchor="center")
    ctk.CTkLabel(popup, text=f"{len(to_delete)} foto dipindahkan ke Recycle Bin.",
                 font=("Consolas", 11), text_color=TEXT_DIM).place(relx=0.5, rely=0.46, anchor="center")
    if _resume_session:
        ctk.CTkLabel(popup, text="Foto yang dilewati siap dilanjutin dari halaman utama.",
                     font=("Consolas", 10), text_color=AMBER).place(relx=0.5, rely=0.63, anchor="center")
    ctk.CTkButton(popup, text="Ke Halaman Utama",
                  command=lambda: [popup.destroy(), show_landing()],
                  fg_color=AMBER, hover_color=AMBER_HOV,
                  text_color="#0c0c0e", font=("Courier New", 11, "bold"),
                  height=36, width=160, corner_radius=7).place(relx=0.5, rely=0.83, anchor="center")

# ══════════════════════════════════════════════════
#  APP BOOTSTRAP
# ══════════════════════════════════════════════════

ctk.set_appearance_mode("dark")
app = ctk.CTk()
app.title("Sweepe")
app.resizable(False, False)
app.configure(fg_color=BG)

# FIX: make the raw underlying Tk window background dark
# so any flash during page transitions is dark (#0c0c0e) instead of white
app.update_idletasks()
app.tk.call(app._w, "configure", "-background", BG)

center_window(1060, 720)

navbar = ctk.CTkFrame(app, fg_color=BG_NAV, height=48, corner_radius=0)
nav_rule = _tk.Canvas(navbar, height=1, bg=AMBER_DIM, highlightthickness=0)
nav_rule.place(x=0, rely=1.0, y=-1, relwidth=1)
nav_title = ctk.CTkLabel(navbar, text="Sweepe",
                          font=("Courier New", 13, "bold"), text_color=AMBER)
nav_title.place(relx=0.5, rely=0.5, anchor="center")
back_btn = ctk.CTkButton(navbar, text="← Back", command=show_landing,
                          fg_color="transparent", hover_color=BTN_SEC_HOV,
                          text_color=TEXT_DIM, font=("Consolas", 11, "bold"),
                          width=72, height=30, corner_radius=6)
done_btn = ctk.CTkButton(navbar, text="Selesai →", command=ask_selesai_now,
                          fg_color="transparent", hover_color=BTN_SEC_HOV,
                          text_color=TEAL, font=("Consolas", 11, "bold"),
                          width=90, height=30, corner_radius=6)

progress_bar_canvas = _tk.Canvas(app, height=3, bg=BG_DEEP, highlightthickness=0)

def _pb_set(value):
    progress_bar_canvas.delete("all")
    if value > 0:
        w = progress_bar_canvas.winfo_width()
        if w <= 1: w = app.winfo_width()
        progress_bar_canvas.create_rectangle(0, 0, int(w * value), 3, fill=AMBER, outline="")

def _pb_place():
    progress_bar_canvas.place(x=0, y=48, relwidth=1, height=3)

def _pb_forget():
    progress_bar_canvas.place_forget()

left_panel = ctk.CTkFrame(app, fg_color="transparent", width=152, corner_radius=0, border_width=0)
left_panel.pack_propagate(False)
left_panel.place_forget()
_tk.Canvas(left_panel, width=2, bg=ROSE, highlightthickness=0).place(relx=1.0, x=-2, y=0, width=2, relheight=1)
ctk.CTkLabel(left_panel, text="←", font=("Courier New", 62, "bold"), text_color=ROSE).place(relx=0.5, rely=0.34, anchor="center")
ctk.CTkLabel(left_panel, text="HAPUS", font=("Consolas", 18, "bold"), text_color=ROSE).place(relx=0.5, rely=0.46, anchor="center")
ctk.CTkLabel(left_panel, text="[ ← ]", font=("Consolas", 9), text_color="#3a1a1a").place(relx=0.5, rely=0.91, anchor="center")

def _lp_on(e):  left_panel.configure(fg_color=ROSE_DIM)
def _lp_off(e): left_panel.configure(fg_color="transparent")
def _lp_click(e):
    left_panel.configure(fg_color=ROSE_DIM)
    app.after(160, lambda: left_panel.configure(fg_color="transparent"))
    swipe_delete()
left_panel.bind("<Enter>", _lp_on)
left_panel.bind("<Leave>", _lp_off)
left_panel.bind("<Button-1>", _lp_click)
for child in left_panel.winfo_children():
    child.bind("<Enter>", _lp_on)
    child.bind("<Leave>", _lp_off)
    child.bind("<Button-1>", _lp_click)

right_panel = ctk.CTkFrame(app, fg_color="transparent", width=152, corner_radius=0, border_width=0)
right_panel.pack_propagate(False)
right_panel.place_forget()
_tk.Canvas(right_panel, width=2, bg=TEAL, highlightthickness=0).place(x=0, y=0, width=2, relheight=1)
ctk.CTkLabel(right_panel, text="→", font=("Courier New", 62, "bold"), text_color=TEAL).place(relx=0.5, rely=0.34, anchor="center")
ctk.CTkLabel(right_panel, text="SIMPAN", font=("Consolas", 18, "bold"), text_color=TEAL).place(relx=0.5, rely=0.46, anchor="center")
ctk.CTkLabel(right_panel, text="[ → ]", font=("Consolas", 9), text_color="#042222").place(relx=0.5, rely=0.91, anchor="center")

def _rp_on(e):  right_panel.configure(fg_color=TEAL_DIM)
def _rp_off(e): right_panel.configure(fg_color="transparent")
def _rp_click(e):
    right_panel.configure(fg_color=TEAL_DIM)
    app.after(160, lambda: right_panel.configure(fg_color="transparent"))
    swipe_keep()
right_panel.bind("<Enter>", _rp_on)
right_panel.bind("<Leave>", _rp_off)
right_panel.bind("<Button-1>", _rp_click)
for child in right_panel.winfo_children():
    child.bind("<Enter>", _rp_on)
    child.bind("<Leave>", _rp_off)
    child.bind("<Button-1>", _rp_click)

label = ctk.CTkLabel(app, text="Sweepe", font=("Courier New", 52, "bold"), text_color=TEXT)
label.place(relx=0.5, rely=0.08, anchor="center")
sub = ctk.CTkLabel(app, text="bersihkan galerimu, effortless.", font=("Consolas", 13), text_color=TEXT_MUTED)
sub.place(relx=0.5, rely=0.155, anchor="center")
divider_line = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=340)
divider_line.place(relx=0.5, rely=0.215, anchor="center")
how_label = ctk.CTkLabel(app, text="cara pakai", font=("Consolas", 11, "bold"), text_color=AMBER)
how_label.place(relx=0.5, rely=0.265, anchor="center")
steps_frame = ctk.CTkFrame(app, fg_color="transparent")
steps_frame.place(relx=0.5, rely=0.46, anchor="center")

steps = [
    ("01", "Pilih Folder",  "Pilih folder yang\nmau dibersihkan"),
    ("02", "Sort Foto",     "Nama, ukuran,\natau tanggal"),
    ("03", "Review",        "← Hapus  →  Simpan\n↓  Undo  ↑  Skip"),
    ("04", "Konfirmasi",    "Cek lagi sebelum\nhapus permanen"),
    ("05", "Recycle Bin",   "Aman di Bin,\nhapus manual kapanpun"),
]
for i, (num, title, desc) in enumerate(steps):
    card = ctk.CTkFrame(steps_frame, fg_color=BG_CARD, corner_radius=10,
                        border_width=1, border_color=BORDER, width=162, height=168)
    card.grid(row=0, column=i*2, padx=0)
    card.pack_propagate(False)
    _tk.Canvas(card, height=2, bg=AMBER_DIM, highlightthickness=0).pack(fill="x")
    ctk.CTkLabel(card, text=num, font=("Consolas", 11, "bold"), text_color=AMBER).pack(pady=(10, 2))
    ctk.CTkLabel(card, text=title, font=("Courier New", 13, "bold"), text_color=TEXT).pack()
    ctk.CTkLabel(card, text=desc, font=("Consolas", 10), text_color=TEXT_MUTED, justify="center").pack(pady=(6, 0))
    if i < len(steps) - 1:
        ctk.CTkLabel(steps_frame, text="·", font=("Courier New", 18), text_color=BORDER).grid(row=0, column=i*2+1, padx=8)

mulai_label = ctk.CTkLabel(app, text="mulai sekarang", font=("Consolas", 11, "bold"), text_color=TEXT_MUTED)
mulai_label.place(relx=0.5, rely=0.695, anchor="center")
btn = ctk.CTkButton(app, text="Pilih Folder  →", command=pick_folder,
                    fg_color=AMBER, hover_color=AMBER_HOV,
                    text_color="#0c0c0e", font=("Courier New", 15, "bold"),
                    height=48, width=220, corner_radius=8)
btn.place(relx=0.5, rely=0.775, anchor="center")

canvas          = ctk.CTkCanvas(app, bg=BG, highlightthickness=0)
carousel_canvas = ctk.CTkCanvas(app, bg=BG_CARD2, highlightthickness=0)
carousel_canvas.bind("<Button-1>",   on_carousel_click)
carousel_canvas.bind("<MouseWheel>", on_carousel_scroll)
carousel_canvas.bind("<Button-4>",   on_carousel_scroll)
carousel_canvas.bind("<Button-5>",   on_carousel_scroll)

filename_label = ctk.CTkLabel(app, text="", font=("Consolas", 10, "bold"), text_color=TEXT)
info_label     = ctk.CTkLabel(app, text="", font=("Consolas", 15), text_color=TEXT_MUTED)
counter_label  = ctk.CTkLabel(app, text="", font=("Courier New", 14, "bold"), text_color=AMBER)

undo_btn = ctk.CTkButton(app, text="UNDO  ↓", command=undo,
                          fg_color="transparent", hover_color=AMBER_DIM,
                          text_color=AMBER, font=("consolas", 18, "bold"),
                          border_width=1, border_color=AMBER_DIM,
                          height=62, width=800, corner_radius=0)
skip_btn = ctk.CTkButton(app, text="SKIP  ↑", command=skip,
                          fg_color="transparent", hover_color=AMBER_DIM,
                          text_color=AMBER, font=("consolas", 18, "bold"),
                          border_width=1, border_color=AMBER_DIM,
                          height=62, width=800, corner_radius=0)

# FIX: removed update_idletasks() from flash functions — was causing the flicker
def _flash_panel(panel, color):
    panel.configure(fg_color=color)
    app.after(180, lambda: panel.configure(fg_color="transparent"))

def _flash_btn(b):
    b.configure(fg_color=AMBER_DIM)
    app.after(180, lambda: b.configure(fg_color="transparent"))

def _kbd_delete(e=None):
    if left_panel.winfo_ismapped(): _flash_panel(left_panel, ROSE_DIM)
    swipe_delete()

def _kbd_keep(e=None):
    if right_panel.winfo_ismapped(): _flash_panel(right_panel, TEAL_DIM)
    swipe_keep()

def _kbd_undo(e=None):
    if undo_btn.winfo_ismapped(): _flash_btn(undo_btn)
    undo()

def _kbd_skip(e=None):
    if skip_btn.winfo_ismapped(): _flash_btn(skip_btn)
    skip()

app.bind("<Left>",  _kbd_delete)
app.bind("<Right>", _kbd_keep)
app.bind("<Down>",  _kbd_undo)
app.bind("<Up>",    _kbd_skip)

def _on_close():
    if left_panel.winfo_ismapped():
        if _group_mode:
            _back_from_group_viewer()
        else:
            _ask_back_from_viewer()
    else:
        app.destroy()

app.protocol("WM_DELETE_WINDOW", _on_close)

_load_resume_session()
show_landing()
app.mainloop()