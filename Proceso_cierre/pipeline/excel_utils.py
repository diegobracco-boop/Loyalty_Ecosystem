"""Utilidades para guardar libros de Excel con openpyxl sin que Excel pida "recuperar".

Contexto (2026-10-03): al guardar `Asientos Cierre Loyalty.xlsx` con openpyxl, Excel abria el
archivo con "hemos encontrado un problema con el contenido". Causa: un vinculo externo
(`externalLink47`) que Excel guarda con 2 relaciones (rId1 = ruta relativa, rId2 = URL absoluta
de SharePoint via la extension `xxl21:alternateUrls`). openpyxl no conoce esa extension: la
descarta y escribe solo la relacion rId2, pero deja `externalBook r:id="rId1"` -> referencia
colgante a una relacion que ya no existe.
"""


def reparar_vinculos_externos(wb) -> int:
    """Hace que cada vinculo externo apunte a la relacion que realmente se va a escribir.
    Devuelve cuantos vinculos corrigio. Llamar justo antes de `wb.save(...)`."""
    corregidos = 0
    for link in getattr(wb, "_external_links", []):
        libro = getattr(link, "externalBook", None)
        relacion = getattr(link, "file_link", None)
        if libro is None or relacion is None:
            continue
        if libro.id != relacion.Id:
            libro.id = relacion.Id
            corregidos += 1
    return corregidos


def quitar_partes_trash(ruta: str) -> int:
    """Saca del .xlsx ya guardado las partes `[trash]/*.dat`: no estan referenciadas por ningun
    rels ni declaradas en [Content_Types].xml (el archivo guardado por Excel no las tiene) y
    aparecieron en el archivo escrito por el pipeline el 2026-10-03. Devuelve cuantas saco."""
    import os
    import shutil
    import zipfile

    with zipfile.ZipFile(ruta) as zin:
        basura = [i for i in zin.infolist() if i.filename.startswith("[trash]/")]
        if not basura:
            return 0
        tmp = ruta + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename.startswith("[trash]/"):
                    continue
                zout.writestr(item, zin.read(item.filename),
                              compress_type=zipfile.ZIP_DEFLATED if item.compress_type else zipfile.ZIP_STORED)
    shutil.move(tmp, ruta)
    return len(basura)
