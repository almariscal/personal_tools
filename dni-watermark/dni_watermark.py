#!/usr/bin/env python3
"""
dni_watermark — Añade una marca de agua a un DNI (u otro documento) y genera
un PDF protegido, pensado para enviar copias de forma segura.

Todo el procesado es 100% local: ningún dato sale de tu ordenador.

Uso rápido:
    python dni_watermark.py dni_anverso.jpg dni_reverso.jpg \
        --text "Copia para la guardería - solo matricula" \
        --output dni_guarderia.pdf

Dos formas de proteger (excluyentes entre sí):
  · Por defecto: PDF cifrado (AES-256) sin permiso de copia/edición.
  · Con --sign: firma de certificación (como un certificado digital) que
    BLOQUEA la edición, es a prueba de manipulaciones y añade un sello visible.

Ejecutándolo sin argumentos entra en modo interactivo (pregunta por los
datos), útil si no quieres recordar las opciones.

Requiere: pypdf, reportlab, Pillow  (pip install -r requirements.txt)
Para firmar (--sign) hace falta además: pyhanko, cryptography
"""
from __future__ import annotations

import argparse
import io
import math
import secrets
import sys
from datetime import date, datetime, timezone
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

DEFAULT_OPACITY = 0.28  # 0 = invisible, 1 = totalmente opaca


# --------------------------------------------------------------------------- #
# Marca de agua
# --------------------------------------------------------------------------- #
def build_watermark_overlay(
    width: float,
    height: float,
    text: str,
    opacity: float = DEFAULT_OPACITY,
    size_factor: float = 1.0,
) -> PdfReader:
    """Crea una página PDF (del tamaño dado, en puntos) con la marca de agua
    repetida en diagonal por toda la superficie.

    - opacity: 0.0 (invisible) .. 1.0 (totalmente opaca).
    - size_factor: multiplicador del tamaño del texto (1.0 = normal).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    font_name = "Helvetica-Bold"
    font_size = max(14, min(width, height) / 28) * size_factor
    c.setFont(font_name, font_size)
    c.setFillColor(Color(0.5, 0.5, 0.5, alpha=opacity))

    text_width = c.stringWidth(text, font_name, font_size)

    # Separación entre repeticiones del texto (escala con el tamaño).
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
# Firma digital (certificación) — bloquea el documento, como un certificado
# --------------------------------------------------------------------------- #
def _generate_self_signed_p12(common_name: str, password: bytes) -> bytes:
    """Genera un certificado autofirmado y lo empaqueta como PKCS#12 (bytes)."""
    import datetime as _dt

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"dni-watermark", key, cert, None,
        serialization.BestAvailableEncryption(password),
    )


