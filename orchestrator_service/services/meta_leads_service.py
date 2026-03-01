"""
Meta Leads Service for ClinicForge
Handles Meta Lead Forms processing, attribution, and management
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from db import db
from services.meta_ads_service import MetaAdsClient
from core.credentials import get_tenant_credential

logger = logging.getLogger(__name__)


class MetaLeadsService:
    """Service for managing Meta Lead Forms leads"""
    
    @staticmethod
    async def process_lead_form_webhook(
        payload: Dict[str, Any], 
        tenant_id: int
    ) -> Dict[str, Any]:
        """
        Process a Meta Lead Forms webhook payload.
        
        Args:
            payload: Webhook payload from Meta
            tenant_id: Tenant ID for multi-tenant isolation
            
        Returns:
            Dict with processing result
        """
        try:
            logger.info(f"📥 Processing Meta Lead Form webhook for tenant {tenant_id}")
            
            # Extract lead data from payload
            lead_data = await MetaLeadsService._extract_lead_data(payload, tenant_id)
            
            # Check for duplicate leads (same phone + campaign within 24h)
            duplicate = await MetaLeadsService._check_duplicate_lead(
                lead_data.get('phone_number'),
                lead_data.get('campaign_id'),
                tenant_id
            )
            
            if duplicate:
                logger.info(f"⚠️ Duplicate lead detected for phone {lead_data.get('phone_number')}")
                return {
                    "status": "duplicate",
                    "lead_id": duplicate,
                    "message": "Lead already exists"
                }
            
            # Enrich with Meta Ads data if available
            if lead_data.get('ad_id'):
                await MetaLeadsService._enrich_with_meta_data(lead_data, tenant_id)
            
            # Save lead to database
            lead_id = await MetaLeadsService._save_lead(lead_data, tenant_id)
            
            # Create initial status history entry
            await MetaLeadsService._create_status_history(
                lead_id, 
                tenant_id, 
                None, 
                'new',
                "Lead received from Meta Form"
            )
            
            logger.info(f"✅ Lead saved successfully: {lead_id}")
            
            return {
                "status": "success",
                "lead_id": str(lead_id),
                "message": "Lead processed successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing lead form webhook: {e}")
            raise
    
    @staticmethod
    async def _extract_lead_data(payload: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
        """Extract lead data from webhook payload"""
        
        lead_data = {
            "tenant_id": tenant_id,
            "webhook_payload": json.dumps(payload),
            "status": "new",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Standard Meta webhook format
        if "entry" in payload:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "leadgen":
                        value = change.get("value", {})
                        
                        # Extract attribution data
                        lead_data.update({
                            "form_id": value.get("form_id"),
                            "page_id": value.get("page_id"),
                            "leadgen_id": value.get("leadgen_id"),
                            "created_time": value.get("created_time"),
                        })
                        
                        # Extract ad data if available
                        if "ad_id" in value:
                            lead_data["ad_id"] = value["ad_id"]
                        if "adset_id" in value:
                            lead_data["adset_id"] = value["adset_id"]
                        if "campaign_id" in value:
                            lead_data["campaign_id"] = value["campaign_id"]
                        
                        # Extract form data
                        form_data = {}
                        for field in value.get("field_data", []):
                            field_name = field.get("name")
                            field_values = field.get("values", [])
                            
                            if field_name == "full_name" and field_values:
                                lead_data["full_name"] = field_values[0]
                            elif field_name == "email" and field_values:
                                lead_data["email"] = field_values[0]
                            elif field_name == "phone_number" and field_values:
                                lead_data["phone_number"] = field_values[0]
                            else:
                                # Store custom questions
                                if field_name not in form_data:
                                    form_data[field_name] = []
                                form_data[field_name].extend(field_values)
                        
                        lead_data["custom_questions"] = json.dumps(form_data)
        
        # Custom flattened payload format (n8n/LeadsBridge, Zapier, etc.)
        else:
            logger.info(f"📥 Processing custom payload with {len(payload)} fields")
            
            # INTELIGENCIA PARA DETECTAR FORMATOS ESPECÍFICOS
            
            # Formato 1: Campos separados claramente (lo ideal)
            field_mapping = {
                # Información del lead
                "name": "full_name",
                "full_name": "full_name",
                "nombre": "full_name",
                "email": "email",
                "phone": "phone_number",
                "phone_number": "phone_number",
                "telefono": "phone_number",
                "celular": "phone_number",
                
                # Atribución Meta Ads (IDs)
                "form_id": "form_id",
                "page_id": "page_id",
                "ad_id": "ad_id",
                "adset_id": "adset_id",
                "campaign_id": "campaign_id",
                
                # Atribución Meta Ads (NOMBRES - lo que NOS IMPORTA)
                "ad_name": "ad_name",
                "creative_name": "ad_name",  # Alias común
                "creative": "ad_name",  # Alias común
                "anuncio": "ad_name",  # Alias común
                
                "adset_name": "adset_name",
                "adgroup_name": "adset_name",  # Alias común
                "conjunto_anuncios": "adset_name",  # Alias común
                
                "campaign_name": "campaign_name",
                "campaña": "campaign_name",  # Alias común
                "campaign": "campaign_name",  # Alias común
                
                "page_name": "page_name",
                "página": "page_name",  # Alias común
                
                # Campos adicionales (para custom_questions)
                "job_title": "job_title",
                "position": "job_title",
                "cargo": "job_title",
                "profession": "job_title",
                "company": "company",
                "empresa": "company",
                "message": "message",
                "mensaje": "message",
                "comments": "message",
                "comentarios": "message",
                "instagram_username": "instagram_username",
                "usuario_instagram": "instagram_username",
            }
            
            # Primera pasada: mapear campos conocidos
            for key, value in payload.items():
                if key in field_mapping and value:
                    mapped_key = field_mapping[key]
                    lead_data[mapped_key] = value
            
            # SEGUNDA PASADA: INTELIGENCIA PARA CAMPOS NO MAPEADOS
            
            # Buscar nombres de campaña/anuncio en campos no mapeados
            campaign_keywords = ["campaña", "campaign", "nombre campaña", "campaign name"]
            ad_keywords = ["anuncio", "ad", "creative", "creativo", "ad name", "creative name"]
            adset_keywords = ["adset", "adgroup", "conjunto", "adset name", "adgroup name"]
            
            for key, value in payload.items():
                if not value:
                    continue
                    
                key_lower = key.lower()
                value_str = str(value)
                
                # Detectar si es un campo de campaña
                if any(kw in key_lower for kw in campaign_keywords):
                    if not lead_data.get("campaign_name"):
                        lead_data["campaign_name"] = value_str
                        logger.info(f"🔍 Detected campaign name from field '{key}': {value_str}")
                
                # Detectar si es un campo de anuncio/creativo (LO QUE MÁS NOS IMPORTA)
                elif any(kw in key_lower for kw in ad_keywords):
                    if not lead_data.get("ad_name"):
                        lead_data["ad_name"] = value_str
                        logger.info(f"🔍 Detected ad name from field '{key}': {value_str}")
                
                # Detectar si es un campo de conjunto de anuncios
                elif any(kw in key_lower for kw in adset_keywords):
                    if not lead_data.get("adset_name"):
                        lead_data["adset_name"] = value_str
                        logger.info(f"🔍 Detected adset name from field '{key}': {value_str}")
            
            # TERCERA PASADA: PROCESAMIENTO ESPECIAL PARA FORMATOS COMBINADOS
            
            # Si tenemos campaign_name pero no ad_name, buscar en otros campos
            if lead_data.get("campaign_name") and not lead_data.get("ad_name"):
                # Buscar en todos los campos restantes
                for key, value in payload.items():
                    if key not in field_mapping and value:
                        value_str = str(value)
                        # Si el valor contiene algo que no sea la campaña, podría ser el anuncio
                        if value_str != lead_data.get("campaign_name"):
                            # Podría ser un campo combinado "adset - ad"
                            if " - " in value_str:
                                parts = value_str.split(" - ", 1)
                                if len(parts) == 2:
                                    lead_data["adset_name"] = parts[0].strip()
                                    lead_data["ad_name"] = parts[1].strip()
                                    logger.info(f"🔍 Split combined field '{key}': adset='{parts[0]}', ad='{parts[1]}'")
                                    break
                            else:
                                # Asumir que es el nombre del anuncio
                                lead_data["ad_name"] = value_str
                                logger.info(f"🔍 Assumed ad name from field '{key}': {value_str}")
                                break
            
            # REGLA FINAL PARA CLINICFORGE: SIEMPRE TENER ad_name
            # Si no tenemos ad_name pero tenemos adset_name, usar adset_name como ad_name
            if not lead_data.get("ad_name") and lead_data.get("adset_name"):
                lead_data["ad_name"] = lead_data["adset_name"]
                logger.info(f"⚠️ Using adset_name as ad_name: {lead_data['adset_name']}")
            
            # Si no tenemos ad_name pero tenemos campaign_name, usar parte del campaign_name
            if not lead_data.get("ad_name") and lead_data.get("campaign_name"):
                # Extraer la parte más específica de la campaña
                campaign_parts = lead_data["campaign_name"].split()
                if len(campaign_parts) > 2:
                    lead_data["ad_name"] = " ".join(campaign_parts[-2:])  # Últimas 2 palabras
                    logger.info(f"⚠️ Extracted ad_name from campaign: {lead_data['ad_name']}")
                else:
                    lead_data["ad_name"] = lead_data["campaign_name"]
                    logger.info(f"⚠️ Using campaign_name as ad_name: {lead_data['campaign_name']}")
            
            # Store remaining fields as custom questions
            custom_fields = {}
            for key, value in payload.items():
                if key not in field_mapping and value and key not in ['id', 'timestamp', 'created_at']:
                    # No incluir campos que ya procesamos
                    if not any([
                        key.lower() in [kw for kw in campaign_keywords],
                        key.lower() in [kw for kw in ad_keywords],
                        key.lower() in [kw for kw in adset_keywords],
                        value == lead_data.get("campaign_name"),
                        value == lead_data.get("ad_name"),
                        value == lead_data.get("adset_name")
                    ]):
                        custom_fields[key] = value
            
            if custom_fields:
                lead_data["custom_questions"] = json.dumps(custom_fields)
                logger.info(f"📝 Stored {len(custom_fields)} custom fields")
        
        # Limpiar y normalizar los datos antes de guardar
        lead_data = await MetaLeadsService._clean_lead_data(lead_data)
        
        return lead_data
    
    @staticmethod
    async def _clean_lead_data(lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Limpia y normaliza los datos del lead"""
        
        # Limpiar teléfono (remover espacios, guiones, etc.)
        if lead_data.get("phone_number"):
            phone = lead_data["phone_number"]
            # Mantener solo números y signo +
            import re
            cleaned_phone = re.sub(r'[^\d+]', '', phone)
            lead_data["phone_number"] = cleaned_phone
        
        # Limpiar email (trim, lowercase)
        if lead_data.get("email"):
            lead_data["email"] = lead_data["email"].strip().lower()
        
        # Limpiar nombre completo (title case)
        if lead_data.get("full_name"):
            # Convertir a título pero preservar mayúsculas correctas
            name = lead_data["full_name"].strip()
            # Solo aplicar title() si no parece tener mayúsculas intencionales
            if not any(c.isupper() for c in name[1:] if c.isalpha()):
                lead_data["full_name"] = name.title()
            else:
                lead_data["full_name"] = name
        
        # Para ClinicForge: asegurar que tenemos ad_name (nuestro campo más importante)
        if not lead_data.get("ad_name"):
            # Intentar derivar de otros campos
            if lead_data.get("adset_name"):
                lead_data["ad_name"] = lead_data["adset_name"]
            elif lead_data.get("campaign_name"):
                # Extraer parte específica del nombre de campaña
                campaign = lead_data["campaign_name"]
                parts = campaign.split()
                if len(parts) > 3:
                    # Tomar las últimas 2-3 palabras como nombre de anuncio
                    lead_data["ad_name"] = " ".join(parts[-3:])
                else:
                    lead_data["ad_name"] = campaign
        
        # Si el ad_name es muy largo, truncarlo
        if lead_data.get("ad_name") and len(lead_data["ad_name"]) > 100:
            lead_data["ad_name"] = lead_data["ad_name"][:97] + "..."
        
        # Asegurar que campaign_name no sea demasiado largo
        if lead_data.get("campaign_name") and len(lead_data["campaign_name"]) > 150:
            lead_data["campaign_name"] = lead_data["campaign_name"][:147] + "..."
        
        return lead_data
    
    @staticmethod
    async def _check_duplicate_lead(
        phone_number: Optional[str], 
        campaign_id: Optional[str], 
        tenant_id: int
    ) -> Optional[str]:
        """Check if lead already exists (same phone + campaign within 24h)"""
        
        if not phone_number:
            return None
        
        query = """
            SELECT id FROM meta_form_leads 
            WHERE tenant_id = $1 
            AND phone_number = $2 
            AND created_at > NOW() - INTERVAL '24 hours'
        """
        
        params = [tenant_id, phone_number]
        
        if campaign_id:
            query += " AND campaign_id = $3"
            params.append(campaign_id)
        
        result = await db.pool.fetchrow(query, *params)
        return str(result["id"]) if result else None
    
    @staticmethod
    async def _enrich_with_meta_data(lead_data: Dict[str, Any], tenant_id: int):
        """
        Enrich lead data with Meta Ads information.
        
        IMPORTANTE: Meta webhook solo envía IDs, no nombres.
        Los nombres se deben obtener via Meta API si hay token disponible.
        
        Si no hay token, los leads se guardan con IDs pero sin nombres descriptivos.
        """
        
        # Primero verificar si ya tenemos nombres (de payload custom)
        already_has_names = any(
            lead_data.get(field) for field in 
            ['ad_name', 'adset_name', 'campaign_name', 'page_name']
        )
        
        if already_has_names:
            logger.info("Lead ya tiene nombres descriptivos del payload")
            return
        
        try:
            token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
            if not token:
                logger.warning("⚠️ No Meta token available for enrichment - Los leads se guardarán sin nombres")
                logger.warning("   Para obtener nombres descriptivos, configura un token de Meta en Configuración")
                return
            
            client = MetaAdsClient(access_token=token)
            
            # Obtener nombres en paralelo para mejor performance
            tasks = []
            
            # Get ad details (incluye creative name)
            if lead_data.get("ad_id") and not lead_data.get("ad_name"):
                tasks.append(_get_ad_details_with_fallback(client, lead_data))
            
            # Get campaign details
            if lead_data.get("campaign_id") and not lead_data.get("campaign_name"):
                tasks.append(_get_campaign_details_with_fallback(client, lead_data))
            
            # Get adset details
            if lead_data.get("adset_id") and not lead_data.get("adset_name"):
                tasks.append(_get_adset_details_with_fallback(client, lead_data))
            
            # Get page details
            if lead_data.get("page_id") and not lead_data.get("page_name"):
                tasks.append(_get_page_details_with_fallback(client, lead_data))
            
            if tasks:
                # Ejecutar todas las tareas en paralelo
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Procesar resultados
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Error en enriquecimiento: {result}")
            
            logger.info(f"✅ Lead enriquecido con Meta API: {lead_data.get('ad_name', 'Sin nombre')}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Could not enrich lead with Meta data: {e}")
            logger.info("Los leads se guardarán con IDs pero sin nombres descriptivos")

