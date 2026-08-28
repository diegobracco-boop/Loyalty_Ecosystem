"""
configurar_datalake.py — guarda las credenciales del datalake del usuario actual
en  envs/.env.<usuario_windows>  (gitignoreado, local, nunca se sube).

El PASSWORD se pide sin eco y NO se imprime ni se loguea.

Correr:  python configurar_datalake.py
(desde Claude Code, el analista lo corre él mismo con:  ! python configurar_datalake.py)
"""
import os
import getpass
from pathlib import Path

envs = Path(__file__).resolve().parent.parent / "envs"
envs.mkdir(exist_ok=True)
user_win = os.environ.get("USERNAME", "").lower() or input("Usuario Windows (para el nombre del archivo): ").strip().lower()
dest = envs / f".env.{user_win}"

print(f"\nCredenciales del datalake  ->  {dest}")
print("(las mismas de Metabase / equipo de datos)\n")
u = input("  USER  (ej: nombre.apellido@ar.infra.d): ").strip()
p = getpass.getpass("  PASSWORD (no se muestra): ")
if not u or not p:
    raise SystemExit("USER y PASSWORD son obligatorios. Nada guardado.")

dest.write_text(f"USER={u}\nPASSWORD={p}\n", encoding="utf-8")
print(f"\nOK -> {dest}")
print("Listo. Verificá con:  python setup_check.py --full")
