import os
import types
import unittest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel
from src.llm_client import (
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_OPENROUTER_BASE_URL,
    get_model_name,
    get_openrouter_client,
    generate_structured_output,
    extract_json_from_text,
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

    def test_get_model_name_default_and_env(self):
        os.environ.pop("OPENROUTER_MODEL", None)
        self.assertEqual(get_model_name(), DEFAULT_OPENROUTER_MODEL)
        os.environ["OPENROUTER_MODEL"] = "meta-llama/llama-3.3-70b-instruct:free"
        self.assertEqual(get_model_name(), "meta-llama/llama-3.3-70b-instruct:free")

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

    def test_get_openrouter_client_explicit_args(self):
        client = get_openrouter_client(api_key="sk-explicit-111", base_url="https://custom.api/v1")
        self.assertEqual(client.api_key, "sk-explicit-111")
        self.assertEqual(str(client.base_url).rstrip("/"), "https://custom.api/v1")

    def test_get_openrouter_client_missing_key_raises_runtime_error(self):
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        with self.assertRaises(RuntimeError) as ctx:
            get_openrouter_client()
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_extract_json_from_text(self):
        self.assertEqual(extract_json_from_text('{"a": 1}'), '{"a": 1}')
        self.assertEqual(extract_json_from_text('```json\n{"a": 1}\n```'), '{"a": 1}')
        self.assertEqual(extract_json_from_text('```\n{"a": 1}\n```'), '{"a": 1}')

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

    def test_generate_structured_output_with_reasoning_effort(self):
        mock_client = MagicMock()
        mock_tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(
                name="DummySchema",
                arguments='{"category": "Base", "confidence": 0.92}'
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
            reasoning_effort="low",
        )

        self.assertEqual(result.category, "Base")
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["extra_body"], {"reasoning": {"effort": "low"}})

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

    def test_generate_structured_output_neither_tool_calls_nor_content_raises(self):
        mock_client = MagicMock()
        mock_response = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        tool_calls=[],
                        content=""
                    )
                )
            ]
        )
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            generate_structured_output(
                client=mock_client,
                model=DEFAULT_OPENROUTER_MODEL,
                prompt="Classify this waste",
                response_model=DummySchema,
            )
        self.assertIn("returned neither tool calls nor message content", str(ctx.exception))

    def test_generate_structured_output_exhausts_retries_raises(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("503 Service Temporarily Unavailable")

        with patch("time.sleep", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                generate_structured_output(
                    client=mock_client,
                    model=DEFAULT_OPENROUTER_MODEL,
                    prompt="Classify this waste",
                    response_model=DummySchema,
                    max_retries=2,
                )
        self.assertIn("503", str(ctx.exception))
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)


if __name__ == "__main__":
    unittest.main()
