import os


def getenv_required(key):
    val = os.getenv(key)
    if val is None or len(val) == 0:
        raise ValueError(f"Required environment variable '{key}' is not set.")
    return val


# Syncthing config
SYNCTHING_URL = getenv_required("SYNCTHING_URL")
SYNCTHING_API_KEY = getenv_required("SYNCTHING_API_KEY")
SYNCTHING_CERT_FILE = getenv_required("SYNCTHING_CERT_FILE")

# Indicator config
CM_RGB_CLI_PATH = getenv_required("CM_RGB_CLI_PATH")
