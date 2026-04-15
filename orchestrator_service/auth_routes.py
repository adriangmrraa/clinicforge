from fastapi import APIRouter, HTTPException, Depends, Request, status, Response
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import uuid
import json
import logging
import asyncio
import asyncpg
from db import db
from auth_service import auth_service
from email_service import email_service

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Nexus Auth"])
logger = logging.getLogger("auth_routes")

# --- MODELS ---


class ClinicPublicResponse(BaseModel):
    id: int
    clinic_name: str


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
    for day in [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]:
        is_working_day = day != "sunday"
        wh[day] = {"enabled": is_working_day, "slots": [slot] if is_working_day else []}
    return wh


@router.get("/clinics", response_model=List[ClinicPublicResponse])
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
@limiter.limit("3/minute")
async def register(request: Request, payload: UserRegister):
    """
    Registers a new user in 'pending' status.
    Para professional/secretary exige tenant_id (sede). Crea fila en professionals con is_active=FALSE.
    """
    existing = await db.fetchval("SELECT id FROM users WHERE email = $1", payload.email)
    if existing:
        raise HTTPException(
            status_code=400, detail="El correo ya se encuentra registrado."
        )

    if payload.role in ("professional", "secretary"):
        if payload.tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail="Debés elegir una sede/clínica para registrarte como profesional o secretaría.",
            )
        tenant_exists = await db.pool.fetchval(
            "SELECT 1 FROM tenants WHERE id = $1", payload.tenant_id
        )
        if not tenant_exists:
            raise HTTPException(status_code=400, detail="La sede elegida no existe.")

    password_hash = auth_service.get_password_hash(payload.password)
    user_id = str(uuid.uuid4())
    first_name = (payload.first_name or "").strip() or "Usuario"
    last_name = (payload.last_name or "").strip() or " "

    try:
        await db.execute(
            """
            INSERT INTO users (id, email, password_hash, role, status, first_name, last_name)
            VALUES ($1, $2, $3, $4, 'pending', $5, $6)
        """,
            user_id,
            payload.email,
            password_hash,
            payload.role,
            first_name,
            last_name,
        )

        if payload.role in ("professional", "secretary"):
            tenant_id = int(payload.tenant_id)
            uid = uuid.UUID(user_id)
            wh_json = json.dumps(_default_working_hours())
            phone_val = (payload.phone_number or "").strip() or None
            specialty_val = (payload.specialty or "").strip() or None
            reg_id = (payload.registration_id or "").strip() or None
            gcal_id = (payload.google_calendar_id or "").strip() or None
            try:
                await db.pool.execute(
                    """
                    INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                    specialty, registration_id, is_active, working_hours, google_calendar_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, $10, NOW(), NOW())
                """,
                    tenant_id,
                    uid,
                    first_name,
                    last_name,
                    payload.email,
                    phone_val,
                    specialty_val,
                    reg_id,
                    wh_json,
                    gcal_id,
                )
            except asyncpg.UndefinedColumnError as e:
                err_str = str(e).lower()
                if "google_calendar_id" in err_str:
                    await db.pool.execute(
                        """
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, NOW(), NOW())
                    """,
                        tenant_id,
                        uid,
                        first_name,
                        last_name,
                        payload.email,
                        phone_val,
                        specialty_val,
                        reg_id,
                        wh_json,
                    )
                elif "phone_number" in err_str:
                    await db.pool.execute(
                        """
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                        specialty, registration_id, is_active, working_hours, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8::jsonb, NOW(), NOW())
                    """,
                        tenant_id,
                        uid,
                        first_name,
                        last_name,
                        payload.email,
                        specialty_val,
                        reg_id,
                        wh_json,
                    )
                elif "updated_at" in err_str:
                    await db.pool.execute(
                        """
                        INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                        specialty, registration_id, is_active, working_hours, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, $9::jsonb, NOW())
                    """,
                        tenant_id,
                        uid,
                        first_name,
                        last_name,
                        payload.email,
                        phone_val,
                        specialty_val,
                        reg_id,
                        wh_json,
                    )
                elif "working_hours" in err_str:
                    try:
                        await db.pool.execute(
                            """
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                            specialty, registration_id, is_active, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, FALSE, NOW(), NOW())
                        """,
                            tenant_id,
                            uid,
                            first_name,
                            last_name,
                            payload.email,
                            phone_val,
                            specialty_val,
                            reg_id,
                        )
                    except asyncpg.UndefinedColumnError as e2:
                        if "phone_number" in str(e2).lower():
                            await db.pool.execute(
                                """
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                                specialty, registration_id, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NOW(), NOW())
                            """,
                                tenant_id,
                                uid,
                                first_name,
                                last_name,
                                payload.email,
                                specialty_val,
                                reg_id,
                            )
                        else:
                            raise
                elif "specialty" in err_str:
                    try:
                        await db.pool.execute(
                            """
                            INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                            registration_id, is_active, working_hours, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8::jsonb, NOW(), NOW())
                        """,
                            tenant_id,
                            uid,
                            first_name,
                            last_name,
                            payload.email,
                            phone_val,
                            reg_id,
                            wh_json,
                        )
                    except asyncpg.UndefinedColumnError as e2:
                        err2 = str(e2).lower()
                        if "phone_number" in err2:
                            await db.pool.execute(
                                """
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email,
                                registration_id, is_active, working_hours, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, FALSE, $7::jsonb, NOW(), NOW())
                            """,
                                tenant_id,
                                uid,
                                first_name,
                                last_name,
                                payload.email,
                                reg_id,
                                wh_json,
                            )
                        elif "working_hours" in err2:
                            await db.pool.execute(
                                """
                                INSERT INTO professionals (tenant_id, user_id, first_name, last_name, email, phone_number,
                                registration_id, is_active, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NOW(), NOW())
                            """,
                                tenant_id,
                                uid,
                                first_name,
                                last_name,
                                payload.email,
                                phone_val,
                                reg_id,
                            )
                        else:
                            raise
                else:
                    raise

        activation_token = str(uuid.uuid4())
        auth_service.log_protocol_omega_activation(payload.email, activation_token)

        # Send welcome email (non-blocking)
        try:
            _tenant_id = int(payload.tenant_id) if payload.tenant_id else None
            if _tenant_id:
                tenant_row = await db.pool.fetchrow(
                    "SELECT name, logo_url FROM tenants WHERE id = $1", _tenant_id
                )
            else:
                tenant_row = None
            _clinic = tenant_row["name"] if tenant_row else "Clínica"
            _logo = tenant_row.get("logo_url", "") if tenant_row else ""
            _platform = os.getenv("FRONTEND_URL", "").split(",")[0].strip()
            _user_email = payload.email
            _user_name = f"{first_name} {last_name}".strip()
            if _user_email and not _user_email.endswith("@dentalogic.local"):
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: email_service.send_welcome_email(
                        to_email=_user_email,
                        user_name=_user_name,
                        role=payload.role,
                        clinic_name=_clinic,
                        platform_url=_platform,
                        logo_url=_logo,
                        is_pending=True,
                    ),
                )
                logger.info(f"Welcome email scheduled for {_user_email}")
        except Exception as e:
            logger.warning(f"Welcome email failed: {e}")

        return {
            "status": "pending",
            "message": "Registro exitoso. Tu cuenta está pendiente de aprobación por el CEO.",
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=500, detail="Error interno durante el registro."
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: UserLogin, response: Response):
    """Authenticates user and returns JWT. Checks for 'active' status. Sets HttpOnly cookie."""
    user = await db.fetchrow("SELECT * FROM users WHERE email = $1", payload.email)

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    if not auth_service.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    if user["status"] != "active":
        raise HTTPException(
            status_code=403,
            detail=f"Tu cuenta está en estado '{user['status']}'. Contactá al administrador.",
        )

    # Verificar si profesional está activo (aprobado por CEO)
    if user["role"] == "professional":
        prof_active = await db.fetchval(
            "SELECT is_active FROM professionals WHERE user_id = $1", user["id"]
        )
        if not prof_active:
            raise HTTPException(
                status_code=403,
                detail="Tu cuenta está pendiente de aprobación. Contactá al administrador.",
            )

    # Regla de Oro: resolver tenant_id y professional_id desde professionals por user_id (aislamiento total)
    prof_row = await db.fetchrow(
        "SELECT id, tenant_id FROM professionals WHERE user_id = $1", user["id"]
    )
    if prof_row is not None:
        tenant_id = int(prof_row["tenant_id"])
        professional_id = int(prof_row["id"])
    else:
        # CEO/secretary: no tienen fila en professionals, usar primera clínica
        tenant_id = int(
            await db.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1") or 1
        )
        professional_id = None

    token_data = {
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "tenant_id": tenant_id,
        "professional_id": professional_id,
    }
    token = auth_service.create_access_token(token_data)

    # Detectar si es HTTPS para decidir si usar secure cookie
    is_secure = os.getenv("NODE_ENV", "production").lower() != "development"

    # Set HttpOnly Cookie (Nexus Security Protocol v7.6)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_secure,  # Solo HTTPS en producción
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
            "tenant_id": tenant_id,
            "professional_id": professional_id,
        },
    }


