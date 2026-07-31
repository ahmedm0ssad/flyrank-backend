# M11 — Test Coverage Gap Audit

**Deliverable for Week 9 Milestone 11. Read-only audit. Do not modify any source or test file.**

Ground truth: `docs/production-readiness-plan.md`, `docs/implementation-plan.md`, all existing `docs/reviews/*.md`.

---

## Category 1: Validation

### What already exists

**Model-level validation — leads:**
- `tests/leads/test_models.py::TestLeadSubmit::test_valid_submission`
- `tests/leads/test_models.py::TestLeadSubmit::test_empty_form_data_rejected`
- `tests/leads/test_models.py::TestLeadSubmit::test_non_dict_form_data_rejected`
- `tests/leads/test_models.py::TestLeadSubmit::test_field_length_exceeds_limit`
- `tests/leads/test_models.py::TestLeadSubmit::test_invalid_email_rejected`
- `tests/leads/test_models.py::TestLeadSubmit::test_valid_email_accepted`
- `tests/leads/test_models.py::TestLeadSubmit::test_invalid_phone_rejected`
- `tests/leads/test_models.py::TestLeadSubmit::test_valid_phone_accepted`
- `tests/leads/test_models.py::TestLeadSubmitEdgeCases::test_referer_exceeds_limit`
- `tests/leads/test_models.py::TestLeadSubmitEdgeCases::test_nested_dict_in_form_data_rejected`
- `tests/leads/test_models.py::TestLeadSubmitEdgeCases::test_injection_in_form_data_key`
- `tests/models/test_lead.py::TestSanitize` (7 tests: html escape, quotes, whitespace, ampersand, plain text, empty, single-quote)

**Model-level validation — widgets:**
- `tests/widgets/test_models.py::TestWidgetCreate::test_valid_minimal`
- `tests/widgets/test_models.py::TestWidgetCreate::test_valid_with_config`
- `tests/widgets/test_models.py::TestWidgetCreate::test_invalid_domain_no_protocol`
- `tests/widgets/test_models.py::TestWidgetCreate::test_invalid_domain_empty`
- `tests/widgets/test_models.py::TestWidgetCreate::test_invalid_brand_color`
- `tests/widgets/test_models.py::TestWidgetCreate::test_invalid_button_text_too_long`
- `tests/widgets/test_models.py::TestWidgetCreate::test_invalid_fields_empty`
- `tests/widgets/test_models.py::TestWidgetCreate::test_fields_not_a_list_rejected`
- `tests/widgets/test_models.py::TestWidgetCreate::test_fields_none_rejected`
- `tests/widgets/test_models.py::TestWidgetUpdate::test_valid_partial_update`

**Router-level validation:**
- `tests/leads/test_router.py::TestSubmitLead::test_422_validation_error`
- `tests/leads/test_router.py::TestSubmitLead::test_413_payload_too_large`
- `tests/widgets/test_router.py::TestCreateWidget::test_create_widget_422_invalid`
- `tests/widgets/test_router.py::TestUpdateWidget::test_update_widget_422`
- `tests/embed/test_router.py::TestGetWidgetConfig::test_config_404` (invalid widget id)
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_404` (invalid widget id)
- `tests/middleware/test_body_limit.py` (5 tests: under, over, exactly at, spoofed, missing Content-Length)

### Genuinely missing

1. **Malformed JSON body** — No test sends raw non-JSON (e.g., `{bad json]}`) to any endpoint; every test uses `json=` parameter which serialises valid JSON.
2. **Empty/`null` body on `POST /submit`** — Only the body-limit middleware tests this indirectly; no router-level test for completely empty request body.
3. **Invalid widget-id format (non-UUID)** — All 404 tests use a valid-UUID that doesn't exist; no test uses `"abc"` or `"../../etc/passwd"` as the id path parameter.
4. **Missing `Content-Type` header** on lead submit — No test verifies behaviour when `Content-Type` is omitted or set to `application/xml`.
5. **LeadSubmit with `{}` form_data (empty but present)** — The model rejects `form_data` that is not a dict, but no test sends `{"form_data": {}}` (valid dict with no keys).

**Gap count: 5**

---

## Category 2: CORS

### What already exists

**CORS headers via TestClient:**
- `tests/middleware/test_cors.py::TestCorsHeaders::test_wildcard_cors_on_get_config`
- `tests/middleware/test_cors.py::TestCorsHeaders::test_wildcard_cors_on_get_widget_js`
- `tests/middleware/test_cors.py::TestCorsHeaders::test_options_preflight_returns_cors`
- `tests/embed/test_router.py::TestCors::test_cors_headers_present_on_get` (config)
- `tests/embed/test_router.py::TestCors::test_cors_headers_on_widget_js`
- `tests/embed/test_router.py::TestCors::test_options_preflight`

**Origin validation (application-layer):**
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_origin_exact_match_accepted`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_subdomain_suffix_bypass_rejected`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_wildcard_matches_subdomain`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_wildcard_matches_bare_domain`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_wildcard_rejects_unrelated`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_missing_origin_rejected_on_post`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_empty_origin_rejected_on_post`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_malformed_origin_rejected`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_punycode_origin_mismatch`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_idn_origin_normalization`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit::test_origin_with_port_stripped`
- `tests/embed/test_service.py::test_origin_exact_match`
- `tests/embed/test_service.py::test_origin_wildcard_match`
- `tests/embed/test_service.py::test_origin_subdomain_suffix_bypass_rejected`
- `tests/embed/test_service.py::test_origin_missing_rejected`
- `tests/embed/test_service.py::test_origin_wildcard_no_match_rejected`
- `tests/dependencies/test_embed.py::TestValidateOrigin` (8 tests covering exact, wildcard, empty, inactive, nonexistent, referer fallback, mismatch)
- `tests/leads/test_service.py::TestSubmitLead::test_origin_mismatch`
- `tests/leads/test_router.py::TestSubmitLead::test_403_origin_mismatch`

