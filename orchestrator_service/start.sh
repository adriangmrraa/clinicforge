#!/bin/sh

# Install PostgreSQL extensions BEFORE alembic (requires autocommit, outside transactions)
echo "Instalando extensiones PostgreSQL..."
python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
for ext in ['pg_trgm', 'vector']:
    try:
        cur.execute(f'CREATE EXTENSION IF NOT EXISTS {ext}')
        print(f'  Extension {ext}: OK')
    except Exception as e:
        print(f'  Extension {ext}: not available ({e})')

# Fix collation version mismatch (idempotent — no-op if versions match)
try:
    cur.execute("ALTER DATABASE postgres REFRESH COLLATION VERSION")
    print('  Collation version: refreshed')
except Exception as e:
    print(f'  Collation version: skipped ({e})')
conn.close()
" 2>/dev/null || echo "  Extension install skipped (connection failed)"

echo "Verificando estado de migraciones..."

# Detect DB state:
# - FRESH: no tables, no alembic → run baseline + stamp head
# - STAMPED_BROKEN: alembic says head but columns missing → nuke + baseline + stamp
# - EXISTING_NO_ALEMBIC: tables exist but no alembic → stamp head
# - NORMAL: alembic + tables + columns OK → upgrade head
DB_ACTION=$(python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\")
has_alembic = cur.fetchone()[0]
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='tenants')\")
has_tenants = cur.fetchone()[0]

if has_tenants and not has_alembic:
    print('EXISTING_NO_ALEMBIC')
elif has_alembic and has_tenants:
    # Check if schema is actually complete
    cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='acquisition_source')\")
    has_recent = cur.fetchone()[0]
    if has_recent:
        print('NORMAL')
    else:
        # Stamped but schema incomplete — nuke everything
        cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\")
        for r in cur.fetchall():
            cur.execute('DROP TABLE IF EXISTS public.\"' + r[0] + '\" CASCADE')
        print('FRESH')
elif has_alembic and not has_tenants:
    # Alembic exists but no tables — drop alembic and start fresh
    cur.execute('DROP TABLE IF EXISTS alembic_version CASCADE')
    print('FRESH')
else:
    print('FRESH')

conn.close()
" 2>/dev/null || echo "FRESH")

echo "DB_ACTION=$DB_ACTION"

if [ "$DB_ACTION" = "EXISTING_NO_ALEMBIC" ]; then
    echo "DB existente sin Alembic. Marcando baseline..."
    alembic stamp head
    echo "Baseline marcado."
elif [ "$DB_ACTION" = "FRESH" ]; then
    echo "DB fresca. Ejecutando baseline..."
    # Run the baseline migration (creates most of the schema)
    alembic upgrade a1b2c3d4e5f6
    # Now run each remaining migration individually, skipping failures
    # (baseline already created some columns/tables that incrementals try to add)
    echo "Ejecutando migraciones incrementales (tolerando duplicados)..."
    python -c "
import subprocess, re, sys
result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True)
head = result.stdout.strip().split()[0] if result.stdout.strip() else ''
result = subprocess.run(['alembic', 'history', '--indicate-current', '-r', 'a1b2c3d4e5f6:' + head], capture_output=True, text=True)
revisions = []
for line in result.stdout.strip().split('\n'):
    m = re.search(r'-> ([a-f0-9]+)', line)
    if m and m.group(1) != 'a1b2c3d4e5f6':
        revisions.append(m.group(1))
revisions.reverse()
failed = 0
for rev in revisions:
    r = subprocess.run(['alembic', 'upgrade', rev], capture_output=True, text=True)
    if r.returncode != 0:
        if 'already exists' in r.stderr or 'DuplicateColumn' in r.stderr or 'DuplicateTable' in r.stderr:
            subprocess.run(['alembic', 'stamp', rev], capture_output=True)
            failed += 1
        else:
            print(f'ERROR en {rev}: {r.stderr[-200:]}', file=sys.stderr)
            subprocess.run(['alembic', 'stamp', rev], capture_output=True)
            failed += 1
print(f'Migraciones: {len(revisions)} total, {failed} con duplicados (stamped)')
"
    echo "Schema completo."
else
    echo "Aplicando migraciones incrementales..."
    alembic upgrade head
    echo "Migraciones aplicadas."
fi

# Patch: columns added outside Alembic (run_meta_ads_migrations.py) — idempotent
echo "Aplicando patches de schema (IF NOT EXISTS)..."
python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
patches = [
    # Meta Ads attribution columns on patients (from run_meta_ads_migrations.py)
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS acquisition_source TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_ad_id TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_ad_name TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_ad_headline TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_ad_body TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_adset_id TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_adset_name TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_campaign_id TEXT',
    'ALTER TABLE patients ADD COLUMN IF NOT EXISTS meta_campaign_name TEXT',
    'CREATE INDEX IF NOT EXISTS idx_patients_acquisition_source ON patients(acquisition_source)',
    'CREATE INDEX IF NOT EXISTS idx_patients_meta_ad_id ON patients(meta_ad_id)',
    'CREATE INDEX IF NOT EXISTS idx_patients_meta_campaign_id ON patients(meta_campaign_id)',
    # pg_trgm indexes (moved from baseline — require extension installed first)
    'CREATE INDEX IF NOT EXISTS idx_patients_first_name_trgm ON patients USING gin(first_name gin_trgm_ops)',
    'CREATE INDEX IF NOT EXISTS idx_patients_last_name_trgm ON patients USING gin(last_name gin_trgm_ops)',
    # pgvector indexes (optional — only if vector extension available)
    'ALTER TABLE faq_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)',
    'ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)',
    'CREATE INDEX IF NOT EXISTS idx_faq_embeddings_vector ON faq_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)',
    'CREATE INDEX IF NOT EXISTS idx_doc_embeddings_vector ON document_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)',
    # Professional blocks on tenant_holidays (migration 060 — safety net)
    'ALTER TABLE tenant_holidays ADD COLUMN IF NOT EXISTS professional_id INTEGER REFERENCES professionals(id) ON DELETE CASCADE',
    'ALTER TABLE tenant_holidays ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT \'global\'',
]
applied = 0
for p in patches:
    try:
        cur.execute(p)
        applied += 1
    except Exception as e:
        print(f'  Patch skip: {e}')
