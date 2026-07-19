# dni-watermark

Añade una **marca de agua** a tu DNI (o cualquier documento) y genera un **PDF
protegido**, pensado para enviar copias de forma segura — por ejemplo, mandar el
DNI a la guardería, al colegio, a un casero, etc.

- ✅ Marca de agua **repetida en diagonal por toda la página** (no se puede recortar), con **opacidad y tamaño ajustables**.
- ✅ **Fecha automática** y texto configurable (deja constancia del propósito).
- ✅ Acepta **fotos/escaneos** (JPG, PNG…) o **PDF**. Junta varias caras/páginas en un solo PDF.
- ✅ PDF **cifrado (AES-256)**: se abre sin contraseña pero **no se puede copiar ni editar**; opcionalmente, contraseña de apertura.
- ✅ **Firma y bloqueo tipo certificado digital** (`--sign`): sello visible + documento a prueba de manipulaciones.
- 🔒 **100% local**: ningún dato sale de tu ordenador.

> **Nota honesta:** la marca de agua es la protección real y disuasoria. Los
> permisos del PDF añaden fricción, pero técnicamente pueden eludirse. La
> combinación (marca que cubre todo + fecha/propósito visibles + permisos)
> es lo razonable para un envío cotidiano.

---

## 🗓️ Uso habitual (el día a día)

El caso típico: **te piden el DNI y no quieres mandarlo "a pelo".** Flujo:

1. Haz una foto (o escaneo) del **anverso** y del **reverso** del DNI y déjalos en una carpeta.
2. Abre una terminal en esa carpeta.
3. Ejecuta **un comando** indicando para quién es la copia:

   ```bash
   python dni_watermark.py anverso.jpg reverso.jpg \
       --text "Copia para la guarderia - solo matricula" \
       -o dni_guarderia.pdf
   ```

4. Se genera `dni_guarderia.pdf`: las dos caras en un PDF, con la marca de agua
   repetida por todo el documento, la **fecha de hoy** y protegido contra copia/edición.
5. Adjúntalo en el correo y listo. Cada vez que lo necesites, cambias el `--text`
   ("Copia para el colegio", "Copia para el alquiler…") y ya está.

¿No te apetece recordar los comandos? Ejecuta **sin argumentos** y te va preguntando:

```bash
python dni_watermark.py
```

---

## ⚙️ Cómo usarlo — dos opciones

Elige la que prefieras. **Sin Docker** es lo más directo si ya tienes Python;
**con Docker** no requiere instalar nada de Python en tu sistema.

### Opción A · Sin Docker (Python)