### Genuinely missing

1. **No CORS header assertions on `POST /submit` success response** — The 403 origin-mismatch test exists, but a successful submission (201) is never checked for `Access-Control-Allow-Origin: *`.
2. **No `Access-Control-Allow-Headers` / `Access-Control-Max-Age` assertion** on preflight responses.
3. **No disallowed-methods test** — OPTIONS with a non-allowed method (e.g., `PUT`, `DELETE`) not tested on public endpoints.

**Gap count: 3**

---

## Category 3: Rate Limiting

### What already exists

- `tests/leads/test_rate_limit.py::TestRateLimits::test_all_tiers_pass` — below limit
- `tests/leads/test_rate_limit.py::TestRateLimits::test_global_ip_blocks` — at limit (100/min)
- `tests/leads/test_rate_limit.py::TestRateLimits::test_widget_ip_blocks` — at limit (30/min)
- `tests/leads/test_rate_limit.py::TestRateLimits::test_widget_global_blocks` — at limit (1000/min)
- `tests/leads/test_rate_limit.py::TestRateLimits::test_per_ip_isolation` — independent IPs
- `tests/leads/test_rate_limit.py::TestRateLimits::test_per_widget_isolation` — independent widgets
- `tests/leads/test_rate_limit.py::TestRateLimits::test_redis_down_fails_open` — Redis outage
- `tests/leads/test_rate_limit.py::TestRateLimits::test_redis_down_in_process_blocks_after_limit`
- `tests/leads/test_rate_limit.py::TestRateLimits::test_redis_down_in_process_per_ip_isolation`
- `tests/leads/test_rate_limit.py::TestRateLimits::test_redis_pipeline_widget_ip_triggers_limit`
- `tests/leads/test_rate_limit.py::TestRateLimits::test_redis_down_redis_error_falls_to_in_process`
- `tests/leads/test_router.py::TestSubmitLead::test_429_rate_limited`
- `tests/test_e2e_widget.py::TestE2EWidget::test_rate_limited_submission`
- `tests/leads/test_audit_log.py::test_rate_limited_outcome_logged`

### Genuinely missing

1. **`Retry-After` header assertion** on 429 response — no test validates the `Retry-After` header value matches the window.
2. **Window reset test** — no test verifies that the counter resets after the window elapses (time-travel mock or TTL-based).
3. **Rate limit + fingerprint dedup interaction** — no test for a submission that is both rate-limited and a duplicate.

**Gap count: 3**

---

## Category 4: Spam Protection

### What already exists

**Heuristic scoring:**
- `tests/leads/test_spam.py::TestSpamScoring::test_clean_submission` — score 0.0
- `tests/leads/test_spam.py::TestSpamScoring::test_empty_form_data`
- `tests/leads/test_spam.py::TestSpamScoring::test_url_in_message`
- `tests/leads/test_spam.py::TestSpamScoring::test_all_fields_identical`
- `tests/leads/test_spam.py::TestSpamScoring::test_non_ascii_avalanche`
- `tests/leads/test_spam.py::TestSpamScoring::test_phone_pattern_mismatch`
- `tests/leads/test_spam.py::TestSpamScoring::test_email_blacklist`
- `tests/leads/test_spam.py::TestSpamScoring::test_threshold_logic_above` (score >= 0.5)
- `tests/leads/test_spam.py::TestSpamScoring::test_threshold_logic_below` (score < 0.5)
- `tests/leads/test_spam.py::TestSpamScoring::test_score_capped_at_one`
- `tests/leads/test_spam.py::TestSpamEdgeCases::test_non_string_values_in_form_data`
- `tests/leads/test_spam.py::TestSpamEdgeCases::test_zero_score_when_all_checks_empty`
- `tests/services/test_spam_service.py` — 22 individual heuristic unit tests

