# Research Findings: Migrating from OpenAI to OpenRouter

**Date:** 2026-11-11  
**Target:** HazWaste Hazardous Waste Management Platform (`D2S-MTP`)  
**Scope:** Client configuration, API endpoints, structured outputs / JSON schema parsing, reasoning parameters, environment variables, and model slugs.

---

## 1. Authentication & Client Initialization

### 1.1 OpenAI SDK Compatibility
OpenRouter provides an OpenAI-compatible API interface. Instead of introducing a new third-party dependency, the project can continue using the official `openai` Python SDK (`openai>=1.50.0`) by pointing the client instance to OpenRouter's `base_url`:

```python
import os
from openai import OpenAI

api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

client = OpenAI(
    base_url=base_url,
    api_key=api_key,
    default_headers={
        "HTTP-Referer": "https://github.com/stars/D2S-MTP",  # Optional: rankings on openrouter.ai
        "X-Title": "Hazardous Waste Management (D2S-MTP)",    # Optional: title on openrouter.ai
    }
)
```

**Primary Sources:**
- OpenRouter Quickstart & OpenAI SDK: [OpenRouter Docs: Quickstart](https://openrouter.ai/docs/quickstart)
- OpenRouter API Reference: [OpenRouter Docs: Requests](https://openrouter.ai/docs/requests)

---

## 2. Structured Outputs & Pydantic Schema Parsing

### 2.1 Current Codebase State
In `src/classify_waste.py` and `src/generate_management_plan.py`, the project currently invokes:
```python
response = active_client.responses.parse(
    model=MODEL,
    input=prompt,
    reasoning={"effort": REASONING_EFFORT},
    text_format=HazardClassification,
)
return response.output_parsed
```
This relies on the OpenAI `responses.parse()` method.

### 2.2 OpenRouter Support for Structured Outputs
OpenRouter supports structured outputs across multiple providers using standard OpenAI-compatible endpoints:

#### Option A: `client.beta.chat.completions.parse()` (Recommended)
The official OpenAI Python SDK provides `client.beta.chat.completions.parse()`, which handles Pydantic schema serialization and response parsing out-of-the-box:
```python
completion = client.beta.chat.completions.parse(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    response_format=HazardClassification,
)
return completion.choices[0].message.parsed
```
- **How it works:** The SDK automatically transforms `HazardClassification` into a JSON Schema payload:
  `{"type": "json_schema", "json_schema": {"name": "...", "strict": true, "schema": ...}}`
  and deserializes the JSON string into the Pydantic model directly.
- **Provider compatibility:** Works reliably across all OpenRouter models that support Structured Outputs (e.g. `openai/gpt-4o`, `openai/gpt-4o-mini`, `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`, `meta-llama/llama-3.3-70b-instruct`).

#### Option B: Standard `client.chat.completions.create()` with Manual `model_validate_json()`
```python
completion = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "HazardClassification",
            "strict": True,
            "schema": HazardClassification.model_json_schema()
        }
    }
)
raw_json = completion.choices[0].message.content
return HazardClassification.model_validate_json(raw_json)
```

**Primary Sources:**
- OpenRouter Structured Outputs: [OpenRouter Docs: Structured Outputs](https://openrouter.ai/docs/structured-outputs)
- OpenAI Structured Outputs Guide: [OpenAI Docs: Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)

---

## 3. Reasoning / Thinking Effort Parameters

### 3.1 Parameter Normalization
In the current code:
`reasoning={"effort": "medium"}`
OpenRouter normalizes reasoning across providers (OpenAI `o1`/`o3`, Anthropic Claude 3.7 Sonnet, DeepSeek R1) using a unified `reasoning` parameter:
```json
{
  "reasoning": {
    "effort": "medium"
  }
}
```
Supported values for `effort` include: `"max"`, `"high"`, `"medium"`, `"low"`, `"minimal"`, `"none"`.

### 3.2 Non-Reasoning Models
For standard non-reasoning models (such as `gpt-4o-mini` or `llama-3.3-70b-instruct`), passing `reasoning={"effort": ...}` may either be safely ignored by OpenRouter or trigger validation warnings depending on the route. It is best practice to make `reasoning` conditional or configurable depending on the chosen model.

**Primary Sources:**
- OpenRouter Reasoning Tokens: [OpenRouter Docs: Reasoning Tokens](https://openrouter.ai/docs/use-cases/reasoning-tokens)

---

## 4. Model Identifier / Slug Conventions

On OpenRouter, model identifiers take the format `provider/model-slug`.
Examples of high-performance models suitable for chemical classification and regulatory planning:
- `openai/gpt-4o-mini`: Very low latency, economical, native structured outputs support.
- `openai/gpt-4o`: Top-tier chemical understanding, native structured outputs.
- `anthropic/claude-3.5-sonnet`: Excellent domain reasoning, strict schema adherence.
- `deepseek/deepseek-chat` / `deepseek/deepseek-r1`: High reasoning capability at low cost.
- `google/gemini-2.0-flash-001`: High speed and context window.

Recommendation: Set default `MODEL` to a reliable OpenRouter slug (e.g. `openai/gpt-4o-mini` or `openai/gpt-4o`) and allow override via `OPENROUTER_MODEL` environment variable.

---

## 5. Summary of Code Areas Requiring Migration

1. **`src/classify_waste.py`**:
   - Environment variable lookup: `OPENROUTER_API_KEY` (with fallback to `OPENAI_API_KEY`).
   - Base URL configuration: `https://openrouter.ai/api/v1`.
   - Model name default: OpenRouter-compatible model slug.
   - API invocation: Standardize on `chat.completions.parse` or `chat.completions.create` with Pydantic schema.
2. **`src/generate_management_plan.py`**:
   - Matching client initialization, model slug, and structured output parsing.
3. **`src/app.py` & `src/services.py`**:
   - Ensure explicit `client` passing remains compatible.
4. **`tests/test_openai_migration.py` & other test suites**:
   - Update `FakeClient` mock structure to reflect the completion / parse call patterns.
   - Assert OpenRouter base URL, API key handling, and model slugs.
