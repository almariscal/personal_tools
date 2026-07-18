# dni-watermark

Añade una **marca de agua** a tu DNI (o cualquier documento) y genera un **PDF
protegido**, pensado para enviar copias de forma segura — por ejemplo, mandar el
DNI a la guardería, al colegio, a un casero, etc.

- ✅ Marca de agua **repetida en diagonal por toda la página** (no se puede recortar).
- ✅ **Fecha automática** y texto configurable (deja constancia del propósito).
- ✅ Acepta **fotos/escaneos** (JPG, PNG…) o **PDF**. Junta varias caras/páginas en un solo PDF.
- ✅ PDF **cifrado (AES-256)**: se abre sin contraseña pero **no se puede copiar ni editar**; opcionalmente, contraseña de apertura.
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

## Opciones

| Opción | Descripción |
|---|---|
| `inputs` | Una o más imágenes/PDF (ej. las dos caras del DNI). |
| `-t`, `--text` | Texto de la marca de agua. |
| `-o`, `--output` | Ruta del PDF de salida. |
| `--password` | Contraseña para **abrir** el PDF (opcional). |
| `--no-date` | No añadir la fecha de hoy a la marca. |
| `--allow-copy` | Permitir copiar texto del PDF (por defecto: no). |
| `--no-print` | No permitir imprimir el PDF. |

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
