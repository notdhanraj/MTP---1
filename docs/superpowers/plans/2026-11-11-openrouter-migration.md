# OpenRouter Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate LLM inference from direct OpenAI to OpenRouter using free model `nvidia/nemotron-3-ultra-550b-a55b:free`, encapsulated in a centralized `src/llm_client.py` module with resilient tool-calling structured output parsing, automatic backoff retry, and full offline test coverage.

**Architecture:** 
- Implement a centralized LLM client module [`src/llm_client.py`](file:///C:/Users/stars/AI-ML/D2S-MTP/src/llm_client.py) providing `get_openrouter_client()` and `generate_structured_output()`.
- Structured outputs are enforced via OpenAI SDK tool-calling (`openai.pydantic_function_tool()`) with forced `tool_choice`, coupled with a fallback parser for models that emit markdown/JSON into `message.content`. This guarantees compatibility with models like `nvidia/nemotron-3-ultra-550b-a55b:free` that support tool calling but reject OpenAI-specific `response_format: json_schema`.
- Refactor [`src/classify_waste.py`](file:///C:/Users/stars/AI-ML/D2S-MTP/src/classify_waste.py) and [`src/generate_management_plan.py`](file:///C:/Users/stars/AI-ML/D2S-MTP/src/generate_management_plan.py) to delegate to `src/llm_client.py`, preserving all public function signatures (`classify_chemical`, `make_plan`) and fallback dossier logic in `src/services.py`.
- Provide [`.env.example`](file:///C:/Users/stars/AI-ML/D2S-MTP/.env.example) documenting OpenRouter credentials and model configuration.
- Migrate [`tests/test_openai_migration.py`](file:///C:/Users/stars/AI-ML/D2S-MTP/tests/test_openai_migration.py) to `tests/test_llm_client.py`, updating mock fixtures to verify OpenRouter client initialization, headers, tool-calling payloads, retry loops, and schema parsing without requiring network access.

**Tech Stack:** Python 3.10+, OpenAI Python SDK (`openai>=1.50.0`), Pydantic v2, FastAPI, standard library `unittest`.

**Spec:** Locked design decisions from the 3-round grilling session and [`docs/research/openrouter-migration.md`](file:///C:/Users/stars/AI-ML/D2S-MTP/docs/research/openrouter-migration.md).

## Global Constraints

- Python Runtime: Strictly target dedicated Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe`. Zero packages in base.
- Testing Framework: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`.
- Run tests via: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest <test_path>`
- Default Model: `nvidia/nemotron-3-ultra-550b-a55b:free`, dynamically overridable via `OPENROUTER_MODEL`.
- Base URL: Default to `https://openrouter.ai/api/v1`, overridable via `OPENROUTER_BASE_URL`.
- Authentication: Check `OPENROUTER_API_KEY` first, fall back to `OPENAI_API_KEY`.
- Attribution Headers: Include `HTTP-Referer: https://github.com/stars/D2S-MTP` and `X-Title: Hazardous Waste Management`.
- Git Author: Aryan Das <starsnipe407@gmail.com>.

---

### Task 1: Centralized OpenRouter Client Module `src/llm_client.py`

**Files:**
- Create: `src/llm_client.py`
- Create: `tests/test_llm_client.py`

**Interfaces:**
- Produces:
  - `DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"`
  - `DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - `get_openrouter_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI`
  - `generate_structured_output(client, model: str, prompt: str, response_model: type[BaseModel], max_retries: int = 2, reasoning_effort: str | None = None) -> BaseModel`

- [ ] **Step 1: Write the failing tests in `tests/test_llm_client.py`**

Test client initialization, headers, model resolution, tool calling, content JSON fallback, and retry on 429/503:

```python
import os
import types
import unittest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel
from src.llm_client import (
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_OPENROUTER_BASE_URL,
    get_openrouter_client,
    generate_structured_output,
)


class DummySchema(BaseModel):
    category: str
    confidence: float


class TestLLMClient(unittest.TestCase):
    def setUp(self):
        self.orig_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_get_openrouter_client_reads_openrouter_api_key(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test-12345"
        os.environ.pop("OPENAI_API_KEY", None)
        client = get_openrouter_client()
        self.assertEqual(client.api_key, "sk-or-test-12345")
        self.assertEqual(str(client.base_url).rstrip("/"), DEFAULT_OPENROUTER_BASE_URL)
        self.assertEqual(client.default_headers.get("HTTP-Referer"), "https://github.com/stars/D2S-MTP")
        self.assertEqual(client.default_headers.get("X-Title"), "Hazardous Waste Management")

    def test_get_openrouter_client_fallback_to_openai_api_key(self):
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ["OPENAI_API_KEY"] = "sk-openai-fallback-67890"
        client = get_openrouter_client()
        self.assertEqual(client.api_key, "sk-openai-fallback-67890")

    def test_get_openrouter_client_missing_key_raises_runtime_error(self):
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        with self.assertRaises(RuntimeError) as ctx:
            get_openrouter_client()
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_generate_structured_output_via_tool_calling(self):
        mock_client = MagicMock()
        mock_tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(
                name="DummySchema",
                arguments='{"category": "Solvent", "confidence": 0.98}'
            )
        )
        mock_response = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        tool_calls=[mock_tool_call],
                        content=None
                    )
                )
            ]
        )
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_structured_output(
            client=mock_client,
            model=DEFAULT_OPENROUTER_MODEL,
            prompt="Classify this waste",
            response_model=DummySchema,
        )

        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.category, "Solvent")
        self.assertEqual(result.confidence, 0.98)

        # Assert tool call format passed to chat.completions.create
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["model"], DEFAULT_OPENROUTER_MODEL)
        self.assertIn("tools", call_kwargs)
        self.assertEqual(call_kwargs["tool_choice"]["type"], "function")

    def test_generate_structured_output_content_json_fallback(self):
        mock_client = MagicMock()
        mock_response = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        tool_calls=[],
                        content='```json\n{"category": "Acid", "confidence": 0.95}\n```'
                    )
                )
            ]
        )
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_structured_output(
            client=mock_client,
            model=DEFAULT_OPENROUTER_MODEL,
            prompt="Classify this waste",
            response_model=DummySchema,
        )

        self.assertIsInstance(result, DummySchema)
        self.assertEqual(result.category, "Acid")
        self.assertEqual(result.confidence, 0.95)

    def test_generate_structured_output_retries_on_rate_limit(self):
        mock_client = MagicMock()
        mock_tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(
                name="DummySchema",
                arguments='{"category": "Toxic", "confidence": 0.88}'
            )
        )
        success_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[mock_tool_call], content=None))]
        )

        # Simulate 1 transient failure then success
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("429 Too Many Requests / Rate limit exceeded"),
            success_response
        ]

        with patch("time.sleep", return_value=None):
            result = generate_structured_output(
                client=mock_client,
                model=DEFAULT_OPENROUTER_MODEL,
                prompt="Classify this waste",
                response_model=DummySchema,
                max_retries=2,
            )

        self.assertEqual(result.category, "Toxic")
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'src.llm_client'`

- [ ] **Step 3: Implement `src/llm_client.py`**

```python
import json
import logging
import os
import re
import time
from typing import TypeVar
from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_REFERER = "https://github.com/stars/D2S-MTP"
DEFAULT_TITLE = "Hazardous Waste Management"

