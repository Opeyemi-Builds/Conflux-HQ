from app.core.privacy import mask_pii, pseudonymise


def test_masks_phone_account_and_email():
    out = mask_pii("Call me on 08031234567, acct 0123456789, mail ada@example.com")
    assert "[PHONE]" in out and "[ACCOUNT]" in out and "[EMAIL]" in out
    assert "08031234567" not in out and "0123456789" not in out


def test_pseudonymise_is_stable_and_hides_input():
    a = pseudonymise("08031234567")
    assert a == pseudonymise(" 08031234567 ")
    assert a.startswith("cust_") and "0803" not in a
    assert pseudonymise(None) is None
