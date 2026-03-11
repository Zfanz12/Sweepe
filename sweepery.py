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

# ══════════════════════════════════════════════════
#  PALETTE  —  Obsidian + Amber  (Dark Luxury)
# ══════════════════════════════════════════════════
BG          = "#0c0c0e"   # near-black, warm tinted
BG_NAV      = "#111114"   # navbar
BG_CARD     = "#18181c"   # card surface
BG_CARD2    = "#111114"   # carousel bg
BG_DEEP     = "#0e0e11"   # sunken areas
BORDER      = "#2a2a32"   # subtle dividers
BORDER_LT   = "#3a3a46"   # slightly lighter border

AMBER       = "#f59e0b"   # primary accent — warm amber
AMBER_HOV   = "#d97706"
AMBER_DIM   = "#92400e"   # muted amber for borders
AMBER_GLOW  = "#fbbf24"   # brighter for highlights

ROSE        = "#fb7185"   # delete / danger
ROSE_HOV    = "#f43f5e"
ROSE_DIM    = "#4c0519"

TEAL        = "#2dd4bf"   # keep / safe
TEAL_HOV    = "#14b8a6"
TEAL_DIM    = "#042f2e"

TEXT        = "#f0f0f4"   # primary
TEXT_DIM    = "#9090a0"   # secondary
TEXT_MUTED  = "#50505e"   # tertiary / hints

BTN_SEC     = "#1e1e24"
BTN_SEC_HOV = "#2a2a34"

# ── State ──
images          = []
index           = 0
to_delete       = []
to_keep         = []
thumb_photos    = []
_current_folder = None
_last_sort_mode = "name_asc"
_resume_session = None
_SESSION_FILE   = Path.home() / ".sweepery_session.json"


# ══════════════════════════════════════════════════
#  PERSISTENT SESSION
# ══════════════════════════════════════════════════

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
        print(f"[sweepery] Could not save session: {e}")

def _load_resume_session():
    global _resume_session
    if not _SESSION_FILE.exists():
        return
    try:
        data      = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
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
        print(f"[sweepery] Could not load session: {e}")
        _resume_session = None


# ══════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════

def show_navbar(back_fn=None, show_done_btn=False, folder_name=None):
    navbar.place(x=0, y=0, relwidth=1)
    if back_fn:
        back_btn.configure(command=back_fn)
        back_btn.place(x=16, y=8)
    else:
        back_btn.place_forget()
    if show_done_btn:
        done_btn.place(relx=1.0, x=-16, rely=0.5, anchor="e")
    else:
        done_btn.place_forget()
    if folder_name:
        nav_title.configure(text=folder_name)
    else:
        nav_title.configure(text="SWEEPERY")

def hide_navbar():
    navbar.place_forget()
    back_btn.place_forget()
    done_btn.place_forget()
    nav_title.configure(text="SWEEPERY")

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
    app.update_idletasks()

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


# ══════════════════════════════════════════════════
#  SESSION SAVE / CLEAR
# ══════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════
#  LANDING
# ══════════════════════════════════════════════════

def show_landing():
    restore_windowed()
    _clear_summary_widgets()
    _clear_landing_extras()

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
        ri          = _resume_session.get("resume_index", 0)
        n_total_r   = len(_resume_session["remaining"])

        resume_card = ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=0,
                                   border_width=1, border_color=AMBER_DIM,
                                   width=500, height=76)
        resume_card._is_resume_widget = True
        resume_card.place(relx=0.5, rely=0.91, anchor="center")
        resume_card.pack_propagate(False)

        # amber left accent bar (drawn on a canvas)
        accent = _tk.Canvas(resume_card, width=3, bg=AMBER, highlightthickness=0)
        accent.place(x=0, y=0, width=3, relheight=1)

        text_block = ctk.CTkFrame(resume_card, fg_color="transparent")
        text_block.place(x=20, rely=0.5, anchor="w")
        ctk.CTkLabel(text_block, text=f'Resume  "{folder_name}"',
                     font=("Courier New", 12, "bold"), text_color=AMBER).pack(anchor="w")
        ctk.CTkLabel(text_block,
                     text=f"{n_total_r - ri} belum direview  ·  {ri} / {n_total_r} selesai",
                     font=("Consolas", 10), text_color=TEXT_MUTED).pack(anchor="w", pady=(2,0))

        btn_block = ctk.CTkFrame(resume_card, fg_color="transparent")
        btn_block.place(relx=1.0, x=-16, rely=0.5, anchor="e")

        def do_resume():
            _clear_landing_extras()
            _resume_now()
        def do_discard():
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
            ("Batal",          None,   BTN_SEC, BTN_SEC_HOV, TEXT),
            ("Ya, ganti folder", "_confirm_pick", AMBER, AMBER_HOV, "#0c0c0e"),
        ])

