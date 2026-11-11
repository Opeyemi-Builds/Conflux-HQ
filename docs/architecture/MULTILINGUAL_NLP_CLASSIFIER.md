# Multilingual Nigerian Banking NLP Classifier

## Supported Linguistic Dialects

ConfluxHQ natively classifies multi-dialect customer grievances without translation loss:

1. **Standard Nigerian English**: Formal banking complaints.
2. **Nigerian Pidgin English**: Colloquial market expressions (`"dem debit me money but alert no drop"`).
3. **Yoruba**: Regional phrases and dialectal terms (`"owo mi ti fe lo"`).
4. **Hausa**: Northern commercial expressions (`"an cire kudi amma ban samu ba"`).
5. **Igbo**: Commercial terms (`"ha wepụrụ ego m n'enweghị nnyefe"`).

## Intent Taxonomy

| Code | Taxonomy | Typical Triggers |
|---|---|---|
| `failed_transfer` | Transfer Failed / Unsettled | Debit without credit, NIBSS timeout, interbank pending |
| `double_debit` | Multiple Debits | Double debit alert, duplicated transaction reference |
| `card_atm` | ATM Trapped / Dispense Error | Card swallowed, cash retract, incomplete dispensing |
| `pos` | POS Transaction Decline | Merchant debit without receipt, terminal connection drop |
| `fraud_scam` | Account Compromise | Unauthorized withdrawal, SIM swap, fake credit alert |
| `app_login` | Digital Channel Lockout | Biometric failure, OTP delivery delay, server error |
