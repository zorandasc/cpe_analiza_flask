import os
from exchangelib import BaseProtocol
import requests


def get_ca_bundle_path(app):
    if os.path.exists("/.dockerenv") or os.name == "posix":
        return "/app/mtel_bundle.pem"
    else:
        project_root = os.path.dirname(app.root_path)
        return os.path.join(project_root, "mtel_bundle.pem")


def configure_exchangelib_ssl(app):
    """
    Force exchangelib to use our CA bundle for all connections.
    Required because the internal Exchange server at webmail.mtel.ba
    does not send intermediate certificates during TLS handshake.
    Call this once during app initialization.
    """

    # Force exchangelib to use our bundle which has the full intermediate chain.
    # Needed because the internal Exchange server does NOT send intermediates.
    ca_bundle = get_ca_bundle_path(app)

    if not os.path.exists(ca_bundle):
        app.logger.warning(f"SSL bundle not found at {ca_bundle}")
        return

    class MtelHttpAdapter(requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs["verify"] = ca_bundle
            return super().send(*args, **kwargs)

    BaseProtocol.HTTP_ADAPTER_CLS = MtelHttpAdapter
    app.logger.info(f"exchangelib SSL configured: {ca_bundle}")


# This is another option
def configure_exchangelib_without_ssl(app):
    """
    Disable SSL verification for exchangelib connections to internal
    Exchange server at webmail.mtel.ba. Safe because:
    - App runs exclusively inside corporate network
    - Internal Exchange server does not send intermediate certificates
    """
    import requests
    from exchangelib.protocol import BaseProtocol
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    class NoVerifyHttpAdapter(requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs["verify"] = False
            return super().send(*args, **kwargs)

    BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHttpAdapter
    app.logger.info("exchangelib SSL verification disabled (internal network only)")
