import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, date, timedelta
from orchestrator_service.main import check_availability

@pytest.mark.asyncio
async def test_check_availability_blocked_insurance():
    with patch("orchestrator_service.main.db.pool.fetchrow", new_callable=AsyncMock) as mock_fetchrow, \
         patch("orchestrator_service.main.db.pool.fetch", new_callable=AsyncMock) as mock_fetch, \
         patch("orchestrator_service.main.current_tenant_id") as mock_tenant_id, \
         patch("orchestrator_service.main.current_customer_phone") as mock_phone:
        
        mock_tenant_id.get.return_value = 1
        mock_phone.get.return_value = "1234567890"

        # Mock tenant config
        mock_fetchrow.side_effect = [
            {"working_hours": {}, "address": "Test", "google_maps_url": "", "max_chairs": 1},
            # Mock patient with BLOCKED insurance
            {
                "id": 1,
                "assigned_professional_id": None,
                "insurance_provider": "OSDE",
                "scheduling_mode": "blocked",
                "scheduling_delay_days": 0,
                "insurance_is_active": True,
                "unpaid_past_apts": 0,
                "unpaid_total": 0.0
            }
        ]
        
        mock_fetch.return_value = []

        result = await check_availability("mañana")
        assert "Por el momento tenemos suspendida temporalmente la atención por la cobertura OSDE" in result


@pytest.mark.asyncio
async def test_check_availability_delayed_insurance():
    with patch("orchestrator_service.main.db.pool.fetchrow", new_callable=AsyncMock) as mock_fetchrow, \
         patch("orchestrator_service.main.db.pool.fetch", new_callable=AsyncMock) as mock_fetch, \
         patch("orchestrator_service.main.current_tenant_id") as mock_tenant_id, \
         patch("orchestrator_service.main.current_customer_phone") as mock_phone, \
         patch("orchestrator_service.main.get_now_arg") as mock_now, \
         patch("orchestrator_service.main.get_tenant_calendar_provider", new_callable=AsyncMock) as mock_cal_prov:
        
        mock_tenant_id.get.return_value = 1
        mock_phone.get.return_value = "1234567890"
        
        today = datetime(2026, 6, 8, 12, 0, 0)
        mock_now.return_value = today
        mock_cal_prov.return_value = "local"

        def fetchrow_side_effect(query, *args, **kwargs):
            if "FROM tenants" in query:
                return {"working_hours": {}, "address": "Test", "google_maps_url": "", "max_chairs": 1}
            if "FROM patients" in query:
                return {
                    "id": 1,
                    "assigned_professional_id": None,
                    "insurance_provider": "OSDE",
                    "scheduling_mode": "delayed",
                    "scheduling_delay_days": 5,
                    "insurance_is_active": True,
                    "unpaid_past_apts": 0,
                    "unpaid_total": 0.0
                }
            return None
            
        mock_fetchrow.side_effect = fetchrow_side_effect
        
        # We also need to mock active_professionals to prevent it from returning "No hay profesionales..."
        def fetch_side_effect(query, *args, **kwargs):
            if "FROM professionals" in query:
                return [{"id": 1, "first_name": "Dr", "last_name": "Test", "google_calendar_id": None, "working_hours": {}, "is_priority_professional": False}]
            if "FROM appointments" in query:
                return []
            return []
            
        mock_fetch.side_effect = fetch_side_effect

        # "mañana" would mean target_date = June 9th. But delay is 5 days, so minimum date is June 13th.
        # It should adjust the target_date and then fail to find slots or find slots on June 13th.
        # Since working_hours are empty, it will fall through to "No encontré días con atención disponible"
        result = await check_availability("mañana")
        
        # The main thing is it shouldn't return the blocked message, it should process normally.
        # We check that it didn't return the blocked string
        assert "suspendida temporalmente" not in result
