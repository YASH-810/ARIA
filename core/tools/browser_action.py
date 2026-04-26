import webbrowser
import urllib.parse
from core.tts_engine import speak_chunk

def browser_action(action: str, query: str = ""):
    try:
        action = action.lower()
        if action == "url":
            url = query if query.startswith("http") else "https://" + query
            speech_text = f"Opening {query}"
        elif action == "youtube":
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            speech_text = f"Playing {query} on YouTube"
        elif action == "wikipedia":
            url = f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(query)}"
            speech_text = f"Searching Wikipedia for {query}"
        else:
            # Default to google search
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            speech_text = f"Searching for {query}"
            
        webbrowser.open(url)
        speak_chunk(speech_text)
        return speech_text
    except Exception as e:
        speak_chunk("Sorry, I encountered an error opening the browser.")
        return f"Error opening browser: {e}"
