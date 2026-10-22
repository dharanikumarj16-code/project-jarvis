# JARVIS: Voice-First Intelligent Computer Automation

The main purpose of the JARVIS project is not simply "AI that controls a computer." It is a **voice-first intelligent computer-control system** designed to reduce or replace physical hand interaction for people who cannot easily operate a conventional PC.

## Core Principle
**Replace physical hand involvement with intelligent voice-driven computer interaction.**

The user's voice becomes the primary input, while JARVIS's automation layer becomes the user's digital hands.

## The Paradigm Shift
You don't want JARVIS to merely convert: *"Click Chrome"* into a mouse click.

You want: *"Prepare my presentation for tomorrow."*
JARVIS should understand the goal, decide the required sequence, operate the computer, observe what happens, recover from errors, and report the result. That is the difference between a voice controller and an AI computer assistant.

## The Flow
**JARVIS = Voice → Intelligence → Automation → Computer**

```text
              USER
                │
          Voice Command
                ↓
        Speech Recognition
                ↓
       ⚡ Fast Intent Router
                ↓
        🧠 Reasoning Model
                ↓
       Task Planning / Memory
                ↓
       Unified Tool Bus
                ↓
 ┌──────────────┼───────────────┐
 ↓              ↓               ↓
Keyboard       Mouse          UI Automation
 ↓              ↓               ↓
Windows       Applications    Accessibility
 └──────────────┼───────────────┘
                ↓
             COMPUTER
                ↓
        Observe + Verify
                ↓
             JARVIS
                ↓
             Voice
```

## The Anatomy of JARVIS
- 🧠 **Brain** → Reasoning model (PydanticAI / Qwen2.5 / Gemini)
- 👂 **Ears** → Speech recognition
- 👁️ **Eyes** → UI Automation, accessibility tree, OCR, screenshots
- ✋ **Hands** → Keyboard, mouse, Windows APIs, browser automation
- 🧩 **Memory** → Persistent user/task knowledge (RAG Layer)
- ⚡ **Router** → Fast intent detection (Local Fallback Parser)
- 🛡️ **Safety** → Permissions and human approval (Unified Tool Bus)
- 🔄 **Learning** → Improve from successful task history
