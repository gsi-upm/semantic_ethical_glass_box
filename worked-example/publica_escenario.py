#!/usr/bin/env python3
"""Publica los TTL de un escenario en SEGB.

Por defecto es un ensayo (dry-run): valida cada fichero con POST /ttl/validate y NO envía nada.
Para enviar de verdad hay que pasar --enviar; antes comprueba GET /healthz/ready. Cada envío deja una entrada
en /history, así que enviar dos veces duplica la auditoría: envíalo una sola vez.

Solo usa la librería estándar.

Variables opcionales:
  SEGB_URL    URL del backend (por defecto http://localhost:5000)
  SEGB_TOKEN  token Bearer, solo si la autenticación está activada. No se imprime.

Uso:
    python3 publica_escenario.py                      # ensayo: valida ttl/escenario/*.ttl (junto a este script)
    python3 publica_escenario.py --enviar             # valida y envía, un log por fichero
    python3 publica_escenario.py --carpeta otra       # usa ttl/otra/
    python3 publica_escenario.py --enviar --sin-validar   # con token logger (validar exige admin)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def call(base_url: str, path: str, payload: dict | None, token: str | None) -> tuple[int, dict | str]:
    """Llama a la API (GET si no hay payload, POST JSON si lo hay). Devuelve (código HTTP, cuerpo).

    Código 0 significa que no hubo respuesta (sin conexión o tiempo agotado).
    """
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            code = resp.status
    except urllib.error.HTTPError as exc:
        body, code = exc.read().decode("utf-8"), exc.code
    except OSError as exc:  # incluye URLError, conexión cortada y tiempo agotado
        return 0, f"sin respuesta de {base_url}: {getattr(exc, 'reason', exc)}"
    try:
        return code, json.loads(body)
    except json.JSONDecodeError:
        return code, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("SEGB_URL", "http://localhost:5000"), help="URL del backend")
    parser.add_argument("--carpeta", default="escenario", help="subcarpeta de ttl/ con los ficheros (orden alfabético)")
    parser.add_argument("--user", default="demo_user", help="valor 'user' que se manda a la API")
    parser.add_argument("--sin-validar", action="store_true",
                        help="no llamar a /ttl/validate (exige rol admin); para publicar con un token logger")
    parser.add_argument("--enviar", action="store_true", help="enviar de verdad (sin esto es un ensayo)")
    args = parser.parse_args()

    token = os.getenv("SEGB_TOKEN")  # no se imprime nunca
    folder = Path(__file__).resolve().parent / "ttl" / args.carpeta
    files = sorted(folder.glob("*.ttl"))
    if not files:
        sys.exit(f"No hay .ttl en {folder}")

    print(f"Modo: {'ENVÍO REAL' if args.enviar else 'ensayo (no se envía nada)'} | API: {args.url}")
    all_valid = True
    total = 0
    if args.sin_validar:
        print("Sin validar: " + ", ".join(f.name for f in files))
    for f in [] if args.sin_validar else files:
        ttl = f.read_text(encoding="utf-8")
        code, body = call(args.url, "/ttl/validate", {"ttl_content": ttl, "user": args.user}, token)
        if code == 0:
            sys.exit(f"{body}. ¿Está el stack arriba? Prueba GET /healthz/ready.")
        if code in (401, 403):
            sys.exit(f"{f.name}: HTTP {code}. /ttl/validate exige rol admin; revisa tu token. "
                     "Con un token logger puedes publicar usando --sin-validar.")
        if code != 200 or not isinstance(body, dict):
            # Un Turtle roto NO llega aquí: según el código da 200 con valid=false y TTL_SYNTAX_ERROR.
            sys.exit(f"{f.name}: la validación no devolvió el formato esperado (HTTP {code}). Respuesta: {body}")
        issues = body.get("issues", [])
        total += body.get("triple_count", 0)
        print(f"- {f.name}: valid={body.get('valid')} tripletas={body.get('triple_count')} "
              f"errores={sum(i.get('severity') == 'error' for i in issues)} "
              f"avisos={sum(i.get('severity') == 'warning' for i in issues)}")
        for i in issues:
            print(f"    [{i.get('severity')}] {i.get('code', '?')}: {i.get('message', '')}")
        all_valid &= bool(body.get("valid"))

    if not args.sin_validar:
        print(f"Total: {len(files)} ficheros, {total} tripletas (sumadas por fichero).")
    if not all_valid:
        print("Hay errores de validación: no se envía nada.")
        return 1
    if not args.enviar:
        print("Ensayo terminado. Añade --enviar para publicar (una sola vez).")
        return 0

    code, body = call(args.url, "/healthz/ready", None, token)
    if code != 200 or not isinstance(body, dict) or not body.get("ready"):
        print(f"El backend no está listo (HTTP {code}): {body}. No se envía nada.")
        return 1

    sent: list[str] = []
    for f in files:
        code, body = call(args.url, "/ttl", {"ttl_content": f.read_text(encoding="utf-8"), "user": args.user}, token)
        print(f"- POST /ttl {f.name}: HTTP {code}")
        if code != 201 or not isinstance(body, dict):
            print(f"  Detalle: {body}")
            if code == 429:
                print("  Había otra transacción en curso: este fichero no se ha insertado y se puede reintentar.")
            elif code == 0:
                print("  Sin respuesta: no se sabe si se insertó. Mira GET /history antes de reintentarlo.")
            print(f"  Ya enviados antes del fallo: {sent or 'ninguno'}. "
                  "No repitas esos: duplicarías su entrada en /history.")
            if sent:
                print("  Para enviar solo los que faltan, cópialos a otra subcarpeta de ttl/ y usa --carpeta.")
            return 1
        print(f"  log_id: {body.get('log_id')}")
        sent.append(f.name)
    print("Enviado. Apunta los log_id y comprueba la auditoría con GET /history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
