"""LLM provider service for fitness plan generation."""

import logging
import os
import traceback
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.services.local_fitness_planner import generate_local_fitness_plan
from app.utils.json_utils import try_parse_json
from app.utils.system_message_fitness import FITNESS_SYSTEM_MESSAGE
from app.utils.unit_normalisation_and_bmi import normalize_and_bmi

logger = logging.getLogger(__name__)
load_dotenv()


def _append_bmi_context(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    prompt: str,
    weight_value: Optional[float],
    weight_unit: Optional[str],
    height_value: Optional[float],
    height_unit: Optional[str],
    height_extra_inches: Optional[float],
) -> str:
    """Append normalized BMI metrics to the user prompt when available."""
    if not (weight_value and height_value):
        return prompt

    try:
        bmi_context = normalize_and_bmi(
            weight_value,
            weight_unit or "kg",
            height_value,
            height_unit or "cm",
            height_extra_inches,
        )
    except (TypeError, ValueError) as exc:
        logger.warning("BMI normalization failed: %s", exc)
        return prompt

    return (
        f"{prompt}\n\nSystem-provided metrics:\n"
        f"- Normalized Weight: {bmi_context.get('normalized_weight_kg')} kg\n"
        f"- Normalized Height: {bmi_context.get('normalized_height_cm')} cm\n"
        f"- BMI: {bmi_context.get('bmi')}\n"
        f"- BMI Category: {bmi_context.get('bmi_category')}"
    )


class LLMService:  # pylint: disable=too-few-public-methods
    """Generate fitness responses via local planner, Ollama, or OpenAI."""

    def __init__(self):
        self.provider = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()
        self.client = None
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self._configure_client()

    def _configure_client(self) -> None:
        """Initialize the provider client based on LLM_PROVIDER."""
        if self.provider in ("local", "demo"):
            logger.info("LLMService using local fitness planner (no OpenAI)")
            return

        if self.provider == "ollama":
            base_url = os.getenv(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434/v1",
            )
            self.client = OpenAI(
                base_url=base_url,
                api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            )
            logger.info("LLMService using Ollama at %s", base_url)
            return

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-replace"):
            raise ValueError(
                "OPENAI_API_KEY not found. Set a real key, or set "
                "LLM_PROVIDER=local in backend/.env"
            )
        self.client = OpenAI(api_key=api_key)

    def generate_chatgpt_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        prompt: str,
        model: str = "gpt-4o",
        history: Optional[List[Dict[str, str]]] = None,
        system_message: str = FITNESS_SYSTEM_MESSAGE,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        enable_web_search: bool = False,
        weight_value: Optional[float] = None,
        weight_unit: Optional[str] = None,
        height_value: Optional[float] = None,
        height_unit: Optional[str] = None,
        height_extra_inches: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured fitness response.

        Providers: local/demo (offline), ollama, openai.
        """
        if enable_web_search:
            logger.info(
                "Web search requested; not supported by the current provider path"
            )

        try:
            if self.provider in ("local", "demo"):
                return generate_local_fitness_plan(
                    prompt=prompt,
                    weight_value=weight_value,
                    weight_unit=weight_unit,
                    height_value=height_value,
                    height_unit=height_unit,
                    height_extra_inches=height_extra_inches,
                )

            return self._generate_via_chat_api(
                prompt=prompt,
                model=model,
                history=history,
                system_message=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                enable_web_search=enable_web_search,
                weight_value=weight_value,
                weight_unit=weight_unit,
                height_value=height_value,
                height_unit=height_unit,
                height_extra_inches=height_extra_inches,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("LLM service error: %s", exc)
            logger.error(traceback.format_exc())
            return {"error": f"LLM service error: {exc}"}

    def _generate_via_chat_api(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        prompt: str,
        model: str,
        history: Optional[List[Dict[str, str]]],
        system_message: str,
        max_tokens: int,
        temperature: float,
        enable_web_search: bool,
        weight_value: Optional[float],
        weight_unit: Optional[str],
        height_value: Optional[float],
        height_unit: Optional[str],
        height_extra_inches: Optional[float],
    ) -> Dict[str, Any]:
        """Call OpenAI-compatible chat completions and parse JSON when possible."""
        logger.info(
            "Generating response (provider=%s, model=%s, web_search=%s)",
            self.provider,
            model,
            enable_web_search,
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_message}
        ]
        if history:
            messages.extend(history)

        prompt = _append_bmi_context(
            prompt,
            weight_value,
            weight_unit,
            height_value,
            height_unit,
            height_extra_inches,
        )
        messages.append({"role": "user", "content": prompt})

        use_model = self.ollama_model if self.provider == "ollama" else model
        response = self.client.chat.completions.create(
            model=use_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            logger.error(
                "No valid response content could be extracted from LLM response."
            )
            return {"error": "No valid response content."}

        parsed = try_parse_json(text)
        return parsed if parsed is not None else {"text": text}
