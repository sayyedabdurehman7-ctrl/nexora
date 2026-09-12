# Publish NEXORA from GitHub

This repository includes a Render configuration for a hosted demo. Render builds the Docker image from GitHub and starts one service containing both the FastAPI API and the Flet browser interface.

1. Push the repository to `https://github.com/sayyedabdurehman7-ctrl/nexora`.
2. On [Render](https://render.com), choose **New > Blueprint** and select the `nexora` repository.
3. Deploy the service and open its generated `https://...onrender.com` URL.
4. In **Environment**, add your own `GEMINI_API_KEY` as a secret and optionally `GEMINI_MODEL`. Never upload `.env`.

The blueprint starts in Mock mode so it works without a key. Set `LLM_PROVIDER=gemini` after adding a key. Render's free filesystem is temporary, so SQLite conversations are demo-only; use a managed database for durable production data. Local microphone and speaker features remain desktop-only.
