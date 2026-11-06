"""Seed one reproducible synthetic spike demo without an external service."""
import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import Complaint, SystemEvent, Transaction
from app.models.enums import Channel, EventType, IssueType, TxnChannel, TxnStatus, TxnType


def seed(bank_id: uuid.UUID, hours: int = 48, seed: int = 7) -> int:
    random.seed(seed)
    db = SessionLocal()
    end = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=hours)
    release = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)

    try:
        # Demo replay is idempotent and never mixes old synthetic runs into a new seed.
        db.query(Complaint).filter(Complaint.bank_id == bank_id).delete()
        db.query(Transaction).filter(Transaction.bank_id == bank_id).delete()
        db.query(SystemEvent).filter(SystemEvent.bank_id == bank_id).delete()
        db.commit()

        complaints = []
        channels = [Channel.X, Channel.INSTAGRAM, Channel.FACEBOOK, Channel.EMAIL, Channel.CALL, Channel.IN_APP]
        normal_text = ["failed transfer debited but not received", "my money never enter", "abeg check my transfer"]
        for i in range(max(300, hours * 20)):
            occurred = start + timedelta(minutes=random.randint(0, int((end - start).total_seconds() / 60)))
            if release < occurred < release + timedelta(hours=2) and random.random() < 0.55:
                text = "my money don enter nowhere; failed transfer on app and USSD"
                issue = IssueType.FAILED_TRANSFER
                channel = random.choice([Channel.IN_APP, Channel.X, Channel.CALL])
            else:
                text = random.choice(normal_text)
                issue = random.choice([IssueType.FAILED_TRANSFER, IssueType.FEES, IssueType.APP_LOGIN])
                channel = random.choice(channels)
            complaints.append(Complaint(bank_id=bank_id, channel=channel, text=text, region="Lagos",
                                        occurred_at=occurred, issue_type=issue))

        for i in range(hours * 30):
            occurred = start + timedelta(minutes=random.randint(0, int((end - start).total_seconds() / 60)))
            failed = release <= occurred <= release + timedelta(hours=2) and random.random() < 0.5
            db.add(Transaction(bank_id=bank_id, reference=f"demo-txn-{i}", txn_type=TxnType.TRANSFER,
                               txn_channel=random.choice([TxnChannel.APP, TxnChannel.USSD]),
                               status=TxnStatus.FAILED if failed else TxnStatus.SUCCESSFUL,
                               processor="SwitchX" if failed else random.choice(["SwitchX", "SwitchY"]),
                               amount=1000 + random.randint(0, 50) * 100, region="Lagos",
                               occurred_at=occurred))
        db.add_all(complaints)
        db.add(SystemEvent(bank_id=bank_id, event_type=EventType.RELEASE, component="app transfer path",
                           version="v4.2.1", description="App transfer release deployed",
                           starts_at=release))
        db.add(SystemEvent(bank_id=bank_id, event_type=EventType.MAINTENANCE,
                           component="card gateway", description="Unrelated maintenance",
                           starts_at=release - timedelta(hours=5)))
        db.commit()
        return len(complaints)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bank_id", help="UUID of the bank")
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()
    print(f"Seeded {seed(uuid.UUID(args.bank_id), args.hours)} synthetic complaints")
