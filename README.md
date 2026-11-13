# docs-ops · operación del proyecto

Carpeta de trabajo esperada (todos los repos clonados lado a lado):
```
CanvaSLS/
├── infra-base/  ms-auth/  ms-cursos/  ms-evaluaciones/  ms-analitica/  ms-notificaciones/  ms-practica/
├── datos-seed/  pruebas-locales/  docs-ops/  frontend-web/
```
| Script | Qué hace |
|---|---|
| `deploy-all.sh [stage]` | Despliega en orden, imprime las `VITE_API_*` y escribe `salida/apis.env` y `salida/apis.json` |
| `smoke_test.py --apis salida/apis.json` | Prueba de humo del sistema desplegado (tabla PASS/FAIL para el informe) |
| `destroy-all.sh` | Elimina todo (vacía S3 primero) |
| `push-all.sh "msg"` | Crea/sube cada carpeta como repo público de la organización (con candado anti-credenciales) |
| `aplicar-frontend.sh <ruta>` | Copia el kit conectado a AWS dentro de `frontend-web` |
| `gen_openapi.py` | Regenera `openapi.yaml` (Swagger) desde los `serverless.yml` |

**Reglas de oro:** (1) las credenciales del Learner Lab duran ~4 h y no se suben jamás; (2) un solo integrante despliega la cuenta de la demo; los demás prueban en la suya (`deploy-all.sh dev --solo ms-auth,ms-<suyo>`); (3) si cambias `common.py`, cópialo a todos los servicios y corre `pruebas-locales/test_e2e.py`.

**Si API Gateway devuelve 500 "Invalid permissions on Lambda function"** (autorizador compartido):
```bash
aws lambda add-permission --function-name ms-auth-dev-autorizar --statement-id apigw-compartido \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:<TU_CUENTA>:*/authorizers/*"
```

## Problemas con la RDS (cursos y evaluaciones)
| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `deploy-all.sh` pide `DB_PASSWORD` | falta la variable | `export DB_PASSWORD='...'` (8+ caracteres, sin `/ @ "` ni espacios) |
| Lambda 502 / timeout en `/cursos` | la RDS no es pública o el Security Group no abre 3306 | RDS → Connectivity: *Publicly accessible = Yes*; Security Group con 3306 de entrada |
| `Access denied for user 'admin'` | la contraseña de los servicios ≠ la de la RDS | usar la MISMA `DB_PASSWORD` y redesplegar `ms-cursos` y `ms-evaluaciones` |
| `No module named 'pymysql'` | no se instaló `vendor/` antes de desplegar | `pip install -r requirements.txt -t vendor` y volver a desplegar ese servicio |
| `'cryptography' package is required` | el usuario usa `caching_sha2_password` | cambiar `Engine` a `mariadb` en `infra-base`, o crear el usuario con `mysql_native_password` |
| La RDS está "stopped" | el laboratorio la detuvo | RDS → Actions → Start (tarda unos minutos) |
| Necesito volver a DynamoDB | RDS no funciona a tiempo | copiar `../_respaldo-dynamodb/ms-cursos`, `ms-evaluaciones` y `datos-seed` sobre las carpetas actuales y redesplegar |
