"""
Mirror Mirror — AI Image Transformation Tool
Supports: xAI Grok  |  Google Gemini
Requires: pip install pillow
Optional: pip install xai-sdk          (for xAI)
          pip install google-genai      (for Gemini)
          pip install opencv-python     (for webcam)
          pip install tkinterdnd2       (for drag-and-drop)
Run:      python mirror_mirror.py
"""

import io
import os
import threading
import tkinter as tk
from tkinter import filedialog, font, messagebox
import base64
import urllib.request

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "Pillow is required.\n\nRun:  pip install pillow"
    )
    raise SystemExit

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ── Soft imports (only needed when the user picks that provider) ──
try:
    import xai_sdk
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import cv2
    WEBCAM_AVAILABLE = True
except ImportError:
    WEBCAM_AVAILABLE = False


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
TITLE        = "Mirror Mirror"
SUBTITLE     = "on the wall"
INSTRUCTIONS = (
    "1. Load a source photo (file, URL, or webcam 📷).\n"
    "2. Choose your AI provider (xAI or Gemini) and enter your API key.\n"
    "3. Edit the prompt if desired, then click Generate.\n"
    "4. Right-click the result or use Save Output to keep it.\n\n"
    "Your API key is used only to call the selected provider's API directly — "
    "nothing is stored or transmitted elsewhere."
)
DEFAULT_PROMPT = (
    "MtF gender swap transformation of the subject; "
    "maintain pose and facial structure, but change body shape, "
    "clothing, and features to emphasize the new gender"
)

# xAI models
XAI_DEFAULT_MODEL = "grok-imagine-image"
XAI_ALT_MODEL     = "grok-imagine-image-pro"

# Gemini models
GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
GEMINI_ALT_MODEL     = "gemini-3-pro-image-preview"
GEMINI_FAST_MODEL    = "gemini-2.5-flash-image"

FRAME_W = 340
FRAME_H = 340

# Colour palette — purple/pink aesthetic
BG          = "#0a0a0f"
SURFACE     = "#111118"
SURFACE2    = "#18181f"
BORDER      = "#2a2535"
ACCENT_A    = "#c9a8ff"
ACCENT_B    = "#f0a8d8"
TEXT        = "#e8e0f0"
TEXT_DIM    = "#8a8099"
ERROR_COL   = "#f08090"
SUCCESS_COL = "#90f0c0"

# Toggle colours
TOGGLE_ON   = "#c9a8ff"
TOGGLE_OFF  = "#3a3545"
TOGGLE_KNOB = "#e8e0f0"


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def fit_image(pil_img, max_w, max_h):
    """Resize a PIL image to fit within max_w x max_h, preserving aspect ratio."""
    pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
    return pil_img


def exif_rotate(pil_img):
    """Apply EXIF orientation tag so phone photos aren't sideways."""
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(pil_img)
    except Exception:
        return pil_img


def load_image_from_path(path):
    """Open an image file and return a PIL Image, respecting EXIF rotation."""
    return exif_rotate(Image.open(path).convert("RGBA"))


