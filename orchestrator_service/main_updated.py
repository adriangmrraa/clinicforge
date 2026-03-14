# ... (continuación del archivo anterior)

            # Continuar con procesamiento normal si no fue bloqueado
            # (El agente LangChain se ejecutará después con el prompt mejorado)
            
        except ImportError as e:
            logger.warning(f"Sistema mejorado no disponible: {e}, usando procesamiento normal")
        
        # 2. Obtener historial de mensajes
        chat_history = await db.get_chat_history(
            from_number=req.final_phone,
            tenant_id=tenant_id,
            limit=10
        )
        
        # 3. Construir contexto del paciente (v7.6)
        patient_context = ""
        if existing_patient:
            patient_context = await build_patient_context(existing_patient["id"], tenant_id)
        
        # 4. Construir contexto de anuncio (Spec 06)
        ad_context = ""
        if req.referral:
            ad_context = build_ad_context(req.referral)
        
        # 5. Detectar idioma
        response_language = detect_language(req.final_message)
        
        # 6. Construir prompt con sistema modular mejorado
        current_time_str = get_now_arg().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = build_system_prompt(
            clinic_name=CLINIC_NAME,
            current_time=current_time_str,
            response_language=response_language,
            hours_start=CLINIC_HOURS_START,
            hours_end=CLINIC_HOURS_END,
            ad_context=ad_context,
            patient_context=patient_context,
        )
        
        # 7. Preparar input para el agente
        agent_input = {
            "input": req.final_message,
            "system_prompt": system_prompt,
            "chat_history": chat_history,
            "patient_id": existing_patient["id"] if existing_patient else req.final_phone,
            "tenant_id": tenant_id,
        }
        
        # 8. Ejecutar agente con sistema mejorado
        try:
            executor = await get_agent_executable_for_tenant(tenant_id, existing_patient["id"] if existing_patient else req.final_phone)
            result = await executor.ainvoke(agent_input)
            output = result.get("output", "")
            
            # Trackear conversación exitosa
            if "enhanced_system" in locals():
                message_count = len(chat_history) + 2  # +2 por mensaje actual y respuesta
                await enhanced_system.track_successful_conversation(
                    existing_patient["id"] if existing_patient else req.final_phone,
                    tenant_id,
                    message_count
                )
            
        except Exception as agent_err:
            logger.error(f"❌ Agent error: {agent_err}", exc_info=True)
            output = "Lo siento, estoy teniendo dificultades técnicas. Por favor, intentá nuevamente en unos minutos."
        
        # 9. Guardar respuesta del asistente
        await db.append_chat_message(
            from_number=req.final_phone,
            role='assistant',
            content=output,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )
        
        # 10. Notificar al frontend
        await sio.emit('NEW_MESSAGE', to_json_safe({
            'phone_number': req.final_phone,
            'tenant_id': tenant_id,
            'message': output,
            'role': 'assistant'
        }))
        
        # 11. Retornar respuesta
        return {
            "output": output,
            "correlation_id": correlation_id,
            "status": "success",
            "send": True,
            "text": output,
        }
        
    except Exception as e:
        logger.error(f"❌ Error general en /chat: {e}", exc_info=True)
        return {
            "output": "Lo siento, ocurrió un error inesperado. Por favor, intentá nuevamente.",
            "correlation_id": correlation_id,
            "status": "error",
            "send": True,
            "text": "Lo siento, ocurrió un error inesperado. Por favor, intentá nuevamente.",
        }


# --- FUNCIONES AUXILIARES ---

def to_json_safe(obj):
    """Convierte objetos a JSON-safe (UUID, datetime, etc.)"""
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_json_safe(v) for v in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, timedelta):
        return str(obj)
    else:
        return obj


