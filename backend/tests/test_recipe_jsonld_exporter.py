from datetime import date

from app.models.ingredient import Ingredient
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeTag,
    Tag,
)
from app.services.recipe_jsonld_exporter import RecipeJSONLDExporter


def _make_recipe(
    *,
    title: str = "Test Recipe",
    description: str | None = None,
    image_url: str | None = None,
    servings: int = 4,
    author: str | None = None,
    date_published: date | None = None,
    prep_time_minutes: int | None = None,
    cook_time_minutes: int | None = None,
    total_time_minutes: int | None = None,
    perform_time_minutes: int | None = None,
    nutrition: dict | None = None,
    aggregate_rating: dict | None = None,
    keywords: str | None = None,
    source_url: str | None = None,
) -> Recipe:
    r = Recipe()
    r.id = 42
    r.title = title
    r.description = description
    r.image_url = image_url
    r.servings = servings
    r.author = author
    r.date_published = date_published
    r.prep_time_minutes = prep_time_minutes
    r.cook_time_minutes = cook_time_minutes
    r.total_time_minutes = total_time_minutes
    r.perform_time_minutes = perform_time_minutes
    r.nutrition = nutrition
    r.aggregate_rating = aggregate_rating
    r.keywords = keywords
    r.source_url = source_url
    r.steps = []
    r.ingredients = []
    r.tags = []
    return r


def _make_ingredient(ing_id: int, name: str) -> Ingredient:
    ing = Ingredient()
    ing.id = ing_id
    ing.name = name
    return ing


def _make_step(
    position: int, text: str, name: str | None = None
) -> RecipeStep:
    s = RecipeStep()
    s.id = position + 100
    s.position = position
    s.text = text
    s.name = name
    return s


def _make_recipe_ingredient(
    ing: Ingredient, quantity: float = 100.0, unit: str = "g"
) -> RecipeIngredient:
    ri = RecipeIngredient()
    ri.id = ing.id
    ri.ingredient_id = ing.id
    ri.quantity = quantity
    ri.unit = unit
    ri.order_index = 0
    ri.ingredient = ing
    return ri


def _make_tag(tag_id: int, name: str, group: str) -> Tag:
    t = Tag()
    t.id = tag_id
    t.name = name
    t.group = group
    return t


def _make_recipe_tag(tag: Tag) -> RecipeTag:
    rt = RecipeTag()
    rt.id = tag.id
    rt.tag_id = tag.id
    rt.tag = tag
    return rt