@router.get("/me")
async def get_me(request: Request):
    """Returns the current authenticated user data. Supports cookies."""
    token = None
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Fallback to Cookie (HttpOnly)
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    token_data = auth_service.decode_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    # Convert TokenData (Pydantic) to dict for enrichment
    result = (
        token_data.model_dump()
        if hasattr(token_data, "model_dump")
        else token_data.dict()
        if hasattr(token_data, "dict")
        else dict(token_data)
    )

    # Enrich with professional_id (always query DB — TokenData doesn't carry it yet)
    user_id = result.get("user_id")
    t_id = result.get("tenant_id")
    if user_id and t_id:
        try:
            prof_id = await db.fetchval(
                "SELECT id FROM professionals WHERE user_id = $1 AND tenant_id = $2",
                uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
                int(t_id),
            )
            result["professional_id"] = int(prof_id) if prof_id is not None else None
        except Exception as e:
            logger.warning(f"Could not resolve professional_id in /auth/me: {e}")
            result["professional_id"] = None
    else:
        result["professional_id"] = None

    return result


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    google_calendar_id: Optional[str] = None
    specialty: Optional[str] = None
    phone_number: Optional[str] = None
    registration_id: Optional[str] = None
    consultation_price: Optional[float] = None
    working_hours: Optional[dict] = None


