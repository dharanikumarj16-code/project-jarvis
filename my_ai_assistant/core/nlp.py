
import spacy
from spacy.matcher import PhraseMatcher
import logging

class IntentRecognizer:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logging.warning("spaCy model 'en_core_web_sm' not found. Intent recognition may be limited.")
            self.nlp = None

        # Define Intent to Mode Mapping
        self.intent_to_mode = {
            "work": "work_mode",
            "ai": "ai_work",
            "CHAT": "CHAT_MODE",
            "general": "general_mode",
            "SYSTEM_INFO": "SYSTEM_MODE",
            "TASKS": "TASK_MODE",
            "WEB": "WEB_MODE",
            "MESSAGING": "MESSAGING_MODE"
        }

        # Keywords for rule-based intent extraction using spaCy lemmas
        self.intent_keywords = {
            "WORK_MODE": ["open", "close", "app"    ,"shortcut", "application", "chrome", "edge", "firefox", "brave", "vivaldi", "opera", "safari", "explorer"],
            "MUSIC": ["music", "song", "play", "pause", "volume", "spotify", "track"],
            "SYSTEM_INFO": ["system", "status", "cpu", "memory", "battery", "info", "battery percentage","ram usage"],
            "TASKS": ["task", "todo", "reminder", "list"],
            "AI": ["ai", "smart", "intelligent", "genius"   ,"brain","think"],
            "CHAT": ["chat", "conversation", "talk", "speak"],
            "LEARNING": ["learn", "teach", "educate", "guide"],
            "WEB": ["search", "google", "find", "research", "website"],
            "MESSAGING": ["message", "whatsapp", "text", "send", "chat"]
        }

    def extract_intent(self, text):
        if not self.nlp:
            return "UNKNOWN", None

        doc = self.nlp(text.lower())
        
        # Simple lemmatization-based intent detection
        lemmas = [token.lemma_ for token in doc]
        
        detected_intent = "UNKNOWN"
        for intent, keywords in self.intent_keywords.items():
            if any(kw in lemmas for kw in keywords):
                detected_intent = intent
                break
        
        mode = self.intent_to_mode.get(detected_intent)
        return detected_intent, mode

    def get_entities(self, text):
        if not self.nlp:
            return []
        doc = self.nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]

# Singleton instance
intent_recognizer = IntentRecognizer()
