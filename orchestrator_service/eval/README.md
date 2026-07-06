# Banco de pruebas del agente (offline)

Corre una lista de **casos de conversación** contra el **prompt real** de la clínica
y un **juez IA** marca cada respuesta ✅/❌. Sirve para:

- **Detectar regresiones**: cambiás el prompt/tokens/modelo y verificás que no se rompió nada.
- **Comparar modelos**: mismo set de casos, distinto modelo → ves calidad + tokens + costo.

Es **100% seguro**: NO usa herramientas (no agenda, no escribe en la base, no manda WhatsApp).
Solo arma el prompt real y le pregunta a la IA; un segundo modelo (juez) evalúa la respuesta.

## Cómo correrlo

Corre **dentro del contenedor del orquestador** (ahí tiene la base, el modelo y la API key).

```bash
# 1) Averiguar el nombre del contenedor de PRUEBAS
docker ps --format '{{.Names}}' | grep -i orchestrator | grep -i pruebas

# 2) Correr el banco (reemplazá <cont> por el nombre)
docker exec -it <cont> python -m eval.run

# Comparar otro modelo (mismos casos)
docker exec -it <cont> python -m eval.run --model deepseek-chat

# Solo una categoría / un caso
docker exec -it <cont> python -m eval.run --categoria cobertura
docker exec -it <cont> python -m eval.run --case nombre-cobertura-no-es-nombre --show-response

# Ver el prompt real que se está probando (para revisarlo)
docker exec -it <cont> python -m eval.run --show-prompt | less
```

Si los archivos `eval/` todavía no están en el contenedor (porque no se deployó), se pueden copiar sin deploy:

```bash
docker cp orchestrator_service/eval <cont>:/app/eval
```

## Requisitos de entorno (ya presentes en el contenedor)

- `POSTGRES_DSN` (o `DATABASE_URL`) — para leer la config real del tenant.
- `OPENAI_API_KEY` (y `DEEPSEEK_API_KEY` si probás DeepSeek).

## Opciones

| Flag | Default | Qué hace |
|------|---------|----------|
| `--tenant N` | 1 | Tenant/clínica a probar |
| `--model X` | el configurado en *Tokens y Métricas* | Fuerza un modelo (para comparar) |
| `--judge-model X` | `gpt-5.4-mini` | Modelo que hace de juez |
| `--categoria C` | (todas) | Filtra por categoría |
| `--case ID` | (todos) | Corre un solo caso |
| `--temperature T` | 0.3 | Temperatura del modelo bajo prueba |
| `--show-response` | off | Imprime la respuesta completa de cada caso |
| `--show-prompt` | off | Vuelca el system prompt y sale |

Código de salida: `0` si pasan todos, `1` si falla alguno (útil para automatizar).

## Agregar casos

Editá `cases.jsonl` — **un caso por línea** (JSON). Campos:

- `id`, `categoria` — identificación.
- `patient_status` — `new_lead` | `patient_no_appointment` | `patient_with_appointment`.
- `patient_context` *(opcional)* — texto de contexto del paciente (turnos, nombre) para simular un paciente existente.
- `history` *(opcional)* — turnos previos: `[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]`.
- `user` — el mensaje del paciente a evaluar.
- `espera` — lista de criterios en lenguaje natural que evalúa el **juez IA**.
- `prohibido` / `requiere` *(opcional)* — subcadenas exactas que NO deben / SÍ deben aparecer (chequeo determinista, más confiable para reglas duras).

## Limitación actual (fase 1)

Esta versión prueba la **conducta conversacional** (saludo, cobertura, tono, profesional interno,
nombre, derivación, etc.) — la "mitad de adelante" de la charla. **No ejecuta herramientas**, así que
los flujos que dependen de `check_availability`/`book_appointment` (ofrecer horarios reales,
`preferred_days`, "fin de mes", secuencia post-booking) se cubren en una **fase 2** con herramientas
simuladas (mock). Está anotado para no dar falsa sensación de cobertura total.
