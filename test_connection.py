"""
test_connection.py — Verify QuickBooks Online connectivity

Run this to confirm auth works and the API is reachable.
On success: prints your company name and first 5 customers.
"""
import os
from auth_qbo import get_tokens, api_get


def main():
    env = os.getenv("QBO_ENVIRONMENT", "sandbox").upper()
    print(f"=== QuickBooks Connection Test ({env}) ===\n")

    print("Step 1: Authenticating...")
    tokens = get_tokens()
    print(f"  Auth OK — Realm ID: {tokens['realm_id']}\n")

    print("Step 2: Fetching company info...")
    data = api_get("companyinfo/{}".format(tokens["realm_id"]), tokens)
    info = data.get("CompanyInfo", {})
    print(f"  Company: {info.get('CompanyName', 'N/A')}")
    print(f"  Country: {info.get('Country', 'N/A')}\n")

    print("Step 3: Fetching customers...")
    data = api_get("query?query=SELECT * FROM Customer MAXRESULTS 5&minorversion=65", tokens)
    customers = data.get("QueryResponse", {}).get("Customer", [])
    print(f"  First {len(customers)} customers:")
    for c in customers:
        print(f"    - {c.get('DisplayName', 'unnamed')}")

    print(f"\n=== All checks passed. QB {env} is connected. ===")


if __name__ == "__main__":
    main()
