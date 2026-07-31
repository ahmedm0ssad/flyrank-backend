# M15 — Gap-Fill: Security, Integration

**Status:** ✅ COMPLETE

## Tests added by category

| Category | Gap | Tests | Count |
|----------|-----|-------|-------|
| **Security (Cat 10)** | #2 — Tenant isolation on list | `TestListWidgets::test_list_widgets_tenant_isolation` — verifies `tenant_id` kwarg matches auth user | 1 |
| | #3 — Non-UUID injection on widget CRUD | `TestGetWidget::test_get_widget_invalid_uuid`, `TestUpdateWidget::test_update_widget_invalid_uuid`, `TestDeleteWidget::test_delete_widget_invalid_uuid` — "abc" → 422 | 3 |
| | #3 — Non-UUID injection on lead_id | `TestReEnrichLead::test_re_enrich_invalid_lead_id`, `TestLeadDetail::test_lead_detail_invalid_lead_id` — "abc" → 422 | 2 |
| **Integration (Cat 11)** | #1 — Create → submit → dashboard listing | `TestE2EWidget::test_create_submit_dashboard_listing` — create widget, submit lead, fetch dashboard leads list | 1 |
| | #2 — Create → update → config reflects | `TestE2EWidget::test_create_update_config_reflects` — create widget, update config, verify public config endpoint reflects changes | 1 |
| | #3 — Submit → enrich → dashboard stats | `TestE2EWidget::test_submit_enrich_dashboard_stats` — submit lead, run enrichment, verify widget stats shows enriched data | 1 |
| | #4 — Cross-widget leads view | `TestE2EWidget::test_cross_widget_leads_view` — create 2 widgets under same tenant, submit leads to each, verify aggregated `GET /leads` | 1 |
| **Total** | | | **10** |

### Notes on gap coverage

- Security gap #1 (401 on PUT/DELETE/GET widget) was already filled by M14 — not re-implemented.
- Security gap #3's submit-endpoint portion (`test_invalid_widget_id_format`, `test_path_traversal_widget_id`) was already filled by M12 — only dashboard routes were genuinely missing at M15 time.

## Commit

```
374c649 M15: Security and Integration gap-fill tests (10 tests)

 tests/leads/test_router.py   |  12 ++++
 tests/test_e2e_widget.py     | 139 ++++++++++++++++++++++++++++++++++-
 tests/widgets/test_router.py |  23 ++++++
 3 files changed, 173 insertions(+), 1 deletion(-)
```

## Test results

```
================== 2 failed, 872 passed, 1 xfailed in 46.61s ==================
```

- **2 failures:** pre-existing Postgres `test_tables_exist`/`test_indexes_exist` (no Postgres running on Windows; same as all prior milestones)
- **1 xfailed:** `test_config_cache_control_header` (Tier C, awaiting Ahmed's sign-off)

## Coverage

```
TOTAL  2603      6    99%
```

Same 6 missing lines as M14 baseline — unchanged. All M15-affected modules at 100%.
