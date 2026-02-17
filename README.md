# tg_mirror

## Introduction
This is the tg_mirror, a tool written to help my friends in the LGBTQ+ community that uses AI to "look through the mirror" and see an alternate version of themselves.

<img src="screenshot.png" width="45%" />

## Installation Instructions
To get started with tg_mirror, follow these simple steps:
  - download mirror-mirror.py
  - pip install xai-sdk pillow tkinterdnd2
  - python mirror-mirror.py

## Transparency and xAI
My goal was to give the user as much privacy and ownership of their photos and API key as practical while still allowing them to see themselves in a new way. Grok Imagine is, in my limited experience, the best AI image editor to consistently perform this kind of gender transformation with a simple prompt. Although you don't have to trust me with your data, you do have to trust xAI/Elon Musk. Their API data FAQ is <a href="https://docs.x.ai/developers/faq/security">at this link</a>, and they say they do not use this input for model training and remove it after 30 days. This is better than using Grok's website or mobile apps, but if you don't feel comfortable using their service, you should not proceed. I will eventually try to make a version of this tool that uses other AI providers and/or a self-hosted version.

## Usage Notes:
  * You will need an xAI API key from <a href="https://console.x.ai/">console.x.ai</a> — new accounts might get some free credits and <a href="https://docs.x.ai/developers/models">pricing is generally</a> between $0.05 and $0.17 / generation
  * grok-imagine-image-pro gives better results but takes longer (30–60s is normal) and is more expensive
  * The prompt is fully editable — you can customize it for FtM, style changes, or anything else the model supports
    * In testing, I was able to tweak the prompt to perform animal transformations as well as couple's gender transformations
  * Your key and photo never leave your machine except to go directly to xAI
  * Make sure you click "Save Output..." to save the generated file. This is a 'one and done' tool.

## ⚠️ Disclaimer
  * This is "Bring Your Own Key" software that runs locally for a user. No data is sent to the developer and the end user is solely responsible for the content they generate using their personal API key.
  * The end user should be mindful of xAI's Acceptable Use Policy.
  * This software is provided "as is," without warranty of any kind.
  * This software is not a mental health tool. If you are in crisis, call <a href="tel:911">911</a> or seek help from a place like <a href="https://trans-care.org/support/">Trans-Care.org</a>.
