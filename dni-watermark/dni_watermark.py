#!/usr/bin/env python3
"""
dni_watermark — Añade una marca de agua a un DNI (u otro documento) y genera
un PDF protegido, pensado para enviar copias de forma segura.

Todo el procesado es 100% local: ningún dato sale de tu ordenador.

Uso rápido:
    python dni_watermark.py dni_anverso.jpg dni_reverso.jpg \
        --text "Copia para la guardería - solo matricula" \
        --output dni_guarderia.pdf

Ejecutándolo sin argumentos entra en modo interactivo (pregunta por los
datos), útil si no quieres recordar las opciones.

Requiere: pypdf, reportlab, Pillow  (pip install -r requirements.txt)
"""
from __future__ import annotations

import argparse
import io
import math
import secrets
import sys
from datetime import date
from pathlib import Path

try:
    from PIL import Image, ImageOps
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions
    from reportlab.lib.colors import Color
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ModuleNotFoundError as exc:  # pragma: no cover - mensaje de ayuda
    sys.exit(
        f"Falta una dependencia ({exc.name}).\n"
        "Instala los requisitos con:\n"
        "    pip install -r requirements.txt"
    )

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
PDF_SUFFIXES = {".pdf"}


# --------------------------------------------------------------------------- #
# Marca de agua
# --------------------------------------------------------------------------- #
def build_watermark_overlay(width: float, height: float, text: str) -> PdfReader:
    """Crea una página PDF (del tamaño dado, en puntos) con la marca de agua
    repetida en diagonal por toda la superficie."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    font_name = "Helvetica-Bold"
    font_size = max(14, min(width, height) / 28)
    c.setFont(font_name, font_size)
    c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.28))

    text_width = c.stringWidth(text, font_name, font_size)

    # Separación entre repeticiones del texto.
    step_x = text_width + font_size * 3
    step_y = font_size * 5

    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(35)

    diagonal = math.hypot(width, height)
    y = -diagonal
    while y <= diagonal:
        x = -diagonal
        while x <= diagonal:
            c.drawString(x, y, text)
            x += step_x
        y += step_y
    c.restoreState()

    c.save()
    buffer.seek(0)
    return PdfReader(buffer)


# --------------------------------------------------------------------------- #
# Conversión de entradas a páginas PDF
# --------------------------------------------------------------------------- #
def image_to_pdf_page(path: Path) -> PdfReader:
    """Coloca una imagen centrada dentro de una página A4 y devuelve el PDF."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respeta la orientación de la foto
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    page_w, page_h = A4
    margin = 28  # ~1 cm
    max_w, max_h = page_w - 2 * margin, page_h - 2 * margin

    scale = min(max_w / img.width, max_h / img.height)
    draw_w, draw_h = img.width * scale, img.height * scale
    x = (page_w - draw_w) / 2
    y = (page_h - draw_h) / 2

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawImage(
        ImageReaderFromPIL(img),
        x, y, width=draw_w, height=draw_h,
        preserveAspectRatio=True, mask="auto",
    )
    c.save()
    buffer.seek(0)
    return PdfReader(buffer)


def ImageReaderFromPIL(pil_image):  # noqa: N802 - nombre estilo reportlab
    """Envuelve una imagen PIL para reportlab sin escribir a disco."""
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def load_pages(path: Path):
    """Devuelve una lista de páginas pypdf para el fichero de entrada."""
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return list(image_to_pdf_page(path).pages)
    if suffix in PDF_SUFFIXES:
        return list(PdfReader(str(path)).pages)
    raise ValueError(
        f"Formato no soportado: {path.name}\n"
        f"Usa una imagen ({', '.join(sorted(IMAGE_SUFFIXES))}) o un PDF."
    )


# --------------------------------------------------------------------------- #
# Proceso principal
# --------------------------------------------------------------------------- #
def make_watermark_text(base_text: str, with_date: bool) -> str:
    if with_date:
        return f"{base_text}  ·  {date.today().isoformat()}"
    return base_text


