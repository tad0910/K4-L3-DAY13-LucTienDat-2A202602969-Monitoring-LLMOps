from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    cccds = (
        "012345678901",
        "001099123456",
    )
    for cccd in cccds:
        out = scrub_text(f"So CCCD cua toi la {cccd}")
        assert cccd not in out
        assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    cards = (
        "1234-5678-9012-3456",
        "1234 5678 9012 3456",
        "1234567890123456",
    )
    for card in cards:
        out = scrub_text(f"Card number: {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out

