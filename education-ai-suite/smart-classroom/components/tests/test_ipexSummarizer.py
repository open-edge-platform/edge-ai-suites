import unittest
from unittest.mock import patch, MagicMock
import os

TEST_MODEL = "Qwen/Qwen2.5-7B-Instruct"
TEST_PROMPT = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Please summarize the following: The Smart Classroom project is a modular, extensible framework designed to process and summarize educational content using advanced AI models. It supports transcription, summarization, and future capabilities like video understanding and real-time analysis. "}
    ]

class TestSummarizer(unittest.TestCase):
    @patch("components.llm.ipex.summarizer.config")
    def test_init_huggingface(self, mock_config):
        mock_config.models.summarizer.model_hub = "huggingface"
        from components.llm.ipex.summarizer import Summarizer
        with patch("components.llm.ipex.summarizer.AutoModelForCausalLM.from_pretrained") as mock_model, \
             patch("components.llm.ipex.summarizer.torch") as mock_torch, \
             patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer:
            mock_model.return_value = MagicMock(half=MagicMock(return_value=MagicMock(to=MagicMock(return_value="model"))))
            mock_tokenizer.return_value = MagicMock()
            summarizer = Summarizer(TEST_MODEL, device="xpu")
            self.assertEqual(summarizer.device, "xpu")
            self.assertIsNotNone(summarizer.model)
            self.assertIsNotNone(summarizer.tokenizer)

    @patch("components.llm.ipex.summarizer.config")
    def test_generate(self, mock_config):
        mock_config.models.summarizer.model_hub = "huggingface"
        mock_config.models.summarizer.max_new_tokens = 10
        from components.llm.ipex.summarizer import Summarizer
        with patch("components.llm.ipex.summarizer.AutoModelForCausalLM.from_pretrained") as mock_model, \
             patch("components.llm.ipex.summarizer.torch") as mock_torch, \
             patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer:
            mock_tokenizer_instance = MagicMock()
            mock_tokenizer_instance.apply_chat_template.return_value = "prompt"
            mock_tokenizer_instance.batch_decode.return_value = ["summary"]
            mock_tokenizer.return_value = mock_tokenizer_instance
            mock_model_instance = MagicMock()
            mock_model_instance.generate.return_value = mock_torch.tensor([[1,2,3,4]])
            mock_model.return_value = mock_model_instance
            mock_model_instance.half.return_value = mock_model_instance
            mock_model_instance.to.return_value = mock_model_instance
            summarizer = Summarizer(TEST_MODEL)
            summarizer.tokenizer = mock_tokenizer_instance
            summarizer.model = mock_model_instance
            mock_torch.inference_mode.return_value.__enter__.return_value = None
            mock_torch.inference_mode.return_value.__exit__.return_value = None
            mock_torch.xpu.synchronize.return_value = None
            mock_torch.tensor.return_value = mock_model_instance.generate.return_value
            model_inputs = MagicMock()
            model_inputs.input_ids = [[1,2]]
            summarizer.tokenizer.__call__ = MagicMock(return_value=model_inputs)
            model_inputs.to.return_value = model_inputs

            result = summarizer.generate("test prompt", stream=False)
            self.assertEqual(result, "summary")

    @patch("components.llm.ipex.summarizer.config")
    def test_generate_stream(self, mock_config):
        mock_config.models.summarizer.model_hub = "huggingface"
        mock_config.models.summarizer.max_new_tokens = 50
        from components.llm.ipex.summarizer import Summarizer
        model = Summarizer(TEST_MODEL, "xpu")
        for response in model.generate(TEST_PROMPT):
            print(response)

    @patch("components.llm.ipex.summarizer.config")
    def test_generate_nonstream(self, mock_config):
        mock_config.models.summarizer.model_hub = "huggingface"
        mock_config.models.summarizer.max_new_tokens = 50
        from components.llm.ipex.summarizer import Summarizer
        model = Summarizer(TEST_MODEL, "xpu")
        print(model.generate(TEST_PROMPT, stream=False))

if __name__ == "__main__":
    unittest.main()
