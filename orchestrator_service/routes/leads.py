"""
Leads Management API for ClinicForge
Endpoints for managing Meta Lead Forms leads
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_ceo_infra_only as get_ceo_user_and_tenant, get_current_user
from services.meta_leads_service import MetaLeadsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/leads", tags=["Leads Management"])


@router.get("")
async def get_leads(
    status: Optional[str] = Query(None, description="Filter by status"),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get leads with filtering options.
    
    Returns paginated list of leads with optional filters.
    """
    user, tenant_id = auth_data
    
    try:
        leads_data = await MetaLeadsService.get_leads(
            tenant_id=tenant_id,
            status=status,
            campaign_id=campaign_id,
            assigned_to=assigned_to,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset
        )
        
        return leads_data
        
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving leads")


@router.get("/{lead_id}")
async def get_lead_details(
    lead_id: str,
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get detailed lead information.
    
    Includes lead data, status history, and notes.
    """
    user, tenant_id = auth_data
    
    try:
        lead_details = await MetaLeadsService.get_lead_details(lead_id, tenant_id)
        
        if not lead_details:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        return lead_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead details: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving lead details")


@router.put("/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    status_update: Dict[str, Any],
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Update lead status.
    
    Request body:
    {
        "new_status": "contacted",
        "change_reason": "Called the lead"
    }
    """
    user, tenant_id = auth_data
    
    new_status = status_update.get("new_status")
    change_reason = status_update.get("change_reason", "")
    
    if not new_status:
        raise HTTPException(status_code=400, detail="new_status is required")
    
    # Validate status
    valid_statuses = ['new', 'contacted', 'consultation_scheduled', 
                     'treatment_planned', 'converted', 'not_interested', 'spam']
    
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        success = await MetaLeadsService.update_lead_status(
            lead_id=lead_id,
            tenant_id=tenant_id,
            new_status=new_status,
            changed_by=str(user.id) if user else None,
            change_reason=change_reason
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Lead not found or update failed")
        
        return {"success": True, "message": "Lead status updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lead status: {e}")
        raise HTTPException(status_code=500, detail="Error updating lead status")


@router.put("/{lead_id}/assign")
async def assign_lead(
    lead_id: str,
    assignment: Dict[str, Any],
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Assign lead to a user.
    
    Request body:
    {
        "assigned_to": "user-uuid-here"
    }
    """
    user, tenant_id = auth_data
    
    assigned_to = assignment.get("assigned_to")
    
    if not assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to is required")
    
    try:
        # Validate UUID format
        UUID(assigned_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format for assigned_to")
    
    try:
        success = await MetaLeadsService.assign_lead(
            lead_id=lead_id,
            tenant_id=tenant_id,
            assigned_to=assigned_to
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Lead not found or assignment failed")
        
        return {"success": True, "message": "Lead assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning lead: {e}")
        raise HTTPException(status_code=500, detail="Error assigning lead")


@router.post("/{lead_id}/notes")
async def add_lead_note(
    lead_id: str,
    note_data: Dict[str, Any],
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Add note to lead.
    
    Request body:
    {
        "content": "Called the lead, interested in implants"
    }
    """
    user, tenant_id = auth_data
    
    content = note_data.get("content")
    
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    
    try:
        note_id = await MetaLeadsService.add_note(
            lead_id=lead_id,
            tenant_id=tenant_id,
            content=content,
            created_by=str(user.id) if user else None
        )
        
        return {"success": True, "note_id": note_id, "message": "Note added successfully"}
        
    except Exception as e:
        logger.error(f"Error adding lead note: {e}")
        raise HTTPException(status_code=500, detail="Error adding note")


@router.post("/{lead_id}/convert")
async def convert_lead_to_patient(
    lead_id: str,
    conversion_data: Dict[str, Any],
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Convert lead to patient.
    
    Request body:
    {
        "patient_id": "patient-uuid-here"
    }
    """
    user, tenant_id = auth_data
    
    patient_id = conversion_data.get("patient_id")
    
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")
    
    try:
        # Validate UUID format
        UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format for patient_id")
    
    try:
        success = await MetaLeadsService.convert_lead_to_patient(
            lead_id=lead_id,
            tenant_id=tenant_id,
            patient_id=patient_id,
            converted_by=str(user.id) if user else None
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Lead or patient not found, or conversion failed")
        
        return {"success": True, "message": "Lead converted to patient successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting lead to patient: {e}")
        raise HTTPException(status_code=500, detail="Error converting lead")


@router.get("/stats/summary")
async def get_leads_summary(
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get leads summary statistics.
    
    Returns counts by status, campaign, and other metrics.
    """
    user, tenant_id = auth_data
    
    try:
        summary = await MetaLeadsService.get_leads_summary(
            tenant_id=tenant_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting leads summary: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving leads summary")


@router.get("/webhook/url")
async def get_webhook_url(
    auth_data: tuple = Depends(get_ceo_user_and_tenant)
):
    """
    Get Meta Leads webhook URL for this tenant.
    
    Returns the complete webhook URL to configure in Meta Ads.
    """
    user, tenant_id = auth_data
    
    try:
        # Get deployment config
        from core.deployment import get_deployment_config
        
        config = await get_deployment_config()
        
        if not config or not config.get("base_url"):
            raise HTTPException(
                status_code=404, 
                detail="Deployment configuration not found"
            )
        
        webhook_url = f"{config['base_url']}/api/webhooks/meta?tenant_id={tenant_id}"
        
        return {
            "webhook_url": webhook_url,
            "verify_token": "clinicforge_meta_secret_token",  # From environment
            "instructions": "Configure this URL in Meta Ads Lead Forms webhook settings"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook URL: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving webhook URL")