class TestRecipeJSONLDExporter:
    def test_minimal_recipe(self) -> None:
        recipe = _make_recipe(title="Pasta")
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["@context"] == "https://schema.org"
        assert result["@type"] == "Recipe"
        assert result["name"] == "Pasta"
        assert result["recipeYield"] == "4"
        assert result["identifier"] == 42
        # Missing fields should be absent
        assert "description" not in result
        assert "image" not in result
        assert "author" not in result
        assert "datePublished" not in result
        assert "prepTime" not in result
        assert "cookTime" not in result
        assert "totalTime" not in result
        assert "performTime" not in result

    def test_description_and_image(self) -> None:
        recipe = _make_recipe(
            title="Pasta",
            description="A simple pasta dish",
            image_url="https://example.com/img.jpg",
        )
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["description"] == "A simple pasta dish"
        assert result["image"] == "https://example.com/img.jpg"

    def test_author_as_person(self) -> None:
        recipe = _make_recipe(title="Pasta", author="Jane Cook")
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["author"] == {"@type": "Person", "name": "Jane Cook"}

    def test_date_published(self) -> None:
        recipe = _make_recipe(
            title="Pasta", date_published=date(2025, 3, 15)
        )
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["datePublished"] == "2025-03-15"

    def test_durations(self) -> None:
        recipe = _make_recipe(
            title="Pasta",
            prep_time_minutes=15,
            cook_time_minutes=45,
            total_time_minutes=60,
            perform_time_minutes=30,
        )
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["prepTime"] == "PT15M"
        assert result["cookTime"] == "PT45M"
        assert result["totalTime"] == "PT1H"
        assert result["performTime"] == "PT30M"

    def test_duration_zero_minutes_included(self) -> None:
        recipe = _make_recipe(title="Pasta", total_time_minutes=0)
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["totalTime"] == "PT0M"

    def test_nutrition_and_aggregate_rating_passthrough(self) -> None:
        nutrition = {"calories": "240 kcal", "fatContent": "12 g"}
        aggregate_rating = {"ratingValue": 4.5, "reviewCount": 23}
        recipe = _make_recipe(
            title="Pasta",
            nutrition=nutrition,
            aggregate_rating=aggregate_rating,
        )
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["nutrition"] == nutrition
        assert result["aggregateRating"] == aggregate_rating

    def test_keywords(self) -> None:
        recipe = _make_recipe(
            title="Pasta", keywords="schnell, einfach, vegetarisch"
        )
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["keywords"] == "schnell, einfach, vegetarisch"

    def test_recipe_ingredients(self) -> None:
        recipe = _make_recipe(title="Pasta")
        ing1 = _make_ingredient(1, "Spaghetti")
        ing2 = _make_ingredient(2, "Tomaten")
        ri1 = _make_recipe_ingredient(ing1, quantity=500.0, unit="g")
        ri2 = _make_recipe_ingredient(ing2, quantity=300.0, unit="g")
        recipe.ingredients = [ri1, ri2]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["recipeIngredient"] == ["Spaghetti", "Tomaten"]

    def test_recipe_steps_as_how_to_steps(self) -> None:
        recipe = _make_recipe(title="Pasta")
        s1 = _make_step(0, "Kochen Sie die Spaghetti.", name="Spaghetti kochen")
        s2 = _make_step(1, "Servieren.")
        recipe.steps = [s1, s2]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        instructions = result["recipeInstructions"]
        assert len(instructions) == 2
        assert instructions[0] == {
            "@type": "HowToStep",
            "text": "Kochen Sie die Spaghetti.",
            "name": "Spaghetti kochen",
        }
        assert instructions[1] == {
            "@type": "HowToStep",
            "text": "Servieren.",
        }
        assert "name" not in instructions[1]

    def test_empty_steps_omitted(self) -> None:
        recipe = _make_recipe(title="Pasta")
        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert "recipeInstructions" not in result

    def test_category_tag(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag = _make_tag(1, "Hauptgericht", "category")
        rt = _make_recipe_tag(tag)
        recipe.tags = [rt]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["recipeCategory"] == "Hauptgericht"

    def test_cuisine_tag(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag = _make_tag(2, "Italienisch", "cuisine")
        rt = _make_recipe_tag(tag)
        recipe.tags = [rt]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["recipeCuisine"] == "Italienisch"

    def test_suitable_for_diet(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag1 = _make_tag(3, "VegetarianDiet", "diet")
        tag2 = _make_tag(4, "GlutenFreeDiet", "diet")
        recipe.tags = [_make_recipe_tag(tag1), _make_recipe_tag(tag2)]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["suitableForDiet"] == [
            "https://schema.org/VegetarianDiet",
            "https://schema.org/GlutenFreeDiet",
        ]

    def test_multiple_tag_groups_together(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag_cat = _make_tag(1, "Hauptgericht", "category")
        tag_cui = _make_tag(2, "Italienisch", "cuisine")
        tag_diet = _make_tag(3, "VegetarianDiet", "diet")
        tag_season = _make_tag(4, "Sommer", "season")
        recipe.tags = [
            _make_recipe_tag(tag_cat),
            _make_recipe_tag(tag_cui),
            _make_recipe_tag(tag_diet),
            _make_recipe_tag(tag_season),
        ]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert result["recipeCategory"] == "Hauptgericht"
        assert result["recipeCuisine"] == "Italienisch"
        assert result["suitableForDiet"] == [
            "https://schema.org/VegetarianDiet"
        ]

    def test_season_tags_ignored(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag = _make_tag(5, "Sommer", "season")
        recipe.tags = [_make_recipe_tag(tag)]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert "recipeCategory" not in result
        assert "recipeCuisine" not in result
        assert "suitableForDiet" not in result

    def test_ingredient_tags_ignored(self) -> None:
        recipe = _make_recipe(title="Pasta")
        tag = _make_tag(6, "Rahm", "ingredient")
        recipe.tags = [_make_recipe_tag(tag)]

        result = RecipeJSONLDExporter.to_jsonld(recipe)
        assert "recipeCategory" not in result
        assert "recipeCuisine" not in result
        assert "suitableForDiet" not in result

    def test_full_recipe(self) -> None:
        recipe = _make_recipe(
            title="Spaghetti Bolognese",
            description="Klassische Bolognese",
            image_url="https://example.com/bolognese.jpg",
            servings=4,
            author="Mamma",
            date_published=date(2025, 6, 1),
            prep_time_minutes=20,
            cook_time_minutes=60,
            total_time_minutes=80,
            perform_time_minutes=30,
            nutrition={"calories": "500 kcal"},
            aggregate_rating={"ratingValue": 4.8, "reviewCount": 42},
            keywords="Pasta, Fleisch, Klassiker",
        )

        ing1 = _make_ingredient(1, "Spaghetti")
        ing2 = _make_ingredient(2, "Hackfleisch")
        recipe.ingredients = [
            _make_recipe_ingredient(ing1, 400, "g"),
            _make_recipe_ingredient(ing2, 300, "g"),
        ]

        s1 = _make_step(0, "Zwiebeln anbraten.", "Soffritto")
        s2 = _make_step(1, "Hackfleisch hinzugeben und anbraten.")
        recipe.steps = [s1, s2]

        tag_cat = _make_tag(1, "Hauptgericht", "category")
        tag_cui = _make_tag(2, "Italienisch", "cuisine")
        tag_diet = _make_tag(3, "LowFatDiet", "diet")
        recipe.tags = [
            _make_recipe_tag(tag_cat),
            _make_recipe_tag(tag_cui),
            _make_recipe_tag(tag_diet),
        ]

        result = RecipeJSONLDExporter.to_jsonld(recipe)

        assert result["@context"] == "https://schema.org"
        assert result["@type"] == "Recipe"
        assert result["name"] == "Spaghetti Bolognese"
        assert result["description"] == "Klassische Bolognese"
        assert result["image"] == "https://example.com/bolognese.jpg"
        assert result["recipeYield"] == "4"
        assert result["author"] == {"@type": "Person", "name": "Mamma"}
        assert result["datePublished"] == "2025-06-01"
        assert result["prepTime"] == "PT20M"
        assert result["cookTime"] == "PT1H"
        assert result["totalTime"] == "PT1H20M"
        assert result["performTime"] == "PT30M"
        assert result["nutrition"] == {"calories": "500 kcal"}
        assert result["aggregateRating"] == {
            "ratingValue": 4.8,
            "reviewCount": 42,
        }
        assert result["keywords"] == "Pasta, Fleisch, Klassiker"
        assert result["recipeIngredient"] == ["Spaghetti", "Hackfleisch"]
        assert len(result["recipeInstructions"]) == 2
        assert result["recipeInstructions"][0] == {
            "@type": "HowToStep",
            "text": "Zwiebeln anbraten.",
            "name": "Soffritto",
        }
        assert result["recipeInstructions"][1] == {
            "@type": "HowToStep",
            "text": "Hackfleisch hinzugeben und anbraten.",
        }
        assert result["recipeCategory"] == "Hauptgericht"
        assert result["recipeCuisine"] == "Italienisch"
        assert result["suitableForDiet"] == [
            "https://schema.org/LowFatDiet"
        ]
        assert result["identifier"] == 42
