# Proposal: verify-payment-receipt-sql-bug

## Intent

Fix SQL error in `verify_payment_receipt` function where `SELECT` query references non-existent column `phone` from `tenants` table. The column should be `bot_phone_number`. This bug affects the professional liquidation dashboard.

## Scope

### In Scope
- Change column name from `phone` to `bot_phone_number` in `verify_payment_receipt` tenant query (line ~4130 of main.py)
- Verify the fix doesn't break existing functionality

### Out of Scope
- No schema changes
- No new features
- No other related queries

## Approach

Simple column name fix in the SQL query. Change `phone` to `bot_phone_number` in the SELECT statement that fetches tenant data.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modified | Line ~4130: tenant query SELECT - change `phone` to `bot_phone_number` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| No related queries affected (isolated bug) | Low | Simple one-line fix |
| No data migration needed | Low | Column already exists in table |

## Rollback Plan

Revert the column name change in the SQL query. The previous query would fail, so the fix is safe.

## Dependencies

- None - this is an isolated fix

## Success Criteria

- [ ] SQL query in verify_payment_receipt executes without "column phone does not exist" error
- [ ] Tenant data is correctly retrieved (including bank config)
- [ ] Function still works end-to-end for payment verification