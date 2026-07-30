TOOL_NAME = "unit_convert"
TOOL_DESCRIPTION = "Convert between common units — length, weight, temperature"
TOOL_ARGS = {"value": "float: value to convert", "from_unit": "str: e.g. km, miles, kg, lbs, celsius, fahrenheit", "to_unit": "str: target unit"}

CONVERSIONS = {
    ("km", "miles"): lambda v: v * 0.621371,
    ("miles", "km"): lambda v: v / 0.621371,
    ("kg", "lbs"): lambda v: v * 2.20462,
    ("lbs", "kg"): lambda v: v / 2.20462,
    ("m", "ft"): lambda v: v * 3.28084,
    ("ft", "m"): lambda v: v / 3.28084,
    ("cm", "inches"): lambda v: v / 2.54,
    ("inches", "cm"): lambda v: v * 2.54,
    ("celsius", "fahrenheit"): lambda v: (v * 9/5) + 32,
    ("fahrenheit", "celsius"): lambda v: (v - 32) * 5/9,
    ("celsius", "kelvin"): lambda v: v + 273.15,
    ("kelvin", "celsius"): lambda v: v - 273.15,
}

def run(args=None):
    try:
        value = float(args.get("value", 0)) if args else 0
        from_unit = args.get("from_unit", "").lower() if args else ""
        to_unit = args.get("to_unit", "").lower() if args else ""

        key = (from_unit, to_unit)
        if key not in CONVERSIONS:
            return {"error": f"unsupported conversion: {from_unit} to {to_unit}"}

        result_val = round(CONVERSIONS[key](value), 3)
        result = f"{value} {from_unit} = {result_val} {to_unit}"
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"error": str(e)}
