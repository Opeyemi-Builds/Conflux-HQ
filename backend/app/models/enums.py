import enum

from sqlalchemy import Enum as SAEnum


def enum_type(e: type[enum.Enum]) -> SAEnum:
    """Portable (SQLite and Postgres) string enum stored by value."""
    return SAEnum(e, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


class Channel(str, enum.Enum):
    X = "x"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    EMAIL = "email"
    CALL = "call"
    BRANCH = "branch"
    IN_APP = "in_app"


class IssueType(str, enum.Enum):
    FAILED_TRANSFER = "failed_transfer"
    DOUBLE_DEBIT = "double_debit"
    CARD_ATM = "card_atm"
    POS = "pos"
    FEES = "fees"
    LOAN = "loan"
    APP_LOGIN = "app_login"
    FRAUD_SCAM = "fraud_scam"
    OTHER = "other"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Sentiment(str, enum.Enum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class TxnType(str, enum.Enum):
    TRANSFER = "transfer"
    POS = "pos"
    ATM = "atm"
    AIRTIME = "airtime"
    BILL = "bill"


class TxnChannel(str, enum.Enum):
    USSD = "ussd"
    APP = "app"
    POS = "pos"
    ATM = "atm"
    WEB = "web"


class TxnStatus(str, enum.Enum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"
    REVERSED = "reversed"


class ReversalStatus(str, enum.Enum):
    NONE = "none"
    PENDING = "pending"
    COMPLETED = "completed"


class EventType(str, enum.Enum):
    RELEASE = "release"
    OUTAGE = "outage"
    MAINTENANCE = "maintenance"
    CONFIG_CHANGE = "config_change"


class DraftKind(str, enum.Enum):
    CUSTOMER_MESSAGE = "customer_message"
    IT_TICKET = "it_ticket"
    REVERSAL_REQUEST = "reversal_request"


class DraftStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole(str, enum.Enum):
    BANK_ADMIN = "bank_admin"  # manages the bank account and its members
    AGENT = "agent"  # customer service
    IT = "it"  # engineering
    MANAGER = "manager"  # read-only analytics


class MemberStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class BankStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class JobKind(str, enum.Enum):
    CLASSIFY_COMPLAINT = "classify_complaint"
    DETECT_SPIKES = "detect_spikes"
    INVESTIGATE_INCIDENT = "investigate_incident"
    DISPATCH_APPROVAL = "dispatch_approval"
    SYNC_SOCIAL_RULES = "sync_social_rules"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    DEAD_LETTER = "dead_letter"