def _confirm_pick(popup):
    popup.destroy()
    _clear_resume_session()
    _clear_landing_extras()
    folder = filedialog.askdirectory(title="Pilih folder")
    if folder:
        show_sort_screen(folder)


# ── Generic popup helper ──────────────────────────
def _make_popup(w, h, title, body, buttons, extra_widget_fn=None):
    """Create a styled modal popup. buttons = list of (label, action, fg, hover, text_color).
       action=None → close only; action="_confirm_pick" → special; otherwise callable."""
    popup = ctk.CTkToplevel(app)
    popup.title("")
    popup.resizable(False, False)
    popup.configure(fg_color=BG_NAV)
    popup.grab_set()
    popup.geometry(f"{w}x{h}+{app.winfo_x()+(app.winfo_width()-w)//2}+{app.winfo_y()+(app.winfo_height()-h)//2}")

    # top amber hairline
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


# ══════════════════════════════════════════════════
#  BACK FROM VIEWER
# ══════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════
#  SORT SCREEN
# ══════════════════════════════════════════════════

def show_sort_screen(folder):
    restore_windowed()
    for w in [label, sub, divider_line, how_label, steps_frame, btn, mulai_label,
              canvas, filename_label, info_label, counter_label,
              undo_btn, skip_btn, carousel_canvas, left_panel, right_panel]:
        w.place_forget()
    _pb_forget(); _clear_summary_widgets(); _clear_landing_extras()

    sort_title = ctk.CTkLabel(app, text="Urutkan Foto",
                               font=("Courier New", 30, "bold"), text_color=TEXT)
    sort_title.place(relx=0.5, rely=0.28, anchor="center")

    sort_sub = ctk.CTkLabel(app, text="Pilih urutan sebelum mulai bersih-bersih",
                             font=("Consolas", 12), text_color=TEXT_MUTED)
    sort_sub.place(relx=0.5, rely=0.365, anchor="center")

    # thin amber rule
    sort_rule = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=260)
    sort_rule.place(relx=0.5, rely=0.415, anchor="center")

    sort_frame = ctk.CTkFrame(app, fg_color="transparent")
    sort_frame.place(relx=0.5, rely=0.63, anchor="center")

    def go_back():
        sort_title.place_forget(); sort_sub.place_forget()
        sort_frame.place_forget(); sort_rule.place_forget()
        show_landing()

    show_navbar(back_fn=go_back, show_done_btn=False)

    def start_with_sort(mode):
        sort_title.place_forget(); sort_sub.place_forget()
        sort_frame.place_forget(); sort_rule.place_forget()
        load_images(folder, mode)

    sort_options = [
        ("Nama",    "nama file",   [("A → Z", "name_asc"), ("Z → A", "name_desc")]),
        ("Ukuran",  "ukuran file", [("Terkecil","size_asc"), ("Terbesar","size_desc")]),
        ("Tanggal", "tanggal",     [("Terbaru","date_desc"), ("Terlama","date_asc")]),
    ]

    for i, (title, desc, buttons) in enumerate(sort_options):
        card = ctk.CTkFrame(sort_frame, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER, width=240, height=148)
        card.grid(row=0, column=i, padx=10)
        card.pack_propagate(False)

        # top accent
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


# ══════════════════════════════════════════════════
#  IMAGE LOADER
# ══════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════
#  VIEWER
# ══════════════════════════════════════════════════

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
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH,
                fill="#fb7185", stipple="gray25", outline="")
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH,
                fill="", outline="#fb7185", width=1)
        elif images[i] in to_keep:
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH,
                fill="#2dd4bf", stipple="gray25", outline="")
            carousel_canvas.create_rectangle(x, y, x+TW, y+TH,
                fill="", outline="#2dd4bf", width=1)

        if i == index:
            carousel_canvas.create_rectangle(x-2, y-2, x+TW+2, y+TH+2,
                fill="", outline=AMBER, width=2)

    # fade edges
    for side_x, anchor_x in [(0, 0), (cw-50, cw-50)]:
        carousel_canvas.create_rectangle(side_x, 0, side_x+50, ch,
            fill=BG_CARD2, outline="", stipple="gray75")

def on_carousel_click(event):
    global index
    cw, STEP, cx = carousel_canvas.winfo_width(), 75, carousel_canvas.winfo_width()//2
    for i in range(len(images)):
        x = cx + (i - index) * STEP - 35
        if x <= event.x <= x + 70:
            index = i; show_image(); break

def reposition_panels():
    if right_panel.winfo_ismapped():
        sw = app.winfo_width()
        right_panel.place(x=sw-152, y=48, relheight=1)
        carousel_canvas.place(x=152, y=48, width=sw-304, height=68)
        draw_carousel()

def show_image():
    if index >= len(images):
        hide_viewer_widgets(); show_summary(); return
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


