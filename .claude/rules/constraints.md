# Project Technical Constraints

## AI Model Requirements
- At least one core semantic task must be AI model-driven (dynamic topic discovery, evidence analysis, etc.). Fixed keywords/regex-only approaches are prohibited.
- Use deterministic rules for: data collection, deduplication, field normalization, validation, security checks.
- Each major finding must include: source review IDs, sample count, confidence level, conflicting evidence.
- Document the model/provider used, prompts, model config, failure-handling strategy, and hallucination-reduction measures.

## Data & Integration
- Support importing review data in JSON and CSV formats.
- No app-specific hard-coded categories, findings, requirements, or test cases.
- Secrets must be injected via environment variables, never committed to the repository.
