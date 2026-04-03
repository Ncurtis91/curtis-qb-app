"""
test_connection.py — Verify QuickBooks sandbox connectivity

Run this first to confirm auth works and the API is reachable.
On success: prints your sandbox company name and first 5 customers.
"""
from auth_qbo import get_tokens, api_get


def main():
    print("=== QuickBooks Sandbox Connection Test ===\n")

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
    print(f"  First {len(customers)} sandbox customers:")
    for c in customers:
        print(f"    - {c.get('DisplayName', 'unnamed')}")

    print("\n=== All checks passed. QB sandbox is connected. ===")


if __name__ == "__main__":
    main()
