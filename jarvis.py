"""JARVIS - space-themed voice AI assistant for Windows. Start it with start_jarvis.bat.
Settings, apps and keys are saved in jarvis_config.json. Errors are written to jarvis_log.txt."""
import asyncio, collections, ctypes, difflib, hashlib, json, math, os, queue, random, re, shutil, subprocess, sys, tempfile, threading, time, traceback, webbrowser
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.stdout is None or sys.stderr is None:          # started with pythonw (no console): log to a file
    sys.stdout = sys.stderr = open(os.path.join(HERE, "jarvis_log.txt"), "a", encoding="utf-8", buffering=1)
sys.excepthook = lambda *a: traceback.print_exception(*a)
threading.excepthook = lambda a: traceback.print_exception(a.exc_type, a.exc_value, a.exc_traceback)
try:
    from tkinter import filedialog
    import customtkinter as ctk
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr
except ImportError as e:
    msg = f"Missing package ({e}). Run start_jarvis.bat again."
    print(msg); sys.exit(msg)
try: import edge_tts
except ImportError: edge_tts = None
try: import anthropic
except ImportError: anthropic = None
try:
    from google import genai
    from google.genai import types as gt
except ImportError: genai = None
try: import pystray
except ImportError: pystray = None
try:
    from PIL import Image, ImageDraw, ImageChops, ImageTk
    HAVE_PIL = True
except ImportError: HAVE_PIL = False

CFG = os.path.join(HERE, "jarvis_config.json")
THEMES_DIR = os.path.join(HERE, "themes")
shutil.rmtree(os.path.join(tempfile.gettempdir(), "jarvis_cache"), ignore_errors=True)   # the old cache could hold broken (silent) audio
CACHE = os.path.join(tempfile.gettempdir(), "jarvis_cache2"); os.makedirs(CACHE, exist_ok=True)
RATE, BLOCK, END_SIL = 16000, 800, 9
CLAUDE_MODEL, GEMINI_MODEL = "claude-haiku-5-5", "gemini-3.8-flash"
OLD_MODELS = {"", "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"}   # retired or retiring
NOWIN = 0x08000000 if os.name == "nt" else 0
WAKE = r"\b(jarvis|jarvas|jervis)\b[,.! ]*"
NEEDS = re.compile(r"\b(today|tonight|tomorrow|yesterday|latest|news|current|currently|right now|price|weather|score|stock|trending|this week|this year|2025|2026|search|look up|google)\b", re.I)
OPEN_V, CLOSE_V = r"open|launch|start|run|play|show|go to|switch to|load", r"close|quit|kill|stop|shut down|shut|terminate|exit"
POLITE = r"(?:(?:please|can you|could you|would you|will you|hey|ok|okay|just)\s+)*"
EXIT = {"exit", "quit", "goodbye", "bye", "goodbye jarvis", "bye jarvis", "exit jarvis", "quit jarvis", "shut down jarvis"}
VOICES = {"British male (Ryan)": "en-GB-RyanNeural", "American male (Guy)": "en-US-GuyNeural", "American female (Aria)": "en-US-AriaNeural",
          "American female (Jenny)": "en-US-JennyNeural", "British female (Sonia)": "en-GB-SoniaNeural", "Indian male (Prabhat)": "en-IN-PrabhatNeural",
          "Indian female (Neerja)": "en-IN-NeerjaNeural", "Urdu male (Asad)": "ur-PK-AsadNeural", "Urdu female (Uzma)": "ur-PK-UzmaNeural",
          "Windows voice (offline)": "windows"}
LANGS = {"English": "en-US", "Urdu": "ur-PK", "Hindi": "hi-IN"}
MODES = ["Always respond", "Wake word + follow-ups"]
PROCS = {"steam": ["steam.exe", "steamwebhelper.exe"], "wallpaper engine": ["wallpaper32.exe", "wallpaper64.exe", "ui32.exe"],
         "notepad": ["notepad.exe"], "calculator": ["CalculatorApp.exe", "calc.exe"], "paint": ["mspaint.exe"],
         "chrome": ["chrome.exe"], "edge": ["msedge.exe"], "spotify": ["Spotify.exe"], "whatsapp": ["WhatsApp.exe"]}
DEFAULT = {"apps": {"steam": "steam://open/main", "wallpaper engine": "steam://rungameid/431960", "this pc": "shell:MyComputerFolder",
    "notepad": "notepad", "calculator": "calc", "paint": "mspaint", "chrome": "chrome", "edge": "msedge", "spotify": "spotify:",
    "whatsapp": "whatsapp:", "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "maps": "https://maps.google.com"},
    "voice": "British male (Ryan)", "speed": 0, "lang": "English", "gemini_key": "", "claude_key": "", "name": "",
    "listen_mode": MODES[0], "mic": "Default", "startup": False, "gemini_model": GEMINI_MODEL, "sens": 5}
THEME_DEFAULTS = {"background": "#04050d", "sky": "#060818", "panel": "#0a0d1f", "panel_alt": "#12163a", "line": "#1d2350",
    "border_card": "#1d2350", "border_control": "#1d2350", "border_focus": "#38e8ff", "border_emphasis": "#7c5cff",
    "text": "#e8ebff", "muted": "#7f88b8", "accent": "#7c5cff", "accent_alt": "#38e8ff", "accent_hover": "#9277ff",
    "nav_hover": "#10142e", "mic_hover": "#2c3470", "danger": "#5b1b2a", "danger_hover": "#7f1d1d", "danger_text": "#ffb4c0",
    "danger_text_active": "#ff8a9b", "user_bubble": "#4a33c9", "close_hover": "#7f1d1d", "option_hover": "#6747e6",
    "muted_button": "#4a1d2e", "muted_button_hover": "#6a2640",
    "idle": "#7c8dff", "listening": "#38e8ff", "thinking": "#ffcf5c", "speaking": "#c07cff", "muted_state": "#4b5278"}
THEME_KEYS = tuple(THEME_DEFAULTS)
THEME_STYLE_DEFAULTS = {"border_width": 1, "border_width_emphasis": 1, "radius_card": 16, "radius_chat": 18,
    "radius_control": 10, "radius_small": 8, "radius_pill": 16, "radius_avatar": 14,
    "sidebar_width": 232, "control_height": 36, "page_padding": 22, "font_family": "Segoe UI",
    "font_family_bold": "Segoe UI Semibold", "font_scale": 1.0}
THEME_STYLE_LIMITS = {"border_width": (0, 8), "border_width_emphasis": (0, 8), "radius_card": (0, 48), "radius_chat": (0, 48),
    "radius_control": (0, 48), "radius_small": (0, 48), "radius_pill": (0, 48), "radius_avatar": (0, 48),
    "sidebar_width": (190, 420), "control_height": (28, 64), "page_padding": (0, 64)}
BG, SKY, PANEL, PANEL2, LINE = (THEME_DEFAULTS[k] for k in ("background", "sky", "panel", "panel_alt", "line"))
TEXT, MUTED, ACC, ACC2 = (THEME_DEFAULTS[k] for k in ("text", "muted", "accent", "accent_alt"))
COLORS = {k: THEME_DEFAULTS[k] for k in ("idle", "listening", "thinking", "speaking")}; COLORS["muted"] = THEME_DEFAULTS["muted_state"]
THEMES = {}
THEME_COLORS = dict(THEME_DEFAULTS)
THEME_STYLE = dict(THEME_STYLE_DEFAULTS)

def themed_font(size, bold=False):
    family_key = "font_family_bold" if bold else "font_family"
    return (THEME_STYLE[family_key], max(8, round(size * THEME_STYLE["font_scale"])))

def discover_themes():
    """Load valid theme JSON files. The filename (without extension) is its stable ID."""
    os.makedirs(THEMES_DIR, exist_ok=True)
    found = {}
    for filename in sorted(os.listdir(THEMES_DIR)):
        if not filename.lower().endswith(".json"): continue
        path = os.path.join(THEMES_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f: data = json.load(f)
            colors = data.get("colors", data)
            if not isinstance(colors, dict): continue
            palette = dict(THEME_DEFAULTS)
            for key in THEME_KEYS:
                value = colors.get(key)
                if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value): palette[key] = value.lower()
            theme_id = os.path.splitext(filename)[0]
            raw_style = data.get("style", {})
            style = dict(THEME_STYLE_DEFAULTS)
            if isinstance(raw_style, dict):
                for key, default in THEME_STYLE_DEFAULTS.items():
                    value = raw_style.get(key)
                    if key.startswith("font_family"):
                        if isinstance(value, str) and value.strip(): style[key] = value.strip()
                    elif isinstance(default, float):
                        if isinstance(value, (int, float)) and 0.75 <= value <= 1.5: style[key] = float(value)
                    elif isinstance(value, int) and key in THEME_STYLE_LIMITS and THEME_STYLE_LIMITS[key][0] <= value <= THEME_STYLE_LIMITS[key][1]: style[key] = value
            found[theme_id] = {"name": str(data.get("name") or theme_id.replace("_", " ").title()), "colors": palette, "style": style}
        except (OSError, ValueError, TypeError) as err:
            print(f"Ignoring theme {filename}: {err}")
    return found

def activate_theme(theme_id):
    global BG, SKY, PANEL, PANEL2, LINE, TEXT, MUTED, ACC, ACC2, COLORS, THEME_COLORS, THEME_STYLE, AVATARS
    theme = THEMES.get(theme_id) or THEMES.get("space") or next(iter(THEMES.values()), None)
    if not theme: return
    p = theme["colors"]
    THEME_COLORS = p
    THEME_STYLE = theme.get("style", dict(THEME_STYLE_DEFAULTS))
    AVATARS = [p[k] for k in ("accent", "accent_alt", "idle", "listening", "thinking", "speaking", "muted_state", "option_hover")]
    BG, SKY, PANEL, PANEL2, LINE = (p[k] for k in ("background", "sky", "panel", "panel_alt", "line"))
    TEXT, MUTED, ACC, ACC2 = (p[k] for k in ("text", "muted", "accent", "accent_alt"))
    COLORS = {k: p[k] for k in ("idle", "listening", "thinking", "speaking")}; COLORS["muted"] = p["muted_state"]
NAV = [("home", "◉   Assistant"), ("apps", "▦   Apps"), ("settings", "⚙   Settings")]
SPEECH_LOCK = threading.Lock()
_mci = ctypes.windll.winmm.mciSendStringW if os.name == "nt" else None

def sh(args, **kw): return subprocess.run(args, capture_output=True, text=True, creationflags=NOWIN, **kw)
def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())
def level(b): return float(np.sqrt(np.mean(b.astype(np.float32) ** 2)))
def ease(t): return 1 - (1 - max(0.0, min(1.0, t))) ** 3
def mix(a, b, t):
    ra, rb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * max(0.0, min(1.0, t))) for x, y in zip(ra, rb))

def sentences(chunks):
    buf = ""
    for c in chunks:
        buf += c
        while True:
            m = re.search(r"(?<=[.!?])\s+", buf)
            if not m: break
            yield buf[:m.start()]; buf = buf[m.end():]
    if buf.strip(): yield buf