conn.close()
print(f'Schema patches: {applied}/{len(patches)} applied')
"

# Fix: secuencia de patient_memories desincronizada (post-restore) + embedding bytea->vector
echo "Aplicando fixes de schema (secuencia patient_memories + pgvector)..."
python << 'PYFIX' 2>&1 || echo "  Schema fixes skipped (non-critical)"
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

# 1) patient_memories: resetear la secuencia del id. Se desincroniza al restaurar un backup
#    (las filas entran con id explicito pero la secuencia no avanza) -> "duplicate key id".
try:
    cur.execute("SELECT pg_get_serial_sequence('patient_memories','id')")
    seq = cur.fetchone()[0]
    if seq:
        cur.execute("SELECT setval('" + seq + "', GREATEST((SELECT COALESCE(MAX(id),0) FROM patient_memories),1))")
        print("  patient_memories: secuencia del id reseteada a MAX(id)")
except Exception as e:
    print("  patient_memories seq skip:", e)

# 2) pgvector: si embedding quedo como bytea (formato viejo inservible, no casteable a
#    vector), recrearla como vector(1536). El app regenera los embeddings al arrancar.
#    Solo actua si es bytea (idempotente). DROP+ADD atomico (rollback si falla el ADD).
for tbl in ('faq_embeddings', 'document_embeddings'):
    try:
        cur.execute("SELECT udt_name FROM information_schema.columns WHERE table_name=%s AND column_name='embedding'", (tbl,))
        row = cur.fetchone()
        if row and row[0] == 'bytea':
            conn.autocommit = False
            try:
                cur.execute('ALTER TABLE ' + tbl + ' DROP COLUMN embedding')
                cur.execute('ALTER TABLE ' + tbl + ' ADD COLUMN embedding vector(1536)')
                conn.commit()
                print('  ' + tbl + ': columna embedding recreada como vector(1536)')
            except Exception as e2:
                conn.rollback()
                print('  ' + tbl + ' pgvector recreate failed (rolled back):', e2)
            finally:
                conn.autocommit = True
    except Exception as e:
        print('  ' + tbl + ' pgvector skip:', e)

conn.close()
PYFIX

# Auto-link: vincular pacientes existentes con conversaciones de chat huérfanas
echo "Vinculando pacientes con conversaciones de chat..."
python << 'PYEOF' 2>&1 || echo "  Auto-link skipped (non-critical)"
import os, re, psycopg2

def generate_phone_variants(phone):
    """Genera variantes de formato para matchear telefonos.
    +542996114843 (paciente) → tambien +5492996114843 (YCloud, con 9)
    +5492996114843 (YCloud) → tambien +542996114843 (sin 9)"""
    digits = re.sub(r"\D", "", phone)
    variants = {digits, "+" + digits, phone}
    if digits.startswith("549") and len(digits) > 3:
        variants.update(["54" + digits[3:], "+54" + digits[3:]])
    elif digits.startswith("54") and len(digits) > 3:
        variants.update(["549" + digits[2:], "+549" + digits[2:]])
    if digits.startswith("011") and len(digits) > 3:
        r = digits[3:]
        variants.update(["54911" + r, "+54911" + r, "11" + r, "+11" + r])
    elif digits.startswith("11") and len(digits) > 3:
        variants.update(["549" + digits, "+549" + digits])
    return list(variants)

dsn = os.environ.get("POSTGRES_DSN", "").replace("postgresql+asyncpg://", "postgresql://")
if dsn.startswith("postgres://"):
    dsn = dsn.replace("postgres://", "postgresql://", 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

linked = skipped = already = 0
cur.execute("SELECT id, phone_number FROM patients WHERE phone_number IS NOT NULL AND phone_number != %s ORDER BY id", ("",))
for pat_id, phone in cur.fetchall():
    variants = generate_phone_variants(phone)
    placeholders = ", ".join("%s" for _ in variants)
    cur.execute(f"""
        SELECT id, linked_patient_id FROM chat_conversations
        WHERE channel = 'whatsapp'
          AND external_user_id IN ({placeholders})
        ORDER BY updated_at DESC LIMIT 1
    """, variants)
    conv = cur.fetchone()
    if not conv:
        skipped += 1
        continue
    conv_id, linked_id = conv
    if linked_id == pat_id:
        already += 1
        continue
    if linked_id is not None:
        skipped += 1
        continue
    cur.execute("UPDATE chat_conversations SET linked_patient_id = %s, linked_at = NOW() WHERE id = %s", (pat_id, conv_id))
    linked += 1

conn.close()
print(f"  Pacientes linkeados: {linked} | Saltados: {skipped} | Ya linkeados: {already}")
PYEOF

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
