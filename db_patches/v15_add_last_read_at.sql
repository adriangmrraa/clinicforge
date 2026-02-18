-- v15_add_last_read_at.sql
-- Añadir columna last_read_at para persistir el estado de lectura de los chats
-- y evitar que las notificaciones reaparezcan tras refrescar la lista.

ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMP WITH TIME ZONE DEFAULT '1970-01-01 00:00:00+00';

COMMENT ON COLUMN chat_conversations.last_read_at IS 'Timestamp del último momento en que el representante abrió la conversación.';