@router.get("/profile")
async def get_profile(request: Request):
    """Returns the detailed profile of the current user, including professional data."""
    user_data = await get_me(request)
    # get_me returns a dict, not a Pydantic model
    user_id = user_data["user_id"] if isinstance(user_data, dict) else user_data.user_id

    user = await db.fetchrow(
        "SELECT id, email, role, first_name, last_name, created_at FROM users WHERE id = $1",
        user_id,
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    profile = dict(user)
    # Serialize UUID/datetime for JSON
    profile["id"] = str(profile["id"])
    if profile.get("created_at"):
        profile["created_at"] = profile["created_at"].isoformat()

    # Professional/CEO data — load from professionals table if linked
    # CEO may also have a professional record for name/phone/specialty
    try:
        prof = await db.fetchrow(
            """SELECT id as professional_id, first_name as prof_first_name,
                      last_name as prof_last_name, email as prof_email,
                      specialty, phone_number, registration_id,
                      google_calendar_id, consultation_price, working_hours,
                      is_active, is_priority_professional, tenant_id
               FROM professionals WHERE user_id = $1
               ORDER BY is_active DESC, tenant_id ASC LIMIT 1""",
            uuid.UUID(user_id),
        )
        if prof:
            prof_dict = dict(prof)
            # Parse JSONB working_hours if string
            if isinstance(prof_dict.get("working_hours"), str):
                try:
                    prof_dict["working_hours"] = json.loads(prof_dict["working_hours"])
                except Exception:
                    pass
            # Convert Decimal to float
            if prof_dict.get("consultation_price") is not None:
                prof_dict["consultation_price"] = float(prof_dict["consultation_price"])
            # Fill name/email from professional if missing in user
            if not profile.get("first_name") and prof_dict.get("prof_first_name"):
                profile["first_name"] = prof_dict["prof_first_name"]
            if not profile.get("last_name") and prof_dict.get("prof_last_name"):
                profile["last_name"] = prof_dict["prof_last_name"]
            if not profile.get("email") and prof_dict.get("prof_email"):
                profile["email"] = prof_dict["prof_email"]
            # Remove temp aliases
            prof_dict.pop("prof_first_name", None)
            prof_dict.pop("prof_last_name", None)
            prof_dict.pop("prof_email", None)
            profile.update(prof_dict)
    except Exception as e:
        logger.warning(f"Profile professional enrichment failed (non-fatal): {e}")

    # Resolve tenant_id for CEO (even without professional record)
    if not profile.get("tenant_id"):
        try:
            tid = await db.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1")
            if tid:
                profile["tenant_id"] = tid
        except Exception:
            pass

    return profile


@router.patch("/profile")
async def update_profile(payload: ProfileUpdate, request: Request):
    """Updates the profile of the current user, including professional fields."""
    user_data = await get_me(request)
    # get_me returns a dict, not a Pydantic model
    user_id = user_data["user_id"] if isinstance(user_data, dict) else user_data.user_id

    # Update users table (name + email)
    update_users_fields = []
    params = []
    if payload.first_name is not None:
        update_users_fields.append(f"first_name = ${len(params) + 1}")
        params.append(payload.first_name)
    if payload.last_name is not None:
        update_users_fields.append(f"last_name = ${len(params) + 1}")
        params.append(payload.last_name)
    if payload.email is not None:
        update_users_fields.append(f"email = ${len(params) + 1}")
        params.append(payload.email)

    if update_users_fields:
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(update_users_fields)}, updated_at = NOW() WHERE id = ${len(params)}"
        await db.execute(query, *params)

    # Update professionals table (for any role that has a linked professional record)
    user_role = user_data["role"] if isinstance(user_data, dict) else user_data.role
    if user_role in ("professional", "ceo", "secretary"):
        prof_fields = []
        prof_params = []

        for field_name, db_col in [
            ("google_calendar_id", "google_calendar_id"),
            ("specialty", "specialty"),
            ("phone_number", "phone_number"),
            ("registration_id", "registration_id"),
        ]:
            val = getattr(payload, field_name, None)
            if val is not None:
                prof_fields.append(f"{db_col} = ${len(prof_params) + 1}")
                prof_params.append(val)

        if payload.consultation_price is not None:
            prof_fields.append(f"consultation_price = ${len(prof_params) + 1}")
            prof_params.append(payload.consultation_price)

        if payload.working_hours is not None:
            prof_fields.append(f"working_hours = ${len(prof_params) + 1}")
            prof_params.append(json.dumps(payload.working_hours))

        if prof_fields:
            prof_params.append(uuid.UUID(user_id))
            query = f"UPDATE professionals SET {', '.join(prof_fields)}, updated_at = NOW() WHERE user_id = ${len(prof_params)}"
            await db.execute(query, *prof_params)

        # Sync first_name/last_name to professionals table too
        name_updates = []
        name_params = []
        if payload.first_name is not None:
            name_updates.append(f"first_name = ${len(name_params) + 1}")
            name_params.append(payload.first_name)
        if payload.last_name is not None:
            name_updates.append(f"last_name = ${len(name_params) + 1}")
            name_params.append(payload.last_name)
        if payload.email is not None:
            name_updates.append(f"email = ${len(name_params) + 1}")
            name_params.append(payload.email)
        if name_updates:
            name_params.append(uuid.UUID(user_id))
            await db.execute(
                f"UPDATE professionals SET {', '.join(name_updates)} WHERE user_id = ${len(name_params)}",
                *name_params,
            )

    return {"message": "Perfil actualizado correctamente."}