# ══════════════════════════════════════════════════
#  SELESAI POPUP
# ══════════════════════════════════════════════════

def ask_selesai_now():
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


# ══════════════════════════════════════════════════
#  SUMMARY SCREEN
# ══════════════════════════════════════════════════

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

    # Title + rule
    tag(ctk.CTkLabel(app, text="Review & Konfirmasi",
                     font=("Courier New", 22, "bold"), text_color=TEXT)
        ).place(relx=0.5, rely=0.07, anchor="center")

    rule_c = _tk.Canvas(app, height=1, bg=AMBER_DIM, highlightthickness=0, width=320)
    rule_c._is_summary_widget = True
    rule_c.place(relx=0.5, rely=0.125, anchor="center")

    # Stat pills
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

    # Size line
    tag(ctk.CTkLabel(app,
                     text=f"Ruang yang dikosongkan  ·  {total_size_str}  dari {n_total} foto",
                     font=("Consolas", 10), text_color=TEXT_MUTED)
        ).place(relx=0.5, rely=0.345, anchor="center")

    # File list
    list_card = tag(ctk.CTkFrame(app, fg_color=BG_CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER,
                                  width=620, height=220))
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

    # Buttons
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


# ══════════════════════════════════════════════════
#  CONFIRM DELETE
# ══════════════════════════════════════════════════

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
app.title("Sweepery")
app.resizable(False, False)
app.configure(fg_color=BG)
app.update_idletasks()
center_window(1060, 720)

# ── Navbar ──────────────────────────────────────
navbar = ctk.CTkFrame(app, fg_color=BG_NAV, height=48, corner_radius=0)

# amber hairline at the bottom of navbar
nav_rule = _tk.Canvas(navbar, height=1, bg=AMBER_DIM, highlightthickness=0)
nav_rule.place(x=0, rely=1.0, y=-1, relwidth=1)

