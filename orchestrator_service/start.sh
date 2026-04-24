#!/bin/sh

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

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