**Honeypot detection:**
- `tests/leads/test_service.py::TestSubmitLead::test_honeypot_branch`
- `tests/leads/test_service.py::TestSubmitLead::test_spam_high_branch`
- `tests/leads/test_router.py::TestSubmitLead::test_honeypot_returns_fake_success`
- `tests/leads/test_router.py::TestListWidgetLeads::test_200_honeypot_excluded_by_default`
- `tests/leads/test_router.py::TestListWidgetLeads::test_200_include_honeypot_shows_all`
- `tests/leads/test_router.py::TestWidgetStats::test_200_stats_honeypot_excluded_from_counts`
- `tests/leads/test_audit_log.py::test_honeypot_outcome_logged`
- `tests/leads/test_audit_log.py::test_spam_flagged_outcome_logged`
- `tests/leads/test_repository.py::test_list_by_widget_excludes_honeypot`
- `tests/leads/test_repository.py::test_list_by_tenant_excludes_honeypot`
- `tests/leads/test_repository.py::test_get_stats_honeypot_excluded_from_counts`
- `tests/leads/test_repository.py::test_stats_avg_spam_score`
- `tests/leads/test_repository.py::test_list_by_widget_filter_spam_range`
- `tests/leads/test_service.py::TestDashboardService::test_get_widget_stats_honeypot_excluded`
- `tests/widgets/test_service.py::TestWidgetService::test_create_widget_generates_honeypot_field`
- `tests/test_e2e_widget.py::TestE2EWidget::test_honeypot_flow`

### Genuinely missing

1. **Exact threshold boundary (0.49 vs 0.5)** — The tests use `score >= 0.5` / `score < 0.5` but no test constructs input that scores exactly 0.49 or 0.5 to verify the boundary.
2. **Honeypot + scoring interaction** — No test verifies that when honeypot is triggered (`spam_score=1.0`), the heuristic scoring is skipped (is it? the service layer checks honeypot first; a test confirming the skip would close a regression risk).

**Gap count: 2**

---

## Category 5: Geo Enrichment

### What already exists

**Provider chain (unit):**
- `tests/leads/test_geo.py::TestGeoEnrich::test_provider_1_ipapi_success`
- `tests/leads/test_geo.py::TestGeoEnrich::test_fallback_to_ipinfo_when_ipapi_fails`
- `tests/leads/test_geo.py::TestGeoEnrich::test_fallback_to_ipapi_com_when_first_two_fail`
- `tests/leads/test_geo.py::TestGeoEnrich::test_all_providers_fail_returns_none`
- `tests/leads/test_geo.py::TestGeoEnrich::test_cache_hit_skips_all_providers`
- `tests/leads/test_geo.py::TestGeoEnrich::test_empty_ip_returns_none`
- `tests/leads/test_geo.py::TestGeoEnrich::test_provider_response_parsing`
- `tests/leads/test_geo.py::TestGeoEnrich::test_provider_order_is_correct`
- `tests/leads/test_geo.py::TestGeoEnrich::test_timeout_on_first_provider_falls_through`

**Individual provider calls:**
- `tests/services/test_geo_service.py::TestCallIpapi::test_returns_parsed_data_on_success`
- `tests/services/test_geo_service.py::TestCallIpapi::test_returns_none_on_error_response`
- `tests/services/test_geo_service.py::TestCallIpapi::test_returns_none_on_http_error`
- `tests/services/test_geo_service.py::TestCallIpapi::test_returns_none_on_timeout`
- `tests/services/test_geo_service.py::TestCallIpinfo::test_returns_parsed_data_on_success`
- `tests/services/test_geo_service.py::TestCallIpinfo::test_skips_when_no_token`
- `tests/services/test_geo_service.py::TestCallIpinfo::test_returns_none_on_http_error`
- `tests/services/test_geo_service.py::TestCallIpapiCom::test_returns_parsed_data_on_success`
- `tests/services/test_geo_service.py::TestCallIpapiCom::test_returns_none_on_api_error`

