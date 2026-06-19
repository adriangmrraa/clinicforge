BEGIN;

-- 1. Limpieza en cascada explícita de leads y sus notas/historiales
DELETE FROM lead_notes WHERE lead_id IN (SELECT id FROM meta_form_leads WHERE phone_number LIKE '%3704868421');
DELETE FROM lead_status_history WHERE lead_id IN (SELECT id FROM meta_form_leads WHERE phone_number LIKE '%3704868421');
DELETE FROM meta_form_leads WHERE phone_number LIKE '%3704868421';

-- 2. Borrado de mensajes de chat
DELETE FROM chat_messages WHERE conversation_id IN (SELECT id FROM chat_conversations WHERE external_user_id LIKE '%3704868421')
   OR from_number LIKE '%3704868421';

-- 3. Borrado de whatsapp_messages
DELETE FROM whatsapp_messages WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421')
   OR from_number LIKE '%3704868421' 
   OR to_number LIKE '%3704868421';

-- 4. Borrado de mensajes crudos entrantes
DELETE FROM inbound_messages WHERE from_number LIKE '%3704868421';

-- 5. Borrado de snapshots y logs de agentes (multi-agent)
DELETE FROM patient_context_snapshots WHERE phone_number LIKE '%3704868421';
DELETE FROM agent_turn_log WHERE phone_number LIKE '%3704868421';

-- 6. Borrado de ejecuciones y logs de automatización
DELETE FROM automation_executions WHERE phone_number LIKE '%3704868421';
DELETE FROM automation_logs WHERE phone_number LIKE '%3704868421';

-- 7. Desvinculación de transacciones contables (se setean a NULL para no romper la caja histórica)
UPDATE accounting_transactions SET patient_id = NULL WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 8. Borrado de planes de tratamiento
DELETE FROM treatment_plan_items WHERE plan_id IN (SELECT id FROM treatment_plans WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421'));
DELETE FROM treatment_plan_payments WHERE plan_id IN (SELECT id FROM treatment_plans WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421'));
DELETE FROM treatment_plan_installments WHERE plan_id IN (SELECT id FROM treatment_plans WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421'));
DELETE FROM treatment_plans WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 9. Borrado de historial clínico y resúmenes
DELETE FROM clinical_record_summaries WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');
DELETE FROM clinical_records WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 10. Borrado de documentos/adjuntos cargados
DELETE FROM patient_documents WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 11. Borrado de fichas digitales del paciente
DELETE FROM patient_digital_records WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 12. Borrado de turnos (appointments)
DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%3704868421');

-- 13. Borrado de memorias persistentes (nova_memories)
DELETE FROM nova_memories WHERE topic_key LIKE '%3704868421%';

-- 14. Borrado de conversaciones de chat
DELETE FROM chat_conversations WHERE external_user_id LIKE '%3704868421';

-- 15. Borrado de menores vinculados (guardian_phone)
DELETE FROM patients WHERE guardian_phone LIKE '%3704868421';

-- 16. Finalmente, borrado del paciente principal
DELETE FROM patients WHERE phone_number LIKE '%3704868421';

COMMIT;