T = TypeVar("T", bound=BaseModel)


def get_model_name() -> str:
    return os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL


def get_openrouter_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> OpenAI:
    resolved_key = (
        api_key
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not resolved_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Please provide a valid OpenRouter API key in your .env file."
        )

    resolved_base_url = (
        base_url
        or os.getenv("OPENROUTER_BASE_URL")
        or DEFAULT_OPENROUTER_BASE_URL
    )

    return OpenAI(
        base_url=resolved_base_url,
        api_key=resolved_key,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", DEFAULT_REFERER),
            "X-Title": os.getenv("OPENROUTER_TITLE", DEFAULT_TITLE),
        },
    )


def extract_json_from_text(text: str) -> str:
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return cleaned


def generate_structured_output(
    client: OpenAI,
    model: str,
    prompt: str,
    response_model: type[T],
    max_retries: int = 2,
    reasoning_effort: str | None = None,
) -> T:
    tool = pydantic_function_tool(response_model)
    function_name = tool["function"]["name"]

    extra_body = {}
    effort = reasoning_effort or os.getenv("OPENROUTER_REASONING_EFFORT")
    if effort:
        extra_body["reasoning"] = {"effort": effort}

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [tool],
                "tool_choice": {"type": "function", "function": {"name": function_name}},
            }
            if extra_body:
                kwargs["extra_body"] = extra_body

            response = client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            # Strategy 1: Tool call arguments
            if message.tool_calls:
                for tc in message.tool_calls:
                    if getattr(tc, "function", None) and tc.function.arguments:
                        return response_model.model_validate_json(tc.function.arguments)

            # Strategy 2: Content markdown / JSON fallback
            if message.content:
                raw_json = extract_json_from_text(message.content)
                return response_model.model_validate_json(raw_json)

            raise RuntimeError(f"OpenRouter model '{model}' returned neither tool calls nor message content.")

        except Exception as e:
            last_exception = e
            err_str = str(e).lower()
            is_transient = any(code in err_str for code in ["429", "rate limit", "503", "busy", "timeout", "temporarily unavailable"])
            if is_transient and attempt < max_retries:
                backoff_time = (2 ** attempt) * 1.0
                logger.warning(f"Transient error querying OpenRouter (attempt {attempt + 1}/{max_retries + 1}): {e}. Backing off {backoff_time}s...")
                time.sleep(backoff_time)
                continue
            raise e

    raise last_exception or RuntimeError(f"Failed to generate structured output after {max_retries + 1} attempts.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): add centralized OpenRouter client and structured output generator"
```

---

### Task 2: Refactor `src/classify_waste.py` to Use OpenRouter

**Files:**
- Modify: `src/classify_waste.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `get_openrouter_client`, `generate_structured_output`, `get_model_name` from `src/llm_client.py`.
- Produces: `classify_chemical(chemical: str, client=None) -> HazardClassification` (preserving exact return type and interface).

- [ ] **Step 1: Write integration test for `classify_chemical` in `tests/test_llm_client.py`**

Add test method to `tests/test_llm_client.py`:

```python
    def test_classify_chemical_uses_openrouter_tool_calling(self):
        from src.classify_waste import classify_chemical, HazardClassification

        mock_client = MagicMock()
        mock_tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(
                name="HazardClassification",
                arguments='{"flammable": true, "carcinogenic": false, "infectious": false, "toxic": true, "corrosive": false}'
            )
        )
        mock_client.chat.completions.create.return_value = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[mock_tool_call], content=None))]
        )

        res = classify_chemical("Acetone", client=mock_client)
        self.assertIsInstance(res, HazardClassification)
        self.assertTrue(res.flammable)
        self.assertTrue(res.toxic)
        self.assertFalse(res.corrosive)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: FAIL (`active_client.responses.parse` AttributeError on mock).

- [ ] **Step 3: Refactor `src/classify_waste.py`**

In `src/classify_waste.py`:
- Replace top-level `client = OpenAI(...)` with lazy discovery:
  ```python
  from src.llm_client import (
      get_openrouter_client,
      generate_structured_output,
      get_model_name,
      DEFAULT_OPENROUTER_MODEL,
  )

  MODEL = get_model_name()
  ```
- In `classify_chemical(chemical, client=None)`:
  ```python
  def classify_chemical(chemical, client=None):
      active_client = client if client is not None else get_openrouter_client()
      prompt = f"""...""" # existing prompt
      return generate_structured_output(
          client=active_client,
          model=get_model_name(),
          prompt=prompt,
          response_model=HazardClassification,
      )
  ```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/classify_waste.py tests/test_llm_client.py
git commit -m "refactor(classify): migrate classify_chemical to OpenRouter structured output"
```

---

### Task 3: Refactor `src/generate_management_plan.py` to Use OpenRouter

**Files:**
- Modify: `src/generate_management_plan.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `get_openrouter_client`, `generate_structured_output`, `get_model_name` from `src/llm_client.py`.
- Produces: `make_plan(chemical: str, categories: list[str], client=None) -> ManagementPlan` (preserving exact return type and interface).

- [ ] **Step 1: Write integration test for `make_plan` in `tests/test_llm_client.py`**

```python
    def test_make_plan_uses_openrouter_tool_calling(self):
        from src.generate_management_plan import make_plan, ManagementPlan

        mock_client = MagicMock()
        mock_tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(
                name="ManagementPlan",
                arguments=json.dumps({
                    "chemical": "Methanol",
                    "identification_and_characterization": "Solvent",
                    "segregation_and_incompatibilities": "Keep away from oxidizers",
                    "recommended_container": "Safety Can",
                    "labeling_requirements": "Flammable",
                    "storage_requirements": "Flammables cabinet",
                    "handling_and_ppe": "Nitrile gloves",
                    "spill_and_emergency_management": "Absorb with pads",
                    "treatment_framework": "Thermal oxidation",
                    "final_disposal_framework": "Authorized TSDF",
                    "usepa_framework": "D001",
                    "indian_framework": "HOWM Schedule II",
                    "prohibited_or_unsafe_actions": "Do not drain dispose",
                    "verification_required": "Flash point check"
                })
            )
        )
        mock_client.chat.completions.create.return_value = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(tool_calls=[mock_tool_call], content=None))]
        )

        plan = make_plan("Methanol", ["Flammable", "Toxic"], client=mock_client)
        self.assertIsInstance(plan, ManagementPlan)
        self.assertEqual(plan.chemical, "Methanol")
        self.assertEqual(plan.recommended_container, "Safety Can")
        self.assertEqual(plan.usepa_framework, "D001")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: FAIL (`responses.parse` AttributeError on mock).

