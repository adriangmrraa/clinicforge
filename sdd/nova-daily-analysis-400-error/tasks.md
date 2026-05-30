# Nova Daily Analysis 400 Error Fix — Tasks

## Phase 1: Diagnose the exact cause - check what model is being used, check API call format
- [x] 1.1 Examine nova_daily_analysis.py _analyze_with_gpt function
- [x] 1.2 Check system_config key MODEL_INSIGHTS retrieval
- [x] 1.3 Identify that API call includes response_format JSON object for any model
- [x] 1.4 Determine that gpt-5.4-mini may not support JSON mode causing 400 error

## Phase 2: Implement model validation - validate model name before API call
- [x] 2.1 Create _validate_model helper that checks against MODEL_PRICING from token_tracker
- [x] 2.2 Log warning and fallback to gpt-4o-mini if model not in MODEL_PRICING
- [x] 2.3 Determine JSON mode support based on provider and type (openai + text)

## Phase 3: Fix JSON mode compatibility - ensure request format is compatible with the model
- [x] 3.1 Conditionally include response_format only when supports_json is True
- [x] 3.2 Implement retry logic: if 400 error with JSON mode incompatibility, retry without JSON mode
- [x] 3.3 Detect JSON mode incompatibility via error message keywords

## Phase 4: Add fallback to gpt-4o-mini if model is invalid
- [x] 4.1 Already integrated into _validate_model: fallback to gpt-4o-mini for unknown models

## Phase 5: Add diagnostics logging for debugging
- [x] 5.1 Log configured model, validated model, JSON mode status
- [x] 5.2 Log full HTTP response details on 400 errors
- [x] 5.3 Log retry attempts and outcomes

## Phase 6: Manual testing after fix
- [ ] 6.1 Deploy changes to test environment
- [ ] 6.2 Set MODEL_INSIGHTS to gpt-5.4-mini via dashboard
- [ ] 6.3 Trigger manual daily analysis run
- [ ] 6.4 Verify logs show warning about model validation and fallback (if needed)
- [ ] 6.5 Check Redis key nova_daily:{tenant_id} is populated with analysis results
- [ ] 6.6 Verify /admin/nova/daily-analysis endpoint returns available: true

## Files Changed
- `orchestrator_service/services/nova_daily_analysis.py` — Added model validation, JSON mode compatibility, retry logic, enhanced logging