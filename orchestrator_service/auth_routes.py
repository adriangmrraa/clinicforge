from fastapi import APIRouter, HTTPException, Depends, Request, status, Response
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import json
import logging
import asyncpg
from db import db
from auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Nexus Auth"])
logger = logging.getLogger("auth_routes")

# --- MODELS ---

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str = "professional"
    first_name: str
    last_name: Optional[str] = ""
    tenant_id: Optional[int] = None  # Obligatorio para professional/secretary
    specialty: Optional[str] = None
    phone_number: Optional[str] = None
    registration_id: Optional[str] = None  # Matrícula
    google_calendar_id: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

# --- ROUTES ---

def _default_working_hours():
    start = "09:00"
    end = "18:00"
    slot = {"start": start, "end": end}
    wh = {}
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        is_working_day = day != "sunday"
        wh[day] = {"enabled": is_working_day, "slots": [slot] if is_working_day else []}
    return wh


@router.get("/clinics")
async def list_clinics_public():
    """
    Lista de clínicas/sedes para el selector del formulario de registro.
    Público (sin autenticación). Solo id y nombre.
    """
    try:
        rows = await db.pool.fetch(
            "SELECT id, clinic_name FROM tenants ORDER BY id ASC"
        )
        return [{"id": r["id"], "clinic_name": r["clinic_name"]} for r in rows]
    except Exception as e:
        logger.warning(f"list_clinics_public failed: {e}")
        return []


@router.post("/register")
async def register(payload: UserRegister):
    """
    Registers a new user in 'pending' status.
    Para professional/secretary exige tenant_id (sede). Crea fila en professionals con is_active=FALSE.
    """
    existing = await db.fetchval("SELECT id FROM users WHERE email = $1", payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya se encuentra registrado.")

    if payload.role in ("professional", "secretary"):
        if payload.tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail="Debés elegir una sede/clínica para registrarte como profesional o secretaría.",
            )
        tenant_exists = await db.pool.fetchval("SELECT 1 FROM tenants WHERE id = $1", payload.tenant_id)
        if not tenant_exists:
            raise HTTPException(status_code=400, detail="La sede elegida no existe.")

    password_hash = auth_service.get_password_hash(payload.password)
    user_id = str(uuid.uuid4())
    first_name = (payload.first_name or "").strip() or "Usuario"
    last_name = (payload.last_name or "").strip() or " "

    try:
        await db.execute("""
            INSERT INTO users (id, email, password_hash, role, status, first_name, last_name)
            VALUES ($1, $2, $3, $4, 'pending', $5, $6)
        """, user_id, payload.email, password_hash, payload.role, first_name, last_name)

        if payload.role in ("professional", "secretary"):
            tenant_id = int(payload.tenant_id)
            uid = uuid.UUID(user_id)
            wh_json = json.dumps(_default_working_hours())
            phone_val = (payload.phone_number or "").strip() or None
            specialty_val = (payload.specialty or "").strip() or None
            reg_id = (payload.registration_id or "").strip() or None
            gcal_id = (payload.google_calendar_id or "").strip() or None
            try:
                await db.pool.execute("""
                    INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                    specialty, registration_id, is_active, working_hours, google_calendar_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, $10, NOW(), NOW())
                """, tenant_id, uid, first_name, last_name, payload.email, phone_val, specialty_val, reg_id, wh_json, gcal_id)
            except asyncpg.UndefinedColumnError as e:
                err_str = str(e).lower()
                if "google_calendar_id" in err_str:
                    await db.pool.execute("""
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, NOW(), NOW())
                    """, tenant_id, uid, first_name, last_name, payload.email, phone_val, specialty_val, reg_id, wh_json)
                elif "phone_number" in err_str:
                    await db.pool.execute("""
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8::jsonb, NOW(), NOW())
                    """, tenant_id, uid, first_name, last_name, payload.email, specialty_val, reg_id, wh_json)
                elif "updated_at" in err_str:
                    await db.pool.execute("""
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, NOW())
                    """, tenant_id, uid, first_name, last_name, payload.email, phone_val, specialty_val, reg_id, wh_json)
                elif "working_hours" in err_str:
                    try:
                        await db.pool.execute("""
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                            specialty, registration_id, is_active, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, NOW(), NOW())
                        """, tenant_id, uid, first_name, last_name, payload.email, phone_val, specialty_val, reg_id)
                    except asyncpg.UndefinedColumnError as e2:
                        if "phone_number" in str(e2).lower():
                            await db.pool.execute("""
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                                specialty, registration_id, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NOW(), NOW())
                            """, tenant_id, uid, first_name, last_name, payload.email, specialty_val, reg_id)
                        else:
                            raise
                elif "specialty" in err_str:
                    try:
                        await db.pool.execute("""
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                            registration_id, is_active, working_hours, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8::jsonb, NOW(), NOW())
                        """, tenant_id, uid, first_name, last_name, payload.email, phone_val, reg_id, wh_json)
                    except asyncpg.UndefinedColumnError as e2:
                        err2 = str(e2).lower()
                        if "phone_number" in err2:
                            await db.pool.execute("""
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                                registration_id, is_active, working_hours, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, FALSE, $7::jsonb, NOW(), NOW())
                            """, tenant_id, uid, first_name, last_name, payload.email, reg_id, wh_json)
                        elif "working_hours" in err2:
                            await db.pool.execute("""
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                                registration_id, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NOW(), NOW())
                            """, tenant_id, uid, first_name, last_name, payload.email, phone_val, reg_id)
                        else:
                            raise
                else:
                    raise

        activation_token = str(uuid.uuid4())
        auth_service.log_protocol_omega_activation(payload.email, activation_token)

        return {
            "status": "pending",
            "message": "Registro exitoso. Tu cuenta está pendiente de aprobación por el CEO.",
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail="Error interno durante el registro.")