- [ ] **Step 3: Refactor `src/generate_management_plan.py`**

In `src/generate_management_plan.py`:
- Use `get_openrouter_client` and `generate_structured_output`:
  ```python
  from src.llm_client import (
      get_openrouter_client,
      generate_structured_output,
      get_model_name,
      DEFAULT_OPENROUTER_MODEL,
  )

  MODEL = get_model_name()
  ```
- In `make_plan(chemical, categories, client=None)`:
  ```python
  def make_plan(chemical, categories, client=None):
      active_client = client if client is not None else get_openrouter_client()
      prompt = f"""...""" # existing prompt
      return generate_structured_output(
          client=active_client,
          model=get_model_name(),
          prompt=prompt,
          response_model=ManagementPlan,
      )
  ```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_llm_client.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/generate_management_plan.py tests/test_llm_client.py
git commit -m "refactor(plan): migrate make_plan to OpenRouter structured output"
```

---

### Task 4: Configuration Template `.env.example` & Service Updates

**Files:**
- Create: `.env.example`
- Modify: `src/services.py` (if any direct references need alignment)
- Remove/Migrate: `tests/test_openai_migration.py`

**Interfaces:**
- Produces: `.env.example` documenting OpenRouter settings.
- Removes legacy `tests/test_openai_migration.py` (fully subsumed by `tests/test_llm_client.py`).

- [ ] **Step 1: Create `.env.example`**

```env
# OpenRouter API Key (Get yours at https://openrouter.ai/keys)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Model Selection (defaults to free Nemotron if unset)
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free

