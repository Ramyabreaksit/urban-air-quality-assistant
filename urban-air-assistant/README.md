# Urban Air Quality Assistant

A GenAI-powered assistant that helps families handle winter smog and urban air pollution.
Enter your city and household details to get live air quality plus a personalised plan:
low-emission daily routines, indoor air quality hacks, sustainable alternatives, and a
plain-language explanation of the impact of each choice.

## Features
- Live US AQI, PM2.5 and PM10 for any city (Open-Meteo, no key needed)
- Personalised plan from Google Gemini, with an offline rule-based fallback if AI is unavailable
- Approximate CO2 saving estimate for switching commute mode
- Accessible UI: labelled inputs, text alongside colour, plain language

## Run locally
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add GEMINI_API_KEY
streamlit run app.py
pytest
```

## Deploy
Push to a public GitHub repo, create an app on Streamlit Community Cloud, and add
`GEMINI_API_KEY` under the app's Secrets.

## Security
Keys live only in secrets, input is sanitised and length-limited, network calls have timeouts,
and the model prompt only uses fetched data. General guidance only, not medical advice.
## Accessibility
- Every input has a visible label and help text
- Air-quality status is written in words, never colour alone, and announced to screen readers
- High-contrast light theme (.streamlit/config.toml)
- Plain-language advice, responsive layout, keyboard-usable form