**Cache / timeout helpers:**
- `tests/services/test_geo_service.py::TestCallWithTimeout::test_returns_coro_result`
- `tests/services/test_geo_service.py::TestCallWithTimeout::test_returns_none_on_timeout`
- `tests/services/test_geo_service.py::TestGetCacheKey::test_returns_prefixed_key`
- `tests/services/test_geo_service.py::TestGetCachedGeo::test_returns_parsed_data_when_found`
- `tests/services/test_geo_service.py::TestGetCachedGeo::test_returns_none_when_not_found`
- `tests/services/test_geo_service.py::TestGetCachedGeo::test_returns_none_on_json_error`
- `tests/services/test_geo_service.py::TestGetCachedGeo::test_returns_none_on_stale_malformed_json`
- `tests/services/test_geo_service.py::TestSetCachedGeo::test_sets_data_with_ttl`
- `tests/services/test_geo_service.py::TestGeoEnrich::test_private_ip_returns_none`

**Worker-level:**
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_successful_enrichment`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_cache_hit_path`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_idempotent_skip_when_already_enriched`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_all_providers_fail`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_retry_cycle_requeues_on_intermediate_failure`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_alert_sent_on_final_failure`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_lead_status_updated_on_final_failure`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_lead_not_found_raises_value_error`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_update_status_returns_none_raises_value_error`
- `tests/test_lead_worker.py::TestRunEnrichmentJob::test_lead_status_updated_to_enriched_on_success`

**E2E:**
- `tests/test_e2e_widget.py::TestE2EWidget::test_enrichment_pipeline_end_to_end`

### Genuinely missing

1. **Submission still succeeds (201) when enrichment later fails** — The worker correctly sets `status=failed` when all providers fail, but no test at the service or router level proves that `POST /submit` returns HTTP 201 and persists the lead even when the enrichment worker subsequently fails. This is the key contract from plan §9 ("submission must still succeed").
2. **Nullable geo fields after enrichment failure** — No test verifies that after all providers fail and the lead transitions to `status=failed`, the geo fields (`geo_country`, `geo_city`, `geo_region`, `geo_isp`, `geo_provider`) are all null/None in the persisted record.

**Gap count: 2**

---

## Category 6: Submission Persistence

### What already exists

- `tests/leads/test_repository.py::TestLeadRepository::test_create_returns_lead` — widget_id stored
- `tests/leads/test_repository.py::TestLeadRepository::test_tenant_isolation` — tenant isolation
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget` — scoped by widget
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_tenant` — scoped by tenant
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_tenant_excludes_honeypot`
- `tests/leads/test_repository.py::TestLeadRepository::test_delete_wrong_tenant`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_sort_order` — timestamp ordering
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_filter_date_range` — date filter
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats_leads_over_time` — time-series
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats_top_countries` — geo_country from stored leads
- `tests/leads/test_repository.py::TestLeadRepository::test_update_status` — status update (geo_country set)
- `tests/leads/test_service.py::TestSubmitLead::test_happy_path` — full pipeline
- `tests/leads/test_router.py::TestSubmitLead::test_201_success` — 201 response with lead_id
- `tests/test_e2e_widget.py::TestE2EWidget::test_full_happy_path` — create → config → submit → verify persisted
- `tests/test_e2e_widget.py::TestE2EWidget::test_enrichment_pipeline_end_to_end` — geo fields populated

### Genuinely missing

1. **`created_at` / `updated_at` explicit type/value assertion** — No test asserts that timestamps are valid datetime objects (or ISO strings) after creation, or that `updated_at` changes on status update.
2. **`fingerprint` field assertion on persisted lead** — The `compute_fingerprint` function is unit-tested and called during submission, but no test verifies that the stored lead record contains the expected SHA-256 fingerprint value.
3. **Nullable geo fields on enrichment failure** — Same as Category 5 #2; listed here for persistence completeness.

**Gap count: 3**

---

## Category 7: Dashboard API

### What already exists

**Auth enforcement (401):**
- `tests/widgets/test_router.py::TestListWidgets::test_list_widgets_401_without_auth`
- `tests/widgets/test_router.py::TestCreateWidget::test_create_widget_401_without_auth`
- `tests/leads/test_router.py::TestAuthEdgeCases::test_401_without_auth`

**Tenant isolation (403/404 for wrong owner):**
- `tests/widgets/test_router.py::TestGetWidget::test_get_widget_403_wrong_tenant`
- `tests/leads/test_router.py::TestAuthEdgeCases::test_404_wrong_tenant_on_lead_detail`