def parse_command(text, keys):
    """('open'|'close', key) if the sentence is an app command, else None."""
    t = re.sub(WAKE, "", text.lower()).strip(" ,.!?"); t = re.sub("^" + POLITE, "", t)
    m = re.match(r"^(%s|%s)\s+(?:the\s+|my\s+|up\s+)?(.+)$" % (OPEN_V, CLOSE_V), t)
    verb, rest = (m.group(1), m.group(2)) if m else (None, t)
    n = norm(rest); keys = [k for k in keys if len(k) >= 3]
    if verb is None: return ("open", n) if n in keys else None
    hit = max((k for k in keys if k in n), key=len, default=None) or (difflib.get_close_matches(n, keys, 1, 0.75) or [None])[0]
    if not hit: return None
    return ("close" if re.fullmatch(CLOSE_V, verb) else "open", hit)

SITES = {"youtube": "https://www.youtube.com/results?search_query=", "google": "https://www.google.com/search?q=",
         "maps": "https://www.google.com/maps/search/", "google maps": "https://www.google.com/maps/search/", "spotify": "https://open.spotify.com/search/"}
SITE_NAMES = {"youtube": "YouTube", "google": "Google", "maps": "Maps", "google maps": "Maps", "spotify": "Spotify"}

def parse_search(text):
    """('search'|'play', site, query) for sentences like 'play lofi on youtube' or 'google python tutorials'."""
    t = re.sub(WAKE, "", text.lower()).strip(" ,.!?"); t = re.sub("^" + POLITE, "", t)
    site = r"(youtube|google maps|google|maps|spotify)"
    m = re.match(r"^(search|look up|find|play|watch|show me|show)\s+(?:for\s+)?(.+?)\s+(?:on|in|from|at)\s+" + site + "$", t)
    if m: return ("play" if m.group(1) in ("play", "watch") and m.group(3) == "youtube" else "search", m.group(3), m.group(2))
    m = re.match(r"^(search|look up|find|play|watch)\s+" + site + r"\s+(?:for\s+)?(.+)$", t)
    if m: return ("play" if m.group(1) in ("play", "watch") and m.group(2) == "youtube" else "search", m.group(2), m.group(3))
    m = re.match(r"^(youtube|google)\s+(?:search\s+)?(?:for\s+)?(.+)$", t)
    if m and len(m.group(2).split()) <= 8: return ("search", m.group(1), m.group(2))
    m = re.match(r"^(?:search(?:\s+the\s+(?:web|internet)|\s+online)?(?:\s+for)?|search\s+up|look\s+up|google)\s+(.+)$", t)
    if m and not re.match(r"(?:my\s+)?(?:files?|computer|pc|laptop|documents?)\b", m.group(1)): return ("search", "google", m.group(1))
    m = re.match(r"^find\s+(.+?)\s+(?:online|on the web|on the internet)$", t)
    if m: return ("search", "google", m.group(1))
    return None

KNOWN_SITES = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "twitter": "https://x.com", "x": "https://x.com", "reddit": "https://www.reddit.com", "github": "https://github.com",
    "netflix": "https://www.netflix.com", "amazon": "https://www.amazon.com", "linkedin": "https://www.linkedin.com", "whatsapp": "https://web.whatsapp.com",
    "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai", "wikipedia": "https://www.wikipedia.org", "stack overflow": "https://stackoverflow.com",
    "twitch": "https://www.twitch.tv", "tiktok": "https://www.tiktok.com", "discord": "https://discord.com", "spotify": "https://open.spotify.com",
    "steam": "https://store.steampowered.com", "pinterest": "https://www.pinterest.com", "ebay": "https://www.ebay.com", "daraz": "https://www.daraz.pk",
    "telegram": "https://web.telegram.org", "outlook": "https://outlook.live.com", "google drive": "https://drive.google.com", "google maps": "https://maps.google.com",
    "google docs": "https://docs.google.com", "epic games": "https://store.epicgames.com", "roblox": "https://www.roblox.com", "minecraft": "https://www.minecraft.net",
    "fiverr": "https://www.fiverr.com", "upwork": "https://www.upwork.com"}
DOWNLOAD_PAGES = {"discord": "https://discord.com/download", "chrome": "https://www.google.com/chrome/", "google chrome": "https://www.google.com/chrome/",
    "firefox": "https://www.mozilla.org/firefox/new/", "brave": "https://brave.com/download/", "opera": "https://www.opera.com/download", "edge": "https://www.microsoft.com/edge/download",
    "steam": "https://store.steampowered.com/about/", "spotify": "https://www.spotify.com/download/", "whatsapp": "https://www.whatsapp.com/download", "telegram": "https://desktop.telegram.org/",
    "zoom": "https://zoom.us/download", "vlc": "https://www.videolan.org/vlc/", "obs": "https://obsproject.com/download", "python": "https://www.python.org/downloads/",
    "vs code": "https://code.visualstudio.com/download", "vscode": "https://code.visualstudio.com/download", "visual studio code": "https://code.visualstudio.com/download",
    "git": "https://git-scm.com/downloads", "node": "https://nodejs.org/en/download", "nodejs": "https://nodejs.org/en/download", "7zip": "https://www.7-zip.org/download.html",
    "notepad plus plus": "https://notepad-plus-plus.org/downloads/", "slack": "https://slack.com/downloads", "skype": "https://www.skype.com/get-skype/",
    "epic games": "https://store.epicgames.com/download", "minecraft": "https://www.minecraft.net/download", "teamviewer": "https://www.teamviewer.com/download/",
    "anydesk": "https://anydesk.com/en/downloads/windows", "winrar": "https://www.win-rar.com/download.html", "java": "https://www.java.com/download/",
    "wallpaper engine": "https://store.steampowered.com/app/431960/Wallpaper_Engine/", "blender": "https://www.blender.org/download/", "gimp": "https://www.gimp.org/downloads/",
    "audacity": "https://www.audacityteam.org/download/"}
SITE_N, DL_N = {norm(k): (v, k) for k, v in KNOWN_SITES.items()}, {norm(k): (v, k) for k, v in DOWNLOAD_PAGES.items()}
KINDS = r"(?:official\s+)?(download\s+page|downloads\s+page|download|downloads|website|web\s+site|site|homepage|home\s+page|web\s+page|webpage|page)"
SITE_VERB = r"open|go to|visit|launch|load|show me|show|take me to|browse to|browse|search for|search|look up|find|get me"
NOT_SITE = {"my", "the", "a", "an", "this", "that", "latest", "last", "new", "recent", "web", "internet", "it", "one"}

def _site(name, intent, generic=False):
    n = norm(name)
    if not n or name in NOT_SITE or name.startswith(("my ", "this ", "that ")): return None
    first, second = (DL_N, SITE_N) if intent == "download" else (SITE_N, DL_N)
    for table in (first, second):
        hit = n if n in table else (difflib.get_close_matches(n, list(table), 1, 0.8) or [None])[0]
        if hit:
            url, nm = table[hit]; nm = nm.upper() if len(nm) <= 3 else nm.title()
            return (url, f"Opening the {nm} download page." if intent == "download" and table is DL_N else f"Opening {nm}.")
    if generic: return None
    q = f"{name} official download" if intent == "download" else f"{name} official website"
    return ("https://www.google.com/search?q=" + __import__("urllib.parse").parse.quote_plus(q), f"Searching Google for {q}.")

def parse_site(text):
    """(url, spoken) for 'open discord download page', 'download chrome', 'go to youtube.com', 'open the steam website'."""
    t = re.sub(WAKE, "", text.lower()).strip(" ,.!?"); t = re.sub("^" + POLITE, "", t); t = re.sub(r"\s+dot\s+", ".", t)
    m = re.match(r"^(?:i (?:want|need) to |where (?:can|do) i |how (?:can|do) i )?download\s+(?:the\s+)?(.+?)(?:\s+(?:app|software|installer|for windows|for pc))?$", t)
    if m: return _site(m.group(1).strip(), "download")
    m = re.match(r"^(?:%s)\s+(?:the\s+)?(.+?)\s+%s$" % (SITE_VERB, KINDS), t)
    if m:
        kind = m.group(2).replace("  ", " "); return _site(m.group(1).strip(), "download" if "download" in kind else "site", generic=kind in ("page", "web page", "webpage"))
    m = re.match(r"^(?:open|go to|visit|browse to|browse|take me to)\s+(?:the\s+)?((?:https?://)?[a-z0-9][a-z0-9-]*\.(?:com|org|net|io|gg|tv|app|dev|co|pk|edu|gov|ai|me|xyz|info)(?:/\S*)?)$", t)
    if m: return (m.group(1) if m.group(1).startswith("http") else "https://" + m.group(1), f"Opening {m.group(1)}.")
    return None

def open_url(url):
    """Open a web address in the default browser, trying every method Windows offers."""
    try:
        if webbrowser.open(url, new=2): return True
    except Exception as err: print("webbrowser error:", err)
    try: os.startfile(url); return True
    except Exception as err: print("startfile error:", err)
    try: subprocess.Popen(["cmd", "/c", "start", "", url], creationflags=NOWIN); return True
    except Exception as err: print("browser error:", err); return False

def youtube_first(query):
    """Id of the first YouTube result (no key needed), or None."""
    import urllib.request, urllib.parse
    req = urllib.request.Request("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query),
                                 headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "en-US,en;q=0.9"})
    html = urllib.request.urlopen(req, timeout=6).read().decode("utf-8", "ignore")
    m = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html) or re.search(r'"videoId":"([\w-]{11})"', html)
    return m.group(1) if m else None

def explain(err, wait=0.0, daily=False):
    e = (err or "").lower()
    if any(w in e for w in ("api key", "api_key", "401", "403", "permission", "unauthenticated", "x-api-key")): return "My AI key was rejected. Please check it in Settings."
    if daily: return "I have used up today's free Gemini allowance. It resets within a day, or you can add a Claude key in Settings."
    if wait: return f"I have hit the free limit. Give me about {int(wait) + 1} seconds."
    if any(w in e for w in ("quota", "429", "exhaust", "rate limit", "resource")): return "I have hit my free AI limit for now. Give me a minute, or add a Claude key in Settings."
    if any(w in e for w in ("timeout", "timed out", "connect", "network", "name resolution", "unavailable", "503", "overloaded")): return "I could not connect to the AI. Check your internet and try again."
    if any(w in e for w in ("404", "not found", "not supported")): return "None of the AI models I tried is available for your key. Press Test AI connection and send me the red error line."
    return "Sorry, I could not reach my brain. Check your key and internet."

JOKES = ["Why do programmers prefer dark mode? Because light attracts bugs.", "I told my computer I needed a break, and now it won't stop sending me vacation ads.",
         "Why did the computer get cold? It left its Windows open.", "There are only ten kinds of people: those who understand binary and those who don't.",
         "Why was the math book sad? It had too many problems.", "I would tell you a UDP joke, but you might not get it."]

def local_answer(t):
    """Instant answers that need no AI: faster, and they save the free quota."""
    now = datetime.now()
    if re.search(r"\bwhat(?:'s| is)? the time\b|\bwhat time is it\b|\bcurrent time\b|\btell me the time\b", t): return f"It is {now.hour % 12 or 12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}."
    if re.search(r"\bwhat(?:'s| is)?(?: the)? (?:today'?s )?date\b|\bwhat day is (?:it|today)\b|\bwhat is today\b", t): return f"Today is {now:%A}, {now.day} {now:%B %Y}."
    if re.fullmatch(r"(?:thanks|thank you)(?: so much| a lot| jarvis)?", t): return "You're welcome."
    if re.fullmatch(r"(?:hi|hello|hey|good morning|good afternoon|good evening)(?: there| jarvis)?", t): return "Hello! What can I do for you?"
    if re.search(r"\bwho are you\b|\bwhat(?:'s| is) your name\b", t): return "I'm Jarvis, your voice assistant."
    if re.search(r"\bwhat can you do\b|\bwhat are your (?:abilities|features)\b", t): return "I can open and close apps, open your files and folders, search YouTube and Google, and chat about almost anything."
    if re.search(r"\btell me a joke\b|\bsay a joke\b|\bmake me laugh\b", t): return random.choice(JOKES)
    return None