async def _get_ad_details_with_fallback(client, lead_data):
    """Obtiene detalles del ad con fallback"""
    try:
        ad_details = await client.get_ad_details(lead_data["ad_id"])
        if ad_details:
            lead_data["ad_name"] = ad_details.get("name", f"Ad {lead_data['ad_id'][:8]}")
            # Asegurar IDs si no estaban
            if not lead_data.get("adset_id") and ad_details.get("adset_id"):
                lead_data["adset_id"] = ad_details["adset_id"]
            if not lead_data.get("campaign_id") and ad_details.get("campaign_id"):
                lead_data["campaign_id"] = ad_details["campaign_id"]
    except Exception as e:
        lead_data["ad_name"] = f"Ad {lead_data['ad_id'][:8]}"
        logger.warning(f"Could not get ad details: {e}")

async def _get_campaign_details_with_fallback(client, lead_data):
    """Obtiene detalles de campaña con fallback"""
    try:
        campaign_details = await client.get_campaign_details(lead_data["campaign_id"])
        if campaign_details:
            lead_data["campaign_name"] = campaign_details.get("name", f"Campaign {lead_data['campaign_id'][:8]}")
    except Exception as e:
        lead_data["campaign_name"] = f"Campaign {lead_data['campaign_id'][:8]}"
        logger.warning(f"Could not get campaign details: {e}")