nav_title = ctk.CTkLabel(navbar, text="SWEEPERY",
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

# ── Progress bar ─────────────────────────────────
progress_bar_canvas = _tk.Canvas(app, height=3, bg=BG_DEEP, highlightthickness=0)

def _pb_set(value):
    progress_bar_canvas.delete("all")
    if value > 0:
        w = progress_bar_canvas.winfo_width()
        if w <= 1: w = app.winfo_width()
        progress_bar_canvas.create_rectangle(0, 0, int(w * value), 3,
                                              fill=AMBER, outline="")

def _pb_place():
    progress_bar_canvas.place(x=0, y=48, relwidth=1, height=3)

def _pb_forget():
    progress_bar_canvas.place_forget()

# ── Left panel (Hapus) ───────────────────────────
left_panel = ctk.CTkFrame(app, fg_color="transparent", width=152,
                           corner_radius=0, border_width=0)
left_panel.pack_propagate(False)
left_panel.place_forget()

# vertical ROSE strip on right edge
_lp_strip = _tk.Canvas(left_panel, width=2, bg=ROSE, highlightthickness=0)
_lp_strip.place(relx=1.0, x=-2, y=0, width=2, relheight=1)

ctk.CTkLabel(left_panel, text="←",
             font=("Courier New", 62, "bold"), text_color=ROSE).place(relx=0.5, rely=0.34, anchor="center")
ctk.CTkLabel(left_panel, text="HAPUS",
             font=("Consolas", 18, "bold"), text_color=ROSE).place(relx=0.5, rely=0.46, anchor="center")
ctk.CTkLabel(left_panel, text="[ ← ]",
             font=("Consolas", 9), text_color="#3a1a1a").place(relx=0.5, rely=0.91, anchor="center")

def _lp_on(e):  left_panel.configure(fg_color=ROSE_DIM)
def _lp_off(e): left_panel.configure(fg_color="transparent")
def _lp_click(e):
    left_panel.configure(fg_color=ROSE_DIM)
    app.after(160, lambda: left_panel.configure(fg_color="transparent"))
    swipe_delete()
left_panel.bind("<Enter>",    _lp_on)
left_panel.bind("<Leave>",    _lp_off)
left_panel.bind("<Button-1>", _lp_click)
for child in left_panel.winfo_children():
    child.bind("<Enter>",    _lp_on)
    child.bind("<Leave>",    _lp_off)
    child.bind("<Button-1>", _lp_click)

# ── Right panel (Simpan) ─────────────────────────
right_panel = ctk.CTkFrame(app, fg_color="transparent", width=152,
                            corner_radius=0, border_width=0)
right_panel.pack_propagate(False)
right_panel.place_forget()

_rp_strip = _tk.Canvas(right_panel, width=2, bg=TEAL, highlightthickness=0)
_rp_strip.place(x=0, y=0, width=2, relheight=1)

ctk.CTkLabel(right_panel, text="→",
             font=("Courier New", 62, "bold"), text_color=TEAL).place(relx=0.5, rely=0.34, anchor="center")
ctk.CTkLabel(right_panel, text="SIMPAN",
             font=("Consolas", 18, "bold"), text_color=TEAL).place(relx=0.5, rely=0.46, anchor="center")
ctk.CTkLabel(right_panel, text="[ → ]",
             font=("Consolas", 9), text_color="#042222").place(relx=0.5, rely=0.91, anchor="center")

def _rp_on(e):  right_panel.configure(fg_color=TEAL_DIM)
def _rp_off(e): right_panel.configure(fg_color="transparent")
def _rp_click(e):
    right_panel.configure(fg_color=TEAL_DIM)
    app.after(160, lambda: right_panel.configure(fg_color="transparent"))
    swipe_keep()
right_panel.bind("<Enter>",    _rp_on)
right_panel.bind("<Leave>",    _rp_off)
right_panel.bind("<Button-1>", _rp_click)
for child in right_panel.winfo_children():
    child.bind("<Enter>",    _rp_on)
    child.bind("<Leave>",    _rp_off)
    child.bind("<Button-1>", _rp_click)

# ── Landing page ─────────────────────────────────
label = ctk.CTkLabel(app, text="SWEEPERY",
                      font=("Courier New", 52, "bold"), text_color=TEXT)
label.place(relx=0.5, rely=0.08, anchor="center")

sub = ctk.CTkLabel(app, text="bersihkan galerimu, effortless.",
                   font=("Consolas", 13), text_color=TEXT_MUTED)
sub.place(relx=0.5, rely=0.155, anchor="center")

divider_line = _tk.Canvas(app, height=1, bg=AMBER_DIM,
                           highlightthickness=0, width=340)
divider_line.place(relx=0.5, rely=0.215, anchor="center")

how_label = ctk.CTkLabel(app, text="cara pakai",
                          font=("Consolas", 11, "bold"), text_color=AMBER)
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

    # top amber rule per card
    _tk.Canvas(card, height=2, bg=AMBER_DIM,
               highlightthickness=0).pack(fill="x")

    ctk.CTkLabel(card, text=num,
                 font=("Consolas", 11, "bold"), text_color=AMBER).pack(pady=(10, 2))
    ctk.CTkLabel(card, text=title,
                 font=("Courier New", 13, "bold"), text_color=TEXT).pack()
    ctk.CTkLabel(card, text=desc,
                 font=("Consolas", 10), text_color=TEXT_MUTED,
                 justify="center").pack(pady=(6, 0))

    if i < len(steps) - 1:
        sep = ctk.CTkLabel(steps_frame, text="·",
                           font=("Courier New", 18), text_color=BORDER)
        sep.grid(row=0, column=i*2+1, padx=8)

mulai_label = ctk.CTkLabel(app, text="mulai sekarang",
                            font=("Consolas", 11, "bold"), text_color=TEXT_MUTED)
mulai_label.place(relx=0.5, rely=0.695, anchor="center")

btn = ctk.CTkButton(app, text="Pilih Folder  →", command=pick_folder,
                    fg_color=AMBER, hover_color=AMBER_HOV,
                    text_color="#0c0c0e", font=("Courier New", 15, "bold"),
                    height=48, width=220, corner_radius=8)
btn.place(relx=0.5, rely=0.775, anchor="center")

# ── Viewer widgets ───────────────────────────────
canvas          = ctk.CTkCanvas(app, bg=BG, highlightthickness=0)
carousel_canvas = ctk.CTkCanvas(app, bg=BG_CARD2, highlightthickness=0)
carousel_canvas.bind("<Button-1>", on_carousel_click)

filename_label = ctk.CTkLabel(app, text="",
                               font=("Consolas", 10, "bold"), text_color=TEXT)
info_label     = ctk.CTkLabel(app, text="",
                               font=("Consolas", 15), text_color=TEXT_MUTED)
counter_label  = ctk.CTkLabel(app, text="",
                               font=("Courier New", 14, "bold"), text_color=AMBER)

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

def _flash_panel(panel, color):
    panel.configure(fg_color=color)
    panel.update_idletasks()
    app.after(180, lambda: panel.configure(fg_color="transparent"))

def _flash_btn(btn):
    btn.configure(fg_color=AMBER_DIM)
    btn.update_idletasks()
    app.after(180, lambda: btn.configure(fg_color="transparent"))

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

# ── Window close handler ─────────────────────────
def _on_close():
    if left_panel.winfo_ismapped():
        _ask_back_from_viewer()
    else:
        app.destroy()

app.protocol("WM_DELETE_WINDOW", _on_close)

# ── Boot ─────────────────────────────────────────
_load_resume_session()
show_landing()

app.mainloop()