"""The syllabus: every activity Sakhi can run, as plain data."""

from dataclasses import dataclass
from typing import Literal

Check = Literal["word", "sentence", "letter", "number", "keywords"]
BoardKind = Literal["word", "sentence", "letter", "number", "math", "science"]


@dataclass(frozen=True)
class Item:
    board: str  # exactly what is shown on the learning board
    answer: str  # the expected answer (what the child should say)
    explain: str  # how to help the child when they get it wrong
    accept: tuple[str, ...] = ()  # keywords that count as correct (science only)


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    board_kind: BoardKind
    check: Check
    ask: str  # what Sakhi does with each item
    intro: str  # said once when the activity starts ("" if none)
    items: tuple[Item, ...]
    segment: int | None = None  # pause and ask "ready?" after this many items
    ordered: bool = False  # take pool items in the listed order instead of at random
    demos: tuple[tuple[int, int], ...] = ()  # (a, b) examples taught with animated sticks before practice
    extra_demo: tuple[int, int] | None = None  # one more example if the child says they do not understand


def _words() -> tuple[Item, ...]:
    # two-letter words first, then three-letter, then four-letter
    pool = (
        "am an at in on up it is "
        "cat sun pen dog bat cup hat bus red big map bag "
        "fish book tree milk hand frog moon star door ball"
    ).split()
    return tuple(Item(w, w, f"Read the word slowly, one letter at a time: {'-'.join(w.upper())}, {w}.") for w in pool)


def _sentences() -> tuple[Item, ...]:
    pool = (
        "The cat is big.|I like my dog.|The sun is hot.|Birds can fly.|I see a bird.|The dog can run.|"
        "My bag is red.|Fish can swim.|She has a pen.|He is my friend.|We eat rice.|The moon is up.|"
        "I can jump.|It is a ball.|Mom has a cup.|The tree is tall."
    ).split("|")
    return tuple(Item(s, s, f"Read it slowly, one word at a time: {s}") for s in pool)


_LETTER_WORDS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
    "apple ball cat dog egg fish goat hat ice jug kite lion mango nest orange pen queen rabbit sun tree umbrella "
    "van watch box yak zebra"
).split()))


def _alphabet() -> tuple[Item, ...]:
    return tuple(
        Item(c, c, f"Say the letter {c} clearly and slowly, and show that {c} is the first letter of '{_LETTER_WORDS[c]}'.")
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )


def _numbers() -> tuple[Item, ...]:
    def explain(n: int) -> str:
        if n < 10:
            return f"Say the number {n} clearly, and show it with {n} fingers or objects."
        if n == 100:
            return "Say the number 100 clearly: it is ten tens, one hundred."
        return f"Say the number {n} clearly and break it up: {n // 10} tens and {n % 10} ones, which is {n}."

    return tuple(Item(str(n), str(n), explain(n)) for n in range(1, 101))


def _addition() -> tuple[Item, ...]:
    return tuple(
        Item(
            f"{a} + {b} = ?",
            str(a + b),
            f"Use the sticks on the board: {a} sticks, then {b} more. Count them all together, one to {a + b}, "
            f"with the child, so {a} plus {b} equals {a + b}.",
        )
        for a, b in ((1, 2), (3, 1), (4, 3), (2, 5), (3, 3))
    )


def _subtraction() -> tuple[Item, ...]:
    return tuple(
        Item(
            f"{a} - {b} = ?",
            str(a - b),
            f"Use the sticks on the board: {a} sticks, {b} of them are crossed out. Count the sticks that are left "
            f"with the child, so {a} minus {b} equals {a - b}.",
        )
        for a, b in ((4, 1), (7, 3), (6, 3), (8, 5), (9, 4))
    )


