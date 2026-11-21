# Custom Voice Assistant Commands

A Home Assistant integration that adds voice commands to Assist. They're
handled **before** any conversation agent, so they work the same with the
built-in agent and with LLM agents (OpenAI, Ollama, llama.cpp, ...), without
costing an LLM call.

## Commands

### Reset conversation

Home Assistant keeps the history of each Assist conversation in memory, and a
voice satellite keeps using the same conversation until it has been idle for
five minutes. If the LLM gets something wrong early on (it invents an
integration, or claims it has no data), it tends to repeat that mistake for the
rest of the conversation.

Say one of these and the history is cleared. The next request starts a new
conversation:

| Spanish | English |
|---|---|
| olvida / borra / reinicia / resetea la conversación | forget / reset / clear the conversation |
| olvida todo lo que hemos hablado | new conversation / start a new conversation |
| nueva conversación | start over |
| empieza de cero | |

The assistant answers "Conversación reiniciada." You can change the sentences
and the reply, or leave the reply empty to stay silent, under **Settings →
Devices & services → Custom Voice Assistant Commands → Configure**.

Sentences use Home Assistant's
[sentence trigger syntax](https://www.home-assistant.io/docs/automation/trigger/#sentence-trigger):
`[word]` makes a word optional, and `(a|b)` gives alternatives. Matching ignores
case and punctuation but **not accents**, so the defaults list both
`conversación` and `conversacion`, because speech-to-text engines are
inconsistent about accents.

The same thing is available as an action for automations and scripts:

```yaml
action: voice_assistant_commands.reset_conversation
data:
  conversation_id: "{{ trigger.user_input.conversation_id }}"  # optional
```

Without `conversation_id`, every conversation is reset. The action returns
`{"reset": [<conversation ids>]}`.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/deantonious/CustomVoiceAssistantCommands`, type **Integration**.
2. Install **Custom Voice Assistant Commands** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Custom Voice Assistant Commands**.

### Manual

Copy `custom_components/voice_assistant_commands` to
`/config/custom_components/`, restart Home Assistant, then add the integration
as above.

Requires Home Assistant 2026.10 or newer.

## How it works

Every Assist conversation is a `ChatSession` in Home Assistant's memory. The
conversation component registers a cleanup callback on each session that
deletes its LLM chat log. Normally that cleanup only runs once a session has
been idle for five minutes. This integration runs the same cleanup on demand.

The voice command runs inside the turn it resets. That turn has to finish first,
because Home Assistant writes the session back when a turn ends, so the reset
happens about half a second after the reply. The next request that arrives with
the old conversation ID gets a new one from Home Assistant, which is how a
satellite ends up in a fresh conversation.

This relies on Home Assistant internals (`homeassistant.helpers.chat_session`
and the conversation agent manager) rather than a public API, so a future Home
Assistant release could break it.

## Development

The tests use
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component).
They need Linux or macOS, because Home Assistant doesn't run on Windows; WSL works.

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv -r requirements_test.txt
.venv/bin/python -m pytest
```