async def _get_adset_details_with_fallback(client, lead_data):
    """Obtiene detalles de adset con fallback"""
    try:
        adset_details = await client.get_adset_details(lead_data["adset_id"])
        if adset_details:
            lead_data["adset_name"] = adset_details.get("name", f"Adset {lead_data['adset_id'][:8]}")
    except Exception as e:
        lead_data["adset_name"] = f"Adset {lead_data['adset_id'][:8]}"
        logger.warning(f"Could not get adset details: {e}")

async def _get_page_details_with_fallback(client, lead_data):
    """Obtiene detalles de página con fallback"""
    try:
        page_details = await client.get_page_details(lead_data["page_id"])
        if page_details:
            lead_data["page_name"] = page_details.get("name", f"Page {lead_data['page_id'][:8]}")
    except Exception as e:
        lead_data["page_name"] = f"Page {lead_data['page_id'][:8]}"
        logger.warning(f"Could not get page details: {e}")
    
    @staticmethod
    async def _save_lead(lead_data: Dict[str, Any], tenant_id: int) -> str:
        """Save lead to database"""
        
        # Prepare data for insertion
        columns = []
        values = []
        placeholders = []
        
        for idx, (key, value) in enumerate(lead_data.items(), 1):
            if value is not None:
                columns.append(key)
                values.append(value)
                placeholders.append(f"${idx}")
        
        query = f"""
            INSERT INTO meta_form_leads ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            RETURNING id
        """
        
        result = await db.pool.fetchrow(query, *values)
        return str(result["id"])
    
    @staticmethod
    async def _create_status_history(
        lead_id: str, 
        tenant_id: int, 
        changed_by: Optional[str], 
        new_status: str,
        change_reason: str
    ):
        """Create status history entry"""
        
        query = """
            INSERT INTO lead_status_history 
            (lead_id, tenant_id, old_status, new_status, changed_by, change_reason)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        
        # Get current status
        current_status_query = """
            SELECT status FROM meta_form_leads WHERE id = $1
        """
        current_result = await db.pool.fetchrow(current_status_query, uuid.UUID(lead_id))
        old_status = current_result["status"] if current_result else None
        
        await db.pool.execute(
            query, 
            uuid.UUID(lead_id), 
            tenant_id, 
            old_status, 
            new_status, 
            changed_by, 
            change_reason
        )
    
    @staticmethod
    async def get_leads(
        tenant_id: int,
        status: Optional[str] = None,
        campaign_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get leads with filtering options"""
        
        query = """
            SELECT 
                mfl.*,
                u.email as assigned_email,
                u.full_name as assigned_name,
                p.full_name as patient_name
            FROM meta_form_leads mfl
            LEFT JOIN users u ON mfl.assigned_to = u.id
            LEFT JOIN patients p ON mfl.converted_to_patient_id = p.id
            WHERE mfl.tenant_id = $1
        """
        
        params = [tenant_id]
        param_count = 1
        
        # Apply filters
        if status:
            param_count += 1
            query += f" AND mfl.status = ${param_count}"
            params.append(status)
        
        if campaign_id:
            param_count += 1
            query += f" AND mfl.campaign_id = ${param_count}"
            params.append(campaign_id)
        
        if assigned_to:
            param_count += 1
            query += f" AND mfl.assigned_to = ${param_count}::uuid"
            params.append(assigned_to)
        
        if date_from:
            param_count += 1
            query += f" AND mfl.created_at >= ${param_count}::timestamp"
            params.append(date_from)
        
        if date_to:
            param_count += 1
            query += f" AND mfl.created_at <= ${param_count}::timestamp"
            params.append(date_to)
        
        # Add ordering and pagination
        query += f" ORDER BY mfl.created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, offset])
        
        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) as total FROM meta_form_leads 
            WHERE tenant_id = $1
        """
        count_params = [tenant_id]
        
        # Apply same filters to count query
        filter_parts = []
        if status:
            filter_parts.append("status = $2")
            count_params.append(status)
        if campaign_id:
            filter_parts.append("campaign_id = $3")
            count_params.append(campaign_id)
        if assigned_to:
            filter_parts.append("assigned_to = $4::uuid")
            count_params.append(assigned_to)
        if date_from:
            filter_parts.append("created_at >= $5::timestamp")
            count_params.append(date_from)
        if date_to:
            filter_parts.append("created_at <= $6::timestamp")
            count_params.append(date_to)
        
        if filter_parts:
            count_query += " AND " + " AND ".join(filter_parts)
        
        # Execute queries
        leads = await db.pool.fetch(query, *params)
        count_result = await db.pool.fetchrow(count_query, *count_params)
        
        # Format results
        formatted_leads = []
        for lead in leads:
            lead_dict = dict(lead)
            
            # Parse JSON fields
            for json_field in ['custom_questions', 'attribution_data', 'webhook_payload']:
                if lead_dict.get(json_field):
                    try:
                        lead_dict[json_field] = json.loads(lead_dict[json_field])
                    except:
                        pass
            
            formatted_leads.append(lead_dict)
        
        return {
            "leads": formatted_leads,
            "total": count_result["total"] if count_result else 0,
            "limit": limit,
            "offset": offset
        }
    
    @staticmethod
    async def get_lead_details(lead_id: str, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed lead information"""
        
        query = """
            SELECT 
                mfl.*,
                u.email as assigned_email,
                u.full_name as assigned_name,
                p.full_name as patient_name,
                p.id as patient_id
            FROM meta_form_leads mfl
            LEFT JOIN users u ON mfl.assigned_to = u.id
            LEFT JOIN patients p ON mfl.converted_to_patient_id = p.id
            WHERE mfl.id = $1 AND mfl.tenant_id = $2
        """
        
        result = await db.pool.fetchrow(query, uuid.UUID(lead_id), tenant_id)
        
        if not result:
            return None
        
        lead_dict = dict(result)
        
        # Parse JSON fields
        for json_field in ['custom_questions', 'attribution_data', 'webhook_payload']:
            if lead_dict.get(json_field):
                try:
                    lead_dict[json_field] = json.loads(lead_dict[json_field])
                except:
                    pass
        
        # Get status history
        history_query = """
            SELECT * FROM lead_status_history 
            WHERE lead_id = $1 
            ORDER BY created_at DESC
        """
        history = await db.pool.fetch(history_query, uuid.UUID(lead_id))
        lead_dict["status_history"] = [dict(h) for h in history]
        
        # Get notes
        notes_query = """
            SELECT ln.*, u.email as created_by_email, u.full_name as created_by_name
            FROM lead_notes ln
            LEFT JOIN users u ON ln.created_by = u.id
            WHERE ln.lead_id = $1 
            ORDER BY ln.created_at DESC
        """
        notes = await db.pool.fetch(notes_query, uuid.UUID(lead_id))
        lead_dict["notes"] = [dict(n) for n in notes]
        
        return lead_dict
    
    @staticmethod
    async def update_lead_status(
        lead_id: str, 
        tenant_id: int, 
        new_status: str, 
        changed_by: Optional[str] = None,
        change_reason: str = ""
    ) -> bool:
        """Update lead status and create history entry"""
        
        try:
            # Update lead status
            update_query = """
                UPDATE meta_form_leads 
                SET status = $1, updated_at = NOW()
                WHERE id = $2 AND tenant_id = $3
                RETURNING id
            """
            
            result = await db.pool.fetchrow(
                update_query, 
                new_status, 
                uuid.UUID(lead_id), 
                tenant_id
            )
            
            if not result:
                return False
            
            # Create status history entry
            await MetaLeadsService._create_status_history(
                lead_id, tenant_id, changed_by, new_status, change_reason
            )
            
            # If converting to patient, set converted_at
            if new_status == "converted":
                converted_query = """
                    UPDATE meta_form_leads 
                    SET converted_at = NOW()
                    WHERE id = $1 AND tenant_id = $2
                """
                await db.pool.execute(
                    converted_query, 
                    uuid.UUID(lead_id), 
                    tenant_id
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
            return False
    
    @staticmethod
    async def assign_lead(
        lead_id: str, 
        tenant_id: int, 
        assigned_to: str
    ) -> bool:
        """Assign lead to a user"""
        
        query = """
            UPDATE meta_form_leads 
            SET assigned_to = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
            RETURNING id
        """
        
        try:
            result = await db.pool.fetchrow(
                query, 
                uuid.UUID(assigned_to), 
                uuid.UUID(lead_id), 
                tenant_id
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Error assigning lead: {e}")
            return False
    
    @staticmethod
    async def add_note(
        lead_id: str, 
        tenant_id: int, 
        content: str, 
        created_by: str
    ) -> str:
        """Add note to lead"""
        
        query = """
            INSERT INTO lead_notes (lead_id, tenant_id, content, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        
        try:
            result = await db.pool.fetchrow(
                query,
                uuid.UUID(lead_id),
                tenant_id,
                content,
                uuid.UUID(created_by) if created_by else None
            )
            return str(result["id"]) if result else None
        except Exception as e:
            logger.error(f"Error adding lead note: {e}")
            raise
    
    @staticmethod
    async def convert_lead_to_patient(
        lead_id: str,
        tenant_id: int,
        patient_id: str,
        converted_by: Optional[str] = None
    ) -> bool:
        """Convert lead to patient and update attribution"""
        
        try:
            # Start transaction
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    # Update lead with patient ID and status
                    update_lead_query = """
                        UPDATE meta_form_leads 
                        SET converted_to_patient_id = $1, 
                            status = 'converted',
                            converted_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $2 AND tenant_id = $3
                        RETURNING ad_id, campaign_id, adset_id
                    """
                    
                    lead_result = await conn.fetchrow(
                        update_lead_query,
                        uuid.UUID(patient_id),
                        uuid.UUID(lead_id),
                        tenant_id
                    )
                    
                    if not lead_result:
                        return False
                    
                    # Update patient with attribution data from lead
                    if lead_result["ad_id"] or lead_result["campaign_id"]:
                        update_patient_query = """
                            UPDATE patients 
                            SET acquisition_source = 'META_ADS',
                                meta_ad_id = $1,
                                meta_campaign_id = $2,
                                meta_adset_id = $3,
                                updated_at = NOW()
                            WHERE id = $4 AND tenant_id = $5
                        """
                        
                        await conn.execute(
                            update_patient_query,
                            lead_result["ad_id"],
                            lead_result["campaign_id"],
                            lead_result["adset_id"],
                            uuid.UUID(patient_id),
                            tenant_id
                        )
                    
                    # Create status history entry
                    history_query = """
                        INSERT INTO lead_status_history 
                        (lead_id, tenant_id, old_status, new_status, changed_by, change_reason)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """
                    
                    await conn.execute(
                        history_query,
                        uuid.UUID(lead_id),
                        tenant_id,
                        'treatment_planned',  # Assuming previous status
                        'converted',
                        uuid.UUID(converted_by) if converted_by else None,
                        "Converted to patient in system"
                    )
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Error converting lead to patient: {e}")
            return False
    
    @staticmethod
    async def get_leads_summary(
        tenant_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get leads summary statistics"""
        
        # Base query for counts by status
        status_query = """
            SELECT 
                status,
                COUNT(*) as count
            FROM meta_form_leads 
            WHERE tenant_id = $1
        """
        
        params = [tenant_id]
        param_count = 1
        
        # Add date filters if provided
        if date_from:
            param_count += 1
            status_query += f" AND created_at >= ${param_count}::timestamp"
            params.append(date_from)
        
        if date_to:
            param_count += 1
            status_query += f" AND created_at <= ${param_count}::timestamp"
            params.append(date_to)
        
        status_query += " GROUP BY status ORDER BY count DESC"
        
        # Query for campaign breakdown
        campaign_query = """
            SELECT 
                campaign_id,
                campaign_name,
                COUNT(*) as total_leads,
                SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as converted_leads,
                SUM(CASE WHEN status = 'consultation_scheduled' THEN 1 ELSE 0 END) as scheduled_consultations
            FROM meta_form_leads 
            WHERE tenant_id = $1 AND campaign_id IS NOT NULL
        """
        
        campaign_params = [tenant_id]
        campaign_param_count = 1
        
        if date_from:
            campaign_param_count += 1
            campaign_query += f" AND created_at >= ${campaign_param_count}::timestamp"
            campaign_params.append(date_from)
        
        if date_to:
            campaign_param_count += 1
            campaign_query += f" AND created_at <= ${campaign_param_count}::timestamp"
            campaign_params.append(date_to)
        
        campaign_query += " GROUP BY campaign_id, campaign_name ORDER BY total_leads DESC LIMIT 10"
        
        # Query for daily trend
        trend_query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_leads,
                SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as converted_leads
            FROM meta_form_leads 
            WHERE tenant_id = $1
        """
        
        trend_params = [tenant_id]
        trend_param_count = 1
        
        if date_from:
            trend_param_count += 1
            trend_query += f" AND created_at >= ${trend_param_count}::timestamp"
            trend_params.append(date_from)
        
        if date_to:
            trend_param_count += 1
            trend_query += f" AND created_at <= ${trend_param_count}::timestamp"
            trend_params.append(date_to)
        
        trend_query += " GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30"
        
        try:
            # Execute all queries
            status_results = await db.pool.fetch(status_query, *params)
            campaign_results = await db.pool.fetch(campaign_query, *campaign_params)
            trend_results = await db.pool.fetch(trend_query, *trend_params)
            
            # Calculate totals
            total_leads = sum(row["count"] for row in status_results)
            converted_leads = sum(
                row["count"] for row in status_results 
                if row["status"] == "converted"
            )
            
            # Calculate conversion rate
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            
            # Format results
            summary = {
                "totals": {
                    "total_leads": total_leads,
                    "converted_leads": converted_leads,
                    "conversion_rate": round(conversion_rate, 2),
                    "active_leads": total_leads - converted_leads
                },
                "by_status": [
                    {"status": row["status"], "count": row["count"]}
                    for row in status_results
                ],
                "by_campaign": [
                    {
                        "campaign_id": row["campaign_id"],
                        "campaign_name": row["campaign_name"] or "Unknown",
                        "total_leads": row["total_leads"],
                        "converted_leads": row["converted_leads"],
                        "scheduled_consultations": row["scheduled_consultations"],
                        "conversion_rate": round(
                            (row["converted_leads"] / row["total_leads"] * 100) 
                            if row["total_leads"] > 0 else 0, 2
                        )
                    }
                    for row in campaign_results
                ],
                "daily_trend": [
                    {
                        "date": row["date"].isoformat() if row["date"] else None,
                        "total_leads": row["total_leads"],
                        "converted_leads": row["converted_leads"]
                    }
                    for row in trend_results
                ]
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting leads summary: {e}")
            raise
    ) -> str:
        """Add note to lead"""
        
        query = """
            INSERT INTO lead_notes (lead_id, tenant_id, content,