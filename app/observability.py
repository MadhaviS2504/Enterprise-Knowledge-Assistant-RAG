"""Privacy-conscious initialization and decorators for Rius observability."""

import logging
import os


log = logging.getLogger(__name__)


def initialize() -> None:
    """Initialize Rius once before instrumented application modules are used.

    No telemetry setup occurs when the API key is missing or when
    RIUS_DISABLED contains an enabled boolean value. Initialization failures are
    logged, but the application continues without observability.
    """
    from dotenv import load_dotenv

    load_dotenv()

    api_key_missing = not os.getenv("RIUS_API_KEY")
    disabled = os.getenv("RIUS_DISABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    if api_key_missing or disabled:
        log.info("Rius observability disabled (no key or kill switch)")
        return

    try:
        import rius

        rius.init(
            service_name=os.getenv(
                "RIUS_SERVICE_NAME",
                "enterprise-knowledge-assistant",
            ),
            capture_content=False,
        )
        log.info("Rius observability enabled without sensitive content capture")
    except Exception:
        log.exception(
            "Rius initialization failed; application will continue without telemetry"
        )


def trace(name: str):
    """Create a decorator that records timing and errors for a named operation.

    Function arguments and return values are not captured. If the Rius package is
    unavailable, the original function is returned unchanged and tracing is
    disabled.
    """

    def decorate(function):
        try:
            import rius

            return rius.observe(
                name=name,
                capture_input=False,
                capture_output=False,
            )(function)
        except ImportError:
            return function

    return decorate