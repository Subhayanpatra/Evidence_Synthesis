import unittest
from unittest.mock import MagicMock, patch

from agents import openai_client


class OpenAIClientTests(unittest.TestCase):
    @patch("agents.openai_client.OpenAI")
    def test_generate_json_uses_responses_api_and_structured_output(self, openai_class):
        response = MagicMock()
        response.output_text = '{"status": "ok"}'
        client = openai_class.return_value
        client.responses.create.return_value = response

        with patch.object(openai_client, "OPENAI_API_KEY", "test-key"):
            result = openai_client.generate_json("Return JSON")

        self.assertEqual(result, {"status": "ok"})
        create_kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(create_kwargs["model"], "gpt-5.6-sol")
        self.assertEqual(create_kwargs["reasoning"], {"effort": "medium"})
        self.assertEqual(
            create_kwargs["text"]["format"],
            {"type": "json_object"},
        )

    def test_generate_json_requires_openai_api_key(self):
        with patch.object(openai_client, "OPENAI_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                openai_client.generate_json("Return JSON")


if __name__ == "__main__":
    unittest.main()
