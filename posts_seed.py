"""Sample blog posts for Step 4/5 demo and testing — one per species, a
paraphrase case (scientific name, no "fox" in the text at all), and a
deliberate no-good-match case (a species with zero corpus coverage), per
the source brief's demo script (§13).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedPost:
    title: str
    body: str


POSTS: list[SeedPost] = [
    SeedPost(
        "Getting to Know the Red Fox",
        "The red fox is one of the most adaptable wild canids, thriving in "
        "forests, grasslands, and even city suburbs. Recognizable by its "
        "rust-orange coat and bushy white-tipped tail, it hunts mostly at "
        "dawn and dusk for rodents, birds, and insects.",
    ),
    SeedPost(
        "The Secretive World of Vulpes Vulpes",
        "Vulpes vulpes, commonly known by its Latin binomial, is one of the "
        "most widespread carnivores on the planet. This piece explores its "
        "hunting habits, its famously bushy tail, and its surprising "
        "adaptability to urban environments.",
    ),
    SeedPost(
        "Life Among Gray Wolves",
        "Gray wolves are highly social animals, living and hunting in "
        "tightly bonded packs led by a breeding pair. Their howls, used to "
        "coordinate hunts and mark territory, can carry for miles across "
        "open wilderness.",
    ),
    SeedPost(
        "Why Dogs Make Great Companions",
        "Domestic dogs have lived alongside humans for tens of thousands of "
        "years, bred over generations for loyalty, trainability, and "
        "companionship. From working breeds to lapdogs, they remain "
        "humanity's most enduring animal partnership.",
    ),
    SeedPost(
        "The Charming Red Panda",
        "The red panda is a small, tree-dwelling mammal native to the "
        "eastern Himalayas and southwestern China. With its rust-colored "
        "fur, ringed tail, and masked face, it's often mistaken for a "
        "relative of the giant panda, though it isn't closely related.",
    ),
    SeedPost(
        "Nighttime Visitors: Understanding Raccoons",
        "Raccoons are highly intelligent, nocturnal mammals known for their "
        "distinctive black facial mask and ringed tail. Their dexterous "
        "front paws let them manipulate objects with surprising precision, "
        "making them notorious for raiding trash cans and pet food bowls.",
    ),
    SeedPost(
        "Domestic Cats: Independent by Nature",
        "The domestic cat has been a human companion for thousands of "
        "years, valued first for pest control and later for companionship. "
        "Despite domestication, cats retain much of their wild ancestors' "
        "hunting instinct and independent streak.",
    ),
    SeedPost(
        "The Majestic African Elephant",
        "African elephants are the largest living land animals, known for "
        "their intelligence, complex social bonds, and remarkable memory. "
        "Their trunks serve as an all-purpose tool for breathing, drinking, "
        "grasping, and communication.",
    ),
]
