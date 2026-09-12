# Free Hugging Face deployment

Hugging Face Docker Spaces can run this repository's Docker container on port 7860. Spaces are Git repositories and can be kept in sync from GitHub with the official `huggingface/hub-sync` GitHub Action.

1. Create an account at [Hugging Face](https://huggingface.co/).
2. Choose **New Space**, select **Docker**, and name it `nexora`.
3. In the Space, open **Settings → Variables and secrets** and add `GEMINI_API_KEY` as a secret if you want Gemini. Keep `LLM_PROVIDER=mock` for a keyless demo.
4. Copy the Space's Git URL. Either upload the repository files to the Space, or connect GitHub using the documented `huggingface/hub-sync` Action after creating an `HF_TOKEN` GitHub secret.
5. Wait for the Docker build, then open the Space URL.

This is a free demo environment. Local SQLite data is temporary, and microphone/speaker hardware belongs to the desktop app, so hosted use is primarily text chat.
