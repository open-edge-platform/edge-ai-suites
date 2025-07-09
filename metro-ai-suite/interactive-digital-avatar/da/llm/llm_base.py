from abc import ABC, abstractmethod
from typing import Generator, Set

from da.util.log import logger


class LLMBaseClient(ABC):

    @abstractmethod
    def generate_text(self, prompt: str) -> Generator[str, None, None]:
        """
        Abstract method to generate text using the LLM.

        :param prompt: The prompt to send to the LLM.
        :return: A generator yielding chunks of generated text from the LLM.
        """
        pass

    def generate_text_one_str(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the LLM, and wrap text Generator into a single str.

        :param prompt: The prompt to send to the LLM.
        :return: A generator yielding chunks of generated text from the LLM.
        """
        answer = "".join(self.generate_text(prompt))
        logger.info(f"Answer from LLM: {answer}")
        return answer

    @abstractmethod
    def generate_text_complete_sentences(self, prompt: str) -> Generator[str, None, None]:
        pass

    def _generate_text_complete_sentences(
            self, prompt: str, min_length: int,
            end_punctuation: Set[str]) -> Generator[str, None, None]:
        """
        Generate text using the LLM, and wrap text Generator into multiple complete sentences.

        Parameters:
        - prompt: The prompt to send to the LLM.
        - min_length: minimum length of the returned string.
        - end_punctuation: a set of characters used to determine sentence boundaries.
        """
        text_generator = self.generate_text(prompt)

        def generate_sentences():
            buffer = []

            for text_piece in text_generator:
                for c in text_piece:
                    buffer.append(c)

                    if c not in end_punctuation:
                        continue

                    if len(buffer) >= min_length:
                        sentence = ''.join(buffer)
                        buffer.clear()
                        yield sentence

            if len(buffer) > 0:
                yield ''.join(buffer)

        for answer in generate_sentences():
            logger.info(f"Answer from LLM: {answer}")
            yield answer
