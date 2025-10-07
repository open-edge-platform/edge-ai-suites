class BaseSummarizer:
    def __init__(self, model_name=..., device="CPU", revision=None):
       raise NotImplementedError

    def generate(self, prompt: str) -> str:
        raise NotImplementedError