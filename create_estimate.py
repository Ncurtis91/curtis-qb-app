"""
create_estimate.py — Create a QBO estimate from customer name + line items

Two line item types:

  Hourly:
    {"type": "hourly", "task": "Remove caulk from 2 windows", "hours": 4}
    → QBO item: "Hourly Services"
    → Description: "Remove caulk from 2 windows : Est - 4 hrs - Rate = $90/hr - $360"
    → Amount: hours × LABOR_RATE

  Flat:
    {"type": "flat", "description": "Carriage light installation (4 fixtures)", "amount": 400.00}
    → QBO item: found/created by description name
    → Amount: as specified

Usage:
    from create_estimate import create_estimate
    result = create_estimate(tokens, "Smith Residence", [
        {"type": "hourly", "task": "Remove caulk from 2 windows", "hours": 4},
        {"type": "flat", "description": "Carriage light installation (4 fixtures)", "amount": 400.00},
    ])
    print(result["url"])
"""

import os
from auth_qbo import get_tokens, api_get, api_post

LABOR_RATE = 90.0  # $/hr — update here when rate changes


# --- Customer helpers ---

def find_customer(tokens: dict, name: str) -> dict | None:
    safe = name.replace("'", "\\'")
    data = api_get(
        f"query?query=SELECT * FROM Customer WHERE DisplayName = '{safe}'&minorversion=65",
        tokens,
    )
    customers = data.get("QueryResponse", {}).get("Customer", [])
    return customers[0] if customers else None


def create_customer(tokens: dict, name: str) -> dict:
    data = api_post("customer", tokens, {"DisplayName": name})
    return data["Customer"]


def find_or_create_customer(tokens: dict, name: str) -> dict:
    customer = find_customer(tokens, name)
    if customer:
        print(f"  Customer found: {customer['DisplayName']} (ID: {customer['Id']})")
        return customer
    print(f"  Customer '{name}' not found — creating...")
    customer = create_customer(tokens, name)
    print(f"  Customer created: {customer['DisplayName']} (ID: {customer['Id']})")
    return customer


# --- Item (service) helpers ---

def find_item(tokens: dict, name: str) -> dict | None:
    safe = name.replace("'", "\\'")
    data = api_get(
        f"query?query=SELECT * FROM Item WHERE Name = '{safe}'&minorversion=65",
        tokens,
    )
    items = data.get("QueryResponse", {}).get("Item", [])
    return items[0] if items else None


def _income_account_ref(tokens: dict) -> dict:
    data = api_get(
        "query?query=SELECT * FROM Account WHERE AccountType = 'Income' MAXRESULTS 5&minorversion=65",
        tokens,
    )
    accounts = data.get("QueryResponse", {}).get("Account", [])
    if accounts:
        return {"value": accounts[0]["Id"], "name": accounts[0]["Name"]}
    return {"value": "1"}


def create_service_item(tokens: dict, name: str) -> dict:
    payload = {
        "Name": name,
        "Type": "Service",
        "UnitPrice": 0.0,
        "IncomeAccountRef": _income_account_ref(tokens),
    }
    data = api_post("item", tokens, payload)
    return data["Item"]


def find_or_create_item(tokens: dict, name: str) -> dict:
    item = find_item(tokens, name)
    if item:
        print(f"  Item found: {item['Name']} (ID: {item['Id']})")
        return item
    print(f"  Item '{name}' not found — creating...")
    item = create_service_item(tokens, name)
    print(f"  Item created: {item['Name']} (ID: {item['Id']})")
    return item


# --- Line item builders ---

def _build_hourly_line(tokens: dict, task: str, hours: float) -> dict:
    amount = round(hours * LABOR_RATE, 2)
    description = f"{task} : Est - {hours} hrs - Rate = ${LABOR_RATE:.0f}/hr - ${amount:.0f}"
    item = find_or_create_item(tokens, "Hourly Services")
    return {
        "Amount": amount,
        "DetailType": "SalesItemLineDetail",
        "Description": description,
        "SalesItemLineDetail": {
            "ItemRef": {"value": item["Id"], "name": item["Name"]},
            "UnitPrice": LABOR_RATE,
            "Qty": hours,
        },
    }


def _build_flat_line(tokens: dict, description: str, amount: float) -> dict:
    item = find_or_create_item(tokens, description)
    return {
        "Amount": amount,
        "DetailType": "SalesItemLineDetail",
        "Description": description,
        "SalesItemLineDetail": {
            "ItemRef": {"value": item["Id"], "name": item["Name"]},
            "UnitPrice": amount,
            "Qty": 1,
        },
    }


# --- Estimate creation ---

def create_estimate(tokens: dict, customer_name: str, line_items: list[dict]) -> dict:
    """
    Create a QBO estimate and return id, doc_number, total, url.

    line_items: list of hourly or flat dicts (see module docstring).
    """
    print(f"\nCreating estimate for: {customer_name}")
    customer = find_or_create_customer(tokens, customer_name)

    qbo_lines = []
    for item in line_items:
        if item.get("type") == "hourly":
            qbo_lines.append(_build_hourly_line(tokens, item["task"], item["hours"]))
        else:
            qbo_lines.append(_build_flat_line(tokens, item["description"], item["amount"]))

    payload = {
        "Line": qbo_lines,
        "CustomerRef": {"value": customer["Id"], "name": customer["DisplayName"]},
        "TxnStatus": "Pending",
    }

    data = api_post("estimate", tokens, payload)
    estimate = data["Estimate"]

    env = os.getenv("QBO_ENVIRONMENT", "sandbox")
    base = "https://app.sandbox.qbo.intuit.com" if env == "sandbox" else "https://app.qbo.intuit.com"
    url = f"{base}/app/estimate?txnId={estimate['Id']}"

    result = {
        "id": estimate["Id"],
        "doc_number": estimate.get("DocNumber", "N/A"),
        "total": estimate.get("TotalAmt", 0.0),
        "url": url,
    }

    print(f"\n  Estimate created!")
    print(f"  ID:     {result['id']}")
    print(f"  Doc #:  {result['doc_number']}")
    print(f"  Total:  ${result['total']:,.2f}")
    print(f"  URL:    {result['url']}")

    return result


# --- Standalone test ---

if __name__ == "__main__":
    tokens = get_tokens()

    result = create_estimate(tokens, "Jones Exterior", [
        {"type": "flat",   "description": "Exterior painting - stucco, 2 coats", "amount": 3200.00},
        {"type": "flat",   "description": "Carriage light installation (4 fixtures)", "amount": 400.00},
        {"type": "hourly", "task": "Remove caulk from 2 windows", "hours": 4},
        {"type": "hourly", "task": "Oil prime rust spots", "hours": 2},
    ])

    print(f"\nDone. Open in QBO: {result['url']}")
