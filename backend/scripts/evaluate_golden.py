"""Build and evaluate the 100-item hand-labelled golden dataset for Conflux HQ."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

GOLDEN_FILE = ROOT / "data" / "synthetic" / "golden_eval_100.json"

GOLDEN_ITEMS = [
    # --- FAILED_TRANSFER (20 items across 5 languages) ---
    {"id": "G001", "channel": "in_app", "language": "english", "issue_type": "failed_transfer", "is_fraud": False, "text": "My transfer of 50,000 naira failed on the mobile app, account debited and beneficiary not credited."},
    {"id": "G002", "channel": "x", "language": "english", "issue_type": "failed_transfer", "is_fraud": False, "text": "Sent 15k via USSD 2 hours ago, debit alert came immediately but no credit at the receiving bank."},
    {"id": "G003", "channel": "email", "language": "english", "issue_type": "failed_transfer", "is_fraud": False, "text": "NIP transfer of N120,000 is still pending and unreversed after a switch timeout this morning."},
    {"id": "G004", "channel": "call", "language": "english", "issue_type": "failed_transfer", "is_fraud": False, "text": "I did a transfer and experienced a debit without credit; the reversal has still not happened."},
    {"id": "G005", "channel": "instagram", "language": "english", "issue_type": "failed_transfer", "is_fraud": False, "text": "My transfer failed at 10am and my 35,000 naira has not been reversed back to my account."},
    {"id": "G006", "channel": "x", "language": "pidgin", "issue_type": "failed_transfer", "is_fraud": False, "text": "Abeg my money don enter nowhere, I send 20k since morning and receiver never see alert."},
    {"id": "G007", "channel": "in_app", "language": "pidgin", "issue_type": "failed_transfer", "is_fraud": False, "text": "Wetin dey happen? Transfer failed on top una app and una still chop my money without reversal."},
    {"id": "G008", "channel": "facebook", "language": "pidgin", "issue_type": "failed_transfer", "is_fraud": False, "text": "Abeg una debit me 45k for transfer wey never reach my mama account since yesterday."},
    {"id": "G009", "channel": "call", "language": "pidgin", "issue_type": "failed_transfer", "is_fraud": False, "text": "My money don enter nowhere o, USSD transfer failed and dem never reverse my 10k."},
    {"id": "G010", "channel": "x", "language": "pidgin", "issue_type": "failed_transfer", "is_fraud": False, "text": "Why una dey hold my pending transfer? Money no credit receiver and e no reverse."},
    {"id": "G011", "channel": "x", "language": "yoruba_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "E jowo my transfer failed since morning, owo mi ti debited sugbon beneficiary not credited."},
    {"id": "G012", "channel": "in_app", "language": "yoruba_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Mo ti send money on the app, owo mi ko de and the failed transfer is still unreversed."},
    {"id": "G013", "channel": "call", "language": "yoruba_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "E jowo help me check my account, transfer failed and owo mi ti debited without credit."},
    {"id": "G014", "channel": "email", "language": "yoruba_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Seun, my bank transfer of 30k ti debited since 9am and ko si credit or reversal yet."},
    {"id": "G015", "channel": "x", "language": "hausa_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Don Allah check my payment, transfer failed on USSD and kudi na is still unreversed."},
    {"id": "G016", "channel": "in_app", "language": "hausa_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "An debita my money for a transfer that is not credited since morning, don Allah reverse it."},
    {"id": "G017", "channel": "call", "language": "hausa_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Don Allah my bank transfer failed and kudi na was debited with no credit to receiver."},
    {"id": "G018", "channel": "x", "language": "igbo_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Biko my transfer failed on the app, ego m was debited and still not credited to the vendor."},
    {"id": "G019", "channel": "in_app", "language": "igbo_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Biko check this payment, debit without credit happened on my transfer and ego m is unreversed."},
    {"id": "G020", "channel": "call", "language": "igbo_mix", "issue_type": "failed_transfer", "is_fraud": False, "text": "Ego m for transfer failed since morning, biko process my reversal urgently."},

    # --- DOUBLE_DEBIT (12 items) ---
    {"id": "G021", "channel": "in_app", "language": "english", "issue_type": "double_debit", "is_fraud": False, "text": "I was debited twice for a single 15,000 naira transfer this afternoon."},
    {"id": "G022", "channel": "email", "language": "english", "issue_type": "double_debit", "is_fraud": False, "text": "Duplicate debit on my account: one transaction produced two separate debit alerts of 22,000."},
    {"id": "G023", "channel": "x", "language": "english", "issue_type": "double_debit", "is_fraud": False, "text": "Your system charged twice for my utility bill payment; please refund the double debit."},
    {"id": "G024", "channel": "call", "language": "pidgin", "issue_type": "double_debit", "is_fraud": False, "text": "Abeg una debit me two times for one transaction, why una dey do double debit?"},
    {"id": "G025", "channel": "x", "language": "pidgin", "issue_type": "double_debit", "is_fraud": False, "text": "Wetin be this? I pay once, una debited twice comot 10k two times for my account."},
    {"id": "G026", "channel": "instagram", "language": "pidgin", "issue_type": "double_debit", "is_fraud": False, "text": "Abeg return my duplicate debit o, dem charged twice for one transfer."},
    {"id": "G027", "channel": "in_app", "language": "yoruba_mix", "issue_type": "double_debit", "is_fraud": False, "text": "E jowo my account was debited twice for one payment, please reverse the double debit."},
    {"id": "G028", "channel": "x", "language": "yoruba_mix", "issue_type": "double_debit", "is_fraud": False, "text": "Mo ti notice duplicate debit on my bank account, owo mi was charged twice today."},
    {"id": "G029", "channel": "call", "language": "hausa_mix", "issue_type": "double_debit", "is_fraud": False, "text": "Don Allah I was debited twice on my bank account, please refund the duplicate debit."},
    {"id": "G030", "channel": "in_app", "language": "hausa_mix", "issue_type": "double_debit", "is_fraud": False, "text": "An debita kudi na two times resulting in a double debit on my payment."},
    {"id": "G031", "channel": "x", "language": "igbo_mix", "issue_type": "double_debit", "is_fraud": False, "text": "Biko my bank account suffered a double debit, ego m was debited twice abụọ ugboro."},
    {"id": "G032", "channel": "email", "language": "igbo_mix", "issue_type": "double_debit", "is_fraud": False, "text": "Biko refund my ego m, I was charged twice nso ugboro abụọ for one transaction."},

    # --- CARD_ATM (12 items) ---
    {"id": "G033", "channel": "branch", "language": "english", "issue_type": "card_atm", "is_fraud": False, "text": "The ATM at Ikeja branch debited me 20,000 naira but cash no dispensed from the machine."},
    {"id": "G034", "channel": "call", "language": "english", "issue_type": "card_atm", "is_fraud": False, "text": "My debit card was swallowed by the ATM gallery machine during a withdrawal."},
    {"id": "G035", "channel": "in_app", "language": "english", "issue_type": "card_atm", "is_fraud": False, "text": "ATM withdrawal failed and cash no dispensed, yet my account balance was reduced by 40k."},
    {"id": "G036", "channel": "x", "language": "pidgin", "issue_type": "card_atm", "is_fraud": False, "text": "Abeg una ATM for Yaba debit me 20k and cash no come out at all!"},
    {"id": "G037", "channel": "call", "language": "pidgin", "issue_type": "card_atm", "is_fraud": False, "text": "ATM machine don card swallowed my debit card and still dey show debit alert."},
    {"id": "G038", "channel": "facebook", "language": "pidgin", "issue_type": "card_atm", "is_fraud": False, "text": "Wetin happen to una ATM? Cash no come out and dem still deduct my 15k."},
    {"id": "G039", "channel": "x", "language": "yoruba_mix", "issue_type": "card_atm", "is_fraud": False, "text": "E jowo the ATM at Dugbe branch debited owo mi and cash no dispensed."},
    {"id": "G040", "channel": "branch", "language": "yoruba_mix", "issue_type": "card_atm", "is_fraud": False, "text": "Mo ti use the ATM this morning, my card swallowed and owo mi was deducted."},
    {"id": "G041", "channel": "call", "language": "hausa_mix", "issue_type": "card_atm", "is_fraud": False, "text": "Don Allah the ATM in Kano debited kudi na and cash no dispensed from the machine."},
    {"id": "G042", "channel": "in_app", "language": "hausa_mix", "issue_type": "card_atm", "is_fraud": False, "text": "Don Allah my bank card swallowed inside the ATM gallery today."},
    {"id": "G043", "channel": "x", "language": "igbo_mix", "issue_type": "card_atm", "is_fraud": False, "text": "Biko the ATM machine debited ego m and ego ọpụpụ cash no come out."},
    {"id": "G044", "channel": "branch", "language": "igbo_mix", "issue_type": "card_atm", "is_fraud": False, "text": "Biko help me, ATM card swallowed my debit card at Enugu branch."},

    # --- POS (11 items) ---
    {"id": "G045", "channel": "in_app", "language": "english", "issue_type": "pos", "is_fraud": False, "text": "My POS terminal transaction at the supermarket declined, but the merchant did not get value."},
    {"id": "G046", "channel": "email", "language": "english", "issue_type": "pos", "is_fraud": False, "text": "POS payment of 18,500 failed on the merchant terminal while my account was debited."},
    {"id": "G047", "channel": "x", "language": "english", "issue_type": "pos", "is_fraud": False, "text": "Paid at a filling station POS terminal; receipt printed declined but I got a debit alert."},
    {"id": "G048", "channel": "call", "language": "pidgin", "issue_type": "pos", "is_fraud": False, "text": "Abeg POS terminal for market print declined receipt, merchant no see money but una debit me."},
    {"id": "G049", "channel": "x", "language": "pidgin", "issue_type": "pos", "is_fraud": False, "text": "Why una POS transaction dey fail for merchant shop and still dey comot money?"},
    {"id": "G050", "channel": "in_app", "language": "yoruba_mix", "issue_type": "pos", "is_fraud": False, "text": "E jowo my POS payment at the merchant terminal declined and owo mi was deducted."},
    {"id": "G051", "channel": "x", "language": "yoruba_mix", "issue_type": "pos", "is_fraud": False, "text": "Mo ti pay on POS terminal, merchant ko si get alert sugbon my bank debited me."},
    {"id": "G052", "channel": "call", "language": "hausa_mix", "issue_type": "pos", "is_fraud": False, "text": "Don Allah muna samun al'amari with my POS terminal payment at the merchant store."},
    {"id": "G053", "channel": "in_app", "language": "hausa_mix", "issue_type": "pos", "is_fraud": False, "text": "Don Allah POS payment declined on the merchant terminal and kudi na was deducted."},
    {"id": "G054", "channel": "x", "language": "igbo_mix", "issue_type": "pos", "is_fraud": False, "text": "Biko my POS terminal payment at the merchant shop declined and ego m was debited."},
    {"id": "G055", "channel": "call", "language": "igbo_mix", "issue_type": "pos", "is_fraud": False, "text": "Biko check my POS payment, merchant terminal declined the transaction today."},

    # --- FEES (10 items) ---
    {"id": "G056", "channel": "email", "language": "english", "issue_type": "fees", "is_fraud": False, "text": "Please explain the unexpected maintenance fee and stamp duty deducted from my account."},
    {"id": "G057", "channel": "in_app", "language": "english", "issue_type": "fees", "is_fraud": False, "text": "Why was a 1,200 naira SMS alert charge and service fee deducted from my savings?"},
    {"id": "G058", "channel": "x", "language": "pidgin", "issue_type": "fees", "is_fraud": False, "text": "Abeg why una dey charge me stamp duty and maintenance fee every week?"},
    {"id": "G059", "channel": "facebook", "language": "pidgin", "issue_type": "fees", "is_fraud": False, "text": "Wetin be this plenty service fee charge wey una deducted for my account?"},
    {"id": "G060", "channel": "in_app", "language": "yoruba_mix", "issue_type": "fees", "is_fraud": False, "text": "E jowo why was this stamp duty fee and charge deducted from owo mi?"},
    {"id": "G061", "channel": "email", "language": "yoruba_mix", "issue_type": "fees", "is_fraud": False, "text": "Mo ti see an unexplained maintenance fee charge deducted on my bank statement."},
    {"id": "G062", "channel": "call", "language": "hausa_mix", "issue_type": "fees", "is_fraud": False, "text": "Don Allah why was a stamp duty fee and charge deducted from my bank balance?"},
    {"id": "G063", "channel": "in_app", "language": "hausa_mix", "issue_type": "fees", "is_fraud": False, "text": "Ina son explanation for the service fee charge deducted on my account."},
    {"id": "G064", "channel": "x", "language": "igbo_mix", "issue_type": "fees", "is_fraud": False, "text": "Biko why was this stamp duty fee and charge deducted from ego m?"},
    {"id": "G065", "channel": "email", "language": "igbo_mix", "issue_type": "fees", "is_fraud": False, "text": "Biko explain the maintenance fee deducted from my bank account this month."},

    # --- LOAN (10 items) ---
    {"id": "G066", "channel": "in_app", "language": "english", "issue_type": "loan", "is_fraud": False, "text": "My salary loan repayment was deducted early and my overdraft balance is still showing."},
    {"id": "G067", "channel": "email", "language": "english", "issue_type": "loan", "is_fraud": False, "text": "I completed my loan repayment yesterday, please update my loan clearance status."},
    {"id": "G068", "channel": "call", "language": "pidgin", "issue_type": "loan", "is_fraud": False, "text": "Abeg I don finish my loan repayment, why una overdraft still dey hold my account?"},
    {"id": "G069", "channel": "in_app", "language": "pidgin", "issue_type": "loan", "is_fraud": False, "text": "Wetin happen to the quick loan wey I apply for? Repayment schedule never show."},
    {"id": "G070", "channel": "in_app", "language": "yoruba_mix", "issue_type": "loan", "is_fraud": False, "text": "E jowo my loan repayment has been paid, please clear my bank overdraft."},
    {"id": "G071", "channel": "email", "language": "yoruba_mix", "issue_type": "loan", "is_fraud": False, "text": "Mo ti complete my loan repayment, e jowo update my loan balance."},
    {"id": "G072", "channel": "call", "language": "hausa_mix", "issue_type": "loan", "is_fraud": False, "text": "Don Allah check my loan repayment and jinginar bashin overdraft status on my account."},
    {"id": "G073", "channel": "in_app", "language": "hausa_mix", "issue_type": "loan", "is_fraud": False, "text": "Ina son update on my bank loan repayment that was deducted yesterday."},
    {"id": "G074", "channel": "in_app", "language": "igbo_mix", "issue_type": "loan", "is_fraud": False, "text": "Biko my loan repayment is complete, update my inye mgbapụta loan record."},
    {"id": "G075", "channel": "email", "language": "igbo_mix", "issue_type": "loan", "is_fraud": False, "text": "Biko check the overdraft and loan repayment on my bank account."},

    # --- APP_LOGIN (10 items) ---
    {"id": "G076", "channel": "x", "language": "english", "issue_type": "app_login", "is_fraud": False, "text": "I cannot log in to the mobile app; the login screen keeps crashing on launch."},
    {"id": "G077", "channel": "in_app", "language": "english", "issue_type": "app_login", "is_fraud": False, "text": "Hardware token and password login on the banking app fails with an app crash error."},
    {"id": "G078", "channel": "x", "language": "pidgin", "issue_type": "app_login", "is_fraud": False, "text": "Abeg una app no dey open since morning, anytime I try login e go do app crash."},
    {"id": "G079", "channel": "instagram", "language": "pidgin", "issue_type": "app_login", "is_fraud": False, "text": "Why I no fit log in for una mobile app? Token and login page no dey work."},
    {"id": "G080", "channel": "x", "language": "yoruba_mix", "issue_type": "app_login", "is_fraud": False, "text": "E jowo I cannot log in, my mobile app crash every time mo ti try login."},
    {"id": "G081", "channel": "in_app", "language": "yoruba_mix", "issue_type": "app_login", "is_fraud": False, "text": "Seun, the banking app no dey open and login token keeps failing today."},
    {"id": "G082", "channel": "x", "language": "hausa_mix", "issue_type": "app_login", "is_fraud": False, "text": "Don Allah ba zan iya shiga the mobile app, login keeps crashing on my phone."},
    {"id": "G083", "channel": "call", "language": "hausa_mix", "issue_type": "app_login", "is_fraud": False, "text": "Ba zan iya log in to my bank app because of a constant app crash."},
    {"id": "G084", "channel": "x", "language": "igbo_mix", "issue_type": "app_login", "is_fraud": False, "text": "Biko my mobile app crash whenever I try login with my token."},
    {"id": "G085", "channel": "in_app", "language": "igbo_mix", "issue_type": "app_login", "is_fraud": False, "text": "Biko help, I cannot log in to my bank app since morning."},

    # --- FRAUD_SCAM (10 items) ---
    {"id": "G086", "channel": "call", "language": "english", "issue_type": "fraud_scam", "is_fraud": True, "text": "Urgent fraud alert: someone called pretending to be a fake agent and asked for my OTP."},
    {"id": "G087", "channel": "x", "language": "english", "issue_type": "fraud_scam", "is_fraud": True, "text": "My account was hacked after a phishing scam link led to an unauthorized debit of 85,000."},
    {"id": "G088", "channel": "call", "language": "pidgin", "issue_type": "fraud_scam", "is_fraud": True, "text": "Abeg someone called say na bank staff asked for my OTP, na scam dem take comot my money!"},
    {"id": "G089", "channel": "x", "language": "pidgin", "issue_type": "fraud_scam", "is_fraud": True, "text": "Fake agent wan do fraud for my account, dem dey ask for my OTP on phone."},
    {"id": "G090", "channel": "call", "language": "yoruba_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "E gba mi, a fake agent called and asked for my OTP to gbajie mi in a scam."},
    {"id": "G091", "channel": "x", "language": "yoruba_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "E jowo block my bank account, mo ti suffer unauthorized fraud debit after someone called."},
    {"id": "G092", "channel": "call", "language": "hausa_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "Don Allah someone called for yaudarar fraud scam and asked for my OTP."},
    {"id": "G093", "channel": "x", "language": "hausa_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "Don Allah help, fake agent tried unauthorized scam on my bank account."},
    {"id": "G094", "channel": "call", "language": "igbo_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "Biko someone called as a fake agent for ntọghọ aka scam and asked for my OTP."},
    {"id": "G095", "channel": "x", "language": "igbo_mix", "issue_type": "fraud_scam", "is_fraud": True, "text": "Biko lock my bank account, unauthorized fraud debit happened on ego m."},

    # --- OTHER (5 items) ---
    {"id": "G096", "channel": "email", "language": "english", "issue_type": "other", "is_fraud": False, "text": "What are the opening hours for your Victoria Island branch on Saturdays?"},
    {"id": "G097", "channel": "x", "language": "pidgin", "issue_type": "other", "is_fraud": False, "text": "Abeg wetin una need make person bring come branch for marriage name change?"},
    {"id": "G098", "channel": "in_app", "language": "yoruba_mix", "issue_type": "other", "is_fraud": False, "text": "E jowo where is the nearest bank branch around Bodija market in Ibadan?"},
    {"id": "G099", "channel": "call", "language": "hausa_mix", "issue_type": "other", "is_fraud": False, "text": "Don Allah ina son to know the documents needed to update my home address at the bank."},
    {"id": "G100", "channel": "email", "language": "igbo_mix", "issue_type": "other", "is_fraud": False, "text": "Biko how can I request a reference letter from my bank branch in Enugu?"},
]


def main() -> None:
    GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_FILE.write_text(json.dumps(GOLDEN_ITEMS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from app.ai.eval import evaluate_golden_set
    report = evaluate_golden_set(mode="rules", path=GOLDEN_FILE)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

