<p align="center">
  <img src="custom_components/assist_utils/brand/icon.png" alt="Assist Utils" width="128">
</p>

<h1 align="center">Assist Utils</h1>

<p align="center">
  Utilities for Home Assistant voice assistants: commands that work with any conversation agent, including LLMs.
</p>

<p align="center">
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.10%2B-18BCF2.svg" alt="Home Assistant 2026.10+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
</p>

---

## Why

LLM voice assistants are great until:

- **They repeat their own mistakes.** A satellite keeps using the same conversation until it has been idle for five minutes. If the LLM said something wrong early on (it invented an integration, or claimed it had no data), it keeps trusting that for the rest of the conversation.
- **The wake word triggers by mistake.** Whatever you say next ("stop", "not you") goes to the LLM, which answers anyway, sometimes with a question that reopens the microphone.

Assist Utils handles these **before** the conversation agent, so they're instant, reliable, and cost no LLM call.

## Features

| | Voice | Button | Action |
|---|:-:|:-:|:-:|
| **[Reset conversation](#reset-conversation)**: clear the conversation history | ✓ | ✓ per satellite and for all | ✓ |
| **[Silent cancel](#silent-cancel)**: end a false wake silently | ✓ | | |
| **[Reset event](#reset-event)**: react to resets in automations | | | event |

Every feature can be [turned on or off](#configuration). Phrases ship in **English** and **Spanish**, and every phrase and reply can be customized.

### Reset conversation

Say a reset phrase and the conversation's history is cleared. Your next request starts a new conversation.

| Language | Default phrases | Reply |
|---|---|---|
| English | forget / reset / clear the conversation · new conversation · start over | "Conversation reset." |
| Spanish | olvida / borra / reinicia la conversación · olvida todo lo que hemos hablado · nueva conversación · empieza de cero | "Conversación reiniciada." |

**Buttons:**

- **Reset conversation** on every Assist satellite's device page. It resets only that satellite's conversation, so it's ideal for a dashboard tile next to the satellite.
- **Reset all conversations** on the Assist Utils device.

**Action** `assist_utils.reset_conversation`:

```yaml
# One satellite (also accepts devices and areas)
action: assist_utils.reset_conversation
target:
  entity_id: assist_satellite.kitchen

# A specific conversation, e.g. from a sentence-triggered automation
action: assist_utils.reset_conversation
data:
  conversation_id: "{{ trigger.user_input.conversation_id }}"

# Everything
action: assist_utils.reset_conversation
```

It returns `{"reset": [<conversation ids>]}`.

### Silent cancel

When the wake word triggers by mistake, say a cancel phrase and the request ends **without a reply and without reaching the conversation agent**.

| Language | Default phrases |
|---|---|
| English | stop · cancel · never mind · nothing · false alarm · wrong wake word · not talking to you · be quiet · shut up |
| Spanish | para · cancela · cancélalo · déjalo · olvídalo · nada · no es nada · no era a ti · falsa alarma · silencio · cállate |

Optionally it can also reset the conversation, so the false wake doesn't stay in the LLM's context.

> [!NOTE]
> Phrases only match when they make up the **whole** sentence, so "stop the music" still reaches your agent. A bare "stop" or "para" is caught by Silent cancel, though, and no longer pauses media. Remove those phrases if you rely on them.

### Reset event

Every reset fires `assist_utils_conversation_reset`:

```yaml
event_type: assist_utils_conversation_reset
data:
  conversation_id: 01JD8Q...
  satellite_id: assist_satellite.kitchen   # when known
  source: voice                             # voice | button | action
```

```yaml
# Example: blink the satellite LED when its conversation is reset
triggers:
  - trigger: event
    event_type: assist_utils_conversation_reset
    event_data:
      satellite_id: assist_satellite.kitchen
actions:
  - action: light.turn_on
    target:
      entity_id: light.kitchen_satellite_led
    data:
      flash: short
```

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=deantonious&repository=CustomVoiceAssistantCommands&category=integration)

Or manually: HACS → ⋮ → **Custom repositories** → add `https://github.com/deantonious/CustomVoiceAssistantCommands` as an **Integration**. Then install **Assist Utils** and restart Home Assistant.

### Manual

Copy `custom_components/assist_utils` into your `/config/custom_components/` folder and restart Home Assistant.

### Set up

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=assist_utils)

**Settings → Devices & services → Add integration → Assist Utils**, then choose the languages whose phrases you want.

## Configuration

**Settings → Devices & services → Assist Utils → Configure** opens a menu:

- **Features:** turn each feature on or off. You also pick these during setup, with everything on by default.

  | Feature | When off |
  |---|---|
  | Reset conversation (voice command) | its phrases are no longer recognized |
  | Silent cancel (voice command) | its phrases go to your conversation agent again |
  | Reset conversation button on each satellite | the satellite buttons are removed |
  | Reset all conversations button | the button is removed |

  The `assist_utils.reset_conversation` action is always available.
- **Languages:** which languages' default phrases are loaded.
- **Reset conversation phrases / Silent cancel phrases:** edit the phrases and the spoken reply (empty = silent). Silent cancel also has *Also reset the conversation*.

**Phrase syntax** (the same as [sentence triggers](https://www.home-assistant.io/docs/automation/trigger/#sentence-trigger)): one phrase per line, no punctuation.

| Syntax | Meaning | Example |
|---|---|---|
| `[word]` | optional | `para [ya]` matches "para" and "para ya" |
| `(a\|b)` | alternatives | `(cancela\|cancelalo)` |

Matching ignores case and punctuation but **not accents**. Speech-to-text engines are inconsistent about accents, so list both spellings (`conversación|conversacion`). Clear the phrases field to go back to the defaults, which then follow your language selection.

> [!TIP]
> **A phrase doesn't match?** Open **Settings → Voice assistants → your assistant → ⋮ → Debug** and look at what speech-to-text actually produced. Short words are often transcribed in another language or without accents. Add that exact text as a phrase.

## Languages

Default phrases live in [`custom_components/assist_utils/sentences/`](custom_components/assist_utils/sentences), one YAML file per language. To add a language, copy `en.yaml`, translate it, add the code to `SUPPORTED_LANGUAGES` in `const.py` and to the `languages` selector in `strings.json`, and open a pull request. Contributions are welcome.

## How it works and limitations

- **Voice commands** use the same mechanism as automation [sentence triggers](https://www.home-assistant.io/docs/automation/trigger/#sentence-trigger). Home Assistant checks them before handing text to any conversation agent.
- **Resetting:** every Assist conversation is a chat session in Home Assistant's memory, and its LLM history is deleted when the session is cleaned up. Normally that happens after five minutes of inactivity. Assist Utils runs that same cleanup on demand.
  - A voice reset waits for its own turn to finish, about half a second.
  - The satellite's next wake starts a new conversation.
- **Internals:** this relies on Home Assistant internals (chat sessions, the conversation agent manager, and the satellite's current conversation) that aren't a public API.
  - Assist Utils checks them at startup. If an update changes them, a **Repairs** card says what broke, and only the affected features are turned off. Satellite buttons then fall back to resetting all conversations.
  - Diagnostics (*Download diagnostics* on the integration) include the check result. They contain no conversation content.
- **Requires** Home Assistant **2026.10** or newer.

## Development

The tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) and need Linux or macOS, because Home Assistant doesn't run on Windows; WSL works.

```bash
uv venv --python 3.14 ~/.venvs/assist-utils
uv pip install --python ~/.venvs/assist-utils -r requirements_test.txt
bash scripts/run_tests_wsl.sh
```

`scripts/make_icon.py` regenerates the brand icons.

**Adding a voice command:**

1. Add `commands/<key>.py` with a `COMMAND`, and register it in `commands/__init__.py`. It shows up on the Features page automatically.
2. Add its phrases to every `sentences/*.yaml` file.
3. Add an `async_step_<key>` phrases step in `config_flow.py`, and its texts (menu entry, step, `selector.features` label) to `strings.json` and the translations.

## License

[MIT](LICENSE)
