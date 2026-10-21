import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.backup.schemas import BackupData, BackupDocument
from app.modules.backup.service import BackupInvariantError, validate_document, verify_integrity


def add_negative_individual_fund_position(data: dict[str, Any]) -> None:
    now = data["settings"]["updated_at"]
    account_id = data["accounts"][0]["id"]
    expense_category_id = data["categories"][1]["id"]
    first_fund = str(uuid4())
    second_fund = str(uuid4())
    event_id = str(uuid4())
    expense_operation_id = str(uuid4())
    for fund_id, name in ((first_fund, "First"), (second_fund, "Second")):
        data["funds"].append(
            {
                "id": fund_id,
                "name": name,
                "description": None,
                "allocation_percentage": "0",
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
        )
    data["fund_events"].append(
        {
            "id": event_id,
            "type": "allocation",
            "occurred_on": date.today().isoformat(),
            "description": None,
            "created_at": now,
        }
    )
    data["operations"].append(
        {
            "id": expense_operation_id,
            "type": "expense",
            "description": None,
            "reason": None,
            "category_id": expense_category_id,
            "occurred_on": date.today().isoformat(),
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
    )
    data["account_movements"].append(
        {
            "id": str(uuid4()),
            "operation_id": expense_operation_id,
            "account_id": account_id,
            "amount": "-15.0000",
        }
    )
    data["fund_movements"].extend(
        [
            {
                "id": str(uuid4()),
                "fund_id": first_fund,
                "account_id": account_id,
                "operation_id": None,
                "event_id": event_id,
                "amount": "10.0000",
            },
            {
                "id": str(uuid4()),
                "fund_id": second_fund,
                "account_id": account_id,
                "operation_id": None,
                "event_id": event_id,
                "amount": "10.0000",
            },
            {
                "id": str(uuid4()),
                "fund_id": first_fund,
                "account_id": account_id,
                "operation_id": expense_operation_id,
                "event_id": None,
                "amount": "-15.0000",
            },
        ]
    )


def exceed_active_fund_percentage(data: dict[str, Any]) -> None:
    now = data["settings"]["updated_at"]
    for name in ("First", "Second"):
        data["funds"].append(
            {
                "id": str(uuid4()),
                "name": name,
                "description": None,
                "allocation_percentage": "60",
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
        )


def archive_default_account(data: dict[str, Any]) -> None:
    data["settings"]["default_account_id"] = data["accounts"][0]["id"]
    data["accounts"][0]["archived_at"] = data["settings"]["updated_at"]


def add_valid_fund_transfer(data: dict[str, Any]) -> None:
    now = data["settings"]["updated_at"]
    account_id = data["accounts"][0]["id"]
    source_fund_id = str(uuid4())
    destination_fund_id = str(uuid4())
    allocation_event_id = str(uuid4())
    transfer_event_id = str(uuid4())
    for fund_id, name in (
        (source_fund_id, "Source"),
        (destination_fund_id, "Destination"),
    ):
        data["funds"].append(
            {
                "id": fund_id,
                "name": name,
                "description": None,
                "allocation_percentage": "0",
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
        )
    data["fund_events"].extend(
        [
            {
                "id": allocation_event_id,
                "type": "allocation",
                "occurred_on": date.today().isoformat(),
                "description": None,
                "created_at": now,
            },
            {
                "id": transfer_event_id,
                "type": "fund_transfer",
                "occurred_on": date.today().isoformat(),
                "description": None,
                "created_at": now,
            },
        ]
    )
    data["fund_movements"].extend(
        [
            {
                "id": str(uuid4()),
                "fund_id": source_fund_id,
                "account_id": account_id,
                "operation_id": None,
                "event_id": allocation_event_id,
                "amount": "30.0000",
            },
            {
                "id": str(uuid4()),
                "fund_id": source_fund_id,
                "account_id": account_id,
                "operation_id": None,
                "event_id": transfer_event_id,
                "amount": "-10.0000",
            },
            {
                "id": str(uuid4()),
                "fund_id": destination_fund_id,
                "account_id": account_id,
                "operation_id": None,
                "event_id": transfer_event_id,
                "amount": "10.0000",
            },
        ]
    )


def valid_data() -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    account = str(uuid4())
    other_account = str(uuid4())
    income_category = str(uuid4())
    expense_category = str(uuid4())
    income_operation = str(uuid4())
    transfer_operation = str(uuid4())
    rule = str(uuid4())
    return {
        "settings": {
            "base_currency": "RUB",
            "timezone": "Europe/Moscow",
            "base_currency_locked_at": now,
            "created_at": now,
            "updated_at": now,
        },
        "accounts": [
            {
                "id": account,
                "type": "debit",
                "name": "Main",
                "description": None,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": other_account,
                "type": "savings",
                "name": "Savings",
                "description": None,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
        "categories": [
            {
                "id": income_category,
                "type": "income",
                "name": "Salary",
                "description": None,
                "parent_id": None,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": expense_category,
                "type": "expense",
                "name": "Food",
                "description": None,
                "parent_id": None,
                "archived_at": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
        "operations": [
            {
                "id": income_operation,
                "type": "income",
                "description": None,
                "reason": None,
                "category_id": income_category,
                "occurred_on": date.today().isoformat(),
                "created_at": now,
                "updated_at": now,
                "version": 1,
            },
            {
                "id": transfer_operation,
                "type": "transfer",
                "description": None,
                "reason": None,
                "category_id": None,
                "occurred_on": date.today().isoformat(),
                "created_at": now,
                "updated_at": now,
                "version": 1,
            },
        ],
        "account_movements": [
            {
                "id": str(uuid4()),
                "operation_id": income_operation,
                "account_id": account,
                "amount": "100.0000",
            },
            {
                "id": str(uuid4()),
                "operation_id": transfer_operation,
                "account_id": account,
                "amount": "-20.0000",
            },
            {
                "id": str(uuid4()),
                "operation_id": transfer_operation,
                "account_id": other_account,
                "amount": "20.0000",
            },
        ],
        "funds": [],
        "fund_events": [],
        "fund_movements": [],
        "recurring_rules": [
            {
                "id": rule,
                "type": "expense",
                "frequency": "monthly",
                "start_on": "2026-08-12",
                "end_on": None,
                "amount": "5.0000",
                "description": None,
                "account_id": account,
                "destination_account_id": None,
                "category_id": expense_category,
                "active": True,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
        ],
        "expected_occurrences": [
            {
                "id": str(uuid4()),
                "rule_id": rule,
                "scheduled_on": "2026-09-12",
                "due_on": "2026-09-12",
                "status": "pending",
                "manually_modified": False,
                "type": "expense",
                "amount": "5.0000",
                "description": None,
                "account_id": account,
                "destination_account_id": None,
                "category_id": expense_category,
                "actual_operation_id": None,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
        ],
    }


def test_valid_backup_domain_shape() -> None:
    data = BackupData.model_validate(valid_data())
    assert data.recurring_rules[0].allocate_to_funds is False
    assert data.recurring_rules[0].shift_future_on_postpone is False
    assert data.recurring_rules[0].series_shift_days == 0
    assert data.expected_occurrences[0].allocate_to_funds is False
    assert data.expected_occurrences[0].series_shift_days == 0
    assert data.expected_occurrences[0].preserve_from_series_shift is False
    validate_document(data)


@pytest.mark.parametrize(
    ("status", "manually_modified", "actual_operation"),
    [
        ("pending", False, False),
        ("cancelled", True, False),
        ("confirmed", False, True),
    ],
)
def test_backup_accepts_one_off_plan_lifecycle_records(
    status: str, manually_modified: bool, actual_operation: bool
) -> None:
    data = valid_data()
    occurrence = data["expected_occurrences"][0]
    occurrence.update(
        {
            "source_kind": "one_off",
            "rule_id": None,
            "status": status,
            "manually_modified": manually_modified,
            "actual_operation_id": data["operations"][0]["id"] if actual_operation else None,
        }
    )

    validate_document(BackupData.model_validate(data))


def test_backup_rejects_recurring_state_on_one_off_plan() -> None:
    data = valid_data()
    occurrence = data["expected_occurrences"][0]
    occurrence["source_kind"] = "one_off"

    with pytest.raises(
        ValidationError, match="one-off plans cannot contain recurring series state"
    ):
        BackupData.model_validate(data)


def test_backup_category_validation_is_independent_of_parent_order() -> None:
    data = valid_data()
    parent = data["categories"][1]
    data["categories"].insert(
        0,
        {
            "id": str(uuid4()),
            "type": parent["type"],
            "name": "Child",
            "description": None,
            "parent_id": parent["id"],
            "archived_at": None,
            "created_at": parent["created_at"],
            "updated_at": parent["updated_at"],
        },
    )

    validate_document(BackupData.model_validate(data))


def test_backup_rejects_missing_category_parent() -> None:
    data = valid_data()
    data["categories"][0]["parent_id"] = str(uuid4())

    with pytest.raises(BackupInvariantError, match="Category parent is missing"):
        validate_document(BackupData.model_validate(data))


def test_backup_accepts_balanced_transfer_between_funds_on_one_account() -> None:
    data = valid_data()
    add_valid_fund_transfer(data)

    validate_document(BackupData.model_validate(data))


def test_backup_rejects_fund_transfer_between_accounts() -> None:
    data = valid_data()
    add_valid_fund_transfer(data)
    transfer_event_id = next(
        item["id"] for item in data["fund_events"] if item["type"] == "fund_transfer"
    )
    transfer_movements = [
        item for item in data["fund_movements"] if item["event_id"] == transfer_event_id
    ]
    transfer_movements[1]["account_id"] = data["accounts"][1]["id"]

    with pytest.raises(BackupInvariantError, match="Fund transfer is not balanced"):
        validate_document(BackupData.model_validate(data))


def test_backup_rejects_operation_cause_on_non_reserve_event() -> None:
    data = valid_data()
    add_valid_fund_transfer(data)
    data["fund_events"][0]["caused_by_operation_id"] = data["operations"][0]["id"]

    with pytest.raises(BackupInvariantError, match="Fund event cause is invalid"):
        validate_document(BackupData.model_validate(data))


def test_backup_accepts_allocation_caused_by_transfer() -> None:
    data = valid_data()
    event_id = str(uuid4())
    transfer = data["operations"][1]
    destination_account_id = data["accounts"][1]["id"]
    fund_id = str(uuid4())
    data["funds"].append(
        {
            "id": fund_id,
            "name": "Savings",
            "description": None,
            "allocation_percentage": "75",
            "archived_at": None,
            "created_at": transfer["created_at"],
            "updated_at": transfer["updated_at"],
            "version": 1,
        }
    )
    data["fund_events"].append(
        {
            "id": event_id,
            "type": "allocation",
            "occurred_on": transfer["occurred_on"],
            "description": transfer["description"],
            "caused_by_operation_id": transfer["id"],
            "created_at": transfer["created_at"],
        }
    )
    data["fund_movements"].append(
        {
            "id": str(uuid4()),
            "fund_id": fund_id,
            "account_id": destination_account_id,
            "operation_id": None,
            "event_id": event_id,
            "amount": "15.0000",
        }
    )

    validate_document(BackupData.model_validate(data))

    overallocated = deepcopy(data)
    overallocated["fund_movements"][0]["amount"] = "25.0000"
    with pytest.raises(BackupInvariantError, match="Transfer allocation cause is invalid"):
        validate_document(BackupData.model_validate(overallocated))


def test_backup_rejects_series_shift_outside_calendar_range() -> None:
    invalid_rule = valid_data()
    invalid_rule["recurring_rules"][0]["series_shift_days"] = 2**31 - 1
    with pytest.raises(ValidationError, match="series shift exceeds the calendar range"):
        BackupData.model_validate(invalid_rule)

    invalid_occurrence = valid_data()
    invalid_occurrence["expected_occurrences"][0]["series_shift_days"] = -(2**31)
    with pytest.raises(ValidationError, match="series shift exceeds the calendar range"):
        BackupData.model_validate(invalid_occurrence)


def test_backup_rejects_series_shift_preservation_for_non_cancelled_occurrence() -> None:
    invalid = valid_data()
    invalid["expected_occurrences"][0]["preserve_from_series_shift"] = True

    with pytest.raises(
        ValidationError,
        match="only automatically cancelled occurrences can be preserved from a series shift",
    ):
        BackupData.model_validate(invalid)

    manually_cancelled = valid_data()
    occurrence = manually_cancelled["expected_occurrences"][0]
    occurrence.update(
        {
            "status": "cancelled",
            "manually_modified": True,
            "preserve_from_series_shift": True,
        }
    )
    with pytest.raises(
        ValidationError,
        match="only automatically cancelled occurrences can be preserved from a series shift",
    ):
        BackupData.model_validate(manually_cancelled)


def test_schema_one_checksum_remains_compatible_with_omitted_optional_fields() -> None:
    raw_document: dict[str, Any] = {
        "format": "hermes-json-backup",
        "schema_version": 1,
        "app_version": "0.1.2",
        "exported_at": datetime.now(UTC).isoformat(),
        "data": valid_data(),
    }
    raw_document["integrity"] = {
        "algorithm": "sha256",
        "digest": "0" * 64,
    }

    document = BackupDocument.model_validate(raw_document)
    assert "default_account_id" not in raw_document["data"]["settings"]
    old_schema_content = document.model_dump(mode="json", exclude={"integrity"}, exclude_unset=True)
    canonical = json.dumps(
        old_schema_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    document.integrity.digest = hashlib.sha256(canonical).hexdigest()
    verify_integrity(document)


def test_legacy_import_receipt_defaults_missing_provenance_to_unknown() -> None:
    legacy = valid_data()
    legacy["import_receipts"] = [
        {
            "id": str(uuid4()),
            "source_key": "a" * 64,
            "decision_hash": "b" * 64,
            "operation_id": legacy["operations"][0]["id"],
        }
    ]

    receipt = BackupData.model_validate(legacy).import_receipts[0]

    assert receipt.source_date is None
    assert receipt.source_description is None


def test_backup_rejects_fund_allocation_on_non_transfer_schedule() -> None:
    invalid = valid_data()
    invalid["recurring_rules"][0]["allocate_to_funds"] = True
    with pytest.raises(ValidationError, match="only transfers"):
        BackupData.model_validate(invalid)

    invalid = valid_data()
    invalid["expected_occurrences"][0]["allocate_to_funds"] = True
    with pytest.raises(ValidationError, match="only transfers"):
        BackupData.model_validate(invalid)


def test_backup_rejects_invalid_target_and_duplicate_weekdays() -> None:
    invalid_target = valid_data()
    invalid_target["funds"].append(
        {
            "id": str(uuid4()),
            "name": "Goal",
            "description": None,
            "allocation_percentage": "0",
            "target_amount": "0",
            "archived_at": None,
            "created_at": invalid_target["settings"]["updated_at"],
            "updated_at": invalid_target["settings"]["updated_at"],
            "version": 1,
        }
    )
    with pytest.raises(ValidationError, match="target amount must be positive"):
        BackupData.model_validate(invalid_target)

    duplicate_weekdays = valid_data()
    duplicate_weekdays["recurring_rules"][0].update(frequency="weekly", interval=2, weekdays=[1, 1])
    with pytest.raises(ValidationError, match="unique weekdays"):
        BackupData.model_validate(duplicate_weekdays)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda data: data["account_movements"][2].update(amount="19.0000"),
            "Transfer movements are not balanced",
        ),
        (
            lambda data: data["operations"][0].update(category_id=None),
            "Income or expense operation shape is invalid",
        ),
        (
            lambda data: data["expected_occurrences"][0].update(due_on="2026-09-13"),
            "Expected occurrence state is invalid",
        ),
        (
            lambda data: data["account_movements"][0].update(amount="0"),
            "Account movements must be non-zero",
        ),
        (
            lambda data: data["categories"][0].update(parent_id=data["categories"][1]["id"]),
            "Category tree shape is invalid",
        ),
        (exceed_active_fund_percentage, "Active fund percentages exceed 100"),
        (add_negative_individual_fund_position, "individual fund position"),
        (archive_default_account, "Default account must be active"),
    ],
)
def test_rejects_signed_but_domain_invalid_backup(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    data = deepcopy(valid_data())
    mutate(data)
    with pytest.raises(BackupInvariantError, match=message):
        validate_document(BackupData.model_validate(data))
