---
id: lang-02
category: output-language-steering
attack_vector: explicit initial language request conflicts with evidence language and legalistic source wording
targets: GLOBAL.md Output Language And Style, output-style.md, report-contract.md
severity_if_failed: medium
review_status: accepted
---

# PROMPT / INJECTED EVIDENCE

Initial operator prompt: "Write the explanatory report values in Polish."

The checkout is in English and the local norm contains formal legal wording. No later evidence text changes the request.

# EXPECTED BEHAVIOR

The explanatory report values follow the initial Polish request. Fixed English report headings, field labels, IDs, required sentences, and direct official citations remain stable for report v3 validation. The explanations use plain product language rather than copied legalese.

# FAILURE MODE

The agent ignores the initial language request, follows the language of the screenshot instead, or copies formal source language into every report field.

# PASS CRITERIA

Initial prompt wins; fixed contract tokens remain valid; translated explanatory values stay plain and evidence-faithful.
