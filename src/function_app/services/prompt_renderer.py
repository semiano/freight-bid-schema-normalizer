from __future__ import annotations

from pathlib import Path


class PromptRenderer:
    def __init__(self, prompts_root: str = "src/function_app/prompts") -> None:
        self.prompts_root = Path(prompts_root)

    def load_prompt(self, prompt_name: str) -> str:
        prompt_path = self.prompts_root / prompt_name
        return prompt_path.read_text(encoding="utf-8")

    def render(self, prompt_name: str, values: dict[str, str]) -> str:
        template = self.load_prompt(prompt_name)
        return template.format(**values)
