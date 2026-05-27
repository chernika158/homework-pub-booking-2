# Ex6 — Rasa integration

## Prompt

How did you wire Rasa CALM into the sovereign-agent `StructuredHalf` protocol?
Describe specifically: (1) how your subclass translates an input `dict` into a
Rasa-compatible intent payload, (2) how your `ActionValidateBooking` custom
action surfaces validation failures back into a `HalfResult`, and (3) one thing
you would change about the integration if you were building this for production.

**Word count:** 200-400 words.

## Your answer

The input dir used `normalise_booking_payload` to transform itself into 
a json in `confirm_booking` dir. `ActioValidateBooking` custom action
caught error on validation step. On the Rasa side, a custom action checks whether the booking is actually valid
The escalation was triggered using `HalfResult`.
and Python code wraps that into a HalfResult that tells the bridge to try again.


## Citations

- sessions/sess_c689fbc596c7/logs/trace.jsonl:15 — booking comfirmation by Rasa
- starter/rasa_half/validator.py — normalise_booking_payload
