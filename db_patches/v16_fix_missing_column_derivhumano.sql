DO $$ 
BEGIN 
    -- 1. Agregar last_derivhumano_at a chat_conversations si no existe
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_conversations' AND column_name='last_derivhumano_at') THEN
        ALTER TABLE chat_conversations ADD COLUMN last_derivhumano_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Added last_derivhumano_at to chat_conversations';
    END IF;

    -- 2. Asegurar índices para query performance
    CREATE INDEX IF NOT EXISTS idx_chat_conv_last_derivhumano ON chat_conversations(last_derivhumano_at);
END $$;
