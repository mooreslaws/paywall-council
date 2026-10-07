# Resource-Limit Fixtures

`cases.json` exercises context-aware, post-ingestion admission before one evidence item or a complete screenshot batch begins.

Each valid accounting record supplies the deployed context window; four non-overlapping occupied-input components; the occupied-input total; cached input as an informational subset; retrieved KB tokens; tool-output, response, and safety reserves; candidate evidence tokens; OCR characters; and elapsed processing time. Retrieved KB and candidate evidence are excluded from occupied input and subtracted exactly once. Cached tokens remain in occupied input.

The fixture set covers evidence below capacity, exact warning and hard boundaries, evidence above hard, a 24k evidence payload that cannot fit a 32k context, a 64k fit with reserves, cached-token accounting, zero remaining capacity, missing metadata, inconsistent and declared-overlap counters, over-window reservations, negative and non-finite inputs, byte-estimate rejection, and screenshot-batch admission.

The configured 24k/32k values remain absolute evidence ceilings. The runtime-effective warning and hard thresholds can be lower. Attachment, file-size, image, PDF, archive, and transport controls remain host or webapp responsibilities.

Single-item admission uses `--evidence-tokens`; batch admission uses `--batch-evidence-tokens` plus `--batch-item-count`. Both modes also require:

```text
--context-window-tokens
--occupied-input-tokens
--host-system-instruction-tokens
--project-instruction-tokens
--task-instruction-tokens
--existing-conversation-tokens
--cached-input-tokens
--retrieved-kb-tokens
--tool-output-reserve-tokens
--response-reserve-tokens
--safety-margin-tokens
--ocr-chars
--elapsed-seconds
```

`--evidence-bytes` remains an estimate-only compatibility input and always rejects admission until an exact host token count is supplied.
