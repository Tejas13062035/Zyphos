import requests

TOOL_NAME = "currency"
TOOL_DESCRIPTION = "Convert an amount between currencies"
TOOL_ARGS = {"amount": "float: amount to convert", "from_currency": "str: e.g. USD", "to_currency": "str: e.g. INR"}

def run(args=None):
    amount = float(args.get("amount", 1)) if args else 1
    from_cur = args.get("from_currency", "USD").upper() if args else "USD"
    to_cur = args.get("to_currency", "INR").upper() if args else "INR"

    try:
        r = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_cur}", timeout=10)
        data = r.json()
        rates = data.get("rates", {})
        if to_cur not in rates:
            return {"error": f"unknown currency: {to_cur}"}
        rate = rates[to_cur]
        converted = round(amount * rate, 2)
        result = f"{amount} {from_cur} = {converted} {to_cur}"
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"error": str(e)}
