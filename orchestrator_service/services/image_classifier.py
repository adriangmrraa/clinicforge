"""
Image classifier module for WhatsApp message classification.

Classifies messages as payment-related, medical, or neutral based on
keyword matching. Used to prevent infinite loop when patient sends
image with pending payment.

Spec: WhatsApp Agent Loop Bug Fix (v8.1)
"""

import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Default Spanish keywords for payment-related terms
DEFAULT_PAYMENT_KEYWORDS = [
    # Strong payment indicators
    r"transferencia",
    r"transferir",
    r"transferí",
    r"pagado",
    r"pagu[eé]",
    r"pago",
    r"comprobante",
    r"recibo",
    r"factura",
    r"boleto",
    r"depósito",
    r"deposito",
    r"depsité",
    r"envié.*pago",
    r"te.*transfiero",
    r"ya.*pagu[eé]",
    # Bank/financial
    r"cbu",
    r"alias",
    r"banco",
    r"mercadopago",
    r"mp",
    r"visa",
    r"mastercard",
    r"débito",
    r"debito",
    r"crédito",
    r"credito",
    # Amount indicators
    r"\$\d+",
    r"\d+\s*pesos",
    r"monto",
]

# Default Spanish keywords for medical-related terms
DEFAULT_MEDICAL_KEYWORDS = [
    # Medical document types
    r"orden.*médica",
    r"orden.*medica",
    r"receta",
    r"prescripci[óo]n",
    r"estudio",
    r"análisis",
    r"analisis",
    r"laboratorio",
    r"rayos?\s*x",
    r"ecograf",
    r"tomograf",
    r"resonancia",
    r"mamograf",
    r"biopsia",
    r"histopatol",
    # Dental
    r"ortodonci",
    r"implante",
    r"prótesis",
    r"protesis",
    r"caries",
    r"endodoncia",
    r"endodoncias",
    r"puente",
    r"corona",
    r"blanqueamiento",
    r"limpieza",
    r"extracci[óo]n",
    # Clinical terms
    r"diagnóstico",
    r"diagnostico",
    r"tratamiento",
    r"consulta",
    r"revisión",
    r"revisi[óo]n",
    r"chequeo",
    r"evaluaci[óo]n",
    # Body parts (for dental/medical context)
    r"diente",
    r"dientes",
    r"muela",
    r"muelas",
    r"encia",
    r"encias",
    r"paladar",
    r"lengua",
    r"labio",
    r"mandíbula",
    r"mandibula",
    # PDF-specific medical terms
    r"informe",
    r"resultado",
    r"resultados",
    r"laboratorio",
    r"analisis de sangre",
    r"análisis de sangre",
    r"rx",
    r"radiografía",
    r"radiografia",
    r"tomografía computada",
    r"tomografia computada",
    r"resonancia magnética",
    r"resonancia magnetica",
    r"eco",
    r"ecografía",
    r"ecografia",
    r"prescripcion",
    r"prescripción",
    r"indicación",
    r"indicacion",
    r"tratamiento",
]

# Strong payment keywords (single match triggers payment classification)
STRONG_PAYMENT_KEYWORDS = [
    r"comprobante",
    r"recibo",
    r"factura",
    r"transferencia",
    r"deposito",
    r"depsósito",
    r"cbu",
]

# Strong medical keywords (single match overrides payment)
STRONG_MEDICAL_KEYWORDS = [
    r"receta",
    r"orden.*médica",
    r"orden.*medica",
    r"rayos?\s*x",
    r"ecograf",
    r"tomograf",
    r"resonancia",
    r"ortodonci",
    r"implante",
    r"prótesis",
    r"protesis",
]