FILE_EXT_WORDS = {"pdf", "docx", "doc", "txt", "xlsx", "xls", "pptx", "ppt", "jpg", "jpeg", "png", "mp3", "mp4", "zip", "rar", "csv", "mkv", "wav"}
SKIP_DIRS = {"node_modules", "appdata", "__pycache__", "venv", "site-packages"}
FILE_RE = re.compile(r"^(?:open|launch|start|show me|show|find|play|go to|run|load)\s+(?:the\s+|my\s+)?(?:(file|folder|document|directory)\s+)?(?:named\s+|called\s+)?(.+)$")
BUILTIN = {"browser": "https://www.google.com", "web browser": "https://www.google.com", "internet": "https://www.google.com", "settings": "ms-settings:", "task manager": "taskmgr", "control panel": "control", "command prompt": "cmd", "snipping tool": "snippingtool", "recycle bin": "shell:RecycleBinFolder"}

def known_folders():
    home, out = os.path.expanduser("~"), {}
    for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
        for base in (home, os.path.join(home, "OneDrive")):
            if os.path.isdir(os.path.join(base, name)): out.setdefault(name.lower(), os.path.join(base, name))
    return out
KF = known_folders()

def index_files(limit=80000, max_s=25):
    """List the files and folders in the user's main folders so Jarvis can open them by name."""
    out, t0 = [], time.time()
    for root in KF.values():
        stack = [(root, 0)]
        while stack and len(out) < limit and time.time() - t0 < max_s:
            path, depth = stack.pop()
            try:
                with os.scandir(path) as it:
                    for e in it:
                        n = e.name
                        if n.startswith((".", "~$")) or n.lower() == "desktop.ini": continue
                        try: isd = e.is_dir(follow_symlinks=False); mt = e.stat().st_mtime
                        except OSError: continue
                        if isd and depth < 5 and n.lower() not in SKIP_DIRS: stack.append((e.path, depth + 1))
                        out.append((norm(n if isd else os.path.splitext(n)[0]), n, e.path, mt, isd))
            except OSError: continue
    return out

def find_path(query, index, want_dir=None):
    """Best matching (name, path, is_dir) for a spoken file name, or None."""
    words = re.findall(r"[a-z0-9]+", query.lower()); ext = next((w for w in words if w in FILE_EXT_WORDS), None)
    words = [w for w in words if w not in FILE_EXT_WORDS and w not in ("dot", "file", "folder", "document", "directory", "the", "my", "named", "called")]
    if not words: return None
    q, best, bs = "".join(words), None, 0.0
    for stem, name, path, mt, isd in index:
        if want_dir is not None and isd != want_dir: continue
        if q == stem: sc = 1.0
        elif all(w in stem for w in words): sc = 0.92 - min(0.25, (len(stem) - len(q)) / 80)
        elif any(len(w) > 2 and w in stem for w in words): sc = difflib.SequenceMatcher(None, q, stem).ratio()
        else: continue
        if ext and name.lower().endswith("." + ext): sc += 0.08
        sc += mt / 1e12                        # newer files win ties
        if sc > bs: best, bs = (name, path, isd), sc
    return best if bs >= 0.6 else None

def discover():
    roots = [os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
             os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
             os.path.join(os.path.expanduser("~"), "Desktop"), os.path.join(os.environ.get("PUBLIC", ""), "Desktop")]
    found = {}
    for root in roots:
        for folder, _, files in os.walk(root):
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext.lower() in (".lnk", ".url") and "uninstall" not in stem.lower(): found.setdefault(norm(stem), (stem, os.path.join(folder, f)))
    return found

def lnk_exe(path):
    if not path.lower().endswith(".lnk"): return None
    try: out = sh(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % path.replace("'", "''")], timeout=10).stdout.strip()
    except Exception: return None
    return os.path.basename(out) if out.lower().endswith(".exe") else None

def mic_names():
    try: names = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    except Exception: names = []
    return ["Default"] + list(dict.fromkeys(names))

def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
AVATARS = [THEME_DEFAULTS[k] for k in ("accent", "accent_alt", "idle", "listening", "thinking", "speaking", "muted_state", "option_hover")]
CHIPS = ["Open YouTube", "Open Downloads", "What can you do?", "Tell me a joke"]
SUBS = {"idle": "I'm ready when you are.", "listening": "I'm listening...", "thinking": "Let me think about that...", "speaking": "", "muted": "The microphone is muted."}
CHIPTXT = {"idle": "●  READY", "listening": "●  LISTENING", "thinking": "●  THINKING", "speaking": "●  SPEAKING", "muted": "●  MUTED"}
CUR = {}

def fade(w, opt, to, start, steps=9, dt=16):
    """Smoothly change a colour option of a widget."""
    key = (str(w), opt); frm = CUR.get(key, [start, 0])[0]; tok = CUR.get(key, [0, 0])[1] + 1; CUR[key] = [frm, tok]
    def step(i=1):
        if CUR[key][1] != tok: return
        c = mix(frm, to, ease(i / steps)); CUR[key][0] = c
        try: w.configure(**{opt: c})
        except Exception: return
        if i < steps: w.after(dt, step, i + 1)
    step()

class AnimButton(ctk.CTkButton):
    """Button whose colour glides between normal and hover instead of snapping."""
    def __init__(self, master, base, hover, **kw):
        super().__init__(master, fg_color=base, hover=False, **kw); self.base, self.hov = base, hover
        self.bind("<Enter>", lambda e: fade(self, "fg_color", self.hov, self.base), add="+")
        self.bind("<Leave>", lambda e: fade(self, "fg_color", self.base, self.base), add="+")
    def set_active(self, on):
        old = self.base; self.base, self.hov = (PANEL2, PANEL2) if on else (PANEL, THEME_COLORS["nav_hover"]); fade(self, "fg_color", self.base, old)

class ChatView(ctk.CTkScrollableFrame):
    """Chat as rounded bubbles that fade in; Jarvis's bubble grows while he is talking."""
    def __init__(self, master):
        super().__init__(master, fg_color=PANEL, corner_radius=THEME_STYLE["radius_chat"], border_width=THEME_STYLE["border_width_emphasis"], border_color=THEME_COLORS["border_emphasis"])
        self.grid_columnconfigure(0, weight=1); self.n, self.rows, self.transcript = 0, [], []
    def bubble(self, who, text):
        if who == "System":
            row = ctk.CTkLabel(self, text=text, text_color=MUTED, font=themed_font(12), wraplength=560); lab = row
            row.grid(row=self.n, column=0, pady=(2, 6))
        else:
            me = who == "You"
            row = ctk.CTkFrame(self, fg_color="transparent"); row.grid(row=self.n, column=0, sticky="e" if me else "w", padx=10, pady=4)
            card = ctk.CTkFrame(row, corner_radius=THEME_STYLE["radius_control"], fg_color=PANEL, border_width=0 if me else THEME_STYLE["border_width"], border_color=THEME_COLORS["border_card"]); card.pack()
            lab = ctk.CTkLabel(card, text=text, wraplength=520, justify="left", anchor="w", text_color=PANEL, font=themed_font(14)); lab.pack(padx=15, pady=(9, 10))
            fade(card, "fg_color", THEME_COLORS["user_bubble"] if me else PANEL2, PANEL, steps=10); fade(lab, "text_color", TEXT, PANEL, steps=10)
        self.n += 1; self.rows.append(row)
        self.transcript.append((who, text))
        if len(self.transcript) > 60: self.transcript.pop(0)
        if len(self.rows) > 60: self.rows.pop(0).destroy()
        self.end(); return lab
    def end(self):
        def go():
            try: self._parent_canvas.yview_moveto(1.0)
            except Exception: pass
        self.after(50, go)