**Pagination:**
- `tests/leads/test_router.py::TestListWidgetLeads::test_200_pagination_params`
- `tests/leads/test_router.py::TestCrossWidgetLeads::test_200_list_all_leads_pagination`
- `tests/widgets/test_service.py::TestWidgetService::test_list_widgets_pagination`
- `tests/widgets/test_repository.py::TestWidgetRepository::test_list_by_tenant_paginated`
- `tests/widgets/test_repository.py::TestWidgetRepository::test_list_by_tenant_second_page`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_paginated`

**Filter/sort:**
- `tests/leads/test_router.py::TestListWidgetLeads::test_200_search_filter`
- `tests/leads/test_router.py::TestListWidgetLeads::test_200_status_filter`
- `tests/widgets/test_router.py::TestListWidgets::test_list_widgets_with_search`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_search`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_filter_status`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_filter_spam_range`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_filter_date_range`
- `tests/leads/test_repository.py::TestLeadRepository::test_list_by_widget_sort_order`
- `tests/widgets/test_repository.py::TestWidgetRepository::test_list_by_tenant_search`
- `tests/widgets/test_repository.py::TestWidgetRepository::test_list_by_tenant_active_filter`

**Stats:**
- `tests/leads/test_router.py::TestWidgetStats::test_200_stats`
- `tests/leads/test_router.py::TestWidgetStats::test_200_stats_honeypot_excluded_from_counts`
- `tests/leads/test_router.py::TestWidgetStats::test_404_widget_not_found`
- `tests/leads/test_router.py::TestGlobalStats::test_200_global_stats`
- `tests/leads/test_service.py::TestDashboardService::test_get_widget_stats_honeypot_excluded`
- `tests/leads/test_service.py::TestDashboardService::test_get_tenant_stats_cross_widget`
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats`
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats_honeypot_excluded_from_counts`
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats_top_countries`
- `tests/leads/test_repository.py::TestLeadRepository::test_get_stats_leads_over_time`
- `tests/leads/test_repository.py::TestLeadRepository::test_get_tenant_stats`
- `tests/leads/test_repository.py::TestLeadRepository::test_stats_avg_spam_score`

**CRUD operations (full):**
- `tests/widgets/test_router.py` — 16 tests covering list, create, get, update, delete with 200/201/204/401/403/404/409/422
- `tests/leads/test_router.py` — ~39 tests covering list leads, detail, stats, export, batch-delete, re-enrich
- `tests/widgets/test_service.py` — 13 tests
- `tests/widgets/test_repository.py` — 18 tests
- `tests/leads/test_repository.py` — 22 tests

### Genuinely missing

1. **`GET /widgets` pagination metadata at router level** — `test_list_widgets_returns_200` does not assert `page`, `page_size`, `total`, `pages` fields in the JSON response (only the service-layer test checks this).
2. **No router-level test for `sort_order` and `date_from`/`date_to`** on lead list endpoints — tested at the repository layer but not via HTTP query params.
3. **No 401 test for `PUT /widgets/{id}`, `DELETE /widgets/{id}`, `GET /widgets/{id}`** — Only List and Create widget endpoints have explicit 401-without-auth tests at the router level.
4. **No router-level test that `GET /leads/stats` excludes honeypot** — widget-level stats has this test; the cross-widget aggregate stats endpoint does not.

**Gap count: 4**

---

## Category 8: Widget Config Endpoint

### What already exists

**Config endpoint (`GET /public/widget/{id}/config`):**
- `tests/embed/test_router.py::TestGetWidgetConfig::test_config_200` — 200 with expected shape
- `tests/embed/test_router.py::TestGetWidgetConfig::test_config_404` — 404 for nonexistent UUID
- `tests/embed/test_router.py::TestGetWidgetConfig::test_config_cached` — second request succeeds (caching confirmed)
- `tests/embed/test_router.py::TestCors::test_cors_headers_present_on_get` — CORS
- `tests/embed/test_router.py::TestCors::test_options_preflight`
- `tests/embed/test_service.py::test_config_caching` — cache miss-then-hit
- `tests/embed/test_service.py::test_config_missing` — returns None for nonexistent widget
- `tests/services/test_embed_service.py::TestGetWidgetConfig` (4 tests: with defaults, inactive returns None, not found returns None, cache hit skips raw widget, cache miss sets cache, Redis failures tolerated)

**Widget.js endpoint (`GET /public/widget/{id}/widget.js`):**
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_200` — 200, content-type, cache-control, widget_id in body
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_404` — 404 for nonexistent
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_410` — 410 for deleted widget
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_caching_headers` — public, max-age, immutable
- `tests/embed/test_router.py::TestGetWidgetJs::test_widget_js_content_type` — application/javascript
- `tests/embed/test_router.py::TestCors::test_cors_headers_on_widget_js`
- `tests/embed/test_widget_js.py::TestRenderWidgetJs` (5 tests: returns string, contains widget_id, references config at runtime, IIFE pattern, config URL in JS)
- `tests/embed/test_widget_js.py::TestGenerateScriptTag` (4 tests: basic tag, versioned URL changes with version, custom base URL, tag format)

