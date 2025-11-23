# Medivio

Medivio is an AI-powered health assistant that helps people understand medical data in a simple way. It takes inputs like X-rays, MRI scans, lab results, and doctor’s notes, and gives clear explanations that anyone can follow. The goal is to make medical information easier and less stressful for users.

---

## Features

* Upload X-ray, MRI, or any medical image
* Paste doctor’s notes or medical text
* Get simple, clear explanations powered by Gemini 2.5
* Multi-modal analysis (image + text)
* Clean Streamlit interface
* Works online, no installation needed
* Secure handling of user inputs
* Optional “Buy Me a Coffee” support link

---

## Tech Stack

* **Streamlit** (main interface)
* **HTML + CSS** (light styling)
* **Gemini 2.5 API** (AI model)
* **Streamlit Community Cloud / Hugging Face Spaces** (deployment)

---

## How I Built It

I built Medivio with Streamlit to make the interface simple and fast. I added some HTML and CSS to improve the layout. The AI part uses Gemini 2.5 through its API, which allows the app to process both medical images and text. After that, I deployed it on Streamlit Community Cloud and Hugging Face Spaces so anyone can access it online.

---

## Inspiration

I wanted to build something that helps people understand medical information without stress. Most medical terms can be confusing, so I created Medivio as a simple tool that explains things in plain language.

---

## Challenges

* Handling large medical images
* Making the UI clean and easy to use
* Getting multi-modal responses to stay consistent
* Managing API errors and timeouts on deployment

---

## What I Learned

I learned how to mix multi-modal AI with a lightweight UI. I also learned how to handle user inputs securely and how to deploy apps smoothly on Streamlit Community Cloud and Hugging Face Spaces.

---

## What’s Next

I plan to train a more specialized model on a bigger medical dataset so the predictions and explanations can become even more accurate. I also want to add speech output, so the app can read explanations aloud.

In the future, I also want to add geolocation support. This will allow the app to suggest nearby clinics or labs based on the user’s country or area.

---

## Setup

1. Clone the repo
2. Install requirements
3. Add your API keys in `.env`
4. Run the app

```
streamlit run app.py
```

