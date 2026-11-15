"""User-approved operational policy, distinct from scientific acceptance."""
WORKFLOW_ENABLED = True
INPUT_POLICY = "unvalidated-estimated-soil-v1"


def operational_status():
    from ..analysis.model import model_status
    from .models import manifest, WARNING
    base = model_status()
    try:
        manifest()
        available = WORKFLOW_ENABLED
    except (OSError, ValueError, KeyError, TypeError):
        available = False
    return {**base, "predictionsEnabled": available, "scientificallyValidated": False,
            "state": "unvalidated_enabled" if available else base["state"],
            "message": ("Unvalidated ML predictions are enabled, including disclosed estimated soil inputs. " + WARNING)
                       if available else base["message"],
            "estimatedInputsAllowed": available}
