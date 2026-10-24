"""
Offline fitness-plan generator for local/demo mode (no OpenAI required).
Produces JSON matching the fitness schema so the workspace UI can render plans + GIFs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


REQUIRED_FIELDS = ("age", "gender", "weight", "height", "fitness_level", "goal")

GOAL_KEYWORDS = {
    "muscle": "muscle building",
    "build muscle": "muscle building",
    "hypertrophy": "muscle building",
    "strength": "strength",
    "fat loss": "fat loss",
    "lose weight": "fat loss",
    "weight loss": "fat loss",
    "endurance": "endurance",
    "cardio": "endurance",
    "maintain": "maintain",
}

LEVEL_KEYWORDS = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}

# Exercises that exist in EXERCISE_MEDIA_MAP (GIF-backed)
DAY_TEMPLATES = {
    "muscle building": [
        {
            "day": "Day 1 - Upper Body",
            "exercises": [
                ("Push-ups", 3, 12, "45 seconds", "8"),
                ("Incline Push-ups", 3, 10, "45 seconds", "7"),
                ("Pike Push-ups", 3, 8, "60 seconds", "8"),
                ("Superman", 3, 12, "45 seconds", "5"),
            ],
            "tips": [
                "Keep your core braced on every push-up variation.",
                "Rest 60–90 seconds between sets if form starts to break.",
            ],
        },
        {
            "day": "Day 2 - Lower Body",
            "exercises": [
                ("Bodyweight Squat", 4, 15, "60 seconds", "9"),
                ("Lunges", 3, 12, "45 seconds", "8"),
                ("Glute Bridges", 3, 15, "45 seconds", "6"),
                ("Calf Raise", 3, 20, "30 seconds", "4"),
            ],
            "tips": [
                "Go as deep as mobility allows while keeping heels flat.",
                "Control the lowering phase for 2–3 seconds.",
            ],
        },
        {
            "day": "Day 3 - Full Body Conditioning",
            "exercises": [
                ("Burpees", 3, 10, "60 seconds", "12"),
                ("Mountain Climber", 3, 20, "45 seconds", "8"),
                ("Plank", 3, "30 seconds", "45 seconds", "5"),
                ("Jumping Jack", 3, 30, "30 seconds", "6"),
            ],
            "tips": [
                "Move with control — quality beats speed.",
                "Finish with light walking as a cool-down.",
            ],
        },
    ],
    "fat loss": [
        {
            "day": "Day 1 - Cardio + Core",
            "exercises": [
                ("Jumping Rope", 3, "45 seconds", "30 seconds", "10"),
                ("High Knee", 3, 30, "30 seconds", "8"),
                ("Mountain Climber", 3, 20, "30 seconds", "8"),
                ("Russian Twist", 3, 20, "30 seconds", "5"),
                ("Plank", 3, "40 seconds", "30 seconds", "5"),
            ],
            "tips": [
                "Keep heart rate elevated with short rests.",
                "Stay hydrated between rounds.",
            ],
        },
        {
            "day": "Day 2 - Strength Circuit",
            "exercises": [
                ("Push-ups", 3, 12, "40 seconds", "8"),
                ("Bodyweight Squat", 3, 15, "40 seconds", "8"),
                ("Lunges", 3, 12, "40 seconds", "7"),
                ("Burpees", 3, 8, "50 seconds", "12"),
            ],
            "tips": [
                "Circuit style: move to the next exercise with minimal rest.",
                "Add a brisk 10-minute walk after the session.",
            ],
        },
        {
            "day": "Day 3 - Active Recovery",
            "exercises": [
                ("Walking", 1, "20 minutes", "—", "60"),
                ("Glute Bridges", 2, 15, "30 seconds", "5"),
                ("Side Plank", 2, "20 seconds/side", "30 seconds", "4"),
                ("Heel Touch", 2, 20, "30 seconds", "4"),
            ],
            "tips": [
                "Keep intensity easy — recovery supports fat loss.",
                "Focus on breathing and posture.",
            ],
        },
    ],
    "strength": [
        {
            "day": "Day 1 - Push Focus",
            "exercises": [
                ("Push-ups", 4, 10, "90 seconds", "8"),
                ("Close-Grip Push-ups", 3, 8, "90 seconds", "8"),
                ("Pike Push-ups", 3, 8, "90 seconds", "8"),
                ("Plank", 3, "45 seconds", "60 seconds", "5"),
            ],
            "tips": ["Prioritize full range of motion.", "Add a pause at the bottom of each push-up."],
        },
        {
            "day": "Day 2 - Legs Focus",
            "exercises": [
                ("Bodyweight Squat", 4, 12, "90 seconds", "9"),
                ("Lunges", 4, 10, "75 seconds", "8"),
                ("Glute Bridges", 3, 12, "60 seconds", "6"),
                ("Calf Raise", 4, 15, "45 seconds", "4"),
            ],
            "tips": ["Drive through mid-foot on squats and lunges.", "Rest fully between heavy sets."],
        },
        {
            "day": "Day 3 - Pull + Core",
            "exercises": [
                ("Superman", 4, 12, "60 seconds", "5"),
                ("Mountain Climber", 3, 16, "45 seconds", "7"),
                ("Leg Raise", 3, 12, "45 seconds", "6"),
                ("Side Plank", 3, "25 seconds/side", "45 seconds", "4"),
            ],
            "tips": ["Squeeze at the top of each Superman rep.", "Keep hips stacked on side planks."],
        },
    ],
    "endurance": [
        {
            "day": "Day 1 - Cardio Base",
            "exercises": [
                ("Running", 1, "20 minutes", "—", "180"),
                ("Jumping Jack", 3, 40, "30 seconds", "6"),
                ("High Knee", 3, 30, "30 seconds", "7"),
            ],
            "tips": ["Keep conversational pace on the run.", "Land softly to reduce joint stress."],
        },
        {
            "day": "Day 2 - Intervals",
            "exercises": [
                ("Burpees", 5, 8, "40 seconds", "12"),
                ("Mountain Climber", 5, 20, "30 seconds", "8"),
                ("Jumping Rope", 5, "40 seconds", "30 seconds", "10"),
                ("Plank", 3, "40 seconds", "30 seconds", "5"),
            ],
            "tips": ["Work hard during intervals, fully recover between rounds."],
        },
        {
            "day": "Day 3 - Steady Movement",
            "exercises": [
                ("Walking", 1, "30 minutes", "—", "90"),
                ("Climbing Stairs", 3, "2 minutes", "60 seconds", "25"),
                ("Bodyweight Squat", 3, 15, "45 seconds", "7"),
            ],
            "tips": ["Stay relaxed and rhythmic.", "Hydrate throughout."],
        },
    ],
    "maintain": [
        {
            "day": "Day 1 - Balanced Strength",
            "exercises": [
                ("Push-ups", 3, 12, "45 seconds", "8"),
                ("Bodyweight Squat", 3, 15, "45 seconds", "8"),
                ("Lunges", 3, 10, "45 seconds", "7"),
                ("Plank", 3, "35 seconds", "40 seconds", "5"),
            ],
            "tips": ["Train consistently 3 days per week.", "Sleep and protein support recovery."],
        },
        {
            "day": "Day 2 - Mobility + Core",
            "exercises": [
                ("Glute Bridges", 3, 15, "30 seconds", "5"),
                ("Superman", 3, 12, "30 seconds", "5"),
                ("Heel Touch", 3, 20, "30 seconds", "4"),
                ("Side Plank", 3, "20 seconds/side", "30 seconds", "4"),
            ],
            "tips": ["Move slowly and breathe deeply."],
        },
        {
            "day": "Day 3 - Light Cardio",
            "exercises": [
                ("Walking", 1, "25 minutes", "—", "75"),
                ("Jumping Jack", 3, 25, "30 seconds", "5"),
                ("High Knee", 3, 20, "30 seconds", "6"),
            ],
            "tips": ["Keep effort easy to moderate."],
        },
    ],
}


def _calc_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100.0
    if height_m <= 0:
        return 0.0
    return round(weight_kg / (height_m ** 2), 1)


def _parse_profile(prompt: str) -> Tuple[Dict[str, Any], List[str]]:
    text = prompt.lower()
    found: Dict[str, Any] = {}
    missing: List[str] = []

    age = re.search(r"\b(\d{1,2})\s*(?:years?\s*old|yo|y/o)\b", text)
    if not age:
        age = re.search(r"\bage[:\s]+(\d{1,2})\b", text)
    if age:
        found["age"] = int(age.group(1))

    if re.search(r"\b(female|woman|girl)\b", text):
        found["gender"] = "female"
    elif re.search(r"\b(male|man|boy)\b", text):
        found["gender"] = "male"

    weight = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(kg|kgs|kilograms?)\b", text)
    if weight:
        found["weight"] = float(weight.group(1))
        found["weight_unit"] = "kg"
    else:
        weight_lb = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(lb|lbs|pounds?)\b", text)
        if weight_lb:
            found["weight"] = round(float(weight_lb.group(1)) * 0.453592, 1)
            found["weight_unit"] = "kg"

    height_cm = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*cm\b", text)
    if height_cm:
        found["height"] = float(height_cm.group(1))
        found["height_unit"] = "cm"
    else:
        height_ft = re.search(
            r"\b(\d)\s*(?:ft|feet|')\s*(\d{1,2})?\s*(?:in|inches|\")?\b",
            text,
        )
        if height_ft:
            feet = int(height_ft.group(1))
            inches = int(height_ft.group(2) or 0)
            found["height"] = round((feet * 12 + inches) * 2.54, 1)
            found["height_unit"] = "cm"

    for key, level in LEVEL_KEYWORDS.items():
        if key in text:
            found["fitness_level"] = level
            break

    for key, goal in GOAL_KEYWORDS.items():
        if key in text:
            found["goal"] = goal
            break

    for field in REQUIRED_FIELDS:
        if field not in found:
            missing.append(field.replace("_", " "))

    return found, missing


def _is_fitness_related(prompt: str) -> bool:
    text = prompt.lower().strip()
    if len(text) < 3:
        return False
    keywords = [
        "fitness", "workout", "exercise", "train", "muscle", "fat", "diet",
        "nutrition", "weight", "height", "kg", "cm", "beginner", "plan",
        "cardio", "strength", "gym", "reps", "sets", "bmi", "lose", "build",
        "years old", "male", "female",
    ]
    return any(k in text for k in keywords)


def _exercise_dict(name: str, sets: int, reps, rest: str, calories: str, level: str) -> Dict[str, Any]:
    reps_label = reps if isinstance(reps, str) else f"{reps} reps"
    return {
        "name": name,
        "sets": sets,
        "reps": reps_label,
        "duration": f"{sets} sets of {reps_label}",
        "rest": rest,
        "calories": f"{calories} kcal",
        "difficulty": level.title(),
        "how_to_perform": [
            f"Set up in a stable position for {name.lower()}.",
            "Perform each rep with controlled tempo and full range.",
            "Exhale on the effort; keep your core engaged.",
            "Stop the set if form breaks down.",
        ],
    }


def generate_local_fitness_plan(
    prompt: str,
    weight_value: Optional[float] = None,
    weight_unit: Optional[str] = None,
    height_value: Optional[float] = None,
    height_unit: Optional[str] = None,
    height_extra_inches: Optional[float] = None,
) -> Dict[str, Any]:
    if not _is_fitness_related(prompt):
        return {
            "error": "I am only assisted to Fitness and Exercise",
            "missing_info": None,
            "title": None,
            "plans": [],
        }

    profile, missing = _parse_profile(prompt)

    # Merge explicit numeric fields from the API request
    if weight_value is not None:
        kg = weight_value if (weight_unit or "kg").lower() in ("kg", "kgs") else weight_value * 0.453592
        profile["weight"] = round(kg, 1)
        if "weight" in missing:
            missing = [m for m in missing if m != "weight"]
    if height_value is not None:
        if (height_unit or "cm").lower() in ("cm",):
            profile["height"] = height_value
        else:
            inches = height_value * 12 + (height_extra_inches or 0)
            profile["height"] = round(inches * 2.54, 1)
        if "height" in missing:
            missing = [m for m in missing if m != "height"]

    if missing:
        return {
            "missing_info": f"Please provide the {', '.join(missing)}",
            "error": None,
            "title": None,
            "plans": [],
        }

    goal = profile.get("goal", "maintain")
    level = profile.get("fitness_level", "beginner")
    templates = DAY_TEMPLATES.get(goal, DAY_TEMPLATES["maintain"])

    bmi = None
    if profile.get("weight") and profile.get("height"):
        bmi = _calc_bmi(float(profile["weight"]), float(profile["height"]))

    plans: List[Dict[str, Any]] = []
    for day in templates:
        exercises = [
            _exercise_dict(name, sets, reps, rest, cal, level)
            for name, sets, reps, rest, cal in day["exercises"]
        ]
        plans.append(
            {
                "day": day["day"],
                "exercises": exercises,
                "tips": day["tips"],
            }
        )

    title_goal = goal.replace("_", " ").title()
    return {
        "title": f"3-Day {title_goal} Plan ({level.title()})",
        "summary": (
            f"Personalized {level} {goal} program for a {profile.get('age')}-year-old "
            f"{profile.get('gender')}. Focus on consistent form, progressive volume, "
            f"and recovery between sessions."
        ),
        "bmi": bmi,
        "plans": plans,
        "error": None,
        "missing_info": None,
    }
