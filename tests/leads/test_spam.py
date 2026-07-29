from app.services.spam_service import score_submission


class TestSpamScoring:
    def test_clean_submission(self):
        score, reasons = score_submission(
            {
                "name": "John Doe",
                "email": "john@example.com",
                "message": "Hello, I am interested in your services.",
            }
        )
        assert score == 0.0
        assert reasons == []

    def test_empty_form_data(self):
        score, reasons = score_submission({})
        assert score == 0.0
        assert reasons == []

    def test_url_in_message(self):
        score, reasons = score_submission(
            {
                "name": "John",
                "email": "john@example.com",
                "message": "Check out https://spam.com/buy-now",
            }
        )
        assert "url_in_field" in reasons
        assert score >= 0.2

    def test_all_fields_identical(self):
        score, reasons = score_submission(
            {
                "name": "same",
                "email": "same",
                "message": "same",
            }
        )
        assert "all_fields_identical" in reasons
        assert score >= 0.3

    def test_non_ascii_avalanche(self):
        score, reasons = score_submission(
            {
                "name": "Привет" * 10,
                "email": "test@test.com",
            }
        )
        assert "non_ascii_avalanche" in reasons
        assert score >= 0.2

    def test_phone_pattern_mismatch(self):
        score, reasons = score_submission(
            {
                "name": "John",
                "email": "john@example.com",
                "phone": "abc",
            }
        )
        assert "phone_pattern_mismatch" in reasons
        assert score >= 0.1

    def test_email_blacklist(self):
        score, reasons = score_submission(
            {
                "name": "John",
                "email": "john@mailinator.com",
            }
        )
        assert "disposable_email_domain" in reasons
        assert score >= 0.4

    def test_threshold_logic_above(self):
        score, reasons = score_submission(
            {
                "name": "John",
                "email": "john@mailinator.com",
                "phone": "abc",
            }
        )
        assert score >= 0.5
        assert len(reasons) >= 2

    def test_threshold_logic_below(self):
        score, reasons = score_submission(
            {
                "name": "John",
                "email": "john@example.com",
                "message": "Hello",
            }
        )
        assert score < 0.5

    def test_score_capped_at_one(self):
        score, reasons = score_submission(
            {
                "name": "same",
                "email": "same@mailinator.com",
                "message": "https://spam.com https://more.com",
                "phone": "abc",
            }
        )
        assert score <= 1.0


class TestSpamEdgeCases:
    def test_non_string_values_in_form_data(self):
        score, reasons = score_submission({"name": "John", "count": 42})
        assert score == 0.0

    def test_zero_score_when_all_checks_empty(self):
        score, reasons = score_submission({"name": "John", "email": "john@example.com"})
        assert score == 0.0
        assert reasons == []
