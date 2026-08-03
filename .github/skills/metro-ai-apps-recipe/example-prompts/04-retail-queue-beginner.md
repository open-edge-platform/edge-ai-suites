# Retail queue-length monitoring stack (first-time user)

I'm new to this. I want a working end-to-end demo that watches a shop entrance
and tells me when the checkout queue gets long. Build it in `./retail-queue-stack/`
for the retail vertical, object of interest `person`, using the default CPU
detector and the bundled sample videos so I don't need real cameras yet. Alert
when `count>4 in 20s per-source`. Ask me the six setup questions in one batched
message with sensible defaults in brackets, accept `defaults` to proceed, then
build and verify the stack.
