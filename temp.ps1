$file = "orchestrator_service/admin_routes.py"
$content = Get-Content $file
$endpoint = @'
@router.get(
    "/patients/{patient_id}/attachments-summary",
    dependencies=[Depends(verify_admin_token)],
    tags=["Pacientes"],
    summary="Obtener el resumen más reciente de adjuntos del paciente",
)
async def get_attachment_summary(
    patient_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Get the most recent attachment summary for a patient."""
    # Verify patient belongs to tenant
    patient = await db.pool.fetchrow(
        "SELECT id, tenant_id FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id, tenant_id
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    # Get latest summary
    summary = await db.pool.fetchrow("""
        SELECT summary_text, attachments_count, attachments_types, created_at
        FROM clinical_record_summaries
        WHERE tenant_id = $1 AND patient_id = $2
        ORDER BY created_at DESC
        LIMIT 1
    """, tenant_id, patient_id)
    
    if not summary:
        return {"summary_text": None, "attachments_count": 0, "attachments_types": [], "created_at": None}
    
    return {
        "summary_text": summary["summary_text"],
        "attachments_count": summary["attachments_count"],
        "attachments_types": summary["attachments_types"] or [],
        "created_at": summary["created_at"].isoformat() if summary["created_at"] else None
    }
'@
$endpointLines = $endpoint -split "`n"
$newContent = @()
$found = $false
for ($i = 0; $i -lt $content.Count; $i++) {
    $line = $content[$i]
    if ($line -eq "# ==================== ENDPOINTS TRATAMIENTOS ====================" -and $i -gt 1 -and $content[$i-1] -eq "" -and $content[$i-2] -eq "") {
        # Insert endpoint lines before the comment, keeping one blank line before comment
        $newContent += $content[$i-2]  # empty line
        $newContent += $endpointLines
        $newContent += ""  # blank line before comment
        $newContent += $line
        $found = $true
    } else {
        $newContent += $line
    }
}
if ($found) {
    Set-Content $file $newContent
    Write-Host "Endpoint added successfully."
} else {
    Write-Host "Pattern not found."
}