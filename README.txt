JARVIS - a space-themed voice assistant for Windows
===================================================

Jarvis listens for "Jarvis ...", talks back, opens and closes your apps, opens
files and folders by name, searches YouTube and Google, and chats using an AI
model. This copy contains NO API keys and no personal settings, so it is safe
to share. You add your own key once, in the app.


QUICK START
-----------
1. Unzip this folder anywhere (Desktop or Documents is fine).
2. Double-click  start_jarvis.bat
   - If Python is missing, the script installs it with winget, then asks you
     to run the file again.
   - The required packages install automatically on first run (one minute).
3. Jarvis opens. Go to Settings -> "AI brain".
4. Paste a free Gemini key from https://aistudio.google.com/apikey
5. Click "Save name and keys", then "Test AI connection".

That is all. The key is stored only on your PC, in jarvis_config.json.


DO I NEED A KEY?
----------------
Only for AI chat. Without a key Jarvis still:
  - listens and speaks
  - opens and closes apps ("Jarvis open chrome")
  - opens files and folders ("Jarvis open my downloads")
  - opens websites and download pages ("Jarvis open the discord download page")
  - searches and plays YouTube ("Jarvis play lofi on youtube")
  - searches Google, tells the time and date, tells jokes

A free Gemini key is enough. A Claude key is optional and only used as a
fallback when Gemini is rate-limited.


USING IT
--------
Say "Jarvis" first (default mode), or type in the box.
  "Jarvis open spotify"          "Jarvis close chrome"
  "Jarvis what's the weather"    "Jarvis play lofi on youtube"
  "Jarvis open my thesis pdf"    "Jarvis open the steam website"

Settings lets you pick the voice, speaking speed, your microphone,
sensitivity, language, when he listens, and the theme.


FILES
-----
  jarvis.py                 the whole app
  jarvis_config.json        your settings and keys (created/updated by the app)
  start_jarvis.bat          normal launcher (no console window)
  start_jarvis_debug.bat    launcher that keeps a console open, for errors
  themes/                   UI themes; drop in your own .json file
  jarvis_log.txt            created at runtime; useful when reporting bugs


REQUIREMENTS
------------
  Windows 10 or 11, Python 3.10+, internet for AI replies and natural voices.
  The "Windows voice (offline)" option in Settings works without internet.
  A microphone for voice control; typing always works.


TROUBLESHOOTING
---------------
  Nothing happens:            run start_jarvis_debug.bat and read the error.
  "My AI key was rejected":   re-paste the key in Settings; make sure it is a
                              Gemini API key, not a Google Cloud OAuth token.
  "I have hit my free limit": free tier per-minute limit; wait a moment or add
                              an optional Claude key.
  No sound:                   pick another voice in Settings and press
                              "Test voice".
  He does not hear you:       raise Sensitivity, choose your microphone
                              explicitly, and check Windows microphone privacy.
  Deleted jarvis_config.json: the app recreates it with defaults.


PRIVACY
-------
  - Keys and settings live only in jarvis_config.json on your PC.
  - Voice is transcribed by Windows/Google speech services, replies come from
    the Gemini (or Claude) API, and natural voices come from Microsoft Edge TTS.
  - Nothing else is uploaded anywhere. There are no telemetry or analytics.


LICENCE
-------
Add whatever licence you like before publishing (MIT is a common choice).
