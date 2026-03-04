# Sistema de Migraciones de ClinicForge — Estado Actual y Roadmap a Alembic

## 1. Contexto: ¿Qué es el "Maintenance Robot"?

Al arrancar el servicio `orchestrator_service`, el archivo `db.py` establece la conexión con PostgreSQL y ejecuta automáticamente todas las migraciones pendientes antes de que la API empiece a recibir tráfico. A este mecanismo lo llamamos internamente **Maintenance Robot**.

```
docker start orchestrator_service
        │
        └── db.connect()
                │
                ├── _apply_foundation()      → Aplica el esquema base (dentalogic_schema.sql)
                │
                └── _run_evolution_pipeline() → Ejecuta lista de parches SQL en orden
```

---

## 2. Los Dos Planos del Sistema Actual

> [!IMPORTANT]
> Este es el punto más crítico para entender por qué ocurren bugs de migración.

El sistema tiene **dos capas que NO están conectadas automáticamente**:

| Plano | Ubicación | ¿Se ejecuta en producción? |
|-------|-----------|---------------------------|
| **Archivos `.sql`** | `orchestrator_service/migrations/patch_0XX_*.sql` | ❌ **NO** — son solo documentación/referencia |
| **Maintenance Robot** | `orchestrator_service/db.py` → `_run_evolution_pipeline` | ✅ **SÍ** — lista de strings SQL en Python |

### Flujo correcto para agregar una migración HOY

```
1. Escribir la migración en migrations/patch_0XX_nombre.sql   ← documentación
         ↓
2. Copiar el SQL al método _run_evolution_pipeline() en db.py ← esto SÍ se ejecuta
         ↓
3. Push + redeploy del orchestrator
```

Si solo se hace el paso 1 y no el 2, **la tabla nunca se crea en producción**. Este fue el bug que causó el error `relation "meta_form_leads" does not exist`.

---

## 3. Estructura del `_run_evolution_pipeline`

```python
# db.py — dentro de la clase Database

async def _run_evolution_pipeline(self, logger):
    patches = [
        # Parche 1: ...
        """
        DO $$
        BEGIN
            -- SQL idempotente aquí
        END $$;
        """,

        # Parche 2: ...
        """CREATE TABLE IF NOT EXISTS ...""",

        # ... (actualmente hasta Parche 27)
    ]

    async with self.pool.acquire() as conn:
        async with conn.transaction():
            for i, patch in enumerate(patches):
                await conn.execute(patch)  # Falla rápido si hay error
```

### Reglas de oro para escribir un parche

- **Idempotente**: debe poder ejecutarse N veces sin romper nada.
  - Usar `CREATE TABLE IF NOT EXISTS`
  - Usar `CREATE INDEX IF NOT EXISTS`
  - Usar bloques `DO $$ BEGIN ... IF NOT EXISTS ... END $$;` para `ALTER TABLE`
- **Sin `BEGIN/COMMIT`** propios: el pipeline ya envuelve todo en una transacción.
- **Sin dependencias externas**: cada parche debe bastarse a sí mismo.

---

## 4. Limitaciones del Sistema Actual

| Limitación | Impacto |
|------------|---------|
| **Sin versioning formal** | No hay tabla de control tipo `alembic_version`. No sabes qué parches se aplicaron y cuáles no. |
| **Sin rollback** | Los parches no tienen `downgrade`. Si un parche rompe algo, hay que corregirlo con otro parche. |
| **Acoplamiento SQL+Python** | El SQL vive dentro de strings en Python, lo que dificulta revisión, linting y testing. |
| **Archivo `.sql` desincronizado** | El `.sql` en `migrations/` es documentación que puede quedar desactualizada fácilmente. |
| **Orden implícito** | El orden de los parches es el orden de la lista en Python. Fácil de romper con un merge mal hecho. |

---

## 5. Roadmap: Migración a Alembic

### ¿Por qué Alembic?

Alembic es el sistema de migraciones estándar para SQLAlchemy. Provee:
- ✅ Tabla `alembic_version` en la DB (sabe exactamente en qué versión está)
- ✅ `upgrade` y `downgrade` por migración
- ✅ Archivos `.py` uno por migración, con historial Git limpio
- ✅ Generación automática de migraciones desde modelos (`--autogenerate`)
- ✅ CLI (`alembic upgrade head`, `alembic history`, etc.)

### Plan de implementación sugerido para el desarrollador

#### Fase 1 — Setup de Alembic (sin romper lo existente)

```bash
pip install alembic sqlalchemy asyncpg
alembic init alembic
```

Configurar `alembic.ini` y `alembic/env.py` apuntando al mismo `POSTGRES_DSN`.

#### Fase 2 — Migración inicial (baseline)

Crear una migración `baseline` que refleje el estado actual de la DB **sin ejecutar nada** (la DB ya existe):

```bash
alembic revision --rev-id=001 --message="baseline_existing_schema"
```

En el archivo generado, el `upgrade()` queda vacío (o usa `pass`) y el `downgrade()` también. Luego marcar la DB en ese estado:

```bash
alembic stamp 001
```

#### Fase 3 — Migraciones nuevas en Alembic

A partir de aquí, cada nueva tabla/columna se crea con:

```bash
alembic revision --autogenerate -m "add_meta_form_leads"
alembic upgrade head
```

#### Fase 4 — Deprecar el Maintenance Robot

Una vez que Alembic está gestionando las migraciones:

1. Reemplazar `_run_evolution_pipeline()` por una llamada a `alembic upgrade head` al inicio.
2. Eliminar los strings SQL de `db.py`.
3. Mantener los archivos `.sql` en `migrations/` como referencia histórica.

#### Fase 5 — CI/CD

Agregar al pipeline de deploy:
```bash
alembic upgrade head  # antes de `uvicorn main:app`
```

---

## 6. Preguntas Frecuentes para la Llamada

**¿Los parches actuales de `db.py` son seguros para coexistir con Alembic?**
Sí, mientras sean idempotentes. Durante la transición se pueden dejar corriendo y Alembic solo gestiona lo nuevo.

**¿Qué pasa si alguien pushea un parche a `db.py` Y una migración Alembic para lo mismo?**
Se ejecutan dos veces — por eso son idempotentes. Pero hay que coordinar y elegir uno solo durante la transición.

**¿Usamos SQLAlchemy Models o SQL puro?**
Alembic funciona con ambos. Con `--autogenerate` necesita modelos SQLAlchemy definidos. Sin modelos, se escriben las migraciones a mano en Python (equivalente a lo actual pero con versionado).

**¿Tiempo estimado de implementación?**
- Fase 1 y 2 (setup + baseline): ~1 día
- Fase 3 (primeras migraciones nuevas): inmediato
- Fase 4 (deprecar Robot): ~2-3 días de pruebas
- Fase 5 (CI/CD): ~1 día
