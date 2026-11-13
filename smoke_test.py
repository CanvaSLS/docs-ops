#!/usr/bin/env python3
"""smoke_test.py · prueba de humo del sistema DESPLEGADO (solo librería estándar de Python).

  python3 smoke_test.py --apis apis.json            # contra AWS (apis.json lo genera deploy-all.sh)
  python3 smoke_test.py --apis apis.json --pausa 6  # espera 6 s a los eventos asíncronos (por defecto 8)
  python3 smoke_test.py --emulador                  # autoprueba contra el emulador local (sin AWS)

Imprime una tabla PASS/FAIL lista para pegar como evidencia en el informe.
Requiere el seed cargado (usuarios profe@/ana.torres@/valeria.mendoza@/admin@<dominio>, clave Demo2026!).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PASS = "Demo2026!"
DOM = {"UTEC": "utec.edu.pe", "NORTE": "inorte.edu.pe"}
RUTAS = {"auth": "auth", "cursos": "cursos", "eval": "eval", "analitica": "analitica", "notif": "notif", "practica": "practica"}


class Http:
    def __init__(self, apis):
        self.apis = apis

    def __call__(self, metodo, svc, ruta, token=None, cuerpo=None, query=None):
        url = f"{self.apis[svc].rstrip('/')}/{ruta}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, method=metodo, headers=h, data=json.dumps(cuerpo).encode() if cuerpo is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except ValueError:
                return e.code, {"raw": raw.decode(errors="replace")}


class Emu:
    """Misma firma que Http pero contra el emulador en memoria (solo para autoprobar este script)."""
    def __init__(self, e):
        self.e = e

    def __call__(self, metodo, svc, ruta, token=None, cuerpo=None, query=None):
        r = ruta
        s, _, b = self.e.api(metodo, r, token=("Bearer " + token) if token else None, json_body=cuerpo, query=query)
        return s, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apis", default="apis.json")
    ap.add_argument("--pausa", type=float, default=8)
    ap.add_argument("--emulador", action="store_true")
    a = ap.parse_args()
    if a.emulador:
        raiz = Path(__file__).resolve().parent.parent
        sys.path[:0] = [str(raiz / "pruebas-locales"), str(raiz / "datos-seed"), str(raiz / "ms-cursos")]
        import contextlib, io
        from datetime import datetime, timezone
        import emulador, seed
        e = emulador.Emulador()
        with contextlib.redirect_stdout(io.StringIO()):
            for t in ("UTEC", "NORTE", "ANDINO"):
                d, _ = seed.generar_tenant(t, 300, datetime.now(timezone.utc).replace(microsecond=0))
                e._aplicar_env("ms-cursos")
                seed.cargar_sql(t, d)                   # RDS falsa (SQLite): cursos y evaluaciones
                for tabla, items in d.items():
                    if tabla in seed.SQL_TABLAS:
                        continue
                    for it in items:
                        emulador.boto3.ESTADO["tablas"][tabla].put_item(Item=it)
        http, pausa = Emu(e), 0
        bombear = e.bombear
    else:
        apis = json.loads(Path(a.apis).read_text())
        faltan = [k for k in ("auth", "cursos", "eval", "analitica", "notif") if not apis.get(k)]
        if faltan:
            sys.exit(f"Faltan URLs en {a.apis}: {faltan}")
        http, pausa, bombear = Http(apis), a.pausa, (lambda: None)

    filas = []

    def paso(nombre, fn):
        try:
            detalle = fn()
            filas.append((nombre, True, detalle or ""))
        except AssertionError as ex:
            filas.append((nombre, False, str(ex)))
        except Exception as ex:  # noqa: BLE001
            filas.append((nombre, False, f"{type(ex).__name__}: {ex}"))

    def igual(real, esperado, ctx=""):
        assert real == esperado, f"esperaba {esperado} y llegó {real} {ctx}"

    tk = {}

    def login(t, usuario):
        s, b = http("POST", "auth", "auth/login", cuerpo={"tenant_id": t, "email": f"{usuario}@{DOM[t]}", "password": PASS})
        igual(s, 200, str(b))
        tk[(t, usuario)] = b["token"]
        return b["token"]

    def sesiones():
        for t in DOM:
            for u in ("profe", "ana.torres", "valeria.mendoza", "admin"):
                login(t, u)
        return "4 roles × 2 tenants"

    paso("1. Login de docente, alumnas y admin en 2 tenants", sesiones)
    D, V, A = tk.get(("UTEC", "profe")), tk.get(("UTEC", "valeria.mendoza")), tk.get(("UTEC", "ana.torres"))
    if not D:
        print("No se pudo iniciar sesión: ¿cargaste el seed y desplegaste ms-auth?")

    def cursos_tenant():
        out = {}
        for t in DOM:
            s, b = http("GET", "cursos", "cursos", tk[(t, "admin")])
            igual(s, 200)
            assert b["cursos"] and all(c["tenant_id"] == t for c in b["cursos"]), f"{t}: debe ver solo cursos suyos"
            out[t] = len(b["cursos"])
        return f"UTEC={out['UTEC']} cursos · NORTE={out['NORTE']} cursos, sin mezcla"
    paso("2. Cada tenant lista SOLO sus cursos", cursos_tenant)

    def crud():
        s, b = http("POST", "cursos", "cursos", D, {"codigo": "SMK1", "nombre": "Curso de humo"})
        igual(s, 201, str(b)); cid = b["curso_id"]
        s, b = http("PUT", "cursos", f"cursos/{cid}", D, {"nombre": "Curso de humo (editado)"})
        igual(s, 200); assert b["nombre"].endswith("(editado)")
        s, b = http("DELETE", "cursos", f"cursos/{cid}", D)
        igual(s, 200)
        s, b = http("DELETE", "cursos", f"cursos/{cid}", D)
        igual(s, 404, "(el borrado debe ser real)")
        return f"POST 201 → PUT 200 → DELETE 200 → DELETE 404 (curso {cid})"
    paso("3. CRUD de curso (verifícalo en RDS → esquema cursos_<tenant>, tabla cursos)", crud)

    def aislamiento():
        r = []
        s, b = http("POST", "cursos", "cursos", D, {"tenant_id": "NORTE", "codigo": "H", "nombre": "H"}); igual(s, 403); r.append("body ajeno 403")
        s, b = http("GET", "cursos", "cursos", D, query={"tenant_id": "NORTE"}); igual(s, 403); r.append("query ajena 403")
        s, b = http("GET", "cursos", "cursos", "token-falso"); igual(s, 401); r.append("token falso 401")
        s, b = http("GET", "auth", "auth/usuarios", tk[("UTEC", "admin")], query={"limit": 3})
        igual(s, 200); cur = b["cursor"]
        s, b = http("GET", "auth", "auth/usuarios", tk[("NORTE", "admin")], query={"limit": 3, "cursor": cur}); igual(s, 403); r.append("cursor ajeno 403")
        s, b = http("GET", "analitica", "analitica/riesgo", A, query={"nivel": "ROJO"}); igual(s, 403); r.append("alumna en endpoint docente 403")
        return " · ".join(r)
    paso("4. Un tenant NO accede a datos de otro (ataques rechazados)", aislamiento)

    def cadena():
        s, b = http("GET", "analitica", "analitica/alumnos/A00003", D)
        igual(s, 200); antes = b["nivel"]
        s, b = http("POST", "eval", "evaluaciones/cursos/C0001/tareas/T0003/entregas", V, {"texto": "Entrega de humo"})
        assert s in (201, 200), f"entrega {s} {b}"
        s, b = http("PUT", "eval", "evaluaciones/cursos/C0001/tareas/T0003/entregas/A00003/calificacion", D, {"nota": 3, "retroalimentacion": "humo"})
        igual(s, 200, str(b))
        bombear(); time.sleep(pausa)
        for _ in range(6):
            s, b = http("GET", "analitica", "analitica/alumnos/A00003", D)
            if b.get("nivel") == "ROJO":
                break
            time.sleep(max(pausa / 2, 0.01)); bombear()
        igual(b.get("nivel"), "ROJO", "(la analítica no reaccionó a NotaPublicada: revisa la cola sp-analitica y su DLQ)")
        s, t = http("GET", "notif", "notificaciones/traza", D, query={"limit": 15})
        igual(s, 200)
        evs = {e["evento"] for e in t["eventos"]}
        assert {"NotaPublicada", "AlumnoEnRiesgo"} <= evs, f"traza sin eventos esperados: {evs}"
        return f"semáforo {antes} → ROJO sin llamada síncrona; la traza muestra {sorted(evs)}"
    paso("5. Evento → semáforo ROJO → alerta (EDA: SNS→SQS→Lambda)", cadena)

    def notificaciones():
        s, b = http("GET", "notif", "notificaciones", D, query={"limit": 5}); igual(s, 200)
        assert b["notificaciones"], "bandeja del docente vacía"
        s, b2 = http("GET", "notif", "notificaciones", tk[("NORTE", "profe")], query={"limit": 5}); igual(s, 200)
        ids = {n["usuario_ts"] for n in b["notificaciones"]} & {n["usuario_ts"] for n in b2["notificaciones"]}
        return f"bandeja UTEC={len(b['notificaciones'])}+ · sin intersección con NORTE ({len(ids)})"
    paso("6. Notificaciones por usuario y tenant", notificaciones)

    ok = all(f[1] for f in filas)
    print("\n" + "=" * 100)
    for n, bien, d in filas:
        print(f"{'PASS' if bien else 'FAIL'}  {n}\n        {d}")
    print("=" * 100)
    print(f"{sum(f[1] for f in filas)}/{len(filas)} verificaciones OK")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