### Genuinely missing

1. **Config payload deep schema assertion** — `test_config_200` checks that keys exist but does not validate types (e.g., that `fields` is `list[str]`, `brand_color` matches hex pattern, `honeypot_field` is a `str`).
2. **`Cache-Control` header on `/config` endpoint** — Only `widget.js` is tested for cache headers; the plan says config should be cached but no header assertion exists at the HTTP level.
3. **Missing / invalid `?v=` query param on `widget.js`** — No test for when `?v=` is omitted, is an invalid integer, or is a non-existent js_version.

**Gap count: 3**

---

## Category 9: Side Effects (Email / Webhook)

### Finding: Feature does not exist

A thorough search of the entire `app/` tree confirms:

- **No email sending code exists** — No import of `smtplib`, no calls to a transactional-email API (Mailgun, SendGrid, Postmark, Amazon SES), no `send_email` or `send_mail` function anywhere.
- **No webhook calling code exists** — No `requests.post()` or `httpx.post()` to a configurable callback URL, no webhook dispatch logic, no webhook URL storage in the widget config schema.
- **The only side-effect mechanism is `send_alert()`** in `app/services/alert.py`, which logs at CRITICAL level. The docstring explicitly states: *"Stub alert hook — swap for Slack/email/webhook in production."*

**This is not a test gap — this is a feature gap.** The plan (§6 pipeline step 13, §7 failure handling) references `send_alert()` which is a logging stub, not an email/webhook delivery system. Adding actual email or webhook side-effects would require:
- New schema fields (webhook URL on widget config)
- New code (email provider integration, webhook HTTP dispatch)
- New background jobs or inline dispatch
- Corresponding tests

Per the plan's tier framework (§1), this is **Tier C — flag only, needs Ahmed's sign-off**. It is not a bug; it is an intentional simplification for the capstone scope.

### What exists (for the `send_alert` stub that does exist)

- `tests/repositories/test_core_remaining.py::TestAlert::test_send_alert_logs_critical`
- `tests/test_lead_worker.py` — mocks `send_alert` in enrichment-failure tests
- `tests/test_worker.py` — mocks `send_alert` in job-failure tests
- `tests/test_report_worker.py` — mocks `send_alert` in report-failure tests

### Gap

None for `send_alert` — the stub is adequately tested. The email/webhook side-effect feature is absent by design.

**Gap count: 0 (feature gap, not test gap)**

---

## Category 10: Security

### What already exists

**401 unauthorized:**
- `tests/widgets/test_router.py::TestListWidgets::test_list_widgets_401_without_auth`
- `tests/widgets/test_router.py::TestCreateWidget::test_create_widget_401_without_auth`
- `tests/leads/test_router.py::TestAuthEdgeCases::test_401_without_auth`

**403 forbidden / origin rejection:**
- `tests/leads/test_router.py::TestSubmitLead::test_403_origin_mismatch`
- `tests/middleware/test_cors.py::TestOriginValidationViaSubmit` (11 tests: exact, bypass, wildcard, missing origin, empty, malformed, punycode, IDN, port-stripped)
- `tests/embed/test_service.py` (5 origin-rejection tests)
- `tests/dependencies/test_embed.py::TestValidateOrigin` (8 origin-rejection tests)

**Tenant isolation (404/wrong-owner):**
- `tests/widgets/test_router.py::TestGetWidget::test_get_widget_403_wrong_tenant`
- `tests/leads/test_router.py::TestAuthEdgeCases::test_404_wrong_tenant_on_lead_detail`
- `tests/widgets/test_repository.py::test_get_by_id_wrong_tenant`
- `tests/widgets/test_repository.py::test_update_wrong_tenant`
- `tests/widgets/test_repository.py::test_soft_delete_wrong_tenant`
- `tests/widgets/test_repository.py::test_tenant_isolation_in_list`
- `tests/widgets/test_repository.py::test_domain_uniqueness_different_tenant`
- `tests/leads/test_repository.py::test_delete_wrong_tenant`
- `tests/leads/test_repository.py::test_tenant_isolation`

**Input sanitization:**
- `tests/models/test_lead.py::TestSanitize` (7 tests: HTML tags, quotes, whitespace, ampersand, plain text, empty string, single quotes)

