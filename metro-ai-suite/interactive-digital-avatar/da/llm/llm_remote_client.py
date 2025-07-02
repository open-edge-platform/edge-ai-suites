from abc import ABC

import requests

from da.llm.llm_base import LLMBaseClient
from da.util.log import logger


class LLMRemoteClient(LLMBaseClient, ABC):
    def __init__(self, base_url: str):
        """
        Initialize the LLM server with a base URL.

        :param base_url: The base URL of the LLM server API.
        """
        self.base_url = base_url
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def send_request(self, payload: dict, iter_line: bool = True):
        """
        Send a streaming HTTP request to the LLM server.

        :param payload: The payload to send in the request body.
        :param iter_line: Some api return llm answer in multi-lines json format,
        while others return plain text in one line. Set True if API provider
        is the former, False otherwise.
        :return: A generator yielding chunks of text from the response.
        """
        url = self.base_url

        logger.info(f"Sending payload to LLM server: {payload}")

        response = requests.post(url, json=payload, headers=self.headers, stream=True)

        if response.status_code == 200:
            logger.info("200 OK from LLM server.")
            if iter_line:
                return response.iter_lines(decode_unicode=True)
            else:
                return response.iter_content(decode_unicode=True)
        else:
            logger.error(f"Error from LLM server: {response.status_code} - {response.reason}")
