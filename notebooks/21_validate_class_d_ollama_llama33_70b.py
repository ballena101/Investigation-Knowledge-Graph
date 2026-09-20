# Databricks notebook source
# MAGIC %md
# MAGIC # 21 — Validate controlled Ollama Llama 3.3 70B service
# MAGIC
# MAGIC Administrative pre-flight check for the Class D comparison route.
# MAGIC
# MAGIC This notebook verifies connectivity to a controlled Ollama service and
# MAGIC confirms that `llama3.3:70b` is installed.
# MAGIC
# MAGIC Passing this technical check is not, by itself, organisational approval
# MAGIC for Class D processing.

# COMMAND ----------

dbutils.widgets.text(
    "ollama_base_url",
    "",
    "Controlled Ollama base URL",
)

# COMMAND ----------

import json
import urllib.request

base_url = dbutils.widgets.get(
    "ollama_base_url"
).strip().rstrip("/")

if not base_url:
    raise ValueError(
        "Enter the controlled Ollama base URL."
    )

if not base_url.startswith(("http://", "https://")):
    raise ValueError(
        "Ollama base URL must start with http:// or https://."
    )

# COMMAND ----------

with urllib.request.urlopen(
    base_url + "/api/tags",
    timeout=30,
) as response:
    payload = json.loads(
        response.read().decode("utf-8")
    )

models = [
    item.get("name")
    for item in payload.get("models", [])
]

print("Ollama service reachable:", base_url)
print("Installed models:")
for model in models:
    print(" -", model)

required_names = {
    "llama3.3:70b",
    "llama3.3:latest",
    "llama3.3",
}

if not any(
    model in required_names
    for model in models
):
    raise RuntimeError(
        "Llama 3.3 70B was not found on the Ollama service. "
        "Install/approve llama3.3:70b before Class D testing."
    )

# COMMAND ----------

request_body = json.dumps(
    {
        "model": "llama3.3:70b",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Return exactly this JSON object and nothing else: "
                    '{"status":"ok"}'
                ),
            }
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
        },
    }
).encode("utf-8")

request = urllib.request.Request(
    base_url + "/api/chat",
    data=request_body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(
    request,
    timeout=600,
) as response:
    result = json.loads(
        response.read().decode("utf-8")
    )

content = (
    result.get("message", {})
    .get("content", "")
)

print("Test response:", content)

# COMMAND ----------

print("")
print("OLLAMA CLASS D PRE-FLIGHT CHECKLIST")
print("1. Service is on controlled/approved compute")
print("2. Network path from Databricks Job is private/approved")
print("3. llama3.3:70b model/version is pinned and recorded")
print("4. Ollama/model logs and retention are reviewed")
print("5. Host storage/swap/cache handling is reviewed")
print("6. Access is restricted to authorised IKG processing")
print("7. No public Ollama endpoint is used for Class D evidence")
print("8. Security/data-protection/legal approval is recorded")
print("")
print("After approval configure App resource:")
print("CLASS_D_OLLAMA_LLAMA70_URL=<approved controlled base URL>")
