#!/usr/bin/env python3
"""gen_openapi.py · genera openapi.yaml (Swagger) DIRECTO de los serverless.yml: nunca se desincroniza.
   python3 gen_openapi.py        # escribe ../frontend-kit/public/docs/openapi.yaml y docs-ops/openapi.yaml
Las URLs reales las inyecta public/docs/index.html leyendo apis.json (lo produce deploy-all.sh)."""
import sys
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "pruebas-locales"))
import emulador  # noqa: E402

SVC = {"ms-auth": "auth", "ms-cursos": "cursos", "ms-evaluaciones": "eval", "ms-analitica": "analitica",
       "ms-notificaciones": "notif", "ms-practica": "practica"}
RESUMEN = {
    "registro": "Registrar usuario (alumno/docente) en un tenant", "login": "Iniciar sesión → token con TTL",
    "me": "Identidad del token", "listarUsuarios": "Listar usuarios del tenant (paginado)",
    "listarCursos": "Listar cursos según rol", "crearCurso": "Crear curso", "modificarCurso": "Modificar curso",
    "eliminarCurso": "Eliminar curso", "listarModulos": "Listar módulos", "publicarModulo": "Publicar módulo (emite ModuloPublicado)",
    "matricularEstudiante": "Matricular (autoservicio del alumno)", "listarMatriculas": "Listar matrículas del curso",
    "agregarMaterial": "Registrar material y obtener URL prefirmada PUT (S3)", "descargarMaterial": "URL prefirmada GET (S3)",
    "listarTareas": "Listar tareas del curso", "crearTarea": "Crear tarea", "registrarEntrega": "Entregar tarea (emite EntregaRegistrada)",
    "listarEntregas": "Listar entregas de una tarea (docente)", "calificarEntrega": "Calificar entrega (emite NotaPublicada)",
    "misNotas": "Mis entregas y resumen", "obtenerIndicadores": "Indicadores y semáforo de un alumno",
    "consultarRiesgo": "Alumnos por nivel de riesgo (GSI)", "resumenRiesgo": "Conteo VERDE/AMBAR/ROJO",
    "listarNotificaciones": "Bandeja del usuario", "marcarLeida": "Marcar una notificación", "marcarTodas": "Marcar todas",
    "trazaEventos": "Línea de tiempo de eventos del tenant", "obtenerQuiz": "Quiz de práctica (sin respuestas)", "completarQuiz": "Calificar quiz (emite QuizCompletado)",
}
EJEMPLOS = {
    ("POST", "auth/login"): {"tenant_id": "UTEC", "email": "profe@utec.edu.pe", "password": "Demo2026!"},
    ("POST", "auth/registro"): {"tenant_id": "UTEC", "email": "nuevo@utec.edu.pe", "nombre": "Nuevo Alumno", "password": "ClaveSegura1", "rol": "alumno"},
    ("POST", "cursos"): {"codigo": "CS2032", "nombre": "Computación en la Nube"},
    ("PUT", "cursos/{curso_id}"): {"nombre": "Computación en la Nube (2026-2)"},
    ("POST", "cursos/{curso_id}/modulos"): {"titulo": "Módulo 7: Observabilidad"},
    ("POST", "evaluaciones/cursos/{curso_id}/tareas"): {"titulo": "Laboratorio 5", "fecha_limite": "2026-12-01T23:59:00Z", "puntaje_max": 20},
    ("POST", "evaluaciones/cursos/{curso_id}/tareas/{tarea_id}/entregas"): {"texto": "Adjunto mi solución"},
    ("PUT", "evaluaciones/cursos/{curso_id}/tareas/{tarea_id}/entregas/{alumno_id}/calificacion"): {"nota": 4, "retroalimentacion": "Reforzar IAM"},
    ("POST", "cursos/{curso_id}/modulos/{modulo_id}/materiales"): {"nombre_archivo": "guia.pdf", "content_type": "application/pdf"},
    ("POST", "practica/quiz/completar"): {"curso_id": "C0001", "respuestas": [{"tarjeta_id": "K00001", "opcion": 0}]},
    ("POST", "notificaciones/leida"): {"id": "D001#2026-11-12T10:00:00Z#<event_id>"},
}


def main():
    e = emulador.Emulador()
    paths = {}
    for r in e.rutas:
        op = {"tags": [r["servicio"]], "summary": RESUMEN.get(r["funcion"], r["funcion"]), "operationId": r["funcion"],
              "responses": {"200": {"description": "OK"}, "400": {"description": "Validación"}, "401": {"description": "Token ausente/inválido/expirado"},
                            "403": {"description": "Rol, tenant o prefijo no autorizado"}, "404": {"description": "No existe en tu tenant"}}}
        if r["auth"]:
            op["security"] = [{"bearer": []}]
        params = [{"name": p, "in": "path", "required": True, "schema": {"type": "string"}} for p in __import__("re").findall(r"\{(\w+)\}", r["path"])]
        if r["metodo"] == "GET":
            params += [{"name": "limit", "in": "query", "schema": {"type": "integer"}}, {"name": "cursor", "in": "query", "schema": {"type": "string"}}]
        if params:
            op["parameters"] = params
        ej = EJEMPLOS.get((r["metodo"], r["path"]))
        if ej:
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"type": "object"}, "example": ej}}}
        item = paths.setdefault("/" + r["path"], {})
        item[r["metodo"].lower()] = op
        item["servers"] = [{"url": f"https://api.invalid/{SVC[r['servicio']]}", "description": r["servicio"]}]
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "CanvaSLS API", "version": "1.0.0",
                 "description": "6 microservicios serverless (un API Gateway cada uno). Pulsa **Authorize**, pega el `token` de /auth/login y prueba. "
                                "El tenant NUNCA se envía: sale del token (Lambda Authorizer). Credenciales demo: profe@utec.edu.pe / Demo2026!"},
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "paths": paths,
    }
    for destino in (AQUI / "openapi.yaml", AQUI.parent / "frontend-kit" / "public" / "docs" / "openapi.yaml"):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"openapi.yaml generado: {len(e.rutas)} operaciones")


if __name__ == "__main__":
    main()
