"""
Mirror Mirror — xAI Grok Image Transformation Tool
Requires: pip install xai-sdk pillow requests
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
    from PIL import Image, ImageTk
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

try:
    import xai_sdk
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "xai-sdk is required.\n\nRun:  pip install xai-sdk"
    )
    raise SystemExit


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
TITLE        = "Mirror Mirror"
SUBTITLE     = "on the wall"
INSTRUCTIONS = (
    "1. Load a source photo (file or URL).\n"
    "2. Enter your xAI API key.\n"
    "3. Edit the prompt if desired, then click Generate.\n"
    "4. Right-click the result or use Save Output to keep it.\n\n"
    "Your API key is used only to call api.x.ai directly — "
    "nothing is stored or transmitted elsewhere."
)
DEFAULT_PROMPT = (
    "MtF gender swap transformation of the subject; "
    "maintain pose and facial structure, but change body shape, "
    "clothing, and features to emphasize the new gender"
)
DEFAULT_MODEL  = "grok-imagine-image-pro"
ALT_MODEL      = "grok-imagine-image"
FRAME_W        = 340
FRAME_H        = 340

# Colour palette — matches the web version's purple/pink aesthetic
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

        self._build_fonts()
        self._build_ui()
        self.update_idletasks()
        self._center_window()

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

        # Header
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

        # Status bar
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(
            outer, textvariable=self._status_var,
            bg=BG, fg=TEXT_DIM, font=self.f_small,
            anchor="center", wraplength=760
        )
        self._status_lbl.pack(fill="x", pady=(6, 0))

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

        tk.Label(col, text="SOURCE IMAGE", bg=BG, fg=TEXT_DIM,
                 font=self.f_label).pack(anchor="w", pady=(0, 6))

        # The canvas frame (image display)
        self._src_frame = self._image_frame(col, side="source")
        self._src_frame.pack(fill="x")

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

        tk.Label(col, text="TRANSFORMED IMAGE", bg=BG, fg=TEXT_DIM,
                 font=self.f_label).pack(anchor="w", pady=(0, 6))

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

        tk.Label(key_col, text="XAI API KEY",
                 bg=BG, fg=TEXT_DIM, font=self.f_label).pack(anchor="w")

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
        model_col = tk.Frame(bottom, bg=BG)
        model_col.pack(side="left", padx=(0, 16))

        tk.Label(model_col, text="MODEL",
                 bg=BG, fg=TEXT_DIM, font=self.f_label).pack(anchor="w")

        self._model_var = tk.StringVar(value=DEFAULT_MODEL)
        for model in (DEFAULT_MODEL, ALT_MODEL):
            tk.Radiobutton(
                model_col, text=model,
                variable=self._model_var, value=model,
                bg=BG, fg=TEXT_DIM,
                selectcolor=SURFACE2,
                activebackground=BG, activeforeground=ACCENT_A,
                font=self.f_small
            ).pack(anchor="w")

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
    def _on_generate(self):
        if self._generating:
            return

        api_key = self._key_var.get().strip()
        prompt  = self._prompt_text.get("1.0", "end").strip()
        model   = self._model_var.get()

        if not api_key:
            self._set_status("Please enter your xAI API key.", "error")
            return
        if not prompt:
            self._set_status("Please enter a prompt.", "error")
            return
        if self._source_pil is None:
            self._set_status("Please load a source image first.", "error")
            return

        self._generating = True
        self._gen_btn.config(state="disabled", text="Generating…")
        self._save_btn.config(state="disabled")
        self._set_status("", "dim")

        # Show overlay terminal
        self._show_overlay()
        self._log(f"Model   : {model}")
        self._log(f"Prompt  : {prompt[:60]}{'…' if len(prompt) > 60 else ''}")
        self._log("─" * 38)
        self._log("Encoding source image to base64")

        # Build base64 data URI from the loaded PIL image
        image_data_uri = pil_to_base64(self._source_pil, fmt="JPEG")
        img_kb = len(image_data_uri) * 3 // 4 // 1024
        self.after(0, lambda: self._log(f"Encoded  : {img_kb} KB"))
        self.after(0, lambda: self._log("Connecting to api.x.ai"))

        def worker():
            try:
                self.after(0, lambda: self._log("Authenticating"))
                os.environ["XAI_API_KEY"] = api_key
                client = xai_sdk.Client()

                self.after(0, lambda: self._log("Sending image + prompt to Grok"))
                response = client.image.sample(
                    prompt=prompt,
                    model=model,
                    image_url=image_data_uri,
                )

                result_url = response.url
                self.after(0, lambda: self._log("Response received"))
                self.after(0, lambda: self._log(f"URL: {result_url[:48]}…"))
                self.after(0, lambda: self._log("Downloading result image"))

                result_img = load_image_from_url(result_url)
                self._result_pil = result_img

                self.after(0, lambda: self._log("Done"))
                self.after(0, lambda: self._on_result(result_img))

            except Exception as e:
                self.after(0, lambda err=e: self._log(f"ERROR: {err}"))
                self.after(0, lambda err=e: self._on_error(str(err)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, img):
        self._hide_overlay()
        self._show_image(self._out_canvas, img)
        self._save_btn.config(state="normal")
        self._set_status("Transformation complete. Use Save Output to keep the result.", "success")
        self._gen_btn.config(state="normal", text="Generate")
        self._generating = False

    def _on_error(self, msg):
        self._hide_overlay()
        self._set_status(f"Error: {msg}", "error")
        self._gen_btn.config(state="normal", text="Generate")
        self._generating = False

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