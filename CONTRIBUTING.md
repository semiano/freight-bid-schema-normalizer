# Contributing

Thanks for contributing to RXO Document Normalizer.

## Development Setup

1. Create a Python virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run tests:
   - `python -m unittest tests/test_artifact_store.py tests/test_sandbox_executor.py tests/test_script_policy.py tests/test_pipeline_runner.py tests/test_planning_service.py tests/test_template_loader.py tests/test_normalization_service.py tests/test_validation_service.py tests/test_output_writer.py tests/test_sheet_classifier.py tests/test_workbook_profiler.py`

## Contribution Guidelines

- Keep pull requests focused and small.
- Add or update tests for behavior changes.
- Avoid committing secrets, local settings, generated artifacts, or environment files.
- Follow existing code style and patterns.

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] Documentation updated (if behavior/config changed)
- [ ] No sensitive values in changed files
- [ ] Infrastructure changes validated with Bicep diagnostics