Necesitas [Python 3.9+](https://www.python.org/downloads/). Una sola vez:

```bash
cd dni-watermark
pip install -r requirements.txt
```

Y a usarlo:

```bash
python dni_watermark.py anverso.jpg reverso.jpg -o dni.pdf -t "Copia para la guarderia"
```

> En Windows quizá tengas que usar `py` en vez de `python`
> (`py -m pip install -r requirements.txt`, `py dni_watermark.py ...`).

### Opción B · Con Docker

No necesitas Python instalado, solo [Docker](https://docs.docker.com/get-docker/).
Construye la imagen una vez:

```bash
docker build -t dni-watermark ./dni-watermark
```

Luego, **desde la carpeta donde tengas tus ficheros**, monta esa carpeta en `/data`:

```bash
# Linux / macOS
docker run --rm -v "$PWD:/data" dni-watermark anverso.jpg reverso.jpg -o dni.pdf -t "Copia para la guarderia"
```

```powershell
# Windows (PowerShell)
docker run --rm -v "${PWD}:/data" dni-watermark anverso.jpg reverso.jpg -o dni.pdf -t "Copia para la guarderia"
```

Modo interactivo con Docker (añade `-it`):

```bash
docker run --rm -it -v "$PWD:/data" dni-watermark
```

> Las rutas que pasas son **relativas a la carpeta que montas** (`/data`), así que
> usa solo el nombre del fichero (`anverso.jpg`), no la ruta completa del sistema.

---

## 🎨 Ajustar la intensidad y el tamaño de la marca

Para envíos donde necesitas la marca **más opaca** (más difícil de ignorar o de
disimular en una captura), sube la opacidad y, si quieres, el tamaño:

```bash
# Marca más opaca y un poco más grande
python dni_watermark.py dni.jpg -t "Copia para la guarderia" --opacity 0.5 --size 1.2
```

- `--opacity` va de `0.0` (invisible) a `1.0` (totalmente opaca). Por defecto `0.28`.
- `--size` es un multiplicador del tamaño del texto (`1.0` = normal, `1.5` = más grande).

## 🔏 Firmar y bloquear (como un certificado digital)

Con `--sign` el PDF se **firma con una firma de certificación**: añade un **sello
visible** abajo a la izquierda (*"DNI · uso limitado · bloqueado el …"*) y deja el
documento **a prueba de manipulaciones** — cualquier edición posterior **invalida
la firma**, igual que cuando firmas con certificado digital. En el visor aparece
en el panel de firmas de la izquierda.

```bash
# Firmar y bloquear (certificado autofirmado, generado al vuelo)
python dni_watermark.py anverso.jpg reverso.jpg --sign -t "Copia para la guarderia - solo matricula"

# Firmar con TU certificado digital (.p12 / .pfx) → firma verificada
python dni_watermark.py dni.jpg --sign --cert mi_certificado.p12 --cert-password ****

# Personalizar el texto del sello
python dni_watermark.py dni.jpg --sign --sign-text "DNI para la guarderia - bloqueado 2026"
```

> **Autofirmado vs. certificado propio.** Sin `--cert` se genera un certificado
> autofirmado: la firma es válida y **bloquea el documento igual**, pero el visor
> mostrará *"identidad no verificada"* (no viene de una autoridad de confianza).
> Si quieres que salga como **firma verificada** (marca verde), usa `--cert` con
> tu certificado digital real (p. ej. el de la **FNMT**) exportado a `.p12`/`.pfx`.

> El modo firma **no se combina con el cifrado** (`--password`): la propia firma
> de certificación ya bloquea la edición. Elige uno u otro:
> **cifrado** (evita copiar texto) **o** **firma** (bloqueo a prueba de manipulaciones).

## 📸 ¿Se pueden bloquear las capturas de pantalla?

**Con honestidad: no.** Ningún PDF puede impedir que el sistema operativo haga una
captura de pantalla — eso solo lo consiguen apps con DRM a nivel de sistema (como
las de vídeo en streaming), no un fichero PDF. Cualquier visor puede capturarse.

La defensa real frente a esto es **la propia marca de agua**: si alguien hace una
captura, **la captura sale igualmente marcada** con el propósito y la fecha. Por
eso, para este caso, lo práctico es subir la opacidad/tamaño (`--opacity`,
`--size`) para que la marca sea imposible de pasar por alto.

## Opciones

| Opción | Descripción |
|---|---|
| `inputs` | Una o más imágenes/PDF (ej. las dos caras del DNI). |
| `-t`, `--text` | Texto de la marca de agua. |
| `-o`, `--output` | Ruta del PDF de salida. |
| `--no-date` | No añadir la fecha de hoy a la marca. |
| `--opacity` | Opacidad de la marca `0.0`–`1.0` (por defecto `0.28`). |
| `--size` | Tamaño del texto de la marca (`1.0` = normal). |
| `--password` | Contraseña para **abrir** el PDF (modo cifrado). |
| `--allow-copy` | Permitir copiar texto del PDF (por defecto: no). |
| `--no-print` | No permitir imprimir el PDF. |
| `--sign` | Firmar y **bloquear** el documento (a prueba de manipulaciones). |
| `--cert` | Tu certificado `.p12`/`.pfx` para firmar (si se omite, se autofirma). |
| `--cert-password` | Contraseña de tu certificado. |
| `--sign-text` | Texto del sello visible de la firma. |
| `--signer` | Nombre del firmante al autofirmar. |

Si no indicas `-o/--output`, el PDF se guarda junto al primer fichero con el
sufijo `_marca_agua.pdf`.

### Más ejemplos

```bash
# Una sola foto, salida automática (dni_marca_agua.pdf)
python dni_watermark.py dni.jpg

# Con contraseña para abrir
python dni_watermark.py dni.jpg --password 1234

# A partir de un PDF existente, permitiendo copiar texto
python dni_watermark.py documento.pdf --allow-copy -o documento_protegido.pdf
```

---

## Aviso

Herramienta de uso personal, sin garantías. La protección de un PDF no sustituye
al buen juicio: envía tus documentos solo a destinatarios de confianza.
