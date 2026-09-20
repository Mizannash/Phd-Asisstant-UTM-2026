# Deployment Guide

1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/) and create a new app.
3. Select your repository and set the main file path to `src/ui/dashboard.py`.
4. In the Streamlit Advanced Settings for your app, add the contents of your `.streamlit/secrets.toml` to the "Secrets" field. For example:

```toml
GROQ_API_KEY = "your_groq_key"
GEMINI_API_KEY = "your_gemini_key"
```

5. Deploy!