def process(
    inputs: list[Path],
    output: Path,
    text: str,
    open_password: str | None,
    allow_copy: bool,
    allow_print: bool,
) -> None:
    writer = PdfWriter()

    for path in inputs:
        for page in load_pages(path):
            box = page.mediabox
            overlay = build_watermark_overlay(
                float(box.width), float(box.height), text
            )
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

    # Permisos: por defecto se puede abrir e imprimir, pero NO copiar texto ni
    # modificar el documento. El "owner password" bloquea el cambio de permisos;
    # si el usuario no lo necesita, generamos uno aleatorio y lo descartamos.
    permissions = UserAccessPermissions(0)
    if allow_print:
        permissions |= UserAccessPermissions.PRINT
        permissions |= UserAccessPermissions.PRINT_TO_REPRESENTATION
    if allow_copy:
        permissions |= UserAccessPermissions.EXTRACT
        permissions |= UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS

    owner_password = secrets.token_urlsafe(16)
    writer.encrypt(
        user_password=open_password or "",
        owner_password=owner_password,
        permissions_flag=permissions,
        algorithm="AES-256",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as fh:
        writer.write(fh)


# --------------------------------------------------------------------------- #
# CLI / interactivo
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Añade una marca de agua a un DNI/documento y genera un PDF protegido.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python dni_watermark.py dni.jpg --text \"Copia para la guarderia\"\n"
            "  python dni_watermark.py anverso.jpg reverso.jpg -o dni.pdf\n"
            "  python dni_watermark.py dni.pdf --password 1234\n"
        ),
    )
    parser.add_argument("inputs", nargs="*", help="Imágenes o PDF de entrada (ej. las dos caras del DNI).")
    parser.add_argument("-t", "--text", help="Texto de la marca de agua.")
    parser.add_argument("-o", "--output", help="Ruta del PDF de salida.")
    parser.add_argument("--password", help="Contraseña para ABRIR el PDF (opcional).")
    parser.add_argument("--no-date", action="store_true", help="No añadir la fecha de hoy a la marca.")
    parser.add_argument("--allow-copy", action="store_true", help="Permitir copiar texto del PDF.")
    parser.add_argument("--no-print", action="store_true", help="No permitir imprimir el PDF.")
    return parser.parse_args(argv)


def prompt(msg: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{msg}{suffix}: ").strip()
    return value or (default or "")


def run_interactive() -> argparse.Namespace:
    print("== dni_watermark (modo interactivo) ==")
    print("Arrastra el/los fichero(s) aquí o escribe la ruta. Deja vacío para terminar.\n")
    inputs: list[str] = []
    while True:
        raw = input(f"Fichero {len(inputs) + 1} (vacío = seguir): ").strip().strip('"').strip("'")
        if not raw:
            if inputs:
                break
            print("Necesitas al menos un fichero.")
            continue
        inputs.append(raw)

    text = prompt("Texto de la marca de agua", "COPIA - uso limitado")
    output = prompt("PDF de salida", "dni_marca_agua.pdf")
    password = prompt("Contraseña para abrir (vacío = sin contraseña)", "")

    ns = argparse.Namespace()
    ns.inputs = inputs
    ns.text = text
    ns.output = output
    ns.password = password or None
    ns.no_date = False
    ns.allow_copy = False
    ns.no_print = False
    return ns


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = run_interactive() if not argv else parse_args(argv)

    input_paths = [Path(p) for p in args.inputs]
    missing = [p for p in input_paths if not p.is_file()]
    if missing:
        print("No encuentro estos ficheros:", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 1

    base_text = args.text or "COPIA - uso limitado"
    text = make_watermark_text(base_text, with_date=not args.no_date)

    if args.output:
        output = Path(args.output)
    else:
        output = input_paths[0].with_name(input_paths[0].stem + "_marca_agua.pdf")

    try:
        process(
            inputs=input_paths,
            output=output,
            text=text,
            open_password=args.password,
            allow_copy=args.allow_copy,
            allow_print=not args.no_print,
        )
    except Exception as exc:  # noqa: BLE001 - mensaje amable para el usuario
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\n✓ PDF generado: {output.resolve()}")
    print(f"  Marca de agua: \"{text}\"")
    if args.password:
        print("  Protegido con contraseña de apertura.")
    else:
        print("  Se abre sin contraseña; copia de texto y edición restringidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