class Hero:
    """Renders the animated space scene (stars, nebula, glowing orb with voice bars) as a PIL image."""
    TINTS = ((255, 255, 255), (190, 210, 255), (215, 195, 255), (255, 235, 210))
    def __init__(self):
        self.w = self.h = 0; self.amp = 0.1; self.shoot = []; self.base = None; self.neb = []
        self.stars = [[random.random(), random.random(), random.random(), random.random() * 6.28, random.choice(self.TINTS)] for _ in range(140)]
        n = 220; y, x = np.mgrid[-1:1:n * 1j, -1:1:n * 1j]; r = np.hypot(x, y); z = np.sqrt(np.clip(1 - r * r, 0, 1))
        L = np.array([-0.45, -0.55, 0.70]); L /= np.linalg.norm(L); diff = np.clip(x * L[0] + y * L[1] + z * L[2], 0, 1)
        fres = np.clip((r - 0.55) / 0.45, 0, 1) ** 2 * 0.55
        self.shade = (0.28 + 0.80 * diff + fres * (1 - diff * 0.6)).astype(np.float32)[..., None]; self.spec = (diff ** 30 * 0.9).astype(np.float32)[..., None]
        self.oalpha = Image.fromarray((np.clip((1 - r) * n / 2, 0, 1) * 255).astype("uint8"), "L")
        m = 360; y, x = np.mgrid[-1:1:m * 1j, -1:1:m * 1j]; r2 = np.hypot(x, y)
        self.glow = Image.fromarray((np.exp(-(r2 * 2.6) ** 1.5) * 255 * (r2 < 1)).astype("uint8"), "L")

    @staticmethod
    def icon(px=64, col=None):
        col = col or THEME_COLORS["idle"]
        h = Hero.__new__(Hero); Hero.__init__(h); c = rgb(col)
        img = Image.new("RGBA", (px, px), (0, 0, 0, 0)); g = h.glow.resize((px, px), Image.BILINEAR)
        img.paste(Image.new("RGBA", (px, px), c + (255,)), (0, 0), g.point([int(v * 0.55) for v in range(256)]))
        d = int(px * 0.56); o = Image.fromarray(np.clip(np.array(c, "float32") * h.shade + 255 * h.spec, 0, 255).astype("uint8"), "RGB").resize((d, d), Image.LANCZOS)
        img.paste(o, ((px - d) // 2,) * 2, h.oalpha.resize((d, d), Image.LANCZOS)); return img

    def rebuild(self, w, h):
        self.w, self.h = w, h
        y, x = np.mgrid[0:h, 0:w].astype("float32"); ny, nx = y / h, x / w
        top, bot = np.array(rgb(SKY), "float32"), np.array(rgb(BG), "float32")
        g = top + (bot - top) * ny[..., None]; vig = 1 - 0.55 * (((nx - 0.5) * 1.1) ** 2 + ((ny - 0.5) * 1.3) ** 2)
        self.base = Image.fromarray(np.clip(g * vig[..., None], 0, 255).astype("uint8"), "RGB"); self.neb = []
        for col, fx, fy, size, k, sp, ph in ((ACC, 0.22, 0.40, 0.95, 0.55, 0.13, 0.0), (ACC2, 0.80, 0.62, 0.85, 0.50, 0.10, 2.0), (COLORS["speaking"], 0.58, 0.10, 0.60, 0.38, 0.16, 4.0)):
            s = int(max(w, h) * size); m = self.glow.resize((s, s), Image.BILINEAR).point([int(v * k) for v in range(256)])
            self.neb.append((Image.new("RGB", (s, s), rgb(col)), m, fx, fy, sp, ph))

    def render(self, w, h, t, mode, col, level, thr, on):
        if (w, h) != (self.w, self.h): self.rebuild(w, h)
        img = self.base.copy(); intro = ease(t / 1.3); c = rgb(col)
        for spr, m, fx, fy, sp, ph in self.neb:
            img.paste(spr, (int((fx + 0.035 * math.sin(t * sp + ph)) * w - spr.width / 2), int((fy + 0.045 * math.cos(t * sp * 0.8 + ph)) * h - spr.height / 2)), m)
        sl = Image.new("RGB", (w, h)); d = ImageDraw.Draw(sl)          # stars are added on top of the background (additive light)
        for s in self.stars:
            s[0] = (s[0] - 0.00012 * (0.3 + s[2] * 1.7)) % 1.0; x, y = s[0] * w, s[1] * h
            tw = (0.5 + 0.5 * math.sin(t * (0.8 + s[2] * 2) + s[3])) * (0.2 + 0.8 * s[2]) * intro
            f = tuple(int(v * tw) for v in s[4])
            if s[2] > 0.82:
                d.ellipse((x - 1.2, y - 1.2, x + 1.2, y + 1.2), fill=f); k = tuple(int(v * 0.35) for v in f)
                d.line((x - 4, y, x + 4, y), fill=k); d.line((x, y - 4, x, y + 4), fill=k)
            else: d.point((x, y), fill=f)
        if random.random() < 0.006 and len(self.shoot) < 2: self.shoot.append([random.uniform(0.35, 1.0) * w, random.uniform(0.0, 0.35) * h, -9.0, 4.2, 0])
        for s in self.shoot[:]:
            s[0] += s[2]; s[1] += s[3]; s[4] += 1; life = s[4] / 42
            if life >= 1 or s[0] < -40 or s[1] > h: self.shoot.remove(s); continue
            for i in range(9):
                a = (1 - i / 9) * (1 - life); d.line((s[0] - s[2] * i * 1.4, s[1] - s[3] * i * 1.4, s[0] - s[2] * (i + 1) * 1.4, s[1] - s[3] * (i + 1) * 1.4), fill=tuple(int(255 * a) for _ in range(3)), width=2 if i < 3 else 1)
        img = ImageChops.add(img, sl); d = ImageDraw.Draw(img)
        lvl = min(1.0, level / 2500) if on else 0.0
        target = {"listening": 0.15 + 0.85 * lvl, "speaking": 0.55 + 0.35 * math.sin(t * 7) ** 2, "thinking": 0.28, "muted": 0.0, "idle": 0.12}[mode]
        self.amp = self.amp * 0.78 + target * 0.22; a = self.amp
        R0 = min(h * 0.17, 58); R = R0 * intro * (1 + 0.05 * a + 0.02 * math.sin(t * 2)); cx, cy = w / 2, h * 0.47
        G = int(R * 7.2); gm = self.glow.resize((G, G), Image.BILINEAR).point([int(v * min(1.0, 0.50 + 0.35 * a + 0.12 * math.sin(t * 2.2))) for v in range(256)])
        img.paste(Image.new("RGB", (G, G), c), (int(cx - G / 2), int(cy - G / 2)), gm)
        B = int(R * 6.4); SS = 2; mk = Image.new("L", (B * SS, B * SS), 0); md = ImageDraw.Draw(mk); o = B * SS / 2
        r = R * 1.34 * SS; md.ellipse((o - r, o - r, o + r, o + r), outline=int(60 + 50 * a), width=3)
        N, sp = 72, (9 if mode == "speaking" else 3.2)
        for i in range(N):
            ang = i / N * 2 * math.pi; f = (0.5 + 0.5 * math.sin(t * sp + i * 0.55)) * (0.5 + 0.5 * math.sin(t * 1.7 - i * 0.21))
            sweep = max(0.0, math.cos(ang - t * 4)) ** 4 if mode == "thinking" else 0.0
            ln = R * (0.07 + 0.95 * a * f + 0.35 * sweep); r0 = R * 1.52 * SS; r1 = r0 + ln * SS
            md.line((o + r0 * math.cos(ang), o + r0 * math.sin(ang), o + r1 * math.cos(ang), o + r1 * math.sin(ang)), fill=int(95 + 160 * min(1.0, f * a * 1.6 + sweep + 0.1)), width=5)
        for i in range(6):
            ang = t * (0.35 + 0.07 * i) * (2.2 if mode == "thinking" else 1) + i * 1.05; orr = R * (2.55 + 0.2 * (i % 3)) * SS
            px, py, ps = o + orr * math.cos(ang), o + orr * 0.62 * math.sin(ang), (2.2 + (i % 3)) * SS; md.ellipse((px - ps, py - ps, px + ps, py + ps), fill=230)
        img.paste(Image.new("RGB", (B, B), c), (int(cx - B / 2), int(cy - B / 2)), mk.reduce(SS))
        D = max(4, int(R * 2)); core = Image.fromarray(np.clip(np.array(c, "float32") * self.shade + 255 * self.spec, 0, 255).astype("uint8"), "RGB").resize((D, D), Image.LANCZOS)
        img.paste(core, (int(cx - D / 2), int(cy - D / 2)), self.oalpha.resize((D, D), Image.LANCZOS))
        bw, by = 260, h - 14; x0 = int(cx - bw / 2); d.rounded_rectangle((x0, by - 2, x0 + bw, by + 2), 2, fill=(22, 27, 62))
        if lvl > 0: d.rounded_rectangle((x0, by - 2, x0 + int(bw * lvl), by + 2), 2, fill=c)
        tx = x0 + int(bw * min(1.0, thr / 2500)); d.line((tx, by - 5, tx, by + 5), fill=(235, 238, 255))
        return img


class Jarvis(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark"); self.title("JARVIS"); self.geometry("1200x790"); self.minsize(1040, 700); self.configure(fg_color=BG)
        self.cfg = json.loads(json.dumps(DEFAULT))
        try: self.cfg.update(json.load(open(CFG, encoding="utf-8")))
        except Exception: pass
        global THEMES
        THEMES = discover_themes()
        if not THEMES:
            THEMES["space"] = {"name": "Space", "colors": dict(THEME_DEFAULTS)}
        self.cfg["theme"] = self.cfg.get("theme", "space")
        if self.cfg["theme"] not in THEMES: self.cfg["theme"] = next(iter(THEMES))
        activate_theme(self.cfg["theme"])
        self.configure(fg_color=BG)
        self.theme_scan_t = time.time()
        if self.cfg.get("gemini_model", "") in OLD_MODELS: self.cfg["gemini_model"] = GEMINI_MODEL
        self.q, self.mode, self.t, self.on, self.running = queue.Queue(), "idle", 0.0, True, True
        self.stream, self.history, self.search_ok, self.found = None, [], True, {}
        self.speaking, self.reopen, self.level, self.noise, self.thr, self.session, self.warned, self.tray = False, False, 0.0, 60.0, 120.0, 0.0, {}, None
        self.uq, self.g_think, self.t_cmd, self.ai_err, self.part_err, self.good_model, self.ai_errs = queue.Queue(), 2, time.time(), None, None, None, []
        self.hist, self.last_read, self.opening, self.speak_t0 = collections.deque(maxlen=120), time.time(), True, 0.0
        self.col, self.page, self.sliding, self.ind_y, self.pages, self.navs, self.shoot = COLORS["idle"], "home", False, 118, {}, [], []
        self.cur, self.toast_f, self.hero, self.hero_photo, self.hero_size, self.frame_ms, self.last_frame, self.txt = None, None, None, None, (0, 0), 10.0, time.time(), {}
        self.files, self.file_scan_t, self.cool, self.ai_wait, self.ai_daily, self.last_q, self.last_t = [], 0.0, {}, 0.0, False, "", 0.0
        self.build_ui(); self.refresh_apps(); self.start_tray()
        try: self.icon_img = ImageTk.PhotoImage(Hero.icon(64)); self.iconphoto(True, self.icon_img)
        except Exception as err: print('icon error:', err)
        threading.Thread(target=lambda: self.q.put(("found", discover())), daemon=True).start(); threading.Thread(target=lambda: self.q.put(("files", index_files())), daemon=True).start()
        threading.Thread(target=self.voice_loop, daemon=True).start(); threading.Thread(target=self.worker, daemon=True).start()
        self.after(60, self.pump); self.after(33, self.animate)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if "--hidden" in sys.argv and self.tray: self.after(300, self.withdraw)

    def report_callback_exception(self, *a): traceback.print_exception(*a)

    # ---------- UI ----------
    def build_ui(self):
        # Resolve the palette immediately before constructing widgets so startup,
        # theme changes, and UI rebuilds all use the same selected JSON theme.
        activate_theme(self.cfg.get("theme", "space"))
        self.configure(fg_color=BG)
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        side = ctk.CTkFrame(self, width=THEME_STYLE["sidebar_width"], fg_color=PANEL, corner_radius=0); side.grid(row=0, column=0, sticky="ns"); side.grid_propagate(False)
        if HAVE_PIL:
            try:
                self.logo = ctk.CTkImage(light_image=Hero.icon(96), dark_image=Hero.icon(96), size=(48, 48))
                ctk.CTkLabel(side, image=self.logo, text="").place(x=18, y=18)
            except Exception as err:
                print("logo error:", err)
                ctk.CTkLabel(side, text="◉", font=("Segoe UI Symbol", 32), text_color=ACC2).place(x=22, y=15)
        else:
            ctk.CTkLabel(side, text="◉", font=("Segoe UI Symbol", 32), text_color=ACC2).place(x=22, y=15)
        ctk.CTkLabel(side, text="JARVIS", font=themed_font(21, True), text_color=TEXT).place(x=76, y=22)
        ctk.CTkLabel(side, text="AI assistant", font=themed_font(12), text_color=MUTED).place(x=77, y=50)
        ctk.CTkFrame(side, height=1, width=192, fg_color=LINE).place(x=20, y=92)
        self.indicator = ctk.CTkFrame(side, width=4, height=40, fg_color=ACC2, corner_radius=2); self.indicator.place(x=0, y=self.ind_y)
        for i, (key, label) in enumerate(NAV):
            b = AnimButton(side, PANEL2 if i == 0 else PANEL, PANEL2 if i == 0 else THEME_COLORS["nav_hover"], text=label, anchor="w", width=192, height=42, corner_radius=THEME_STYLE["radius_control"],
                           text_color=TEXT, font=themed_font(14, True), command=lambda k=key: self.show_page(k)); b.place(x=20, y=118 + i * 52); self.navs.append(b)
        card = ctk.CTkFrame(side, fg_color=PANEL2, corner_radius=THEME_STYLE["radius_card"], width=192, height=100); card.place(x=20, rely=1.0, y=-120); card.pack_propagate(False)
        self.dot = ctk.CTkLabel(card, text="●  Ready", font=themed_font(14, True), text_color=COLORS["idle"]); self.dot.place(x=16, y=12)
        self.mic = AnimButton(card, LINE, THEME_COLORS["mic_hover"], text="Mic on", width=160, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], font=themed_font(13, True), text_color=TEXT, command=self.toggle); self.mic.place(x=16, y=48)
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0); self.content.grid(row=0, column=1, sticky="nsew")
        # --- assistant page
        home = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0); home.grid_rowconfigure(2, weight=1); home.grid_columnconfigure(0, weight=1)
        self.sky = ctk.CTkCanvas(home, height=330, bg=SKY, highlightthickness=THEME_STYLE["border_width_emphasis"], highlightbackground=THEME_COLORS["border_emphasis"]); self.sky.grid(row=0, column=0, sticky="ew", padx=THEME_STYLE["page_padding"], pady=(THEME_STYLE["page_padding"], 10)); self.init_hero()
        chips = ctk.CTkFrame(home, fg_color="transparent"); chips.grid(row=1, column=0, sticky="w", padx=THEME_STYLE["page_padding"], pady=(0, 10))
        for text in CHIPS: AnimButton(chips, PANEL2, LINE, text=text, height=32, corner_radius=THEME_STYLE["radius_pill"], font=themed_font(12), text_color=TEXT, command=lambda t=text: self.run(self.handle, t, True)).pack(side="left", padx=(0, 8))
        self.chat = ChatView(home); self.chat.grid(row=2, column=0, sticky="nsew", padx=THEME_STYLE["page_padding"])
        bar = ctk.CTkFrame(home, fg_color="transparent"); bar.grid(row=3, column=0, padx=THEME_STYLE["page_padding"], pady=14, sticky="ew"); bar.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(bar, placeholder_text="Type a command or a question...", height=max(40, THEME_STYLE["control_height"] + 8), corner_radius=THEME_STYLE["radius_control"], fg_color=PANEL2, border_color=THEME_COLORS["border_control"], border_width=THEME_STYLE["border_width"]); self.entry.grid(row=0, column=0, sticky="ew"); self.entry.bind("<Return>", self.send); self.bind_entry_theme(self.entry)
        AnimButton(bar, ACC, THEME_COLORS["accent_hover"], text="Send", width=92, height=44, corner_radius=THEME_STYLE["radius_control"], font=themed_font(14, True), text_color="#ffffff", command=self.send).grid(row=0, column=1, padx=(10, 0))
        # --- apps page
        apps = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0); apps.grid_columnconfigure(0, weight=1); apps.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(apps, fg_color="transparent"); top.grid(row=0, column=0, sticky="ew", padx=THEME_STYLE["page_padding"], pady=(24, 0)); top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Apps", font=themed_font(28, True), text_color=TEXT).grid(row=0, column=0, sticky="w")
        self.search = ctk.CTkEntry(top, placeholder_text="Search apps...", width=250, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], fg_color=PANEL2, border_color=THEME_COLORS["border_control"], border_width=THEME_STYLE["border_width"]); self.search.grid(row=0, column=1); self.search.bind("<KeyRelease>", lambda e: self.refresh_apps()); self.bind_entry_theme(self.search)
        self.count = ctk.CTkLabel(apps, text="", text_color=MUTED, anchor="w"); self.count.grid(row=1, column=0, sticky="w", padx=28, pady=(0, 6))
        self.applist = ctk.CTkScrollableFrame(apps, fg_color=BG, corner_radius=0); self.applist.grid(row=2, column=0, sticky="nsew", padx=16)
        for c in range(3): self.applist.grid_columnconfigure(c, weight=1, uniform="tile")
        add = ctk.CTkFrame(apps, fg_color=PANEL, corner_radius=THEME_STYLE["radius_card"], border_width=THEME_STYLE["border_width"], border_color=THEME_COLORS["border_card"]); add.grid(row=3, column=0, sticky="ew", padx=THEME_STYLE["page_padding"], pady=16); add.grid_columnconfigure(1, weight=1)
        self.an = ctk.CTkEntry(add, placeholder_text="Name you will say", width=190, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], fg_color=PANEL2, border_color=THEME_COLORS["border_control"], border_width=THEME_STYLE["border_width"]); self.an.grid(row=0, column=0, padx=14, pady=14); self.bind_entry_theme(self.an)
        self.ap = ctk.CTkEntry(add, placeholder_text="Path, website or link", height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], fg_color=PANEL2, border_color=THEME_COLORS["border_control"], border_width=THEME_STYLE["border_width"]); self.ap.grid(row=0, column=1, sticky="ew", pady=14); self.bind_entry_theme(self.ap)
        AnimButton(add, PANEL2, LINE, text="File", width=64, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=TEXT, command=self.browse).grid(row=0, column=2, padx=(8, 4))
        AnimButton(add, PANEL2, LINE, text="Folder", width=70, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=TEXT, command=self.browse_dir).grid(row=0, column=3, padx=4)
        AnimButton(add, ACC, THEME_COLORS["accent_hover"], text="Add", width=84, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color="#ffffff", font=themed_font(13, True), command=self.add_app).grid(row=0, column=4, padx=(4, 14))
        # --- settings page
        sp = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0); sp.grid_columnconfigure(0, weight=1); sp.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(sp, text="Settings", font=themed_font(28, True), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=26, pady=(24, 6))
        s = ctk.CTkScrollableFrame(sp, fg_color=BG, corner_radius=0); s.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14)); s.grid_columnconfigure(0, weight=1)
        E = dict(fg_color=PANEL2, border_color=THEME_COLORS["border_control"], border_width=THEME_STYLE["border_width"], height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"])
        M = dict(fg_color=PANEL2, button_color=ACC, button_hover_color=THEME_COLORS["option_hover"], dropdown_fg_color=PANEL2, dropdown_hover_color=THEME_COLORS["border_focus"], height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"])
        sr, rows = [0], {}
        def section(title, sub=""):
            f = ctk.CTkFrame(s, fg_color=PANEL, corner_radius=THEME_STYLE["radius_card"], border_width=THEME_STYLE["border_width"], border_color=THEME_COLORS["border_card"]); f.grid(row=sr[0], column=0, sticky="ew", padx=6, pady=7); sr[0] += 1; f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(f, text=title, font=themed_font(16, True), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
            if sub: ctk.CTkLabel(f, text=sub, font=themed_font(12), text_color=MUTED, wraplength=560, justify="left").grid(row=1, column=0, sticky="w", padx=18)
            rows[f] = 2; return f
        def put(f, w, label=None):
            if label: ctk.CTkLabel(f, text=label, anchor="w", font=themed_font(12), text_color=MUTED).grid(row=rows[f], column=0, sticky="ew", padx=18, pady=(10, 0)); rows[f] += 1
            w.grid(row=rows[f], column=0, sticky="ew", padx=18, pady=(3, 0)); rows[f] += 1; return w
        def done(f): ctk.CTkFrame(f, height=14, fg_color="transparent").grid(row=rows[f], column=0)
        f = section("Appearance", "Themes are loaded from the themes folder. Add a JSON file there to make it available.")
        self.theme_menu = put(f, ctk.CTkOptionMenu(f, values=[], command=self.select_theme, **M), "Theme")
        self.refresh_themes()
        put(f, ctk.CTkLabel(f, text=f"Theme folder: {THEMES_DIR}", text_color=MUTED, wraplength=560, justify="left", anchor="w")); done(f)
        f = section("Assistant", "How Jarvis talks to you and when he answers.")
        self.name = put(f, ctk.CTkEntry(f, placeholder_text="Your name (optional)", **E), "What should Jarvis call you?"); self.name.insert(0, self.cfg["name"])
        self.respond = put(f, ctk.CTkOptionMenu(f, values=MODES, command=lambda v: self.save("listen_mode", v), **M), "When should he respond?"); self.respond.set(self.cfg["listen_mode"])
        self.lang = put(f, ctk.CTkOptionMenu(f, values=list(LANGS), command=lambda v: self.save("lang", v), **M), "Language you speak"); self.lang.set(self.cfg["lang"]); done(f)
        f = section("Voice", "Natural voices need internet. The Windows voice works offline.")
        self.voice = put(f, ctk.CTkOptionMenu(f, values=list(VOICES), command=lambda v: self.save("voice", v), **M), "Voice"); self.voice.set(self.cfg["voice"])
        self.speed = put(f, ctk.CTkSlider(f, from_=-30, to=40, progress_color=ACC, button_color=ACC2, command=lambda v: self.save("speed", int(v))), "Speaking speed"); self.speed.set(self.cfg["speed"])
        put(f, AnimButton(f, PANEL2, LINE, text="Test voice", height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=TEXT, command=lambda: self.run(self.say, "Hello, I am Jarvis. How do I sound?"))); done(f)
        f = section("Microphone", "The bar under the orb shows your voice. The white mark is where he starts listening.")
        names = mic_names(); self.micmenu = put(f, ctk.CTkOptionMenu(f, values=names, command=self.set_mic, **M), "Microphone"); self.micmenu.set(self.cfg["mic"] if self.cfg["mic"] in names else "Default")
        self.sens = put(f, ctk.CTkSlider(f, from_=1, to=10, number_of_steps=9, progress_color=ACC, button_color=ACC2, command=lambda v: self.save("sens", int(v))), "Sensitivity (raise it if he misses your voice)"); self.sens.set(self.cfg["sens"]); done(f)
        f = section("AI brain", "A free Gemini key from aistudio.google.com is enough. A Claude key is optional.")
        self.gk = put(f, ctk.CTkEntry(f, show="*", **E), "Gemini key"); self.gk.insert(0, self.cfg["gemini_key"])
        self.gm = put(f, ctk.CTkEntry(f, **E), "Gemini model (filled in automatically)"); self.gm.insert(0, self.cfg.get("gemini_model") or GEMINI_MODEL)
        self.ck = put(f, ctk.CTkEntry(f, show="*", **E), "Claude key (optional)"); self.ck.insert(0, self.cfg["claude_key"])
        put(f, AnimButton(f, ACC, THEME_COLORS["accent_hover"], text="Save name and keys", height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color="#ffffff", font=themed_font(13, True), command=self.save_keys))
        put(f, AnimButton(f, PANEL2, LINE, text="Test AI connection", height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=TEXT, command=lambda: self.run(self.ask, "Say hello in one short friendly sentence."))); done(f)
        f = section("System")
        sw = put(f, ctk.CTkSwitch(f, text="Start with Windows (runs in the tray)", progress_color=ACC, command=lambda: self.set_startup(sw.get()))); sw.select() if self.cfg["startup"] else sw.deselect()
        put(f, ctk.CTkLabel(f, text="Closing the window keeps Jarvis listening from the system tray (near the clock).", text_color=MUTED, wraplength=520, justify="left", anchor="w"))
        put(f, AnimButton(f, THEME_COLORS["danger"], THEME_COLORS["danger_hover"], text="Quit Jarvis", height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=THEME_COLORS["danger_text"], command=self.quit_app)); done(f)
        self.pages = {"home": home, "apps": apps, "settings": sp}; home.place(relx=0, rely=0, relwidth=1, relheight=1)

    def refresh_themes(self):
        global THEMES
        latest = discover_themes()
        if latest: THEMES = latest
        if self.cfg.get("theme") not in THEMES: self.cfg["theme"] = next(iter(THEMES), "space")
        if hasattr(self, "theme_menu"):
            labels = [theme["name"] for theme in THEMES.values()]
            self.theme_names = {theme["name"]: key for key, theme in THEMES.items()}
            self.theme_menu.configure(values=labels)
            self.theme_menu.set(THEMES[self.cfg["theme"]]["name"])

    def bind_entry_theme(self, entry):
        entry.bind("<FocusIn>", lambda _event, w=entry: w.configure(border_color=THEME_COLORS["border_focus"]), add="+")
        entry.bind("<FocusOut>", lambda _event, w=entry: w.configure(border_color=THEME_COLORS["border_control"]), add="+")

    def select_theme(self, label):
        theme_id = getattr(self, "theme_names", {}).get(label)
        if not theme_id or theme_id == self.cfg.get("theme"): return
        self.cfg["theme"] = theme_id
        self.persist()
        activate_theme(theme_id)
        self.configure(fg_color=BG)
        page, transcript = self.page, list(getattr(self.chat, "transcript", []))
        for child in self.winfo_children(): child.destroy()
        self.navs = []; self.pages = {}; self.build_ui()
        if HAVE_PIL:
            try: self.icon_img = ImageTk.PhotoImage(Hero.icon(64)); self.iconphoto(True, self.icon_img)
            except Exception as err: print("icon refresh error:", err)
        for who, message in transcript: self.chat.bubble(who, message)
        self.refresh_apps()
        self.page = "home"
        if page != "home":
            self.pages[page].place(relx=0, rely=0, relwidth=1, relheight=1)
            for key, button in zip((k for k, _ in NAV), self.navs): button.set_active(key == page)
            self.page = page
        self.col = COLORS.get(self.mode, COLORS["idle"])


    def show_page(self, key):
        if key == self.page or self.sliding: return
        keys = [k for k, _ in NAV]; d = 1 if keys.index(key) > keys.index(self.page) else -1
        old, new = self.pages[self.page], self.pages[key]; self.page, self.sliding = key, True
        for k, b in zip(keys, self.navs): b.set_active(k == key)
        y0, y1 = self.ind_y, 118 + keys.index(key) * 52; self.ind_y = y1
        new.place(relx=0.12 * d, rely=0, relwidth=1, relheight=1); new.lift()
        def step(i=0):
            e = ease(i / 16); new.place(relx=0.12 * d * (1 - e), rely=0, relwidth=1, relheight=1); self.indicator.place(x=0, y=int(y0 + (y1 - y0) * e))
            if i < 16: self.after(14, step, i + 1)
            else: old.place_forget(); self.sliding = False
        step()

    def refresh_apps(self):
        for w in self.applist.winfo_children(): w.destroy()
        q = self.search.get().strip().lower() if hasattr(self, "search") else ""
        for i, (name, target) in enumerate([(n, t) for n, t in sorted(self.cfg["apps"].items()) if q in n.lower()]): self.tile(i, name, str(target))
        self.count.configure(text=f"{len(self.cfg['apps'])} saved apps  Â·  {len(self.found)} more found on this PC  Â·  {len(self.files)} files and folders indexed. Say a name and he opens it.")

    def tile(self, i, name, target):
        card = ctk.CTkFrame(self.applist, corner_radius=THEME_STYLE["radius_card"], fg_color=PANEL, border_width=THEME_STYLE["border_width"], border_color=THEME_COLORS["border_card"]); card.grid(row=i // 3, column=i % 3, padx=7, pady=7, sticky="nsew")
        ic = ctk.CTkFrame(card, width=48, height=48, corner_radius=THEME_STYLE["radius_avatar"], fg_color=AVATARS[sum(map(ord, name)) % len(AVATARS)]); ic.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w"); ic.grid_propagate(False)
        ctk.CTkLabel(ic, text=name[:1].upper(), font=themed_font(21, True), text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(card, text="×", width=26, height=26, corner_radius=THEME_STYLE["radius_small"], fg_color=PANEL, hover_color=THEME_COLORS["close_hover"], text_color=MUTED, command=lambda n=name: self.remove(n)).place(relx=1.0, x=-10, y=10, anchor="ne")
        ctk.CTkLabel(card, text=name.title(), font=themed_font(15, True), text_color=TEXT, anchor="w").grid(row=1, column=0, sticky="w", padx=18)
        ctk.CTkLabel(card, text=(target if len(target) < 26 else target[:23] + "..."), font=themed_font(11), text_color=MUTED, anchor="w").grid(row=2, column=0, sticky="w", padx=18)
        btns = ctk.CTkFrame(card, fg_color="transparent"); btns.grid(row=3, column=0, sticky="w", padx=12, pady=(10, 16))
        AnimButton(btns, ACC, THEME_COLORS["accent_hover"], text="Open", width=72, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color="#ffffff", command=lambda n=name, t=target: self.run(self.launch, n, t)).pack(side="left", padx=4)
        AnimButton(btns, LINE, THEME_COLORS["mic_hover"], text="Close", width=72, height=THEME_STYLE["control_height"], corner_radius=THEME_STYLE["radius_control"], text_color=TEXT, command=lambda n=name, t=target: self.run(self.close_app, n, t)).pack(side="left", padx=2)
        def inside(e):
            w = card.winfo_containing(e.x_root, e.y_root)
            while w is not None:
                if w is card: return True
                w = getattr(w, "master", None)
            return False
        def enter(e): fade(card, "border_color", ACC, LINE); fade(card, "fg_color", PANEL2, PANEL)
        def leave(e):
            if not inside(e): fade(card, "border_color", LINE, LINE); fade(card, "fg_color", PANEL, PANEL)
        for w in [card] + list(card.winfo_children()):
            try: w.bind("<Enter>", enter, add="+"); w.bind("<Leave>", leave, add="+")
            except Exception: pass

    def browse(self):
        p = filedialog.askopenfilename(title="Pick an app or shortcut", filetypes=[("All files", "*.*"), ("Apps", "*.exe *.lnk *.url *.bat")])
        if p:
            self.ap.delete(0, "end"); self.ap.insert(0, p)
            if not self.an.get(): self.an.insert(0, os.path.splitext(os.path.basename(p))[0].lower())

    def browse_dir(self):
        p = filedialog.askdirectory(title="Pick a folder")
        if p:
            self.ap.delete(0, "end"); self.ap.insert(0, os.path.normpath(p))
            if not self.an.get(): self.an.insert(0, os.path.basename(p).lower())

    def add_app(self):
        n, p = self.an.get().strip().lower(), self.ap.get().strip().strip('"')
        if n and p:
            self.cfg["apps"][n] = p; self.persist(); self.an.delete(0, "end"); self.ap.delete(0, "end"); self.refresh_apps(); self.toast(f"Added {n}. Say \"open {n}\".")

    def remove(self, n): self.cfg["apps"].pop(n, None); self.persist(); self.refresh_apps()
    def save(self, k, v): self.cfg[k] = v; self.persist()
    def set_mic(self, v): self.save("mic", v); self.reopen = True
    def save_keys(self):
        self.cfg.update(gemini_key=self.gk.get().strip(), claude_key=self.ck.get().strip(), name=self.name.get().strip(), gemini_model=self.gm.get().strip() or GEMINI_MODEL)
        self.persist(); self.search_ok, self.g_think, self.good_model = True, 2, None; self.toast("Saved.")
    def persist(self):
        try: json.dump(self.cfg, open(CFG, "w", encoding="utf-8"), indent=2)
        except OSError as err: print("config save error:", err)
    def toggle(self):
        self.on = not self.on; self.mic.configure(text="Mic on" if self.on else "Muted", text_color=TEXT if self.on else THEME_COLORS["danger_text_active"])
        old = self.mic.base; self.mic.base, self.mic.hov = (LINE, THEME_COLORS["mic_hover"]) if self.on else (THEME_COLORS["muted_button"], THEME_COLORS["muted_button_hover"]); fade(self.mic, "fg_color", self.mic.base, old)
        if self.on: self.hist.clear()
        else: self.drain()
        self.set_state("idle" if self.on else "muted")
    def drain(self):
        while not self.uq.empty():
            try: self.uq.get_nowait()
            except queue.Empty: break
    def send(self, _=None):
        t = self.entry.get().strip()
        if t: self.entry.delete(0, "end"); self.run(self.handle, t, True)
    def run(self, fn, *a): threading.Thread(target=fn, args=a, daemon=True).start()
    def log(self, who, text): self.q.put(("log", (who, text)))
    def set_state(self, s): self.q.put(("state", s))

    def toast(self, text):
        try: self.toast_f.destroy()
        except Exception: pass
        f = ctk.CTkFrame(self, corner_radius=THEME_STYLE["radius_card"], fg_color=PANEL2, border_width=THEME_STYLE["border_width_emphasis"], border_color=THEME_COLORS["border_emphasis"]); self.toast_f = f
        ctk.CTkLabel(f, text=text, font=themed_font(13), text_color=TEXT, wraplength=340, justify="left").pack(padx=18, pady=11)
        def pos(y):
            try: f.place(relx=1.0, rely=1.0, x=-26, y=y, anchor="se"); f.lift()
            except Exception: pass
        def go_in(i=0):
            if self.toast_f is not f: return
            pos(int(90 - 116 * ease(i / 14)))
            if i < 14: self.after(16, go_in, i + 1)
            else: self.after(2600, go_out)
        def go_out(i=0):
            if self.toast_f is not f: return
            pos(int(-26 + 116 * ease(i / 14)))
            if i < 14: self.after(16, go_out, i + 1)
            else: f.destroy()
        go_in()

    def pump(self):
        if time.time() - self.theme_scan_t >= 2.0:
            self.theme_scan_t = time.time()
            self.refresh_themes()
        try:
            while True:
                k, a = self.q.get_nowait()
                if k == "log":
                    self.chat.bubble(a[0], a[1])
                    if a[0] == "System" and len(a[1]) < 140: self.toast(a[1])
                elif k == "add":
                    first, txt = a
                    if first: self.cur = self.chat.bubble("Jarvis", txt.strip())
                    elif self.cur is not None and txt.strip(): self.cur.configure(text=self.cur.cget("text") + txt); self.chat.end()
                elif k == "state":
                    if (a == "muted") != self.on:
                        self.mode = a; self.dot.configure(text="●  " + {"idle": "Ready", "muted": "Muted"}.get(a, a.capitalize()), text_color=COLORS[a])
                elif k == "found": self.found = a; self.refresh_apps()
                elif k == "files": self.files = a; self.refresh_apps()
                elif k == "show": self.deiconify(); self.lift(); self.focus_force()
                elif k == "toggle": self.toggle()
                elif k == "quit": self.quit_app()
        except queue.Empty: pass
        if self.on and not self.opening and self.stream is not None and time.time() - self.last_read > 5:   # microphone froze: force a reopen
            self.last_read = time.time(); print("mic stalled, restarting it")
            try: self.stream.abort()
            except Exception: pass
        self.after(60, self.pump)

    # ---------- animated space hero ----------
    def init_hero(self):
        c = self.sky; self.hero = Hero() if HAVE_PIL else None
        self.hero_item = c.create_image(0, 0, anchor="nw")
        self.greet = c.create_text(28, 24, anchor="nw", text="", fill=TEXT, font=themed_font(21, True))
        self.subtxt = c.create_text(29, 58, anchor="nw", text="", fill=MUTED, font=themed_font(12))
        self.chip = c.create_text(0, 0, anchor="ne", text="", fill=ACC, font=themed_font(13, True))
        self.clock = c.create_text(0, 0, anchor="ne", text="", fill=MUTED, font=themed_font(11))
        self.hint = c.create_text(0, 0, text='Try "open discord download page", "search for pizza near me", "open downloads" or ask anything', fill=MUTED, font=themed_font(11))

    def animate(self):
        t0 = time.time()
        try: self.draw_hero()
        except Exception: traceback.print_exc()
        self.frame_ms = 0.85 * self.frame_ms + 0.15 * (time.time() - t0) * 1000
        self.after(33 if self.frame_ms < 24 else 50, self.animate)       # slow PCs get a lower frame rate instead of lag

    def draw_hero(self):
        if self.hero is None or self.page != "home" or not self.winfo_viewable(): return
        c = self.sky; w, h = c.winfo_width(), c.winfo_height()
        if w < 160 or h < 160: return
        now = time.time(); self.t += min(0.1, now - self.last_frame); self.last_frame = now; self.col = mix(self.col, COLORS[self.mode], 0.12)
        img = self.hero.render(w, h, self.t, self.mode, self.col, self.level, self.thr, self.on)
        if self.hero_photo is None or self.hero_size != (w, h): self.hero_photo = ImageTk.PhotoImage(img); self.hero_size = (w, h); c.itemconfig(self.hero_item, image=self.hero_photo)
        else: self.hero_photo.paste(img)
        hr, n = datetime.now().hour, self.cfg.get("name", "")
        want = {self.greet: ("Good morning" if hr < 12 else "Good afternoon" if hr < 18 else "Good evening") + (f", {n}" if n else ""), self.subtxt: SUBS[self.mode],
                self.chip: CHIPTXT[self.mode], self.clock: datetime.now().strftime("%A %d %B  Â·  %H:%M")}
        for it, tx in want.items():
            if self.txt.get(it) != tx: self.txt[it] = tx; c.itemconfig(it, text=tx)
        c.itemconfig(self.chip, fill=self.col); c.coords(self.chip, w - 26, 26); c.coords(self.clock, w - 26, 50); c.coords(self.hint, w / 2, h - 34)

    # ---------- background / tray ----------
    def start_tray(self):
        if not pystray or not HAVE_PIL: return
        try:
            img = Hero.icon(64)
            m = pystray.Menu(pystray.MenuItem("Show Jarvis", lambda i, it: self.q.put(("show", None)), default=True),
                             pystray.MenuItem("Mute / unmute mic", lambda i, it: self.q.put(("toggle", None))),
                             pystray.MenuItem("Quit", lambda i, it: self.q.put(("quit", None))))
            self.tray = pystray.Icon("jarvis", img, "Jarvis", m); self.tray.run_detached()
        except Exception as err: print("tray error:", err); self.tray = None

    def on_close(self):
        if self.tray: self.withdraw(); self.log("Jarvis", "Still listening in the tray. Right-click the tray icon to quit.")
        else: self.quit_app()

    def quit_app(self):
        self.running = False
        for fn in (lambda: self.tray.stop(), lambda: self.stream.abort(), lambda: self.stream.close()):
            try: fn()
            except Exception: pass
        self.destroy()

    def set_startup(self, on):
        self.save("startup", bool(on))
        path = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup", "Jarvis.vbs")
        try:
            if on:
                exe = sys.executable; pyw = exe[:-10] + "pythonw.exe" if exe.lower().endswith("python.exe") else exe
                open(path, "w").write('CreateObject("WScript.Shell").Run """%s"" ""%s"" --hidden", 0, False\n' % (pyw, os.path.join(HERE, "jarvis.py")))
            elif os.path.exists(path): os.remove(path)
        except OSError as err: self.log("System", f"Could not change the startup setting: {err}")

    # ---------- voice out ----------
    def say(self, text): self.say_parts([text])

    def tts_file(self, text, voice):
        key = hashlib.md5(f"{voice}|{self.cfg['speed']}|{text}".encode()).hexdigest()[:16]; keep = len(text) <= 70
        path = os.path.join(CACHE, ("" if keep else "tmp_") + key + ".mp3")
        if not os.path.exists(path):
            tmp = path + ".part"       # write to a temp name so a failed download is never played later
            async def go(): await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=f"{int(self.cfg['speed']):+d}%").save(tmp), 15)
            try:
                asyncio.run(go())
                if os.path.getsize(tmp) < 500: raise OSError("empty audio")
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except OSError: pass
        return path, keep

    def play(self, path, max_s=90):
        buf = ctypes.create_unicode_buffer(32); _mci("close jv", None, 0, None)
        if _mci(f'open "{path}" type mpegvideo alias jv', None, 0, None) != 0: raise OSError("cannot open audio")
        ctypes.windll.winmm.mciSendStringW("status jv length", buf, 32, None)
        try: length = int(buf.value) / 1000
        except ValueError: length = None
        if length is not None and length < 0.2: _mci("close jv", None, 0, None); raise OSError("empty audio")
        t0 = time.time(); _mci("play jv", None, 0, None); time.sleep(0.05); end = t0 + (length + 3 if length else max_s)
        while time.time() < end:
            ctypes.windll.winmm.mciSendStringW("status jv mode", buf, 32, None)
            if buf.value != "playing": break
            time.sleep(0.03)
        _mci("close jv", None, 0, None)
        if length and time.time() - t0 < length * 0.4: raise OSError("playback ended too early")

    def offline(self, text):   # Windows built-in voice through PowerShell (works from any thread)
        try: sh(["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([Console]::In.ReadToEnd())"], input=text, timeout=120)
        except Exception as err: print("offline voice error:", err)

    def say_parts(self, parts):
        """Show and speak sentences as they arrive; the next one is prepared while the current one plays."""
        with SPEECH_LOCK:
            self.part_err = None; shown, started = [False], [False]
            voice = VOICES.get(self.cfg["voice"], "windows"); edge = voice != "windows" and edge_tts is not None and _mci is not None
            clean = lambda t: re.sub(r"https?://\S+|[*_#`]", "", t).strip()
            def show(p): self.q.put(("add", (not shown[0], (" " if shown[0] else "") + p))); shown[0] = True
            def begin():     # the orb says "speaking" and the mic ignores his voice only once sound really starts
                if not started[0]:
                    started[0] = True; self.speaking, self.speak_t0 = True, time.time(); self.set_state("speaking")
                    print(f"latency: {time.time() - self.t_cmd:.1f}s from understood text to first sound")
            def sound(p, path, keep):
                begin()
                try: self.play(path)
                except Exception as err: print("play error:", err); self.offline(p)
                if not keep:
                    try: os.remove(path)
                    except OSError: pass
            try:
                try:
                    if edge:
                        pq = queue.Queue()
                        def producer():
                            failed = False
                            try:
                                for p in parts:
                                    p = clean(p)
                                    if not p: continue
                                    show(p)
                                    if not failed:
                                        try: pq.put((p, *self.tts_file(p, voice)))
                                        except Exception as err:
                                            print("voice error:", err); failed = True
                                            if time.time() - self.warned.get("tts", 0) > 300:
                                                self.warned["tts"] = time.time(); self.log("System", "The natural voice is unavailable, so I am using the Windows voice. Check your internet, or run: pip install -U edge-tts")
                                    if failed: pq.put((p, None, False))
                            except Exception as err: self.part_err = err
                            pq.put(None)
                        threading.Thread(target=producer, daemon=True).start()
                        while True:
                            try: it = pq.get(timeout=30)
                            except queue.Empty: print("voice pipeline timed out"); break
                            if it is None: break
                            p, path, keep = it
                            if path: sound(p, path, keep)
                            else: begin(); self.offline(p)
                    else:
                        text = " ".join(clean(p) for p in parts)
                        if text: show(text); begin(); self.offline(text)
                except Exception as err: self.part_err = err
                if shown[0]: self.q.put(("add", (False, "\n\n")))
            finally:
                if started[0]: time.sleep(0.25)
                self.speaking = False; self.set_state("idle" if self.on else "muted")

    # ---------- apps ----------
    def table(self):
        t = dict(self.found)
        for n, p in BUILTIN.items(): t[norm(n)] = (n, p)
        for n, p in KF.items(): t[norm(n)] = (n, p)             # downloads, documents, desktop, pictures, music, videos
        for n, p in self.cfg["apps"].items(): t[norm(n)] = (n, p)
        return t

    def launch(self, name, target):
        try:
            if str(target).startswith("http"):
                if not open_url(str(target)): raise OSError("browser")
            else: os.startfile(target)
        except Exception as err: print("launch error:", name, err); return self.say(f"Sorry, I could not open {name}.")
        self.say(f"Opening {name}.")

    def close_app(self, name, target):
        if norm(name) in ("thispc", "fileexplorer") or os.path.isdir(str(target)) or str(target).startswith("shell:"):
            sh(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).Windows() | ForEach-Object { $_.Quit() }"]); return self.say("Closed.")
        t = str(target); exes = PROCS.get(name.lower())
        if not exes: exe = os.path.basename(t) if t.lower().endswith(".exe") else lnk_exe(t); exes = [exe] if exe else []
        if not exes: return self.say(f"I can't close {name}. It may be a website or a Store app.")
        ok = False
        for x in exes: ok = sh(["taskkill", "/IM", x, "/F"]).returncode == 0 or ok
        self.say(f"Closed {name}." if ok else f"{name} is not running.")

    # ---------- AI ----------
    def system(self):
        n = self.cfg["name"]
        return ("You are Jarvis, a warm, quick-witted AI voice assistant on the user's Windows PC" + (f" and the user's name is {n}" if n else "") +
                f". It is {datetime.now():%A %d %B %Y, %H:%M}. Your replies are spoken aloud, so talk naturally like a person: usually one to three short sentences, "
                "no markdown, lists or links. Ask a brief follow-up when it helps. The user can say 'open X' or 'close X' to control apps. Use web search for recent or uncertain facts.")

    def ask(self, question):
        gk, ck = self.cfg["gemini_key"], self.cfg["claude_key"]
        provs = ([("gemini", gk)] if gk and genai else []) + ([("claude", ck)] if ck and anthropic else [])
        if not provs:
            if time.time() - self.warned.get("key", 0) > 60: self.warned["key"] = time.time(); self.say("I need an API key to chat. Open Settings and paste a free Gemini key.")
            return
        self.history.append(("user", question)); self.set_state("thinking"); need, got = bool(NEEDS.search(question)), []; self.ai_err, self.ai_errs, ans = None, [], ""
        for attempt in range(2):
            self.ai_wait, self.ai_daily = 0.0, False
            for kind, key in provs:               # if one provider fails, try the other
                got.clear(); t0 = time.time()
                src = self.gemini_stream(key, need) if kind == "gemini" else self.claude_stream(key, need)
                def chunks(src=src, kind=kind, t0=t0):
                    for c in src:
                        if not got: print(f"AI first words after {time.time() - t0:.1f}s ({kind}, web search={need})")
                        got.append(c); yield c
                self.say_parts(sentences(chunks()))
                if "".join(got).strip(): break
            ans = "".join(got).strip()
            if ans or not (0 < self.ai_wait <= 8): break
            print(f"free limit: waiting {self.ai_wait:.0f}s and trying once more"); time.sleep(self.ai_wait + 0.5)    # short per-minute limit: wait it out
        if not ans:
            self.history.pop(); self.log("System", f"AI problem: {self.ai_err or self.part_err or 'no reply received'}")
            return self.say(explain(str(self.ai_err or self.part_err or ""), self.ai_wait, self.ai_daily))
        self.history.append(("model", ans))
        while len(self.history) > 8: self.history.pop(0); self.history.pop(0)

    def think_cfg(self):
        try:
            if self.g_think == 2: return gt.ThinkingConfig(thinking_level="minimal")     # Gemini 3 models
            if self.g_think == 1: return gt.ThinkingConfig(thinking_budget=0)             # older models
        except Exception: pass
        return None

    def discover_models(self, cl, tried):
        """Ask Google which models this key can use and return the newest Flash ones."""
        try: names = [m.name.split("/")[-1] for m in cl.models.list() if "generateContent" in (getattr(m, "supported_actions", None) or [])]
        except Exception as err: print("model list error:", err); return []
        def ver(n):
            m = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash(-lite)?", n)
            return (float(m.group(1)), not m.group(2)) if m else None
        return [n for _, n in sorted(((ver(n), n) for n in names if ver(n) and n not in tried), reverse=True)][:3]

    def gemini_stream(self, key, need):
        cl = genai.Client(api_key=key, http_options=gt.HttpOptions(timeout=20000))
        cts = [gt.Content(role=r, parts=[gt.Part(text=t)]) for r, t in self.history]; want = self.cfg.get("gemini_model") or GEMINI_MODEL
        todo = collections.deque(dict.fromkeys([self.good_model or want, want, "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]))
        tried, discovered, waits = set(), False, []
        while todo:
            model = todo.popleft(); tried.add(model); left = self.cool.get(model, 0) - time.time()
            if left > 0: waits.append(left)                # this model is resting after hitting its free limit: use another one
            else:
                for _ in range(4):
                    search = need and self.search_ok; kw = dict(system_instruction=self.system()); sent = False
                    if search: kw["tools"] = [gt.Tool(google_search=gt.GoogleSearch())]
                    tc = self.think_cfg()
                    if tc: kw["thinking_config"] = tc
                    try:
                        for ch in cl.models.generate_content_stream(model=model, contents=cts, config=gt.GenerateContentConfig(**kw)):
                            if ch.text: sent = True; yield ch.text
                    except Exception as err:
                        self.ai_errs.append(f"{model}: {str(err)[:150]}"); self.ai_err = " | ".join(self.ai_errs[-4:]); print(f"Gemini error ({model}):", err); low = str(err).lower()
                        if sent: return
                        if self.g_think and "think" in low: self.g_think -= 1; continue
                        if search and any(w in low for w in ("search", "ground", "tool")): self.search_ok = False; continue
                        if any(w in low for w in ("api key", "api_key", "401", "403", "permission", "unauthenticated")): return
                        if any(w in low for w in ("quota", "429", "exhaust", "rate limit", "resource")):
                            m = re.search(r"retry(?:delay|\s+in)\D{0,12}([\d.]+)\s*s", low); d = float(m.group(1)) + 1 if m else 30.0
                            if "perday" in low.replace("_", "").replace(" ", ""): d, self.ai_daily = 1800.0, True
                            self.cool[model] = time.time() + d; waits.append(d)
                        break                      # quota, unknown model or overload: try the next model
                    if sent:
                        self.good_model = model
                        if self.cfg.get("gemini_model") != model: self.cfg["gemini_model"] = model; self.persist()   # remember the model that works
                        return
                    if search: self.search_ok = False   # empty reply: relax the options and retry
                    elif self.g_think: self.g_think -= 1
                    else: break
            if not todo and not discovered:
                discovered = True; todo.extend(self.discover_models(cl, tried))
        if waits: self.ai_wait = min(waits)

    def claude_stream(self, key, need):
        m = [{"role": "assistant" if r == "model" else "user", "content": t} for r, t in self.history]
        kw = {"tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]} if need else {}
        try:
            with anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1).messages.stream(model=CLAUDE_MODEL, max_tokens=500, system=self.system(), messages=m, **kw) as st:
                for t in st.text_stream: yield t
        except Exception as err: self.ai_err = str(err)[:160]; print("Claude error:", err)

    # ---------- brain ----------
    def web(self, kind, site, query):
        import urllib.parse as up
        q = query.strip(); url = SITES[site] + (up.quote_plus(q) if "?" in SITES[site] else up.quote(q))
        if kind == "play" and site == "youtube":
            vid = None
            try: vid = youtube_first(q)
            except Exception as err: print("youtube lookup failed:", err)
            if vid: url = f"https://www.youtube.com/watch?v={vid}"
            else: kind = "search"
        if not open_url(url): return self.say("Sorry, I could not open your browser.")
        self.say(f"Playing {q} on YouTube." if kind == "play" else f"Searching {SITE_NAMES[site]} for {q}.")

    def visit(self, url, spoken):
        if not open_url(url): return self.say("Sorry, I could not open your browser.")
        self.say(spoken)

    def open_path(self, bare, text):
        """'open the downloads folder', 'open resume pdf', 'open d drive'. True if it handled the sentence."""
        m = re.match(r"^(?:open|show|go to)\s+(?:the\s+|my\s+)?([a-z])\s*drive$", bare)
        if m and os.path.exists(m.group(1).upper() + ":\\"):
            self.log("You", text); os.startfile(m.group(1).upper() + ":\\"); self.say(f"Opening drive {m.group(1).upper()}."); return True
        fm = FILE_RE.match(bare)
        if not fm or len(fm.group(2).split()) > 8: return False
        kind, query = fm.group(1), fm.group(2); want = None if not kind else kind in ("folder", "directory")
        hit = find_path(query, self.files, want)
        if not hit and kind and time.time() - self.file_scan_t > 60:           # maybe a brand-new file: look again
            self.file_scan_t = time.time(); self.files = index_files(max_s=8); hit = find_path(query, self.files, want)
        if not hit:
            if not kind: return False                                           # not clearly about files: let the AI answer
            self.log("You", text); self.say(f"I could not find a {kind} called {query}."); return True
        self.log("You", text)
        try: os.startfile(hit[1])
        except Exception as err: print("open error:", err); self.say(f"Sorry, I could not open {hit[0]}."); return True
        self.say(f"Opening {hit[0]}."); return True

    def handle(self, text, typed=False):
        self.t_cmd = time.time(); t = re.sub(r"[^\w\s']", "", text.lower()).strip()
        if not t: return
        wake = re.search(WAKE, t) is not None
        if not (typed or wake or self.cfg["listen_mode"] == MODES[0] or time.time() < self.session): return
        bare = re.sub(WAKE, "", t).strip()
        if not typed and bare == self.last_q and time.time() - self.last_t < 4: return          # the same sentence heard twice
        self.last_q, self.last_t = bare, time.time(); self.session = time.time() + 30
        if bare in EXIT: self.log("You", text); self.say("Goodbye."); self.q.put(("quit", None)); return
        site = parse_site(t)
        if site: self.log("You", text); return self.visit(*site)
        srch = parse_search(t)
        if srch: self.log("You", text); return self.web(*srch)
        cmd = parse_command(t, list(self.table()))
        if cmd:
            self.log("You", text); name, target = self.table()[cmd[1]]; return (self.close_app if cmd[0] == "close" else self.launch)(name, target)
        if self.open_path(bare, text): return
        ans = local_answer(bare)
        if ans: self.log("You", text); return self.say(ans)
        q = re.sub(WAKE, "", text, flags=re.I).strip()
        if not q: self.log("You", text); return self.say("Yes?")
        if not (typed or wake) and len(q.split()) < 2: return                                   # a lone word is probably noise: do not waste AI quota
        self.log("You", text); self.ask(q)

    # ---------- microphone ----------
    def open_stream(self):
        self.opening = True
        try:
            try: self.stream.abort(); self.stream.close()
            except Exception: pass
            dev = None
            if self.cfg["mic"] != "Default":
                for i, d in enumerate(sd.query_devices()):
                    if d["max_input_channels"] > 0 and d["name"] == self.cfg["mic"]: dev = i; break
            self.stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCK, device=dev); self.stream.start(); self.reopen = False
            amb = sum(level(self.stream.read(BLOCK)[0]) for _ in range(10)) / 10; self.noise = max(amb, 30.0); self.hist.clear()
            if amb < 1: self.log("System", "The microphone looks silent. Check Windows Settings > Privacy > Microphone (allow desktop apps) or pick another microphone in Settings.")
        finally: self.opening, self.last_read = False, time.time()

    def hear(self):
        pre, frames, silent, talking = collections.deque(maxlen=6), [], 0, False
        while self.running:
            if self.reopen: return "REOPEN"
            try: b, _ = self.stream.read(BLOCK)      # always keep reading, even when muted, so the device never stalls
            except Exception as err: print("mic error:", err); return "ERR"
            self.last_read = time.time(); lv = level(b); self.level = lv; self.hist.append(lv)
            if len(self.hist) >= 20: self.noise = min(float(np.percentile(self.hist, 25)), 1500.0)   # follows the room noise up and down
            sens = self.cfg["sens"]; self.thr = max(self.noise * max(1.6, 5.0 - 0.4 * sens), max(40.0, 140.0 - 10 * sens))
            if self.speaking and time.time() - self.speak_t0 > 150: self.speaking = False                 # safety: never stay deaf
            if self.speaking or not self.on: pre.clear(); frames, silent, talking = [], 0, False; continue
            loud = lv > self.thr
            if not talking:
                if loud: talking, frames = True, list(pre) + [b.copy()]; self.set_state("listening")
                else: pre.append(b.copy())
            else:
                frames.append(b.copy()); silent = 0 if loud else silent + 1
                if silent >= END_SIL or len(frames) >= 240:
                    if len(frames) - silent >= 3: return np.concatenate(frames[:max(1, len(frames) - silent + 3)]).tobytes()   # trim silence: faster upload
                    pre.clear(); frames, silent, talking = [], 0, False; self.set_state("idle")                                  # a click, not speech
        return None

    def voice_loop(self):
        greeted, raw = False, None
        while self.running:
            try: self.open_stream()
            except Exception as err:
                if time.time() - self.warned.get("mic", 0) > 120:
                    self.warned["mic"] = time.time(); self.log("System", f"I can't open the microphone ({err}). Pick another one in Settings. You can still type.")
                self.set_state("muted" if not self.on else "idle"); time.sleep(5); continue
            if not greeted: greeted = True; n = self.cfg["name"]; self.run(self.say, f"Jarvis online{', ' + n if n else ''}. How can I help?")
            while self.running:                 # keeps listening even while he is thinking: new sentences are queued
                raw = self.hear()
                if isinstance(raw, str): break
                if raw is None: time.sleep(0.2); continue
                self.uq.put(raw)
            if raw == "ERR": time.sleep(1.5)

    def worker(self):
        rec = sr.Recognizer(); rec.operation_timeout = 8
        while self.running:
            raw = self.uq.get()
            if not self.on: continue
            t0 = time.time(); self.set_state("thinking"); text, failed = None, True
            for _ in range(2):
                try: text = rec.recognize_google(sr.AudioData(raw, RATE, 2), language=LANGS[self.cfg["lang"]]); failed = False; break
                except sr.UnknownValueError: failed = False; break
                except Exception as err: print("recognize error:", err); time.sleep(0.3)
            print(f"speech-to-text took {time.time() - t0:.1f}s -> {text!r}")
            if failed and time.time() - self.warned.get("net", 0) > 30: self.warned["net"] = time.time(); self.log("System", "Speech service not reachable. Check your internet.")
            if text is None:
                if not failed and len(raw) > 38400: self.log("System", "I did not catch that. Please say it again.")
                self.set_state("idle"); continue
            try: self.handle(text)
            except Exception: traceback.print_exc()
            self.set_state("idle")

def single_instance():
    import socket
    s = socket.socket()
    try: s.bind(("127.0.0.1", 48653)); s.listen(1); return s
    except OSError: return None

if __name__ == "__main__":
    lock = single_instance()
    if lock is None:
        if os.name == "nt": ctypes.windll.user32.MessageBoxW(0, "Jarvis is already running. Look for its icon in the system tray near the clock.", "Jarvis", 0)
        sys.exit(0)
    try: Jarvis().mainloop()
    except Exception: traceback.print_exc(); raise
