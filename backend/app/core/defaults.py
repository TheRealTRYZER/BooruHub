"""BooruHub Default Settings."""

DEFAULT_USER_TAGS = "order:score rating:general"

# Default mappings created for new users
# unitag -> {danbooru, e621, rule34}
STARTER_MAPPINGS = [
    {
        "unitag": "order:score",
        "danbooru_tags": "order:score",
        "e621_tags": "order:score",
        "rule34_tags": "sort:score:desc"
    },
    {
        "unitag": "rating:general",
        "danbooru_tags": "rating:general",
        "e621_tags": "rating:safe",
        "rule34_tags": "rating:general"
    },
    {
        "unitag": "rating:explicit",
        "danbooru_tags": "rating:explicit",
        "e621_tags": "rating:e",
        "rule34_tags": "rating:explicit"
    },
    {
        "unitag": "male",
        "danbooru_tags": "1boy, 2boys, multiple_boys",
        "e621_tags": "male",
        "rule34_tags": "male"
    },
    {
        "unitag": "female",
        "danbooru_tags": "1girl, 2girls, multiple_girls",
        "e621_tags": "female",
        "rule34_tags": "female"
    },
    {
        "unitag": "futanari",
        "danbooru_tags": "futanari",
        "e621_tags": "gynomorph",
        "rule34_tags": "futanari"
    },
    {
        "unitag": "order:hot",
        "danbooru_tags": "order:rank",
        "e621_tags": "order:hot",
        "rule34_tags": "sort:score:desc"
    }
]