**Body-limit middleware:**
- `tests/middleware/test_body_limit.py` (5 tests: under, over, exactly-at, spoofed Content-Length, missing Content-Length)
- `tests/leads/test_router.py::TestSubmitLead::test_413_payload_too_large`

**404 for wrong ID:**
- `tests/widgets/test_router.py::TestGetWidget::test_get_widget_404`
- `tests/widgets/test_router.py::TestUpdateWidget::test_update_widget_404`
- `tests/widgets/test_router.py::TestDeleteWidget::test_delete_widget_404`
- `tests/leads/test_router.py::TestSubmitLead::test_404_widget_not_found`
- `tests/leads/test_router.py::TestReEnrichLead::test_404_lead_not_found`
- `tests/leads/test_router.py::TestReEnrichLead::test_404_widget_not_found`
- `tests/leads/test_router.py::TestLeadDetail::test_404_lead_not_found`
- `tests/leads/test_router.py::TestLeadDetail::test_404_widget_not_found`
- `tests/leads/test_router.py::TestWidgetStats::test_404_widget_not_found`
- `tests/leads/test_router.py::TestExportCSV::test_404_widget_not_found`
- `tests/leads/test_router.py::TestDeleteLead::test_404_delete_not_found`

### Genuinely missing

1. **401 on `PUT /widgets/{id}`, `DELETE /widgets/{id}`, `GET /widgets/{id}`** — Only List and Create endpoints have explicit 401-without-auth tests; the other CRUD endpoints lack this guard at the router test level.
2. **No router-level test that `GET /widgets` only returns the authenticated tenant's widgets** — The `test_get_widget_403_wrong_tenant` tests single-widget access, but the list endpoint has no "I only see my own widgets" test at the router layer.
3. **No non-UUID injection test on widget_id / lead_id path params** — All 404 tests use a valid-UUID that doesn't exist; no test passes `"abc"`, `"../../../etc/passwd"`, or SQL-like strings as the path parameter.

**Gap count: 3**

---

## Category 11: Integration

### What already exists

**`tests/test_e2e_widget.py` (7 tests, E2E with mocked externals):**
- `TestE2EWidget::test_full_happy_path` — create widget → GET config → POST submit → verify lead persisted
- `TestE2EWidget::test_honeypot_flow` — create → config → submit with honeypot → verify honeypot_triggered=True
- `TestE2EWidget::test_duplicate_submission_dedup` — submit same payload twice → same lead_id
- `TestE2EWidget::test_widget_config_caching` — GET config twice → same response
- `TestE2EWidget::test_widget_js_served` — GET widget.js → 200, JS content-type, contains widget_id
- `TestE2EWidget::test_rate_limited_submission` — submit when rate-limited → 429
- `TestE2EWidget::test_enrichment_pipeline_end_to_end` — submit → run enrichment worker directly → verify geo fields populated

**`tests/test_lead_worker.py` (10 tests):**
Full enrichment worker lifecycle: success, cache-hit, idempotent skip, all-providers-fail, retry cycle, alert, status updates, not-found, update-status-failure

**Other multi-step flows:**
- `tests/repositories/test_report_repo.py::TestReportRepository::test_full_lifecycle` — create → get → update lifecycle
- `tests/leads/test_audit_log.py` — submit + verify audit log for success, honeypot, dedup, rate-limit, origin-rejected, spam-flagged

### Genuinely missing

1. **Create → submit → dashboard leads listing** — No test creates a widget, submits a lead (as an unauthenticated visitor), then fetches the dashboard leads list (as authenticated owner) to verify the lead appears in the UI.
2. **Create → update → config reflects changes** — No test creates a widget, updates its config (e.g., brand_color), then fetches the public config to see the updated value.
3. **Create → submit → enrich → dashboard stats** — No test that creates a widget, submits leads, runs enrichment, then fetches widget stats and verifies enriched counts.
4. **Cross-widget leads view** — No test that creates two widgets under the same tenant, submits leads to each, then verifies `GET /leads` returns correct aggregated data.

**Gap count: 4**

---

## Feature Gap: Email / Webhook Side-Effects

**Category 9 finding escalated:** The codebase has **no email sending or webhook calling capability**. The only side-effect mechanism is `send_alert()` (`app/services/alert.py:6`), a logging stub whose docstring says *"swap for Slack/email/webhook in production"*.

This is **Tier C — flag only, needs Ahmed's sign-off**. Building actual email or webhook delivery is a design decision beyond test coverage. The plan (§6, §7) references `send_alert()` which is satisfied by the logging stub. Full email/webhook integration would be a new feature, not a bug fix.

---

## Summary Table