async def get_tenant_keywords(tenant_id: int) -> Dict[str, List[str]]:
    """
    Fetch tenant-specific keyword lists from database.

    Returns:
        Dict with 'payment_keywords' and 'medical_keywords' lists.
        Returns default keywords if not configured.
    """
    from db import get_pool

    pool = get_pool()
    try:
        row = await pool.fetchrow(
            """
            SELECT config::jsonb->'payment_keywords' as payment_kw,
                   config::jsonb->'medical_keywords' as medical_kw
            FROM tenants WHERE id = $1
            """,
            tenant_id,
        )

        payment_kw = row["payment_kw"] if row and row["payment_kw"] else None
        medical_kw = row["medical_kw"] if row and row["medical_kw"] else None

        return {
            "payment_keywords": payment_kw
            if isinstance(payment_kw, list)
            else DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": medical_kw
            if isinstance(medical_kw, list)
            else DEFAULT_MEDICAL_KEYWORDS,
        }
    except Exception as e:
        logger.warning(f"Error fetching tenant keywords: {e}")
        return {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }


def _compile_keywords(keywords: List[str]) -> List[re.Pattern]:
    """Compile list of keyword patterns into regex objects."""
    compiled = []
    for kw in keywords:
        try:
            compiled.append(re.compile(kw, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{kw}': {e}")
    return compiled


def _match_keywords(text: str, patterns: List[re.Pattern]) -> List[str]:
    """Match text against compiled patterns, return matched keywords."""
    matched = []
    for pattern in patterns:
        if pattern.search(text):
            matched.append(pattern.pattern)
    return matched


async def classify_message(
    text: str,
    tenant_id: int,
    vision_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify a WhatsApp message as payment-related, medical, or neutral.

    Args:
        text: The message text to classify
        tenant_id: Tenant ID for tenant-specific keyword configuration
        vision_description: Optional vision API description of attached image

    Returns:
        Dict with:
        - is_payment: bool - True if message appears to be payment-related
        - is_medical: bool - True if message appears to be medical document
        - keywords_found: List[str] - List of matched keywords
        - confidence: float - Confidence score (0.0 to 1.0)
        - classification: str - 'payment', 'medical', or 'neutral'
    """
    if not text and not vision_description:
        return {
            "is_payment": False,
            "is_medical": False,
            "keywords_found": [],
            "confidence": 0.0,
            "classification": "neutral",
        }

    # Prepare text inputs
    text_lower = text.lower() if text else ""
    vision_lower = vision_description.lower() if vision_description else ""
    full_text = (text_lower + " " + vision_lower).strip()

    # Get tenant-specific keywords
    keywords_config = await get_tenant_keywords(tenant_id)
    payment_patterns = _compile_keywords(keywords_config["payment_keywords"])
    medical_patterns = _compile_keywords(keywords_config["medical_keywords"])
    strong_payment_patterns = _compile_keywords(STRONG_PAYMENT_KEYWORDS)
    strong_medical_patterns = _compile_keywords(STRONG_MEDICAL_KEYWORDS)

    # Match keywords separately for text and vision description
    text_payment_matches = (
        _match_keywords(text_lower, payment_patterns) if text_lower else []
    )
    text_medical_matches = (
        _match_keywords(text_lower, medical_patterns) if text_lower else []
    )
    vision_payment_matches = (
        _match_keywords(vision_lower, payment_patterns) if vision_lower else []
    )
    vision_medical_matches = (
        _match_keywords(vision_lower, medical_patterns) if vision_lower else []
    )

    # Combined matches (for strong keyword detection and keyword list)
    payment_matches = text_payment_matches + vision_payment_matches
    medical_matches = text_medical_matches + vision_medical_matches
    strong_payment_matches = _match_keywords(full_text, strong_payment_patterns)
    strong_medical_matches = _match_keywords(full_text, strong_medical_patterns)

    # Weighted counts: vision matches count double (primary input)
    payment_weight = len(text_payment_matches) + 2 * len(vision_payment_matches)
    medical_weight = len(text_medical_matches) + 2 * len(vision_medical_matches)

    # Determine classification
    is_payment = False
    is_medical = False
    confidence = 0.0
    keywords_found = []

    # Strong medical keywords override everything
    if strong_medical_matches:
        is_medical = True
        is_payment = False
        confidence = 1.0
        keywords_found = strong_medical_matches + medical_matches
    # Strong payment keywords are enough to classify as payment
    elif strong_payment_matches:
        is_payment = True
        is_medical = False
        confidence = 1.0
        keywords_found = strong_payment_matches + payment_matches
    # Medical keywords override payment when both present
    elif medical_weight >= 1:
        is_medical = True
        is_payment = False
        confidence = min(0.9, 0.5 + (medical_weight / 10.0))
        keywords_found = medical_matches
    # Payment keywords with sufficient weight
    elif payment_weight >= 2:
        is_payment = True
        confidence = min(0.8, 0.3 + (payment_weight / 10.0))
        keywords_found = payment_matches
    # Weak payment indication
    elif payment_weight >= 1:
        is_payment = True
        confidence = 0.3
        keywords_found = payment_matches
    else:
        keywords_found = []

    # Boost confidence if there are vision matches (primary input)
    if (vision_payment_matches or vision_medical_matches) and confidence < 0.9:
        confidence = min(confidence + 0.1, 0.9)

    # Determine final classification
    if is_medical:
        classification = "medical"
    elif is_payment:
        classification = "payment"
    else:
        classification = "neutral"

    result = {
        "is_payment": is_payment,
        "is_medical": is_medical,
        "keywords_found": keywords_found,
        "confidence": confidence,
        "classification": classification,
    }

    logger.info(
        f"Message classified for tenant {tenant_id}: {classification} "
        f"(payment={is_payment}, medical={is_medical}, confidence={confidence:.2f})"
    )

    return result


async def classify_from_vision(
    vision_description: str, tenant_id: int
) -> Dict[str, any]:
    """Classify based solely on Vision API description."""
    return await classify_message(
        text="", tenant_id=tenant_id, vision_description=vision_description
    )


# Synchronous version for simpler use cases
def classify_message_sync(
    text: str,
    payment_keywords: Optional[List[str]] = None,
    medical_keywords: Optional[List[str]] = None,
) -> Dict[str, any]:
    """
    Synchronous version of classify_message for simpler use cases.
    Uses default keywords if none provided.

    Args:
        text: The message text to classify
        payment_keywords: Optional custom payment keywords
        medical_keywords: Optional custom medical keywords

    Returns:
        Dict with is_payment, is_medical, keywords_found, confidence, classification
    """
    if not text:
        return {
            "is_payment": False,
            "is_medical": False,
            "keywords_found": [],
            "confidence": 0.0,
            "classification": "neutral",
        }

    text_lower = text.lower()

    payment_kw = payment_keywords or DEFAULT_PAYMENT_KEYWORDS
    medical_kw = medical_keywords or DEFAULT_MEDICAL_KEYWORDS

    payment_patterns = _compile_keywords(payment_kw)
    medical_patterns = _compile_keywords(medical_kw)
    strong_payment_patterns = _compile_keywords(STRONG_PAYMENT_KEYWORDS)
    strong_medical_patterns = _compile_keywords(STRONG_MEDICAL_KEYWORDS)

    payment_matches = _match_keywords(text_lower, payment_patterns)
    medical_matches = _match_keywords(text_lower, medical_patterns)
    strong_payment_matches = _match_keywords(text_lower, strong_payment_patterns)
    strong_medical_matches = _match_keywords(text_lower, strong_medical_patterns)

    is_payment = False
    is_medical = False
    confidence = 0.0

    if strong_medical_matches:
        is_medical = True
        confidence = 1.0
        keywords_found = strong_medical_matches + medical_matches
    elif strong_payment_matches:
        is_payment = True
        confidence = 1.0
        keywords_found = strong_payment_matches + payment_matches
    elif len(payment_matches) >= 2:
        is_payment = True
        is_medical = len(medical_matches) >= 1
        confidence = min(0.8, len(payment_matches) / 5.0)
        keywords_found = payment_matches + medical_matches
    elif len(medical_matches) >= 1:
        is_medical = True
        confidence = min(0.8, len(medical_matches) / 3.0)
        keywords_found = medical_matches
    elif payment_matches:
        is_payment = True
        confidence = 0.3
        keywords_found = payment_matches
    else:
        keywords_found = []

    if is_medical:
        classification = "medical"
    elif is_payment:
        classification = "payment"
    else:
        classification = "neutral"

    return {
        "is_payment": is_payment,
        "is_medical": is_medical,
        "keywords_found": keywords_found,
        "confidence": confidence,
        "classification": classification,
    }
