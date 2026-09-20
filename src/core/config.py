import os
from dotenv import load_dotenv

# Load .env file (lowest priority)
load_dotenv()

def get_masked_key(key_value: str) -> str:
    """Returns masked key: first6 + '...' + last4 only."""
    if not key_value or len(key_value) <= 10:
        return "***"
    return f"{key_value[:6]}...{key_value[-4:]}"

def get_secret(key_name: str) -> str:
    """
    Retrieve a secret in priority order:
    1. Streamlit secrets (st.secrets)
    2. Environment variable (os.environ / .env)
    """
    secret_value = None
    source = ""

    # 1: Streamlit secrets
    try:
        import streamlit as st
        if key_name in st.secrets:
            secret_value = str(st.secrets[key_name]).strip()
            source = "st.secrets"
    except ImportError:
        pass
    except Exception:
        pass

    # 2: Environment variable
    if not secret_value:
        val = os.getenv(key_name)
        if val:
            secret_value = val.strip()
            source = "os.getenv"

    if not secret_value:
        raise ValueError(f"CRITICAL ERROR: Secret '{key_name}' not found. It must be provided via Streamlit Secrets or environment variables.")
        
    masked = get_masked_key(secret_value)
    print(f"[config] Loaded {key_name} from {source}: {masked}")
    return secret_value
