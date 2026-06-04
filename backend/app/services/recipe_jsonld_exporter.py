from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.duration_serializer import DurationSerializer

if TYPE_CHECKING:
    from app.models.recipe import Recipe


class RecipeJSONLDExporter:
    @staticmethod
    def to_jsonld(recipe: Recipe) -> dict[str, Any]:
        result: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": recipe.title,
        }

        if recipe.description is not None:
            result["description"] = recipe.description
        if recipe.image_url is not None:
            result["image"] = recipe.image_url
        if recipe.author is not None:
            result["author"] = {"@type": "Person", "name": recipe.author}
        if recipe.date_published is not None:
            result["datePublished"] = recipe.date_published.isoformat()

        result["recipeYield"] = str(recipe.servings)

        prep_time = DurationSerializer.to_iso_duration(
            recipe.prep_time_minutes
        )
        if prep_time is not None:
            result["prepTime"] = prep_time

        cook_time = DurationSerializer.to_iso_duration(
            recipe.cook_time_minutes
        )
        if cook_time is not None:
            result["cookTime"] = cook_time

        total_time = DurationSerializer.to_iso_duration(
            recipe.total_time_minutes
        )
        if total_time is not None:
            result["totalTime"] = total_time

        perform_time = DurationSerializer.to_iso_duration(
            recipe.perform_time_minutes
        )
        if perform_time is not None:
            result["performTime"] = perform_time

        if recipe.nutrition is not None:
            result["nutrition"] = recipe.nutrition
        if recipe.aggregate_rating is not None:
            result["aggregateRating"] = recipe.aggregate_rating
        if recipe.keywords is not None:
            result["keywords"] = recipe.keywords

        if recipe.ingredients:
            ingredient_names: list[str] = []
            for ri in recipe.ingredients:
                ingredient_names.append(ri.ingredient.name)
            result["recipeIngredient"] = ingredient_names

        if recipe.steps:
            steps: list[dict[str, Any]] = []
            for step in recipe.steps:
                step_dict: dict[str, Any] = {
                    "@type": "HowToStep",
                    "text": step.text,
                }
                if step.name is not None:
                    step_dict["name"] = step.name
                steps.append(step_dict)
            result["recipeInstructions"] = steps

        if recipe.tags:
            diet_tags: list[str] = []
            for rt in recipe.tags:
                tag = rt.tag
                if tag.group == "category":
                    result["recipeCategory"] = tag.name
                elif tag.group == "cuisine":
                    result["recipeCuisine"] = tag.name
                elif tag.group == "diet":
                    diet_tags.append(
                        f"https://schema.org/{tag.name}"
                    )
            if diet_tags:
                result["suitableForDiet"] = diet_tags

        result["identifier"] = recipe.id

        return result
