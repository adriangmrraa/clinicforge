import os
print("All env keys:", list(os.environ.keys()))
print("POSTGRES_DSN:", os.getenv("POSTGRES_DSN"))
