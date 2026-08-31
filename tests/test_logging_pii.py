from config.log_config import ObfuscatePIIProcessor


def test_obfuscate_pii_processor():
    processor = ObfuscatePIIProcessor()

    event_dict = {
        "event": "test",
        "token": "secret123",
        "nested": {"password": "pwd", "Token": "should_be_masked", "safe_key": "safe_val"},
        "lista": [{"api_key": "x"}, "plain_string"],
    }

    result = processor(None, "info", event_dict)

    assert result["token"] == "***REDACTED***"
    assert result["nested"]["password"] == "***REDACTED***"
    assert result["nested"]["Token"] == "***REDACTED***"
    assert result["nested"]["safe_key"] == "safe_val"
    assert result["lista"][0]["api_key"] == "***REDACTED***"
    assert result["lista"][1] == "plain_string"
