"""Browser-demo stand-in for the openai package: live checks need the full app."""

MESSAGE = "Live checks need the full app with a Meta Model API key. See 'Run it' in the README."


class OpenAI:
    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError(MESSAGE)


class AsyncOpenAI(OpenAI):
    pass
