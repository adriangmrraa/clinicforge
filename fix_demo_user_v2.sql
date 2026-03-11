DELETE FROM users WHERE email = 'gamarraadrian200@gmail.com';
INSERT INTO users (id, email, password_hash, role, status) 
VALUES (gen_random_uuid(), 'gamarraadrian200@gmail.com', '$2b$12$FYNlyJHDxfog4LHmg1imkeZFLZvJGZmesaqyVPVhPQ3FLXf9s06/i', 'ceo', 'active');
