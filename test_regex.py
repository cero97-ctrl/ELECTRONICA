import re
import json
json_str = '{"text": "Kirchhoff. $\\\\$ Descripción"}'
data = json.loads(json_str)
s = data["text"]
print(repr(s))