| Category | Gap Count | Milestone |
|----------|-----------|-----------|
| 1. Validation | 5 | **M12** |
| 2. CORS | 3 | **M12** |
| 3. Rate limiting | 3 | **M12** |
| 4. Spam protection | 2 | **M13** |
| 5. Geo enrichment | 2 | **M13** |
| 6. Submission persistence | 3 | **M14** |
| 7. Dashboard API | 4 | **M14** |
| 8. Widget config endpoint | 3 | **M14** |
| 9. Side effects (email/webhook) | 0 (feature gap — Tier C) | **M13** (flag only, no build) |
| 10. Security | 3 | **M15** |
| 11. Integration | 4 | **M15** |
| **Total** | **32** | |

### Per-milestone totals

| Milestone | Categories | Gap Count | Needed? |
|-----------|------------|-----------|---------|
| **M12** | 1 (Validation), 2 (CORS), 3 (Rate limiting) | **11** | **Yes** |
| **M13** | 4 (Spam), 5 (Geo), 9 (Side effects — flag only) | **4** | **Yes** (4 test gaps + 1 Tier C flag) |
| **M14** | 6 (Persistence), 7 (Dashboard), 8 (Widget config) | **10** | **Yes** |
| **M15** | 10 (Security), 11 (Integration) | **7** | **Yes** |

**All four milestones (M12–M15) are needed.** M12 has the most gaps (11), driven largely by validation edge cases. M13 has the fewest (4 test gaps) plus the Category 9 feature flag. M14 covers 10 gaps across persistence, dashboard, and widget config. M15 covers 7 gaps in security hardening and end-to-end integration.

---

## Milestone 12 Completion Report

**Completed:** 2026-07-30  
**Milestone:** M12 — Gap-Fill: Validation, CORS, Rate Limiting  
**Status:** ✅ COMPLETE  

### Summary of Work Performed

Following the M11 Test Coverage Gap Audit, I implemented gap-fill tests for Milestone 12 categories:

#### Category 1: Validation — 7 tests added
- `test_malformed_json_body`: Send raw non-JSON → 422
- `test_empty_body_rejected`: Empty body → 422
- `test_invalid_widget_id_format`: 'abc' as UUID → 422
- `test_path_traversal_widget_id`: '../../etc/passwd' → 404
- `test_missing_content_type`: Valid JSON, no Content-Type → 201
- `test_xml_content_type_rejected`: JSON with application/xml → 422
- `test_empty_form_data_dict_rejected`: {} → 422 (model correctly rejects)

#### Category 2: CORS — 3 tests added
- `test_cors_on_submit_success`: Verify ACAO: * on 201 response
- `test_preflight_headers_include_allow_headers_and_max_age`: Verify ACAH and AC-Max-Age
- `test_preflight_with_disallowed_method_returns_400`: OPTIONS with PUT → 400

#### Category 3: Rate Limiting — 3 tests added
- `test_429_retry_after_header`: Verify Retry-After == 60 (RATE_LIMIT_WINDOW)
- `test_window_reset_after_retry_after_expires`: Block then pass after window reset
- `test_rate_limit_takes_precedence_over_dedup`: 429 > dedup (rate limit wins)

### Test Results
- **Tests added:** 13 total (7 Validation + 3 CORS + 3 Rate Limiting)
- **All new tests pass:** ✅
- **Full test suite:** 844 passed, 2 failed (pre-existing DB schema failures requiring Postgres)
- **Coverage:** 99% total (6 missing lines — same as M10d baseline)
- **Net test count increase:** +13 (831 → 844) matching M10d baseline + M12 contributions

### Commits
1. `19663c9` - M12 Category 2: CORS gap-fill tests (tests/middleware/test_cors.py)
2. `16fcc4b` - M12 Categories 1+3: Validation and Rate-Limiting gap-fill tests (tests/leads/test_router.py)  
3. `0791bdd` - Fix CI configuration: add missing tests/scrapers/ to pytest command (.github/workflows/ci.yml)

### Lintingering Results
- isort: passes
- black: passes (2 files unchanged)
- ruff: 13 pre-existing warnings in TestOriginValidationViaSubmit (RUF012/RUF059) — none in new code

### Notes
- The M11 audit slightly over-counted Validation gap #5 (empty_form_data_dict) — the LeadSubmit model already validates non-empty form_data at app/models/lead.py:24. Test was kept with corrected 422 assertion for coverage completeness.
- All tests follow existing patterns, mock external dependencies, and remain deterministic and isolated.
- No app/source code was modified — strictly test-only gap filling as required.

**Milestone 12 is complete and ready for review.** Proceed to M13.
