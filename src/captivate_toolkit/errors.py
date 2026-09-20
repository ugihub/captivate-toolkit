class CaptivateError(Exception):
    """Base class for expected, user-facing failures."""


class ConfigError(CaptivateError):
    pass


class ExtractionError(CaptivateError):
    pass


class UnsupportedFormatError(ExtractionError):
    pass


class RenderError(CaptivateError):
    pass


class MediaError(CaptivateError):
    pass


class AnalysisError(CaptivateError):
    pass