async def build_patient_context(patient_id: int, tenant_id: int) -> str:
    """Construye contexto del paciente (v7.6)"""
    try:
        patient = await db.pool.fetchrow(
            "SELECT first_name, last_name, dni FROM patients WHERE id = $1 AND tenant_id = $2",
            patient_id, tenant_id
        )
        if not patient:
            return ""
        
        # Obtener turnos próximos
        appointments = await db.pool.fetch(
            """
            SELECT a.date_time, t.name as treatment_name, p.full_name as professional_name
            FROM appointments a
            LEFT JOIN treatments t ON a.treatment_id = t.id
            LEFT JOIN professionals p ON a.professional_id = p.id
            WHERE a.patient_id = $1 AND a.tenant_id = $2 AND a.date_time >= NOW()
            ORDER BY a.date_time ASC
            LIMIT 3
            """,
            patient_id, tenant_id
        )
        
        context_parts = []
        
        # Datos básicos
        if patient['first_name']:
            context_parts.append(f"Nombre: {patient['first_name']} {patient['last_name'] or ''}")
        if patient['dni']:
            context_parts.append(f"DNI: {patient['dni']}")
        
        # Turnos próximos
        if appointments:
            appt_text = "Turnos próximos:\n"
            for appt in appointments:
                date_str = appt['date_time'].strftime("%d/%m/%Y %H:%M")
                treatment = appt['treatment_name'] or "Consulta"
                professional = appt['professional_name'] or "Dra. María Laura Delgado"
                appt_text += f"- {date_str}: {treatment} con {professional}\n"
            context_parts.append(appt_text.strip())
        
        return "\n".join(context_parts) if context_parts else ""
        
    except Exception as e:
        logger.error(f"Error construyendo contexto del paciente: {e}")
        return ""


def build_ad_context(referral: Dict[str, Any]) -> str:
    """Construye contexto de anuncio (Spec 06)"""
    if not referral:
        return ""
    
    parts = []
    
    source_type = referral.get("source_type", "META_ADS")
    if source_type == "META_ADS":
        parts.append("Este paciente llegó desde un anuncio de Meta Ads.")
        
        headline = referral.get("headline")
        if headline:
            parts.append(f"Título del anuncio: \"{headline}\"")
        
        body = referral.get("body")
        if body:
            parts.append(f"Texto del anuncio: \"{body}\"")
        
        ad_id = referral.get("ad_id")
        if ad_id:
            parts.append(f"ID del anuncio: {ad_id}")
    
    elif source_type == "GOOGLE_ADS":
        parts.append("Este paciente llegó desde Google Ads.")
    
    elif source_type == "ORGANIC":
        parts.append("Este paciente llegó de forma orgánica (búsqueda, recomendación, etc.).")
    
    return "\n".join(parts)


def detect_language(text: str) -> str:
    """Detecta idioma del mensaje"""
    if not text:
        return "es"
    
    # Detección simple basada en palabras clave
    text_lower = text.lower()
    
    english_words = ["hello", "hi", "appointment", "doctor", "pain", "tooth"]
    french_words = ["bonjour", "salut", "rendez-vous", "docteur", "dent", "mal"]
    
    english_count = sum(1 for word in english_words if word in text_lower)
    french_count = sum(1 for word in french_words if word in text_lower)
    
    if english_count > 2:
        return "en"
    elif french_count > 2:
        return "fr"
    else:
        return "es"


# --- ENDPOINTS DE HEALTH ---

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint con información del sistema."""
    return {
        "service": "ClinicForge Orchestrator",
        "version": "2.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": {
            "enhanced_agent": True,
            "multi_tenant": True,
            "whatsapp_integration": True,
            "calendar_sync": True,
            "meta_ads_attribution": True,
            "ai_guardrails": True,
            "modular_prompts": True,
            "predictive_validation": True,
            "context_memory": True,
            "intelligent_fallback": True,
            "ab_testing": True,
            "metrics_dashboard": True
        }
    }


# --- MAIN ---
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Iniciando servidor en {host}:{port}")
    uvicorn.run(
        "main_updated:app",
        host=host,
        port=port,
        reload=os.getenv("ENV") == "development",
        log_level="info"
    )