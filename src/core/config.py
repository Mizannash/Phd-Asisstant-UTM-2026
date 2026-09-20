import os
from dotenv import load_dotenv

# Load .env file (lowest priority)
load_dotenv()

def get_secret(key_name: str) -> str:
    """
    Retrieve a secret in priority order:
    1. Environment variable (os.environ)
    2. Streamlit secrets (st.secrets)
    3. .env file (via load_dotenv which populates os.environ but doesn't override existing)
    """
    # 1 & 3: Environment variable (including .env loaded vars)
    val = os.getenv(key_name)
    if val:
        return val.strip()

    # 2: Streamlit secrets
    try:
        import streamlit as st
        if key_name in st.secrets:
            return str(st.secrets[key_name]).strip()
    except ImportError:
        pass
    except Exception:
        pass

    raise ValueError(f"CRITICAL ERROR: Secret '{key_name}' not found. It must be provided via environment variables, Streamlit Secrets, or .env file.")

def get_masked_key(key_value: str) -> str:
    """Returns masked key: first6 + '...' + last4 only."""
    if not key_value or len(key_value) <= 10:
        return "..."
    return f"{key_value[:6]}...{key_value[-4:]}"
