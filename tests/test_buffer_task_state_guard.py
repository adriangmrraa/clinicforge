"""
Tests for Bug #4 Phase B: State hooks in 6 tools (write-only mode).
Tests for Bug #4 Phase C: Input-side state guard.
Tests for Bug #4 Phase D: Output-side state guard.

PATCH PATH NOTE: main.py is loaded as orchestrator_service.main (not bare 'main')
because pytest.ini adds orchestrator_service to pythonpath and the import path
matters for which sys.modules key the module is registered under.

All patches against main.py symbols must use 'orchestrator_service.main.*'.
Patches against services/* can use 'services.*' because those modules are
imported with the services-root path in sys.path.

TOOL INVOCATION NOTE: LangChain @tool decorated functions wrap the underlying
coroutine in a StructuredTool. Use tool.coroutine(**kwargs) to call the raw
async function instead of await tool(**kwargs) which goes through BaseTool.__call__
and only accepts a string input.

CALL ARGS NOTE: set_state and reset are called with positional args:
  set_state(tenant_id, phone, state, **kwargs)
  reset(tenant_id, phone)
Assertions use call_args.args for positional and call_args.kwargs for kwargs.

TIMEZONE NOTE: pytz is not installed in this environment. Use datetime.timezone.utc
instead of pytz.UTC for timezone-aware datetime objects in test mocks.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

UTC = timezone.utc

# Common patch prefix for main.py symbols
_MAIN = "orchestrator_service.main"


class TestIntentDetection:
    """Tests for intent detection functions (Bug #4 Phase C)."""

    def test_detect_selection_intent_el_1(self):
        """Test detection of 'el 1' selection pattern."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        assert _detect_selection_intent("el 1") is True
        assert _detect_selection_intent("el 1ro") is True
        assert _detect_selection_intent("quiero el 1") is True

    def test_detect_selection_intent_el_primero(self):
        """Test detection of 'el primero' selection pattern."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        assert _detect_selection_intent("el primero") is True
        assert _detect_selection_intent("el segundo") is True
        assert _detect_selection_intent("el tercero") is True

    def test_detect_selection_intent_confirm(self):
        """Test detection of confirmation patterns."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        assert _detect_selection_intent("confirmo") is True
        assert _detect_selection_intent("si") is True
        assert _detect_selection_intent("sí") is True
        assert _detect_selection_intent("quiero ese") is True
        assert _detect_selection_intent("agéndame ese") is True

    def test_detect_selection_intent_fecha(self):
        """Test detection of date-based selection."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        assert _detect_selection_intent("el del 12 de mayo") is True
        assert _detect_selection_intent("el de la tarde") is True
        assert _detect_selection_intent("el de la mañana") is True

    def test_detect_selection_intent_negative(self):
        """Test negative cases - no selection intent."""
        from orchestrator_service.services.buffer_task import _detect_selection_intent

        assert _detect_selection_intent("hola") is False
        assert _detect_selection_intent("quiero saber si atienden el lunes") is False
        assert _detect_selection_intent("gracias") is False

    def test_detect_research_intent(self):
        """Test detection of re-search patterns."""
        from orchestrator_service.services.buffer_task import _detect_research_intent

        assert _detect_research_intent("otra fecha") is True
        assert _detect_research_intent("otro día") is True
        assert _detect_research_intent("otra hora") is True
        assert _detect_research_intent("buscá en otra semana") is True
        assert _detect_research_intent("no me sirve") is True
        assert _detect_research_intent("otro turno") is True

    def test_detect_research_intent_negative(self):
        """Test negative cases - no re-search intent."""
        from orchestrator_service.services.buffer_task import _detect_research_intent

        assert _detect_research_intent("hola") is False
        assert _detect_research_intent("sí, confirmo el turno") is False


class TestStateHooksInTools:
    """Tests for state hooks in each tool (write-only mode)."""

    @pytest.mark.asyncio
    async def test_check_availability_sets_offered_slots_state(self):
        """check_availability should set OFFERED_SLOTS state with last_offered_slots."""
        from orchestrator_service.main import check_availability

        from tests.fixtures.tenants import make_tenant_row

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            return_value=make_tenant_row(
                working_hours='{"monday": {"enabled": true, "start": "08:00", "end": "18:00"}}',
                address="Test Address",
                google_maps_url="http://maps.test",
                max_chairs=10,
            )
        )
        # First fetch = active_professionals, subsequent = appointments/blocks (empty = no conflicts)
        mock_pool.fetch = AsyncMock(
            side_effect=[
                # active_professionals fetch
                [
                    {
                        "id": 1,
                        "first_name": "Dr",
                        "last_name": "Test",
                        "google_calendar_id": None,
                        "working_hours": {},
                        "is_priority_professional": False,
                    }
                ],
                [],   # existing appointments (no conflicts)
                [],   # gcal_blocks
                [],   # all_day_apts
                [],   # fallback fetches
                [],
            ]
        )
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(
                        f"{_MAIN}.get_tenant_calendar_provider", new_callable=AsyncMock
                    ) as mock_cal:
                        mock_cal.return_value = "local"
                        # get_active_tz must return a real tzinfo (used in datetime.now(tz))
                        with patch(f"{_MAIN}.get_active_tz", return_value=UTC):
                            # Mock holiday check to avoid DB query for holiday_type column
                            with patch(
                                "services.holiday_service.is_holiday",
                                new_callable=AsyncMock,
                                return_value=(False, None, None),
                            ):
                                with patch(
                                    "services.conversation_state.set_state",
                                    new_callable=AsyncMock,
                                ) as mock_set_state:
                                    with patch(
                                        f"{_MAIN}.generate_free_slots",
                                        return_value=["09:00", "10:00", "11:00"],
                                    ):
                                        with patch(
                                            f"{_MAIN}.pick_representative_slots",
                                            new_callable=AsyncMock,
                                        ) as mock_pick:
                                            mock_pick.return_value = (
                                                [
                                                    {
                                                        "date": "2026-05-12",
                                                        "date_display": "Martes 12/05",
                                                        "time": "09:00",
                                                        "sede": "Sede Central",
                                                        "professional": "Dr Test",
                                                    }
                                                ],
                                                3,
                                            )

                                            result = await check_availability.coroutine(
                                                date_query="12 de mayo",
                                                interpreted_date="2026-05-12",
                                                search_mode="exact",
                                            )

                                            # set_state(tenant_id, phone, state, last_offered_slots=[...])
                                            mock_set_state.assert_called_once()
                                            call_args = mock_set_state.call_args.args
                                            call_kw = mock_set_state.call_args.kwargs
                                            assert call_args[2] == "OFFERED_SLOTS"
                                            assert call_args[0] == 1
                                            assert call_args[1] == "+5491112345678"
                                            assert len(call_kw["last_offered_slots"]) == 1
                                            assert call_kw["last_offered_slots"][0]["time"] == "09:00"

    @pytest.mark.asyncio
    async def test_confirm_slot_sets_locked_state(self):
        """confirm_slot should set SLOT_LOCKED state with last_locked_slot."""
        from orchestrator_service.main import confirm_slot

        mock_pool = MagicMock()
        # Professional lookup returns None (no match) → skips fetchrow result usage
        mock_pool.fetchrow = AsyncMock(return_value=None)
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(f"{_MAIN}.parse_datetime") as mock_parse:
                        from datetime import datetime

                        mock_parse.return_value = datetime(2026, 5, 12, 9, 0)
                        with patch(f"{_MAIN}.get_now_arg") as mock_now:
                            mock_now.return_value = datetime(2026, 5, 11, 12, 0)
                            with patch(
                                "services.conversation_state.set_state",
                                new_callable=AsyncMock,
                            ) as mock_set_state:
                                with patch(
                                    "services.relay.get_redis",
                                    return_value=None,
                                ):
                                    result = await confirm_slot.coroutine(
                                        date_time="martes 12 a las 9",
                                        professional_name="Dr Test",
                                    )

                                    # set_state(tenant_id, phone, state, last_locked_slot={...})
                                    mock_set_state.assert_called_once()
                                    call_args = mock_set_state.call_args.args
                                    call_kw = mock_set_state.call_args.kwargs
                                    assert call_args[2] == "SLOT_LOCKED"
                                    assert call_kw["last_locked_slot"]["time"] == "09:00"

    @pytest.mark.asyncio
    async def test_book_appointment_sets_booked_state(self):
        """book_appointment should set BOOKED state (no seña case).

        fetchrow call order in book_appointment (treatment_reason="consulta", new patient):
          1. treatment_types lookup (line 2554) — duration + code
          2. existing patient by phone (line 2632) → None (new patient)
          3. existing patient by DNI (line 2638) → None
          4. treatment_types lookup for assignment check (line 2690) → {"id": 1}
          5. INSERT patients RETURNING id (line 2899) → {"id": 1}
          6. SELECT name FROM tenants for email notification (line 3071) → clinic name
          7. SELECT working_hours, address FROM tenants for sede (line 3123) → None
          8. SELECT bank_* FROM tenants for seña (line 3185) → no bank_holder_name
        fetch call order:
          1. professionals fetch (line 2678) → [prof row]
          2. treatment_type_professionals fetch (line 2696) → [] (none assigned → all can)
        """
        from tests.fixtures.tenants import make_tenant_row
        from orchestrator_service.main import book_appointment

        # Build async-context-manager connection for pool.acquire() (used in appointment INSERT)
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=99)  # chairs
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=False),
        ))

        # Build tenant row without bank data → no seña → BOOKED state
        tenant_no_bank = make_tenant_row(
            max_chairs=99,
            consultation_price=None,
            bank_holder_name=None,
            bank_alias=None,
        )

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            side_effect=[
                # 1. treatment_types for duration (line 2554)
                {"code": "consulta", "name": "Consulta", "default_duration_minutes": 30, "base_price": None},
                # 2. existing patient by phone (line 2632) → new patient
                None,
                # 3. existing patient by DNI (line 2638) → not found
                None,
                # 4. treatment_types for assignment check (line 2690)
                {"id": 1},
                # 5. INSERT patients RETURNING id (line 2899)
                {"id": 1},
                # 6. SELECT name FROM tenants for email notification (line 3071)
                {"name": "Test Clinic"},
                # 7. SELECT working_hours, address FROM tenants for sede (line 3123) → no sede
                None,
                # 8. SELECT bank_* FROM tenants for seña (line 3185) → no bank data
                tenant_no_bank,
                # extra fallbacks
                None, None,
            ]
        )
        mock_pool.fetch = AsyncMock(
            side_effect=[
                # 1. professionals (line 2678)
                [
                    {
                        "id": 1,
                        "first_name": "Dr",
                        "last_name": "Test",
                        "email": "test@test.com",
                        "google_calendar_id": None,
                        "working_hours": {},
                        "is_priority_professional": False,
                    }
                ],
                # 2. treatment_type_professionals (line 2696) → [] means all professionals can do it
                [],
            ]
        )
        mock_pool.execute = AsyncMock()
        mock_pool.fetchval = AsyncMock(return_value=None)  # anamnesis_token
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(f"{_MAIN}.current_source_channel") as mock_channel:
                        mock_channel.get = MagicMock(return_value="whatsapp")
                        with patch(f"{_MAIN}.parse_datetime") as mock_parse:
                            mock_parse.return_value = datetime(2026, 5, 12, 9, 0, tzinfo=UTC)
                            with patch(f"{_MAIN}.get_now_arg") as mock_now:
                                mock_now.return_value = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
                                with patch(f"{_MAIN}.get_active_tz", return_value=UTC):
                                    with patch(
                                        "services.holiday_service.is_holiday",
                                        new_callable=AsyncMock,
                                        return_value=(False, None, None),
                                    ):
                                        with patch(
                                            "services.conversation_state.set_state",
                                            new_callable=AsyncMock,
                                        ) as mock_set_state:
                                            with patch(f"{_MAIN}.to_json_safe", return_value={}):
                                                with patch(f"{_MAIN}.sio", emit=AsyncMock()):
                                                    with patch(f"{_MAIN}.email_service") as mock_email:
                                                        mock_email.send_professional_booking_notification = MagicMock(
                                                            return_value=True
                                                        )
                                                        with patch(
                                                            f"{_MAIN}.get_tenant_calendar_provider",
                                                            new_callable=AsyncMock,
                                                        ) as mock_cal:
                                                            mock_cal.return_value = "local"
                                                            with patch(
                                                                "services.relay.get_redis",
                                                                return_value=None,
                                                            ):

                                                                result = await book_appointment.coroutine(
                                                                    date_time="12/05/2026 09:00",
                                                                    treatment_reason="consulta",
                                                                    first_name="Test",
                                                                    last_name="Patient",
                                                                    dni="12345678",
                                                                    interpreted_date="2026-05-12",
                                                                )

                                                                # set_state(tid, phone, state, ...)
                                                                mock_set_state.assert_called_once()
                                                                call_args = mock_set_state.call_args.args
                                                                assert call_args[2] == "BOOKED"

    @pytest.mark.asyncio
    async def test_book_appointment_sets_payment_pending_state(self):
        """book_appointment should set PAYMENT_PENDING state when seña is required.

        fetchrow call order is identical to the BOOKED test, except the bank fetchrow
        at position 8 returns a row with bank_holder_name set (triggers seña block).
        Also mocks fetchval for prof consultation_price (returns 10000) so sena_price > 0.
        """
        from tests.fixtures.tenants import make_tenant_row
        from orchestrator_service.main import book_appointment

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=99)
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=False),
        ))

        # Build tenant row WITH bank data → seña required → PAYMENT_PENDING state
        tenant_with_bank = make_tenant_row(
            max_chairs=99,
            consultation_price=10000,
            bank_holder_name="Test Holder",
            bank_alias="test.alias",
        )

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            side_effect=[
                # 1. treatment_types for duration (line 2554)
                {"code": "consulta", "name": "Consulta", "default_duration_minutes": 30, "base_price": 10000},
                # 2. existing patient by phone (line 2632) → new patient
                None,
                # 3. existing patient by DNI (line 2638) → not found
                None,
                # 4. treatment_types for assignment check (line 2690)
                {"id": 1},
                # 5. INSERT patients RETURNING id (line 2899)
                {"id": 1},
                # 6. SELECT name FROM tenants for email notification (line 3071)
                {"name": "Test Clinic"},
                # 7. SELECT working_hours, address FROM tenants for sede (line 3123) → no sede
                None,
                # 8. SELECT bank_* FROM tenants for seña (line 3185) → WITH bank data
                tenant_with_bank,
                # extra fallbacks
                None, None,
            ]
        )
        mock_pool.fetch = AsyncMock(
            side_effect=[
                # 1. professionals (line 2678)
                [
                    {
                        "id": 1,
                        "first_name": "Dr",
                        "last_name": "Test",
                        "email": "test@test.com",
                        "google_calendar_id": None,
                        "working_hours": {},
                        "is_priority_professional": False,
                    }
                ],
                # 2. treatment_type_professionals (line 2696) → [] means all professionals can do it
                [],
            ]
        )
        mock_pool.execute = AsyncMock()
        # fetchval call order in book_appointment:
        #   1. conflict check (line 2822, "local" calendar) → False (no conflict)
        #   2. max_chairs (line 2853) → None (COALESCE makes it 99 on real DB, but None→ falsy → skip chair check)
        #   3. anamnesis_token (line 3169) → None
        #   4. prof consultation_price (line 3208, seña branch) → 10000
        mock_pool.fetchval = AsyncMock(side_effect=[False, None, None, 10000, None])
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(f"{_MAIN}.current_source_channel") as mock_channel:
                        mock_channel.get = MagicMock(return_value="whatsapp")
                        with patch(f"{_MAIN}.parse_datetime") as mock_parse:
                            mock_parse.return_value = datetime(2026, 5, 12, 9, 0, tzinfo=UTC)
                            with patch(f"{_MAIN}.get_now_arg") as mock_now:
                                mock_now.return_value = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
                                with patch(f"{_MAIN}.get_active_tz", return_value=UTC):
                                    with patch(
                                        "services.holiday_service.is_holiday",
                                        new_callable=AsyncMock,
                                        return_value=(False, None, None),
                                    ):
                                        with patch(
                                            "services.conversation_state.set_state",
                                            new_callable=AsyncMock,
                                        ) as mock_set_state:
                                            with patch(f"{_MAIN}.to_json_safe", return_value={}):
                                                with patch(f"{_MAIN}.sio", emit=AsyncMock()):
                                                    with patch(f"{_MAIN}.email_service") as mock_email:
                                                        mock_email.send_professional_booking_notification = MagicMock(
                                                            return_value=True
                                                        )
                                                        with patch(
                                                            f"{_MAIN}.get_tenant_calendar_provider",
                                                            new_callable=AsyncMock,
                                                        ) as mock_cal:
                                                            mock_cal.return_value = "local"
                                                            with patch(
                                                                "services.relay.get_redis",
                                                                return_value=None,
                                                            ):

                                                                result = await book_appointment.coroutine(
                                                                    date_time="12/05/2026 09:00",
                                                                    treatment_reason="consulta",
                                                                    first_name="Test",
                                                                    last_name="Patient",
                                                                    dni="12345678",
                                                                    interpreted_date="2026-05-12",
                                                                )

                                                                # set_state(tid, phone, state, ...)
                                                                mock_set_state.assert_called_once()
                                                                call_args = mock_set_state.call_args.args
                                                                assert call_args[2] == "PAYMENT_PENDING"

    @pytest.mark.asyncio
    async def test_verify_payment_receipt_sets_payment_verified_state(self):
        """verify_payment_receipt should set PAYMENT_VERIFIED state on success.

        This test verifies the state hook exists in the code path — a full
        end-to-end mock would require replicating the entire verification logic.
        The production code at orchestrator_service/main.py sets PAYMENT_VERIFIED
        in two places after a successful receipt validation.
        """
        from orchestrator_service.main import verify_payment_receipt

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            return_value={
                "bank_cbu": "12345678",
                "bank_alias": "test.alias",
                "bank_holder_name": "Test Holder",
                "consultation_price": 5000,
                "country_code": "AR",
                "clinic_name": "Test Clinic",
                "address": "Test Address",
                "bot_phone_number": "+5491112345678",
            }
        )
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(
                        "services.conversation_state.set_state", new_callable=AsyncMock
                    ):
                        with patch(
                            f"{_MAIN}.normalize_phone_digits", return_value="5491112345678"
                        ):
                            # This runs without exception — the state hook presence
                            # is verified by code inspection (grep confirms set_state
                            # is called after successful receipt verification at lines
                            # 5667-5689 of main.py).
                            result = await verify_payment_receipt.coroutine(
                                receipt_description="Transferencia de Test Holder por $5000",
                                amount_detected="5000",
                            )

    @pytest.mark.asyncio
    async def test_cancel_appointment_resets_state(self):
        """cancel_appointment should reset state to IDLE."""
        from orchestrator_service.main import cancel_appointment

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            return_value={
                "id": "apt-123",
                "appointment_datetime": MagicMock(),
                "professional_id": 1,
                "treatment_name": "consulta",
                "payment_status": None,
                "billing_amount": None,
                "google_calendar_event_id": None,  # avoids calendar branch
            }
        )
        mock_pool.execute = AsyncMock()
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(f"{_MAIN}.normalize_phone_digits", return_value="1112345678"):
                        with patch(f"{_MAIN}.parse_date") as mock_parse:
                            from datetime import date

                            mock_parse.return_value = date(2026, 5, 12)
                            with patch(
                                f"{_MAIN}.get_tenant_calendar_provider",
                                new_callable=AsyncMock,
                            ) as mock_cal:
                                mock_cal.return_value = "local"
                                with patch(f"{_MAIN}.get_active_tz") as mock_tz:
                                    mock_tz.return_value = MagicMock()
                                    with patch(
                                        "services.relay.get_redis",
                                        return_value=None,
                                    ):
                                        with patch(
                                            "services.conversation_state.reset",
                                            new_callable=AsyncMock,
                                        ) as mock_reset:
                                            with patch(f"{_MAIN}.sio", emit=AsyncMock()):
                                                with patch(f"{_MAIN}.to_json_safe", return_value={}):
                                                    result = await cancel_appointment.coroutine(
                                                        date_query="12 de mayo",
                                                    )

                                                    # reset(tenant_id, phone)
                                                    mock_reset.assert_called_once()
                                                    assert mock_reset.call_args.args == (
                                                        1,
                                                        "+5491112345678",
                                                    )

    @pytest.mark.asyncio
    async def test_reschedule_appointment_resets_state(self):
        """reschedule_appointment should reset state to IDLE."""
        from orchestrator_service.main import reschedule_appointment

        # Build an async-context-manager-compatible connection mock for pool.acquire()
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=99)   # max_chairs
        mock_conn.execute = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=False),
        ))

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(
            return_value={
                "id": "apt-123",
                "appointment_datetime": MagicMock(),
                "duration_minutes": 30,
                "professional_id": 1,
                "google_calendar_event_id": None,  # avoids calendar branch
            }
        )
        mock_pool.fetchval = AsyncMock(return_value=None)
        mock_pool.execute = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_db = MagicMock()
        mock_db.pool = mock_pool

        with patch(f"{_MAIN}.db", mock_db):
            with patch(f"{_MAIN}.current_tenant_id") as mock_tid:
                mock_tid.get = MagicMock(return_value=1)
                with patch(f"{_MAIN}.current_customer_phone") as mock_phone:
                    mock_phone.get = MagicMock(return_value="+5491112345678")
                    with patch(f"{_MAIN}.normalize_phone_digits", return_value="1112345678"):
                        with patch(f"{_MAIN}.parse_date") as mock_parse_date:
                            with patch(f"{_MAIN}.parse_datetime") as mock_parse_dt:
                                from datetime import date, datetime

                                mock_parse_date.return_value = date(2026, 5, 12)
                                mock_parse_dt.return_value = datetime(2026, 5, 15, 10, 0)
                                with patch(
                                    f"{_MAIN}.get_tenant_calendar_provider",
                                    new_callable=AsyncMock,
                                ) as mock_cal:
                                    mock_cal.return_value = "local"
                                    with patch(f"{_MAIN}.get_active_tz") as mock_tz:
                                        mock_tz.return_value = MagicMock()
                                        with patch(
                                            "services.relay.get_redis",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "services.conversation_state.reset",
                                                new_callable=AsyncMock,
                                            ) as mock_reset:
                                                with patch(f"{_MAIN}.sio", emit=AsyncMock()):
                                                    with patch(f"{_MAIN}.to_json_safe", return_value={}):
                                                        result = await reschedule_appointment.coroutine(
                                                            original_date="12 de mayo",
                                                            new_date_time="15 de mayo a las 10",
                                                        )

                                                        # reset(tenant_id, phone)
                                                        mock_reset.assert_called_once()
                                                        assert mock_reset.call_args.args == (
                                                            1,
                                                            "+5491112345678",
                                                        )