def sign_pdf(
    pdf_bytes: bytes,
    output: Path,
    stamp_text: str,
    reason: str,
    cert_path: str | None,
    cert_password: str | None,
    signer_name: str,
) -> bool:
    """Firma el PDF con una firma de CERTIFICACIÓN que bloquea la edición.

    Devuelve True si el certificado es de confianza (aportado por el usuario),
    False si es autofirmado (se verá como "identidad no verificada").
    """
    import os
    import tempfile

    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers
        from pyhanko.stamp import TextStampStyle
    except ModuleNotFoundError:
        raise SystemExit(
            "Para firmar (--sign) necesitas pyhanko y cryptography:\n"
            "    pip install pyhanko cryptography\n"
            "(o simplemente: pip install -r requirements.txt)"
        )

    tmp_p12 = None
    trusted = bool(cert_path)
    try:
        if cert_path:
            p12_path = cert_path
            passphrase = (cert_password or "").encode()
        else:
            p12_bytes = _generate_self_signed_p12(signer_name, b"dni")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".p12")
            tmp.write(p12_bytes)
            tmp.close()
            tmp_p12 = tmp.name
            p12_path = tmp.name
            passphrase = b"dni"

        signer = signers.SimpleSigner.load_pkcs12(p12_path, passphrase=passphrase)
        if signer is None:
            raise SystemExit(
                "No pude cargar el certificado. Revisa la ruta y la contraseña "
                "(--cert / --cert-password)."
            )

        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        fields.append_signature_field(
            writer,
            fields.SigFieldSpec(sig_field_name="Firma1", on_page=0, box=(36, 36, 330, 132)),
        )
        meta = signers.PdfSignatureMetadata(
            field_name="Firma1",
            reason=reason,
            certify=True,
            docmdp_permissions=fields.MDPPerm.NO_CHANGES,
        )
        pdf_signer = signers.PdfSigner(
            meta, signer=signer, stamp_style=TextStampStyle(stamp_text=stamp_text)
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as out:
            pdf_signer.sign_pdf(writer, output=out)
    finally:
        if tmp_p12:
            os.unlink(tmp_p12)

    return trusted


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
    opacity: float,
    size_factor: float,
    sign: bool,
    cert_path: str | None,
    cert_password: str | None,
    stamp_text: str,
    reason: str,
    signer_name: str,
) -> bool | None:
    writer = PdfWriter()

    for path in inputs:
        for page in load_pages(path):
            box = page.mediabox
            overlay = build_watermark_overlay(
                float(box.width), float(box.height), text, opacity, size_factor
            )
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

    if sign:
        # La firma de certificación bloquea la edición y es a prueba de
        # manipulaciones; no se combina con el cifrado AES.
        buffer = io.BytesIO()
        writer.write(buffer)
        return sign_pdf(
            buffer.getvalue(), output, stamp_text=stamp_text, reason=reason,
            cert_path=cert_path, cert_password=cert_password, signer_name=signer_name,
        )

    # Modo cifrado: se puede abrir e imprimir, pero NO copiar texto ni modificar.
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
    return None


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
            "  python dni_watermark.py anverso.jpg reverso.jpg -o dni.pdf --opacity 0.45\n"
            "  python dni_watermark.py dni.jpg --sign --text \"Copia para la guarderia\"\n"
            "  python dni_watermark.py dni.jpg --sign --cert mi_certificado.p12 --cert-password ****\n"
        ),
    )
    parser.add_argument("inputs", nargs="*", help="Imágenes o PDF de entrada (ej. las dos caras del DNI).")
    parser.add_argument("-t", "--text", help="Texto de la marca de agua.")
    parser.add_argument("-o", "--output", help="Ruta del PDF de salida.")
    parser.add_argument("--no-date", action="store_true", help="No añadir la fecha de hoy a la marca.")

    grp = parser.add_argument_group("apariencia de la marca de agua")
    grp.add_argument("--opacity", type=float, default=DEFAULT_OPACITY,
                     help=f"Opacidad 0.0-1.0 (por defecto {DEFAULT_OPACITY}; súbela para más intensidad).")
    grp.add_argument("--size", type=float, default=1.0,
                     help="Tamaño del texto de la marca (1.0 = normal, 1.5 = más grande).")

    enc = parser.add_argument_group("protección por cifrado (modo por defecto)")
    enc.add_argument("--password", help="Contraseña para ABRIR el PDF (opcional).")
    enc.add_argument("--allow-copy", action="store_true", help="Permitir copiar texto del PDF.")
    enc.add_argument("--no-print", action="store_true", help="No permitir imprimir el PDF.")

    sig = parser.add_argument_group("firma y bloqueo (como certificado digital)")
    sig.add_argument("--sign", action="store_true",
                     help="Firmar y BLOQUEAR el documento (a prueba de manipulaciones). No se combina con el cifrado.")
    sig.add_argument("--cert", help="Tu certificado .p12/.pfx (ej. certificado digital). Si se omite, se autofirma.")
    sig.add_argument("--cert-password", help="Contraseña de tu certificado .p12/.pfx.")
    sig.add_argument("--sign-text", help="Texto del sello visible de la firma (por defecto se genera del --text).")
    sig.add_argument("--signer", help="Nombre que aparece como firmante al autofirmar (por defecto: Titular del DNI).")
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
    opacity = prompt("Opacidad de la marca 0.0-1.0", str(DEFAULT_OPACITY))
    size = prompt("Tamaño de la marca (1.0 = normal)", "1.0")

    sign = prompt("¿Firmar y bloquear como certificado digital? (s/N)", "n").lower().startswith("s")
    cert = password = None
    if sign:
        cert = prompt("Ruta de tu certificado .p12/.pfx (vacío = autofirmado)", "") or None
        if cert:
            password = prompt("Contraseña del certificado", "") or None
    else:
        password = prompt("Contraseña para abrir el PDF (vacío = sin contraseña)", "") or None

    ns = argparse.Namespace()
    ns.inputs = inputs
    ns.text = text
    ns.output = output
    ns.no_date = False
    ns.opacity = float(opacity)
    ns.size = float(size)
    ns.password = password
    ns.allow_copy = False
    ns.no_print = False
    ns.sign = sign
    ns.cert = cert
    ns.cert_password = password if (sign and cert) else None
    ns.sign_text = None
    ns.signer = None
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

    if not 0.0 <= args.opacity <= 1.0:
        print("La opacidad (--opacity) debe estar entre 0.0 y 1.0.", file=sys.stderr)
        return 1

    base_text = args.text or "COPIA - uso limitado"
    text = make_watermark_text(base_text, with_date=not args.no_date)
    today = date.today().isoformat()

    if args.output:
        output = Path(args.output)
    else:
        output = input_paths[0].with_name(input_paths[0].stem + "_marca_agua.pdf")

    signer_name = args.signer or "Titular del DNI (autofirmado)"
    stamp_text = args.sign_text or (
        f"DNI - USO LIMITADO\n{base_text}\nBloqueado el {today}\n"
        "Firmado por: %(signer)s\n%(ts)s"
    )
    reason = f"Uso limitado: {base_text}. Documento bloqueado el {today}."

    try:
        trusted = process(
            inputs=input_paths,
            output=output,
            text=text,
            open_password=args.password,
            allow_copy=args.allow_copy,
            allow_print=not args.no_print,
            opacity=args.opacity,
            size_factor=args.size,
            sign=args.sign,
            cert_path=args.cert,
            cert_password=args.cert_password,
            stamp_text=stamp_text,
            reason=reason,
            signer_name=signer_name,
        )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - mensaje amable para el usuario
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\n✓ PDF generado: {output.resolve()}")
    print(f"  Marca de agua: \"{text}\"  (opacidad {args.opacity}, tamaño {args.size})")
    if args.sign:
        print("  Firmado y BLOQUEADO: no se puede editar sin invalidar la firma.")
        if trusted:
            print("  Certificado propio: la firma se mostrará como verificada.")
        else:
            print("  Certificado autofirmado: válido y bloqueado, pero el visor")
            print("  mostrará \"identidad no verificada\". Usa --cert con tu")
            print("  certificado digital si necesitas que salga como de confianza.")
    elif args.password:
        print("  Protegido con contraseña de apertura; copia y edición restringidas.")
    else:
        print("  Se abre sin contraseña; copia de texto y edición restringidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