# Optional OpenRouter Base URL (defaults to https://openrouter.ai/api/v1)
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Optional Reasoning Effort (e.g. medium, high)
# OPENROUTER_REASONING_EFFORT=medium
```

- [ ] **Step 2: Remove legacy `tests/test_openai_migration.py`**

Remove `tests/test_openai_migration.py` since all migration tests now reside in `tests/test_llm_client.py`.

- [ ] **Step 3: Run full repository test suite**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s tests -v`  
Expected: PASS (all tests pass across `test_app.py`, `test_models.py`, `test_services.py`, `test_llm_client.py`).

- [ ] **Step 4: Commit**

```bash
git rm tests/test_openai_migration.py
git add .env.example
git commit -m "docs(env): add .env.example and clean up legacy migration test file"
```

---

### Task 5: End-to-End Batch Ingestion & Lookup Verification

**Files:**
- Modify: `tests/test_services.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: Complete refactored stack (`src/llm_client.py`, `src/classify_waste.py`, `src/generate_management_plan.py`, `src/services.py`, `src/app.py`).
- Produces: Verified end-to-end lookup, SSE streaming, and remediation using OpenRouter client mocks.

- [ ] **Step 1: Update mock clients in `tests/test_services.py` and `tests/test_app.py`**

In `tests/test_services.py` and `tests/test_app.py`, update `FakeClient` to support `client.chat.completions.create` returning tool calls and message content matching `generate_structured_output`, ensuring all mock tests remain fast and offline.

- [ ] **Step 2: Run full test suite**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s tests -v`  
Expected: All tests pass cleanly (approx 70+ tests passing, 0 errors, 0 failures).

- [ ] **Step 3: Commit**

```bash
git add tests/test_services.py tests/test_app.py
git commit -m "test(integration): verify services and app test suites with OpenRouter mocks"
```