MODULES: dict[str, Module] = {
    m.id: m
    for m in (
        Module(
            "english_words", "Word reading", "word", "word",
            "Look at the word on the board and ask the child to read it, in your own natural words (for example 'Look at this "
            "word. Can you read it for me?', said in the teaching language). Do NOT say the word and do NOT spell it out: wait for the child.",
            "", _words(), segment=5, ordered=True,
        ),
        Module(
            "english_sentences", "Sentence reading", "sentence", "sentence",
            "The sentence is taught by a recorded demonstration, so do not read, spell or say any word of it "
            "yourself. Ask the child to read the whole sentence.", "", _sentences(), segment=5,
        ),
        Module(
            "alphabet", "Alphabet A to Z", "letter", "letter",
            "Ask the child to say the letter shown on the board. Do NOT say the letter yourself: wait for the child.",
            "", _alphabet(),
        ),
        Module(
            "numbers", "Numbers 1 to 100", "number", "number",
            "Ask the child to say the number shown on the board. Do NOT say the number yourself: wait for the child.",
            "", _numbers(),
        ),
        Module(
            "addition", "Addition", "math", "number",
            "Ask the child to work it out and say the answer. Do NOT say the answer.", "", _addition(),
            demos=((2, 3), (4, 2)), extra_demo=(1, 4),
        ),
        Module(
            "subtraction", "Subtraction", "math", "number",
            "Ask the child to work it out and say the answer. Do NOT say the answer.", "", _subtraction(),
            demos=((5, 2), (6, 4)), extra_demo=(7, 2),
        ),
        Module(
            "science_living", "Living and non-living things", "science", "keywords",
            "Ask the question shown on the board and wait for the child's answer.",
            "Living things grow and need food, water and air, like dogs, people and plants. "
            "Non-living things, like rocks, chairs and toys, do not grow or need food.",
            (
                Item("Is a dog living or non-living?", "living", "A dog grows and needs food and water, so it is living.", ("living", "alive")),
                Item("Does a plant grow?", "yes", "Yes! Plants grow, and they need water and sunlight, so they are living.", ("yes", "yeah", "yep")),
                Item("Is a chair a living thing?", "no, it is non-living", "A chair does not grow or eat, so it is non-living.", ("no", "non living", "nonliving", "not living")),
                Item("Is a rock living or non-living?", "non-living", "A rock does not grow or need food, so it is non-living.", ("non living", "nonliving", "not living", "not alive")),
                Item("Do living things need water?", "yes", "Yes! All living things need water to live and grow.", ("yes", "yeah", "yep")),
            ),
        ),
        Module(
            "science_senses", "The five senses", "science", "keywords",
            "Ask the question shown on the board and wait for the child's answer.",
            "We have five senses: eyes to see, ears to hear, nose to smell, tongue to taste, and skin to feel touch.",
            (
                Item("Which part of your body helps you hear?", "ears", "We hear with our ears.", ("ear", "ears")),
                Item("Which sense helps you smell a flower?", "nose", "We smell with our nose.", ("nose", "smell")),
                Item("What do we use to see?", "eyes", "We see with our eyes.", ("eye", "eyes")),
                Item("What do we use to taste food?", "tongue", "We taste with our tongue.", ("tongue",)),
                Item("Which part of the body feels touch, like soft or rough?", "skin", "We feel touch with our skin.", ("skin", "hand", "hands", "touch")),
            ),
        ),
        Module(
            "science_plants_animals", "Plants and animals", "science", "keywords",
            "Ask the question shown on the board and wait for the child's answer.",
            "A plant has roots, a stem, leaves and a flower. Animals need food, water and a shelter to live.",
            (
                Item("Which part of the plant takes in water?", "roots", "The roots take in water from the soil.", ("root", "roots")),
                Item("Can you name one part of a plant?", "roots, stem, leaves or flower", "A plant has roots, a stem, leaves and a flower.", ("root", "roots", "stem", "leaf", "leaves", "flower")),
                Item("What does an animal need to live?", "food, water or shelter", "Animals need food, water and a shelter to live.", ("food", "water", "shelter", "home", "air")),
                Item("Which part of the plant holds it up straight?", "stem", "The stem holds the plant up.", ("stem",)),
                Item("Where does a bird live?", "in a nest", "A bird lives in a nest, which is its shelter.", ("nest", "tree", "home")),
            ),
        ),
        Module(
            "science_weather", "Weather and seasons", "science", "keywords",
            "Ask the question shown on the board and wait for the child's answer.",
            "Weather can be sunny, rainy, windy or cloudy. The four seasons are summer, the rainy season, "
            "autumn and winter, and we wear different clothes in each.",
            (
                Item("What do we use when it rains?", "an umbrella or a raincoat", "When it rains we use an umbrella or a raincoat.", ("umbrella", "raincoat", "rain coat")),
                Item("What kind of clothes do we wear in cold weather?", "warm clothes like a sweater", "In cold weather we wear warm clothes, like a sweater.", ("warm", "sweater", "woolen", "woollen", "jacket", "coat", "thick")),
                Item("Can you describe a sunny day?", "hot, bright, with the sun in the sky", "A sunny day is bright and warm, with the sun in the sky.", ("sun", "sunny", "hot", "bright", "warm", "shine", "shining")),
                Item("Which season has a lot of rain?", "the rainy season", "The rainy season, or monsoon, has a lot of rain.", ("rainy", "rain", "monsoon")),
                Item("Which weather has many clouds in the sky?", "cloudy", "On a cloudy day the sky is full of clouds.", ("cloudy", "cloud", "clouds")),
            ),
        ),
    )
}
