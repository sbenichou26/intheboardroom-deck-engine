# In The Boardroom — Deck Intelligence Engine

Streamlit app that generates institutional "Discussion Materials" decks on sports
assets (clubs, leagues, federations) for investment funds, from sourced public
research only.

## Run locally

```bash
pip install -r requirements.txt
# create .streamlit/secrets.toml from the example, with real values
streamlit run app.py
```

## Secrets (required)

Set these in `.streamlit/secrets.toml` locally, and in Streamlit Community Cloud
under **App → Settings → Secrets**:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
APP_PASSWORD = "a-strong-password"
```

The app refuses to run without `APP_PASSWORD`: every generation is billed to the
API key, so the password gate keeps a public URL from being used by anyone who
finds it.

## Models

- `claude-sonnet-5` — entity identification
- `claude-opus-4-8` — deck generation (streaming, web search enabled)
