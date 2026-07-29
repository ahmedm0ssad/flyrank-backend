from app.services.spam_service import (
    _check_all_fields_identical,
    _check_email_blacklist,
    _check_non_ascii_avalanche,
    _check_phone_pattern,
    _check_url_in_fields,
)


class TestCheckUrlInFields:
    def test_detects_url_in_value(self):
        reasons = _check_url_in_fields(
            {"message": "Check out https://spam.com/buy-now"}
        )
        assert reasons == ["url_in_field"]

    def test_returns_empty_when_no_url(self):
        reasons = _check_url_in_fields({"message": "Hello, I am interested."})
        assert reasons == []

    def test_detects_http_url(self):
        reasons = _check_url_in_fields({"comment": "http://evil.com/click"})
        assert reasons == ["url_in_field"]

    def test_empty_form_data(self):
        reasons = _check_url_in_fields({})
        assert reasons == []


class TestCheckAllFieldsIdentical:
    def test_detects_identical_fields(self):
        reasons = _check_all_fields_identical(
            {"name": "aaa", "email": "aaa", "phone": "aaa"}
        )
        assert reasons == ["all_fields_identical"]

    def test_returns_empty_when_different(self):
        reasons = _check_all_fields_identical(
            {"name": "John", "email": "john@test.com"}
        )
        assert reasons == []

    def test_ignores_empty_values(self):
        reasons = _check_all_fields_identical({"name": "", "email": ""})
        assert reasons == []

    def test_single_field_not_flagged(self):
        reasons = _check_all_fields_identical({"name": "aaa"})
        assert reasons == []


class TestCheckNonAsciiAvalanche:
    def test_detects_high_non_ascii_ratio(self):
        reasons = _check_non_ascii_avalanche(
            {"name": "\u00e9\u00e9\u00e9\u00e9\u00e9a"}
        )
        assert reasons == ["non_ascii_avalanche"]

    def test_returns_empty_when_low_ratio(self):
        reasons = _check_non_ascii_avalanche({"name": "\u00e9abc"})
        assert reasons == []

    def test_returns_empty_for_ascii_only(self):
        reasons = _check_non_ascii_avalanche({"name": "Hello World"})
        assert reasons == []

    def test_empty_form_data(self):
        reasons = _check_non_ascii_avalanche({})
        assert reasons == []


class TestCheckPhonePattern:
    def test_valid_phone_passes(self):
        reasons = _check_phone_pattern({"phone": "+1234567890"})
        assert reasons == []

    def test_invalid_phone_flagged(self):
        reasons = _check_phone_pattern({"phone": "abc123"})
        assert reasons == ["phone_pattern_mismatch"]

    def test_missing_phone_passes(self):
        reasons = _check_phone_pattern({"name": "John"})
        assert reasons == []

    def test_empty_phone_passes(self):
        reasons = _check_phone_pattern({"phone": ""})
        assert reasons == []


class TestCheckEmailBlacklist:
    def test_disposable_domain_flagged(self):
        reasons = _check_email_blacklist({"email": "test@mailinator.com"})
        assert reasons == ["disposable_email_domain"]

    def test_legitimate_email_passes(self):
        reasons = _check_email_blacklist({"email": "john@gmail.com"})
        assert reasons == []

    def test_missing_email_passes(self):
        reasons = _check_email_blacklist({"name": "John"})
        assert reasons == []

    def test_empty_email_passes(self):
        reasons = _check_email_blacklist({"email": ""})
        assert reasons == []

    def test_case_insensitive_domain_check(self):
        reasons = _check_email_blacklist({"email": "test@MAILINATOR.COM"})
        assert reasons == ["disposable_email_domain"]

    def test_guerrillamail_flagged(self):
        reasons = _check_email_blacklist({"email": "test@guerrillamail.com"})
        assert reasons == ["disposable_email_domain"]