def load_image_from_url(url):
    """Fetch an image from a URL and return a PIL Image, respecting EXIF rotation."""
    req = urllib.request.Request(url, headers={"User-Agent": "MirrorMirror/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    return exif_rotate(Image.open(io.BytesIO(data)).convert("RGBA"))


def pil_to_base64(pil_img, fmt="JPEG"):
    """Convert a PIL image to a base64-encoded data URI string."""
    if fmt == "JPEG":
        pil_img = pil_img.convert("RGB")   # JPEG doesn't support alpha
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return f"data:{mime};base64,{b64}"


# ─────────────────────────────────────────────
#  Toggle Switch Widget
# ─────────────────────────────────────────────
class ToggleSwitch(tk.Canvas):
    """A custom animated toggle switch widget."""

    def __init__(self, parent, label_left="xAI", label_right="Gemini",
                 command=None, **kwargs):
        self._switch_w = 52
        self._switch_h = 26
        self._knob_r = 9
        self._padding = 4

        # Total canvas: labels + switch
        super().__init__(parent, height=self._switch_h + 4,
                         bg=BG, highlightthickness=0, **kwargs)

        self._state = False   # False = left (xAI), True = right (Gemini)
        self._command = command
        self._label_left = label_left
        self._label_right = label_right
        self._anim_progress = 0.0  # 0.0 = left, 1.0 = right

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_click)

    def _on_configure(self, event=None):
        self._draw()

    def _draw(self):
        self.delete("all")
        cw = self.winfo_width()
        if cw < 10:
            return

        # Label measurements
        left_font = ("Helvetica", 10, "bold")
        right_font = ("Helvetica", 10, "bold")

        # Positions: [left_label]  [switch]  [right_label]
        switch_x = (cw - self._switch_w) // 2
        switch_y = 2
        mid_y = switch_y + self._switch_h // 2

        # Left label
        left_colour = ACCENT_A if not self._state else TEXT_DIM
        self.create_text(switch_x - 8, mid_y, text=self._label_left,
                         anchor="e", fill=left_colour, font=left_font)

        # Right label
        right_colour = ACCENT_B if self._state else TEXT_DIM
        self.create_text(switch_x + self._switch_w + 8, mid_y,
                         text=self._label_right,
                         anchor="w", fill=right_colour, font=right_font)

        # Track (rounded rectangle)
        track_colour = TOGGLE_ON if self._state else TOGGLE_OFF
        r = self._switch_h // 2
        x0, y0 = switch_x, switch_y
        x1, y1 = switch_x + self._switch_w, switch_y + self._switch_h
        self.create_arc(x0, y0, x0 + 2*r, y1, start=90, extent=180,
                        fill=track_colour, outline=track_colour)
        self.create_arc(x1 - 2*r, y0, x1, y1, start=-90, extent=180,
                        fill=track_colour, outline=track_colour)
        self.create_rectangle(x0 + r, y0, x1 - r, y1,
                              fill=track_colour, outline=track_colour)

        # Knob
        knob_travel = self._switch_w - 2 * self._padding - 2 * self._knob_r
        knob_cx = (switch_x + self._padding + self._knob_r
                   + self._anim_progress * knob_travel)
        knob_cy = mid_y
        self.create_oval(knob_cx - self._knob_r, knob_cy - self._knob_r,
                         knob_cx + self._knob_r, knob_cy + self._knob_r,
                         fill=TOGGLE_KNOB, outline=TOGGLE_KNOB)

    def _on_click(self, event=None):
        self._state = not self._state
        self._animate(0)

    def _animate(self, step):
        """Smooth slide animation over ~150 ms."""
        total_steps = 6
        if step <= total_steps:
            if self._state:
                self._anim_progress = step / total_steps
            else:
                self._anim_progress = 1.0 - step / total_steps
            self._draw()
            self.after(25, self._animate, step + 1)
        else:
            self._anim_progress = 1.0 if self._state else 0.0
            self._draw()
            if self._command:
                self._command(self._state)

    @property
    def is_gemini(self):
        return self._state

    def set_state(self, gemini: bool):
        """Programmatically set the toggle state."""
        self._state = gemini
        self._anim_progress = 1.0 if gemini else 0.0
        self._draw()


# ─────────────────────────────────────────────
#  Main application window
# ─────────────────────────────────────────────
class MirrorMirrorApp(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(820, 720)

        # State
        self._source_pil   = None   # Original PIL image (full size)
        self._source_url   = None   # URL if loaded from network
        self._result_pil   = None   # Generated PIL image
        self._tk_source    = None   # PhotoImage references (must be kept alive)
        self._tk_result    = None
        self._generating   = False
        self._cancel_gen   = False  # Flag to abort generation
        self._gen_id       = 0      # Increments each generation; stale callbacks ignored
        self._provider     = "xai"  # "xai" or "gemini"
        self._xai_key      = ""     # Stored API keys per provider
        self._gemini_key   = ""

        # Straggler queue: completed results from cancelled/superseded generations
        self._straggler_queue = []   # list of PIL Images, FIFO, max 5
        self._straggler_popup = None  # Toplevel reference (single popup)

        # Concurrent-request guard for Gemini
        self._gemini_inflight = False   # True while blocking API call is running
        self._pending_gen = None        # (api_key, prompt, model) to start when slot clears

        # Webcam state
        self._webcam_cap   = None   # cv2.VideoCapture
        self._webcam_active = False
        self._webcam_job   = None   # after() ID for frame polling
        self._tk_webcam    = None   # PhotoImage for webcam frame

        self._build_fonts()
        self._build_ui()
        self.update_idletasks()
        self._center_window()

        # Clean up webcam on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._stop_webcam()
        self.destroy()

    # ── Fonts ──────────────────────────────────
    def _build_fonts(self):
        self.f_title    = font.Font(family="Georgia",        size=28, weight="bold")
        self.f_subtitle = font.Font(family="Georgia",        size=13, slant="italic")
        self.f_label    = font.Font(family="Helvetica",      size=9,  weight="bold")
        self.f_body     = font.Font(family="Helvetica",      size=10)
        self.f_small    = font.Font(family="Helvetica",      size=9)
        self.f_mono     = font.Font(family="Courier New",    size=10)
        self.f_btn      = font.Font(family="Helvetica",      size=11, weight="bold")
        self.f_hint     = font.Font(family="Helvetica",      size=9,  slant="italic")

    # ── UI construction ─────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self, bg=BG, padx=28, pady=22)
        outer.pack(fill="both", expand=True)

        # Header (with toggle)
        self._build_header(outer)

        # Divider
        self._divider(outer)

        # Image panels row
        panels_row = tk.Frame(outer, bg=BG)
        panels_row.pack(fill="x", pady=(0, 16))
        panels_row.columnconfigure(0, weight=1)
        panels_row.columnconfigure(1, weight=0)
        panels_row.columnconfigure(2, weight=1)

        self._build_source_panel(panels_row)
        self._build_arrow(panels_row)
        self._build_output_panel(panels_row)

        # Controls
        self._build_controls(outer)

        # Status bar row: [⚡ Late Image notice] ... [status text]
        status_row = tk.Frame(outer, bg=BG)
        status_row.pack(fill="x", pady=(6, 0))

        # Straggler notice (left) — hidden until queue is non-empty
        self._straggler_notice = tk.Label(
            status_row,
            text="",
            bg=BG, fg=ERROR_COL,
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w"
        )
        self._straggler_notice.pack(side="left")
        self._straggler_notice.bind("<Button-1>", lambda e: self._show_straggler_popup())

        # Status text (right / center)
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(
            status_row, textvariable=self._status_var,
            bg=BG, fg=TEXT_DIM, font=self.f_small,
            anchor="center", wraplength=700
        )
        self._status_lbl.pack(side="left", expand=True, fill="x")

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", pady=(0, 8))

        tk.Label(hdr, text="✦  " + TITLE + "  ✦",
                 bg=BG, fg=ACCENT_A, font=self.f_title).pack()
        tk.Label(hdr, text=SUBTITLE,
                 bg=BG, fg=TEXT_DIM, font=self.f_subtitle).pack()

        instr = tk.Label(hdr, text=INSTRUCTIONS,
                         bg=BG, fg=TEXT_DIM, font=self.f_small,
                         justify="left", wraplength=760, anchor="w")
        instr.pack(fill="x", pady=(10, 0))

    def _divider(self, parent):
        fr = tk.Frame(parent, bg=BORDER, height=1)
        fr.pack(fill="x", pady=12)

    def _build_source_panel(self, parent):
        col = tk.Frame(parent, bg=BG)
        col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Label row with webcam icon
        label_row = tk.Frame(col, bg=BG)
        label_row.pack(fill="x", pady=(0, 6))

        tk.Label(label_row, text="SOURCE IMAGE", bg=BG, fg=TEXT_DIM,
                 font=self.f_label).pack(side="left")

        # Webcam button
        webcam_tooltip = "Open webcam" if WEBCAM_AVAILABLE else "Webcam unavailable (pip install opencv-python)"
        self._webcam_btn = tk.Button(
            label_row, text="📷",
            command=self._toggle_webcam,
            bg=BG, fg=ACCENT_A, relief="flat",
            font=("Helvetica", 14),
            cursor="hand2" if WEBCAM_AVAILABLE else "arrow",
            activebackground=SURFACE, activeforeground=ACCENT_B,
            bd=0, padx=4, pady=0
        )
        self._webcam_btn.pack(side="right")

        # The canvas frame (image display)
        self._src_frame = self._image_frame(col, side="source")
        self._src_frame.pack(fill="x")

        # Webcam controls overlay (capture + close buttons)
        # These sit on top of the source canvas via place()
        self._webcam_controls = tk.Frame(self._src_canvas, bg="")
        self._webcam_controls.configure(bg="")

        # Circular capture button — built as a canvas for the round shape
        self._capture_canvas = tk.Canvas(
            self._webcam_controls, width=50, height=50,
            bg=SURFACE, highlightthickness=0, bd=0
        )
        # Draw outer ring
        self._capture_canvas.create_oval(3, 3, 47, 47,
                                          outline=ACCENT_A, width=3, fill="")
        # Draw inner filled circle
        self._capture_canvas.create_oval(10, 10, 40, 40,
                                          fill=ACCENT_A, outline=ACCENT_A,
                                          tags="inner")
        self._capture_canvas.bind("<Button-1>", self._capture_webcam)
        self._capture_canvas.bind("<Enter>",
                                  lambda e: self._capture_canvas.itemconfigure(
                                      "inner", fill=ACCENT_B, outline=ACCENT_B))
        self._capture_canvas.bind("<Leave>",
                                  lambda e: self._capture_canvas.itemconfigure(
                                      "inner", fill=ACCENT_A, outline=ACCENT_A))
        self._capture_canvas.pack(side="left", padx=(0, 8))

        # Close (X) button for webcam
        self._webcam_close_btn = tk.Button(
            self._webcam_controls, text="✕",
            command=self._stop_webcam,
            bg=SURFACE, fg=ERROR_COL, relief="flat",
            font=("Helvetica", 14, "bold"),
            cursor="hand2", bd=0, padx=6, pady=0,
            activebackground=SURFACE2, activeforeground=ERROR_COL
        )
        self._webcam_close_btn.pack(side="left")

        # URL input row
        url_row = tk.Frame(col, bg=BG)
        url_row.pack(fill="x", pady=(8, 0))

        tk.Label(url_row, text="URL:", bg=BG, fg=TEXT_DIM,
                 font=self.f_small).pack(side="left", padx=(0, 6))

        self._url_var = tk.StringVar()
        url_entry = tk.Entry(url_row, textvariable=self._url_var,
                             bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                             relief="flat", font=self.f_small,
                             highlightthickness=1,
                             highlightbackground=BORDER,
                             highlightcolor=ACCENT_A)
        url_entry.pack(side="left", fill="x", expand=True)
        url_entry.bind("<Return>", lambda e: self._load_from_url())

        tk.Button(url_row, text="Load", command=self._load_from_url,
                  bg=SURFACE2, fg=ACCENT_A, relief="flat",
                  font=self.f_small, padx=8, cursor="hand2",
                  activebackground=SURFACE, activeforeground=ACCENT_A
                  ).pack(side="left", padx=(6, 0))

        # File button
        btn_row = tk.Frame(col, bg=BG)
        btn_row.pack(fill="x", pady=(6, 0))

        browse_label = "Browse File…  (or drag & drop above)" if DND_AVAILABLE else "Browse File…"
        tk.Button(btn_row, text=browse_label,
                  command=self._browse_file,
                  bg=SURFACE, fg=TEXT, relief="flat",
                  font=self.f_small, padx=10, pady=5,
                  cursor="hand2",
                  activebackground=SURFACE2, activeforeground=ACCENT_A
                  ).pack(side="left")

    def _build_output_panel(self, parent):
        col = tk.Frame(parent, bg=BG)
        col.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        # Label row with AI provider toggle
        out_label_row = tk.Frame(col, bg=BG)
        out_label_row.pack(fill="x", pady=(0, 6))

        tk.Label(out_label_row, text="TRANSFORMED IMAGE", bg=BG, fg=TEXT_DIM,
                 font=self.f_label).pack(side="left")

        # AI Provider toggle (compact, upper-right of output panel)
        self._toggle = ToggleSwitch(
            out_label_row, label_left="xAI", label_right="Gemini",
            command=self._on_provider_toggle, width=160
        )
        self._toggle.pack(side="right")

        self._out_frame = self._image_frame(col, side="output")
        self._out_frame.pack(fill="x")

        # Overlay frame sits on top of the canvas using place()
        self._overlay = tk.Frame(self._out_canvas, bg="#0a0a0f")
        self._overlay_text = tk.Text(
            self._overlay,
            bg="#0a0a0f", fg=ACCENT_A,
            font=("Courier New", 9),
            relief="flat", bd=0,
            state="disabled",
            wrap="word",
            highlightthickness=0,
            padx=10, pady=10,
            cursor="arrow",
        )
        self._overlay_text.pack(fill="both", expand=True)
        self._overlay_lines = []
        self._ellipsis_job = None
        self._ellipsis_count = 0

        # Save button
        self._save_btn = tk.Button(
            col, text="Save Output…",
            command=self._save_output,
            bg=SURFACE, fg=ACCENT_B, relief="flat",
            font=self.f_small, padx=10, pady=5,
            cursor="hand2",
            activebackground=SURFACE2, activeforeground=ACCENT_B,
            state="disabled"
        )
        self._save_btn.pack(anchor="w", pady=(6, 0))

    def _image_frame(self, parent, side="source"):
        """Create a fixed-size bordered canvas for displaying images."""
        border = tk.Frame(parent, bg=BORDER, padx=1, pady=1)

        canvas = tk.Canvas(
            border,
            width=FRAME_W, height=FRAME_H,
            bg=SURFACE, highlightthickness=0
        )
        canvas.pack()

        # Placeholder text
        placeholder = "Drop a photo here or\nenter a URL below" if side == "source" else "Your reflection\nawaits…"
        canvas.create_text(
            FRAME_W // 2, FRAME_H // 2,
            text=placeholder,
            fill=TEXT_DIM,
            font=self.f_hint,
            justify="center",
            tags="placeholder"
        )

        # Register drag-and-drop on source canvas if available
        if side == "source" and DND_AVAILABLE:
            canvas.drop_target_register(DND_FILES)
            canvas.dnd_bind("<<Drop>>", self._on_drop)

        # Store canvas reference
        if side == "source":
            self._src_canvas = canvas
        else:
            self._out_canvas = canvas

        return border

    def _build_arrow(self, parent):
        mid = tk.Frame(parent, bg=BG)
        mid.grid(row=0, column=1, sticky="ns", padx=4)

        # Vertically centred arrow
        spacer = tk.Frame(mid, bg=BG, height=FRAME_H // 2 - 20)
        spacer.pack()
        tk.Label(mid, text="→", bg=BG, fg=BORDER,
                 font=font.Font(family="Helvetica", size=28)).pack()

    def _build_controls(self, parent):
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(fill="x", pady=(4, 0))

        # ── Prompt ──
        tk.Label(ctrl, text="TRANSFORMATION PROMPT",
                 bg=BG, fg=TEXT_DIM, font=self.f_label).pack(anchor="w")

        self._prompt_text = tk.Text(
            ctrl, height=4, wrap="word",
            bg=SURFACE, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=self.f_body,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT_A,
            padx=10, pady=8
        )
        self._prompt_text.insert("1.0", DEFAULT_PROMPT)
        self._prompt_text.pack(fill="x", pady=(4, 12))

        # ── Bottom row: key + model + generate ──
        bottom = tk.Frame(ctrl, bg=BG)
        bottom.pack(fill="x")

        # API Key
        key_col = tk.Frame(bottom, bg=BG)
        key_col.pack(side="left", fill="x", expand=True, padx=(0, 16))

        self._key_label_var = tk.StringVar(value="XAI API KEY")
        self._key_label = tk.Label(key_col, textvariable=self._key_label_var,
                                   bg=BG, fg=TEXT_DIM, font=self.f_label)
        self._key_label.pack(anchor="w")

        self._key_var = tk.StringVar()
        key_entry = tk.Entry(
            key_col, textvariable=self._key_var,
            show="•", bg=SURFACE, fg=TEXT,
            insertbackground=TEXT, relief="flat",
            font=self.f_mono,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT_A
        )
        key_entry.pack(fill="x", ipady=6, pady=(4, 0))

        # Model toggle
        self._model_col = tk.Frame(bottom, bg=BG)
        self._model_col.pack(side="left", padx=(0, 16))

        tk.Label(self._model_col, text="MODEL",
                 bg=BG, fg=TEXT_DIM, font=self.f_label).pack(anchor="w")

        self._model_var = tk.StringVar(value=XAI_DEFAULT_MODEL)
        self._model_radios = []
        self._build_model_radios()

        # Generate button
        self._gen_btn = tk.Button(
            bottom, text="Generate",
            command=self._on_generate,
            bg=ACCENT_A, fg=BG,
            relief="flat", font=self.f_btn,
            padx=24, pady=10,
            cursor="hand2",
            activebackground=ACCENT_B,
            activeforeground=BG
        )
        self._gen_btn.pack(side="left", anchor="s")

    def _build_model_radios(self):
        """Create model radio buttons for the current provider."""
        # Remove old radios
        for rb in self._model_radios:
            rb.destroy()
        self._model_radios.clear()

        if self._provider == "xai":
            models = (XAI_DEFAULT_MODEL, XAI_ALT_MODEL)
            self._model_var.set(XAI_DEFAULT_MODEL)
        else:
            # Cheapest → mid (default) → most powerful
            models = (GEMINI_FAST_MODEL, GEMINI_DEFAULT_MODEL, GEMINI_ALT_MODEL)
            self._model_var.set(GEMINI_DEFAULT_MODEL)

        for model in models:
            rb = tk.Radiobutton(
                self._model_col, text=model,
                variable=self._model_var, value=model,
                bg=BG, fg=TEXT_DIM,
                selectcolor=SURFACE2,
                activebackground=BG, activeforeground=ACCENT_A,
                font=self.f_small
            )
            rb.pack(anchor="w")
            self._model_radios.append(rb)

    # ── Provider toggle ────────────────────────
    def _on_provider_toggle(self, is_gemini):
        """Called when the toggle switch changes state."""
        # Save current key before switching
        current_key = self._key_var.get().strip()
        if self._provider == "xai":
            self._xai_key = current_key
        else:
            self._gemini_key = current_key

        # Switch provider
        self._provider = "gemini" if is_gemini else "xai"
        self._key_label_var.set("GEMINI API KEY" if is_gemini else "XAI API KEY")
        self._build_model_radios()

        # Restore the saved key for the new provider
        self._key_var.set(self._gemini_key if is_gemini else self._xai_key)

    # ── Window centering ────────────────────────
    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Webcam ──────────────────────────────────
    def _toggle_webcam(self):
        """Start or stop the webcam preview."""
        if not WEBCAM_AVAILABLE:
            self._set_status(
                "Webcam requires OpenCV.  Run:  pip install opencv-python",
                "error"
            )
            return

        if self._webcam_active:
            self._stop_webcam()
        else:
            self._start_webcam()

    def _start_webcam(self):
        """Open the webcam and start streaming frames to the source canvas."""
        try:
            self._webcam_cap = cv2.VideoCapture(0)
            if not self._webcam_cap.isOpened():
                self._set_status("Could not open webcam.", "error")
                self._webcam_cap = None
                return
        except Exception as e:
            self._set_status(f"Webcam error: {e}", "error")
            return

        self._webcam_active = True
        self._webcam_btn.config(fg=ACCENT_B)  # Visual cue it's active
        self._set_status("Webcam active — click ⏺ to capture, ✕ to cancel.", "dim")

        # Show capture controls at the bottom-centre of the source canvas
        self._webcam_controls.place(relx=0.5, rely=0.92, anchor="center")

        self._poll_webcam()

    def _poll_webcam(self):
        """Read a frame from the webcam and display it on the source canvas."""
        if not self._webcam_active or self._webcam_cap is None:
            return

        ret, frame = self._webcam_cap.read()
        if ret:
            # Convert BGR (OpenCV) → RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(frame_rgb)

            # Fit to canvas
            display = pil_frame.copy()
            fit_image(display, FRAME_W, FRAME_H)
            tk_img = ImageTk.PhotoImage(display)

            self._src_canvas.delete("all")
            self._src_canvas.create_image(
                FRAME_W // 2, FRAME_H // 2,
                anchor="center", image=tk_img
            )
            self._tk_webcam = tk_img  # Keep reference

            # Store the full-res frame for potential capture
            self._webcam_last_frame = pil_frame

        # Poll again in ~33 ms (~30 fps)
        self._webcam_job = self.after(33, self._poll_webcam)

    def _capture_webcam(self, event=None):
        """Capture the current webcam frame as the source image."""
        if hasattr(self, '_webcam_last_frame') and self._webcam_last_frame:
            self._source_pil = self._webcam_last_frame.convert("RGBA")
            self._source_url = None
            self._set_status("Source image captured from webcam.", "success")

        self._stop_webcam()

        # Re-display the captured image (not the live feed)
        if self._source_pil:
            self._show_image(self._src_canvas, self._source_pil)

    def _stop_webcam(self):
        """Stop the webcam and clean up."""
        self._webcam_active = False

        if self._webcam_job:
            self.after_cancel(self._webcam_job)
            self._webcam_job = None

        if self._webcam_cap is not None:
            self._webcam_cap.release()
            self._webcam_cap = None

        self._webcam_btn.config(fg=ACCENT_A)  # Reset icon colour

        # Hide capture controls
        self._webcam_controls.place_forget()

        # If no source image was captured, restore the placeholder
        if self._source_pil is None:
            self._src_canvas.delete("all")
            placeholder = "Drop a photo here or\nenter a URL below"
            self._src_canvas.create_text(
                FRAME_W // 2, FRAME_H // 2,
                text=placeholder,
                fill=TEXT_DIM,
                font=self.f_hint,
                justify="center",
                tags="placeholder"
            )

    # ── Drag and drop ───────────────────────────
    def _on_drop(self, event):
        """Handle a file dropped onto the source canvas."""
        # tkinterdnd2 wraps paths in braces if they contain spaces
        path = event.data.strip().strip("{}")
        if not path:
            return
        try:
            img = load_image_from_path(path)
            self._source_pil = img
            self._source_url = None
            self._show_image(self._src_canvas, img)
            self._set_status("Source image loaded from dropped file.", "dim")
        except Exception as e:
            self._set_status(f"Could not load dropped file: {e}", "error")

    # ── Image loading ───────────────────────────
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select source image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            img = load_image_from_path(path)
            self._source_pil = img
            self._source_url = None
            self._show_image(self._src_canvas, img)
            self._set_status("Source image loaded from file.", "dim")
        except Exception as e:
            self._set_status(f"Could not load file: {e}", "error")

    def _load_from_url(self):
        url = self._url_var.get().strip()
        if not url:
            self._set_status("Please enter a URL.", "error")
            return
        self._set_status("Loading image from URL…", "dim")
        self.update_idletasks()

        def worker():
            try:
                img = load_image_from_url(url)
                self._source_pil = img
                self._source_url = url
                self.after(0, lambda: self._show_image(self._src_canvas, img))
                self.after(0, lambda: self._set_status("Source image loaded from URL.", "dim"))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Could not load URL: {e}", "error"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_image(self, canvas, pil_img):
        """Fit and display a PIL image on a canvas."""
        display = pil_img.copy()
        fit_image(display, FRAME_W, FRAME_H)
        tk_img = ImageTk.PhotoImage(display)

        canvas.delete("all")
        canvas.create_image(FRAME_W // 2, FRAME_H // 2, anchor="center", image=tk_img)

        # Keep reference to avoid garbage collection
        if canvas is self._src_canvas:
            self._tk_source = tk_img
        else:
            self._tk_result = tk_img

    # ── Loading overlay ─────────────────────────
    def _show_overlay(self):
        """Place the terminal overlay over the output canvas."""
        self._overlay_lines = []
        self._overlay_text.config(state="normal")
        self._overlay_text.delete("1.0", "end")
        self._overlay_text.config(state="disabled")
        self._overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._ellipsis_count = 0
        self._tick_ellipsis()

    def _hide_overlay(self):
        """Remove the overlay."""
        if self._ellipsis_job:
            self.after_cancel(self._ellipsis_job)
            self._ellipsis_job = None
        self._overlay.place_forget()

    def _log(self, message):
        """Append a line to the overlay terminal and scroll to bottom."""
        self._overlay_lines.append(message)
        self._overlay_text.config(state="normal")
        self._overlay_text.delete("1.0", "end")
        self._overlay_text.insert("end", "\n".join(self._overlay_lines))
        self._overlay_text.see("end")
        self._overlay_text.config(state="disabled")

    def _tick_ellipsis(self):
        """Animate a trailing ellipsis on the last line every 500 ms."""
        if not self._overlay_lines:
            self._ellipsis_job = self.after(500, self._tick_ellipsis)
            return
        dots = "." * ((self._ellipsis_count % 3) + 1)
        self._ellipsis_count += 1
        # Rewrite last line with updated dots
        base = self._overlay_lines[-1].rstrip(". ")
        display_lines = self._overlay_lines[:-1] + [base + dots]
        self._overlay_text.config(state="normal")
        self._overlay_text.delete("1.0", "end")
        self._overlay_text.insert("end", "\n".join(display_lines))
        self._overlay_text.see("end")
        self._overlay_text.config(state="disabled")
        self._ellipsis_job = self.after(500, self._tick_ellipsis)

    # ── Generation ──────────────────────────────
    # NOTE (future dev): A Cancel button was partially implemented here but
    # removed for v2.0 because Gemini's API doesn't support request cancellation
    # mid-flight. Pressing Cancel had no effect on the in-progress HTTP call;
    # the API would still complete (or fail) and bill the user. The straggler
    # queue below was designed to surface those late-arriving results — it is
    # preserved so a future provider with true async cancellation support can
    # wire up to it. See _add_straggler() and _show_straggler_popup().

    def _on_generate(self):
        if self._generating:
            return

        api_key = self._key_var.get().strip()
        prompt  = self._prompt_text.get("1.0", "end").strip()
        model   = self._model_var.get()

        if not api_key:
            label = "Gemini" if self._provider == "gemini" else "xAI"
            self._set_status(f"Please enter your {label} API key.", "error")
            return
        if not prompt:
            self._set_status("Please enter a prompt.", "error")
            return
        if self._source_pil is None:
            self._set_status("Please load a source image first.", "error")
            return

        # Warn on likely wrong-provider key
        if self._provider == "gemini" and api_key.startswith("xai-"):
            self._set_status(
                "⚠ That looks like an xAI key. Toggle to xAI or enter a Gemini key.",
                "error"
            )
            return
        if self._provider == "xai" and not api_key.startswith("xai-"):
            self._set_status(
                "⚠ xAI keys usually start with 'xai-'. Check your key or toggle to Gemini.",
                "error"
            )
            return

        # Check provider SDK availability
        if self._provider == "xai" and not XAI_AVAILABLE:
            self._set_status(
                "xAI SDK not installed.  Run:  pip install xai-sdk", "error"
            )
            return
        if self._provider == "gemini" and not GEMINI_AVAILABLE:
            self._set_status(
                "Google GenAI not installed.  Run:  pip install google-genai",
                "error"
            )
            return

        self._generating = True
        self._gen_id += 1
        current_gen_id = self._gen_id

        # Disable the button so the user can't queue a second request while
        # waiting.  The Generate label and style stay the same.
        self._gen_btn.config(state="disabled")
        self._save_btn.config(state="disabled")
        self._set_status("", "dim")

        # Show overlay terminal
        self._show_overlay()
        self._log(f"Provider: {self._provider.upper()}")
        self._log(f"Model   : {model}")
        ellipsis = "\u2026"
        short_prompt = prompt[:60] + (ellipsis if len(prompt) > 60 else "")
        self._log(f"Prompt  : {short_prompt}")
        self._log("\u2500" * 38)

        # Start elapsed time counter
        self._start_elapsed_timer()

        if self._provider == "xai":
            self._generate_xai(api_key, prompt, model, current_gen_id)
        else:
            self._generate_gemini(api_key, prompt, model, current_gen_id)

    def _generate_xai(self, api_key, prompt, model, gen_id):
        """Run generation via xAI Grok API (existing logic)."""
        self._log("Encoding source image to base64")
        image_data_uri = pil_to_base64(self._source_pil, fmt="JPEG")
        img_kb = len(image_data_uri) * 3 // 4 // 1024
        self.after(0, lambda: self._log(f"Encoded  : {img_kb} KB"))
        self.after(0, lambda: self._log("Connecting to api.x.ai"))

        def worker():
            try:
                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda: self._log("Authenticating"))
                os.environ["XAI_API_KEY"] = api_key
                client = xai_sdk.Client()

                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda: self._log("Sending image + prompt to Grok"))
                response = client.image.sample(
                    prompt=prompt,
                    model=model,
                    image_url=image_data_uri,
                )

                if self._cancel_gen or gen_id != self._gen_id:
                    return

                result_url = response.url
                self.after(0, lambda: self._log("Response received"))
                self.after(0, lambda: self._log(f"URL: {result_url[:48]}\u2026"))
                self.after(0, lambda: self._log("Downloading result image"))

                result_img = load_image_from_url(result_url)

                # Stale gen: route to straggler queue instead of dropping
                if gen_id != self._gen_id:
                    self.after(0, lambda img=result_img: self._add_straggler(img))
                    return
                self._result_pil = result_img
                self.after(0, lambda: self._log("Done"))
                self.after(0, lambda: self._on_result(result_img))

            except Exception as e:
                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda err=e: self._log(f"ERROR: {err}"))
                self.after(0, lambda err=e: self._on_error(str(err)))

        threading.Thread(target=worker, daemon=True).start()

    def _generate_gemini(self, api_key, prompt, model, gen_id):
        """Run generation via Google Gemini API."""
        self._log("Preparing source image for Gemini")

        # Prepare a copy of the source image in RGB for Gemini
        source_rgb = self._source_pil.convert("RGB")
        if "pro" in model:
            self._log("Note: Pro model includes a Thinking step — may take 1-3 min")
        self.after(0, lambda: self._log("Connecting to Gemini API"))

        def worker():
            client = None
            try:
                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda: self._log("Authenticating"))
                client = genai.Client(api_key=api_key)

                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda: self._log(f"Sending image + prompt to {model}"))
                self.after(0, lambda: self._log("Safety: least-restrictive mode"))
                self._gemini_inflight = True   # Block concurrent requests while waiting
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, source_rgb],
                    config=genai_types.GenerateContentConfig(
                        response_modalities=["Image"],
                        safety_settings=[
                            genai_types.SafetySetting(
                                category="HARM_CATEGORY_HARASSMENT",
                                threshold="BLOCK_NONE",
                            ),
                            genai_types.SafetySetting(
                                category="HARM_CATEGORY_HATE_SPEECH",
                                threshold="BLOCK_NONE",
                            ),
                            genai_types.SafetySetting(
                                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                threshold="BLOCK_NONE",
                            ),
                            genai_types.SafetySetting(
                                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                                threshold="BLOCK_NONE",
                            ),
                        ],
                    ),
                )

                if self._cancel_gen:
                    return  # Hard cancel — don't even straggler-queue
                self.after(0, lambda: self._log("Response received"))

                # Extract image from response parts — guard against empty/refused responses
                result_img = None

                candidates = getattr(response, "candidates", None) or []
                if not candidates:
                    # Gemini returned no candidates — almost always a content policy refusal
                    finish = None
                    try:
                        finish = response.prompt_feedback.block_reason
                    except Exception:
                        pass
                    reason = f" (reason: {finish})" if finish else ""
                    raise RuntimeError(
                        f"Gemini declined this request{reason}. "
                        "Try softening the prompt or switching to the flash model."
                    )

                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    if getattr(part, "inline_data", None) is not None:
                        img_bytes = part.inline_data.data
                        if isinstance(img_bytes, str):
                            raw = base64.b64decode(img_bytes)
                        else:
                            raw = bytes(img_bytes)
                        result_img = Image.open(
                            io.BytesIO(raw)
                        ).convert("RGBA")
                        break

                if result_img is None:
                    # Try the .as_image() helper if available
                    for part in getattr(response, "parts", None) or []:
                        if getattr(part, "inline_data", None) is not None:
                            try:
                                result_img = part.as_image().convert("RGBA")
                                break
                            except Exception:
                                pass

                if result_img is None:
                    raise RuntimeError(
                        "Gemini returned no image. The model may have declined "
                        "the request or returned text only."
                    )

                # Stale gen: route to straggler queue instead of dropping
                if gen_id != self._gen_id:
                    self.after(0, lambda img=result_img: self._add_straggler(img))
                    return
                self._result_pil = result_img
                self.after(0, lambda: self._log("Image decoded successfully"))
                self.after(0, lambda: self._log("Done"))
                self.after(0, lambda: self._on_result(result_img))

            except Exception as e:
                if self._cancel_gen or gen_id != self._gen_id:
                    return
                self.after(0, lambda err=e: self._log(f"ERROR: {err}"))
                self.after(0, lambda err=e: self._on_error(str(err)))
            finally:
                # Always release client resources to prevent connection leak
                try:
                    if client is not None:
                        del client
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, img):
        self._stop_elapsed_timer()
        self._hide_overlay()
        self._show_image(self._out_canvas, img)
        self._save_btn.config(state="normal")
        self._set_status("Transformation complete. Use Save Output to keep the result.", "success")
        self._gen_btn.config(state="normal")
        self._generating = False

    def _on_error(self, msg):
        self._generating = False   # Set BEFORE stopping timer so tick() exits cleanly
        self._stop_elapsed_timer()
        # Clear the output canvas so the old image doesn't mislead the user
        self._out_canvas.delete("all")
        self._out_canvas.create_text(
            FRAME_W // 2, FRAME_H // 2,
            text="\u2717  Generation failed",
            fill=ERROR_COL,
            font=self.f_hint,
            justify="center"
        )
        self._hide_overlay()
        self._set_status(f"Error: {msg}", "error")
        self._gen_btn.config(state="normal")

    # ── Straggler queue ─────────────────────────────────────────────────────
    # This queue holds images that arrived AFTER a generation was superseded
    # (e.g. the user started a new generation while the previous one was still
    # in-flight).  In v2.0 the Cancel button was removed because Gemini's API
    # does not support mid-flight cancellation — see the note near _on_generate.
    # The straggler machinery is preserved for future use with providers that
    # DO support async cancellation (e.g. a self-hosted model, OpenAI streaming,
    # or a future xAI streaming API).
    #
    # To wire up: when a cancel is confirmed and the old gen_id is retired,
    # the background worker should call self._add_straggler(img) instead of
    # silently discarding the result.  Everything else below handles display.
    STRAGGLER_MAX = 5

    def _add_straggler(self, img):
        """Add a late-arriving image to the straggler queue (max STRAGGLER_MAX)."""
        if len(self._straggler_queue) >= self.STRAGGLER_MAX:
            # Drop the oldest silently to respect the cap
            self._straggler_queue.pop(0)
        self._straggler_queue.append(img)
        self._update_straggler_notice()

    def _update_straggler_notice(self):
        """Show/hide/update the ⚡ Late Image label based on queue length."""
        n = len(self._straggler_queue)
        if n > 0:
            self._straggler_notice.config(
                text=f"\u26a1 Late Image ({n})"
            )
        else:
            self._straggler_notice.config(text="")

    def _show_straggler_popup(self):
        """Show (or raise) the straggler review popup with the oldest image."""
        if not self._straggler_queue:
            return
        # Bring existing popup to front if already open
        if self._straggler_popup and self._straggler_popup.winfo_exists():
            self._straggler_popup.lift()
            self._straggler_popup_refresh()
            return

        # Build the popup window
        popup = tk.Toplevel(self)
        popup.title("Late Result")
        popup.configure(bg=BG)
        popup.resizable(False, False)
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)  # X = close only
        self._straggler_popup = popup

        # Center on main window
        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width() - 420) // 2
        py = self.winfo_y() + (self.winfo_height() - 530) // 2
        popup.geometry(f"420x530+{px}+{py}")

        # Title label
        tk.Label(
            popup, text="\u26a1  Late Result",
            bg=BG, fg=ERROR_COL,
            font=("Segoe UI", 12, "bold")
        ).pack(pady=(16, 4))

        # Image canvas
        self._straggler_canvas = tk.Canvas(
            popup, width=380, height=380,
            bg=SURFACE, highlightthickness=0
        )
        self._straggler_canvas.pack(padx=20, pady=(4, 0))

        # Buttons row
        btn_row = tk.Frame(popup, bg=BG)
        btn_row.pack(pady=14)
        tk.Button(
            btn_row, text="Save",
            command=self._straggler_save,
            bg=SUCCESS_COL, fg=BG,
            relief="flat", font=self.f_btn,
            padx=18, pady=7, cursor="hand2"
        ).pack(side="left", padx=6)
        tk.Button(
            btn_row, text="Dismiss",
            command=self._straggler_dismiss,
            bg=SURFACE2, fg=TEXT,
            relief="flat", font=self.f_btn,
            padx=18, pady=7, cursor="hand2"
        ).pack(side="left", padx=6)

        self._straggler_popup_refresh()

    def _straggler_popup_refresh(self):
        """Draw the current oldest straggler onto the popup canvas."""
        if not self._straggler_queue:
            return
        img = self._straggler_queue[0]
        canvas = self._straggler_canvas
        fitted = fit_image(img, 380, 380)
        self._tk_straggler = ImageTk.PhotoImage(fitted)
        canvas.delete("all")
        cw, ch = 380, 380
        iw, ih = fitted.size
        canvas.create_image((cw - iw) // 2, (ch - ih) // 2,
                             anchor="nw", image=self._tk_straggler)

    def _straggler_save(self):
        """Save the oldest straggler image then dismiss it."""
        if not self._straggler_queue:
            return
        from tkinter import filedialog
        img = self._straggler_queue[0]
        path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("All files", "*.*")]
        )
        if path:
            try:
                fmt = "PNG" if path.lower().endswith(".png") else "JPEG"
                save_img = img.convert("RGB") if fmt == "JPEG" else img
                save_img.save(path, format=fmt, quality=95)
                self._set_status(f"Late result saved to {path}", "success")
            except Exception as e:
                self._set_status(f"Save failed: {e}", "error")
        self._straggler_dismiss()

    def _straggler_dismiss(self):
        """Remove the oldest straggler and update the popup / notice."""
        if self._straggler_queue:
            self._straggler_queue.pop(0)
        self._update_straggler_notice()
        if not self._straggler_queue:
            # Close popup when queue is empty
            if self._straggler_popup and self._straggler_popup.winfo_exists():
                self._straggler_popup.destroy()
        else:
            # Show next image in popup
            self._straggler_popup_refresh()

    # ── Elapsed time counter ────────────────────
    def _start_elapsed_timer(self):
        """Start a 1-second ticker that updates the status bar with elapsed time."""
        import time
        self._elapsed_start = time.time()
        self._elapsed_job = None
        self._tick_elapsed()

    def _tick_elapsed(self):
        import time
        if not self._generating:
            return
        elapsed = int(time.time() - self._elapsed_start)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}:{secs:02d}" if mins else f"{secs}s"
        self._set_status(f"Generating… ({time_str} elapsed)  \u2014  click Cancel to abort", "dim")
        self._elapsed_job = self.after(1000, self._tick_elapsed)

    def _stop_elapsed_timer(self):
        if hasattr(self, '_elapsed_job') and self._elapsed_job:
            self.after_cancel(self._elapsed_job)
            self._elapsed_job = None

    # ── Save output ─────────────────────────────
    def _save_output(self):
        if self._result_pil is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save output image",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            fmt = "PNG" if path.lower().endswith(".png") else "JPEG"
            save_img = self._result_pil.convert("RGB") if fmt == "JPEG" else self._result_pil
            save_img.save(path, format=fmt, quality=95)
            self._set_status(f"Saved to {path}", "success")
        except Exception as e:
            self._set_status(f"Save failed: {e}", "error")

    # ── Status ──────────────────────────────────
    def _set_status(self, msg, kind="dim"):
        colour = {
            "dim":     TEXT_DIM,
            "error":   ERROR_COL,
            "success": SUCCESS_COL,
        }.get(kind, TEXT_DIM)
        self._status_lbl.config(fg=colour)
        self._status_var.set(msg)


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = MirrorMirrorApp()
    app.mainloop()