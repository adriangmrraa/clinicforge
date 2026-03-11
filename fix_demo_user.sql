UPDATE users SET password_hash = '$2b$12$FYNlyJHDxfog4LHmg1imkeZFLZvJGZmesaqyVPVhPQ3FLXf9s06/i', email = 'gamarraadrian200@gmail.com', status = 'active' WHERE email = 'germanreynoso94@gmail.com';
INSERT INTO users (email, password_hash, role, status)
SELECT 'gamarraadrian200@gmail.com', '$2b$12$FYNlyJHDxfog4LHmg1imkeZFLZvJGZmesaqyVPVhPQ3FLXf9s06/i', 'ceo', 'active'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'gamarraadrian200@gmail.com');