@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, response: Response):
    """ Authenticates user and returns JWT. Checks for 'active' status. Sets HttpOnly cookie. """
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", payload.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    
    if not auth_service.verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    
    if user['status'] != 'active':
        raise HTTPException(
            status_code=403, 
            detail=f"Tu cuenta está en estado '{user['status']}'. Contactá al administrador."
        )

    # Regla de Oro: resolver tenant_id desde professionals por user_id (aislamiento total)
    tenant_id = await db.fetchval(
        "SELECT tenant_id FROM professionals WHERE user_id = $1",
        user['id']
    )
    if tenant_id is None:
        # CEO/secretary: no tienen fila en professionals, usar primera clínica
        tenant_id = await db.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1") or 1
    tenant_id = int(tenant_id)

    token_data = {
        "user_id": str(user['id']),
        "email": user['email'],
        "role": user['role'],
        "tenant_id": tenant_id,
    }
    token = auth_service.create_access_token(token_data)

    # Set HttpOnly Cookie (Nexus Security Protocol v7.6)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True, # Production-ready (HTTPS expected)
        samesite="lax",
        max_age=86400 * 7 # 7 days
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user['id']),
            "email": user['email'],
            "role": user['role'],
            "tenant_id": tenant_id,
        }
    }

@router.get("/me")
async def get_me(request: Request):
    """ Returns the current authenticated user data. Supports cookies. """
    token = None
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Fallback to Cookie (HttpOnly)
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    token_data = auth_service.decode_token(token)
    
    if not token_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    return token_data

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    google_calendar_id: Optional[str] = None

@router.get("/profile")
async def get_profile(request: Request):
    """ Returns the detailed clinical profile of the current professional/user. """
    user_data = await get_me(request)
    user_id = user_data.user_id
    
    # Base user data
    user = await db.fetchrow("SELECT id, email, role, first_name, last_name FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    profile = dict(user)
    
    # Professional specific data
    if user['role'] == 'professional':
        prof = await db.fetchrow("SELECT google_calendar_id, is_active FROM professionals WHERE user_id = $1", uuid.UUID(user_id))
        if prof:
            profile.update(dict(prof))
            
    return profile

@router.patch("/profile")
async def update_profile(payload: ProfileUpdate, request: Request):
    """ Updates the clinical profile of the current professional/user. """
    user_data = await get_me(request)
    user_id = user_data.user_id
    
    # Update users table
    update_users_fields = []
    params = []
    if payload.first_name is not None:
        update_users_fields.append(f"first_name = ${len(params)+1}")
        params.append(payload.first_name)
    if payload.last_name is not None:
        update_users_fields.append(f"last_name = ${len(params)+1}")
        params.append(payload.last_name)
        
    if update_users_fields:
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(update_users_fields)} WHERE id = ${len(params)}"
        await db.execute(query, *params)
        
    # Update professionals table if applicable
    if user_data.role == 'professional' and payload.google_calendar_id is not None:
        await db.execute("""
            UPDATE professionals 
            SET google_calendar_id = $1 
            WHERE user_id = $2
        """, payload.google_calendar_id, uuid.UUID(user_id))
        
    return {"message": "Perfil actualizado correctamente."}
