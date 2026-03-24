"""
Config Manager - Gestión de configuración del sistema desde el dashboard
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestor de configuración del sistema"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.logger = logging.getLogger(__name__)
        self._table_ready = False

    async def ensure_table(self):
        """Crea la tabla de configuración si no existe y carga defaults"""
        if self._table_ready or not self.db_pool:
            return
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS system_config (
            id SERIAL PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            value TEXT NOT NULL,
            data_type VARCHAR(50) NOT NULL,
            description TEXT,
            category VARCHAR(100) NOT NULL,
            tenant_id INTEGER DEFAULT 1,
            updated_by VARCHAR(100),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(key);
        CREATE INDEX IF NOT EXISTS idx_system_config_category ON system_config(category);
        CREATE INDEX IF NOT EXISTS idx_system_config_tenant ON system_config(tenant_id);
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(create_table_sql)
            self._table_ready = True
            self.logger.info("✅ Tabla de system_config verificada/creada")
            await self._initialize_default_config()
        except Exception as e:
            self.logger.error(f"❌ Error creando tabla system_config: {e}")

    async def _initialize_default_config(self):
        """Inicializa configuración por defecto"""
        default_config = [
            {"key": "OPENAI_MODEL", "value": "gpt-4o-mini", "data_type": "string", "description": "Modelo OpenAI para chats con pacientes (agente principal)", "category": "ai"},
            {"key": "MODEL_INSIGHTS", "value": "gpt-4o-mini", "data_type": "string", "description": "Modelo OpenAI para análisis de conversaciones (insights)", "category": "ai"},
            {"key": "OPENAI_TEMPERATURE", "value": "0.7", "data_type": "float", "description": "Temperatura para generación (0-2)", "category": "ai"},
            {"key": "MAX_TOKENS_PER_RESPONSE", "value": "1000", "data_type": "integer", "description": "Máximo de tokens por respuesta", "category": "ai"},
            {"key": "ENABLE_TOKEN_TRACKING", "value": "true", "data_type": "boolean", "description": "Habilitar tracking de tokens", "category": "monitoring"},
            {"key": "DAILY_TOKEN_LIMIT", "value": "100000", "data_type": "integer", "description": "Límite diario de tokens (0 = ilimitado)", "category": "limits"},
            {"key": "ENABLE_ADVANCED_FEATURES", "value": "false", "data_type": "boolean", "description": "Habilitar features avanzadas del sistema mejorado", "category": "features"},
            {"key": "RESPONSE_LANGUAGE", "value": "es", "data_type": "string", "description": "Idioma por defecto para respuestas", "category": "localization"},
            {"key": "CLINIC_NAME", "value": "Dra. María Laura Delgado", "data_type": "string", "description": "Nombre de la clínica", "category": "clinic"},
            {"key": "CLINIC_LOCATION", "value": "Calle Córdoba 431, Neuquén Capital", "data_type": "string", "description": "Dirección de la clínica", "category": "clinic"},
            {"key": "BUSINESS_HOURS_START", "value": "08:00", "data_type": "string", "description": "Hora de apertura", "category": "clinic"},
            {"key": "BUSINESS_HOURS_END", "value": "19:00", "data_type": "string", "description": "Hora de cierre", "category": "clinic"},
        ]
        try:
            await self._insert_default_config(default_config)
            self.logger.info("✅ Configuración por defecto inicializada")
        except Exception as e:
            self.logger.error(f"❌ Error inicializando configuración: {e}")
    
    async def _insert_default_config(self, configs):
        """Inserta configuración por defecto"""
        async with self.db_pool.acquire() as conn:
            for config in configs:
                # Verificar si ya existe
                existing = await conn.fetchrow(
                    "SELECT id FROM system_config WHERE key = $1",
                    config["key"]
                )
                
                if not existing:
                    await conn.execute("""
                        INSERT INTO system_config 
                        (key, value, data_type, description, category, tenant_id)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    config["key"],
                    config["value"],
                    config["data_type"],
                    config["description"],
                    config["category"],
                    1  # tenant_id por defecto
                    )
    
    async def get_config(self, key: str, tenant_id: int = 1) -> Optional[Any]:
        """Obtiene valor de configuración"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value, data_type FROM system_config WHERE key = $1 AND tenant_id = $2",
                    key, tenant_id
                )
                
                if not row:
                    # Fallback a variable de entorno
                    env_value = os.getenv(key)
                    if env_value:
                        return env_value
                    return None
                
                value = row["value"]
                data_type = row["data_type"]
                
                # Convertir al tipo de dato correcto
                if data_type == "integer":
                    return int(value)
                elif data_type == "float":
                    return float(value)
                elif data_type == "boolean":
                    return value.lower() in ("true", "1", "yes", "on")
                elif data_type == "json":
                    return json.loads(value)
                else:
                    return value
                    
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo configuración {key}: {e}")
            return None
    
    async def set_config(self, key: str, value: Any, data_type: str = None, 
                        description: str = None, category: str = "general",
                        tenant_id: int = 1, updated_by: str = "dashboard") -> bool:
        """Establece valor de configuración"""
        try:
            # Determinar tipo de dato si no se especifica
            if data_type is None:
                if isinstance(value, bool):
                    data_type = "boolean"
                    str_value = "true" if value else "false"
                elif isinstance(value, int):
                    data_type = "integer"
                    str_value = str(value)
                elif isinstance(value, float):
                    data_type = "float"
                    str_value = str(value)
                elif isinstance(value, (dict, list)):
                    data_type = "json"
                    str_value = json.dumps(value, ensure_ascii=False)
                else:
                    data_type = "string"
                    str_value = str(value)
            else:
                str_value = str(value)
            
            async with self.db_pool.acquire() as conn:
                # Verificar si existe
                existing = await conn.fetchrow(
                    "SELECT id FROM system_config WHERE key = $1 AND tenant_id = $2",
                    key, tenant_id
                )
                
                if existing:
                    # Actualizar
                    await conn.execute("""
                        UPDATE system_config 
                        SET value = $1, data_type = $2, updated_by = $3, 
                            updated_at = NOW(), description = COALESCE($4, description)
                        WHERE key = $5 AND tenant_id = $6
                    """,
                    str_value, data_type, updated_by, description, key, tenant_id
                    )
                else:
                    # Insertar nuevo
                    await conn.execute("""
                        INSERT INTO system_config 
                        (key, value, data_type, description, category, tenant_id, updated_by)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    key, str_value, data_type, description, category, tenant_id, updated_by
                    )
                
                self.logger.info(f"✅ Configuración actualizada: {key} = {str_value}")
                
                # Actualizar variable de entorno en tiempo de ejecución
                os.environ[key] = str_value
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error estableciendo configuración {key}: {e}")
            return False
    
    async def get_all_config(self, tenant_id: int = 1, category: str = None) -> Dict[str, Any]:
        """Obtiene toda la configuración"""
        try:
            async with self.db_pool.acquire() as conn:
                query = "SELECT key, value, data_type, description, category FROM system_config WHERE tenant_id = $1"
                params = [tenant_id]
                
                if category:
                    query += " AND category = $2"
                    params.append(category)
                
                query += " ORDER BY category, key"
                
                rows = await conn.fetch(query, *params)
                
                config_dict = {}
                for row in rows:
                    key = row["key"]
                    value = row["value"]
                    data_type = row["data_type"]
                    
                    # Convertir al tipo de dato correcto
                    if data_type == "integer":
                        config_dict[key] = int(value)
                    elif data_type == "float":
                        config_dict[key] = float(value)
                    elif data_type == "boolean":
                        config_dict[key] = value.lower() in ("true", "1", "yes", "on")
                    elif data_type == "json":
                        try:
                            config_dict[key] = json.loads(value)
                        except:
                            config_dict[key] = value
                    else:
                        config_dict[key] = value
                
                return config_dict
                
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo toda la configuración: {e}")
            return {}
    
    async def get_config_by_category(self, tenant_id: int = 1) -> Dict[str, Dict[str, Any]]:
        """Obtiene configuración agrupada por categoría"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT key, value, data_type, description, category 
                    FROM system_config 
                    WHERE tenant_id = $1 
                    ORDER BY category, key
                """, tenant_id)
                
                config_by_category = {}
                for row in rows:
                    category = row["category"]
                    if category not in config_by_category:
                        config_by_category[category] = {}
                    
                    key = row["key"]
                    value = row["value"]
                    data_type = row["data_type"]
                    
                    # Convertir al tipo de dato correcto
                    if data_type == "integer":
                        config_by_category[category][key] = int(value)
                    elif data_type == "float":
                        config_by_category[category][key] = float(value)
                    elif data_type == "boolean":
                        config_by_category[category][key] = value.lower() in ("true", "1", "yes", "on")
                    elif data_type == "json":
                        try:
                            config_by_category[category][key] = json.loads(value)
                        except:
                            config_by_category[category][key] = value
                    else:
                        config_by_category[category][key] = value
                
                return config_by_category
                
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo configuración por categoría: {e}")
            return {}
    
    async def export_config(self, tenant_id: int = 1) -> str:
        """Exporta configuración como YAML"""
        config = await self.get_all_config(tenant_id)
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)
    
    async def import_config(self, yaml_content: str, tenant_id: int = 1, 
                          updated_by: str = "dashboard") -> Dict[str, bool]:
        """Importa configuración desde YAML"""
        results = {}
        try:
            config_dict = yaml.safe_load(yaml_content)
            
            for key, value in config_dict.items():
                success = await self.set_config(
                    key=key,
                    value=value,
                    tenant_id=tenant_id,
                    updated_by=updated_by
                )
                results[key] = success
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error importando configuración: {e}")
            return {"error": str(e)}

# Instancia global del config manager
config_manager = None

def init_config_manager(db_pool):
    """Inicializa el config manager global"""
    global config_manager
    config_manager = ConfigManager(db_pool)
    return config_manager