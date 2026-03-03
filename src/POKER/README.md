<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/1Hk0iXPHAfyjvoklEyLTTj4L0iXTCjpsN

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set `OPENROUTER_POKER_API` in [.env.local](.env.local) (e.g., export it in your `~/.zshrc`), pointing to your OpenRouter key.
3. Run the app:
   `npm run dev`

Notes:
- Six fixed models battle by default: x-ai/grok-4.1-fast, google/gemini-3-flash-preview, openai/gpt-5-mini, moonshotai/kimi-k2-thinking, deepseek/deepseek-v3.2, qwen/qwen3-max.
- Each decision has a 60s max think; if a model doesn’t respond in time, it auto-folds.
- Game data is streamed to `game-log.ndjson` (NDJSON) while the Vite dev server runs. The client also keeps a rolling in-browser cache for redundancy.
