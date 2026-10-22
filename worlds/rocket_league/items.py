from BaseClasses import Item, ItemClassification


BASE_ITEM_ID = 12_346_000
ITEM_NAME_TO_ID = {
    "Win Ticket": BASE_ITEM_ID + 1,
    "Victory": BASE_ITEM_ID + 2,
    "What a Save!": BASE_ITEM_ID + 101,
    "Nice Shot!": BASE_ITEM_ID + 102,
    "This is Rocket League!": BASE_ITEM_ID + 103,
    "Calculated.": BASE_ITEM_ID + 104,
    "Incoming!": BASE_ITEM_ID + 105,
    "Great Pass!": BASE_ITEM_ID + 106,
}

FILLER_ITEMS = tuple(name for name in ITEM_NAME_TO_ID if name not in {"Win Ticket", "Victory"})


def create_item(world, name: str) -> Item:
    if name == "Win Ticket":
        classification = ItemClassification.progression
        code = ITEM_NAME_TO_ID[name]
    elif name == "Victory":
        classification = ItemClassification.progression
        code = ITEM_NAME_TO_ID[name]
    else:
        classification = ItemClassification.filler
        code = ITEM_NAME_TO_ID[name]
    return Item(name, classification, code, world.player)


def create_item_pool(world) -> None:
    fillable_location_count = world.options.win_checks.value + 20 + (5 if world.options.non1v1_mode.value else 0)
    ticket_count = world.options.win_tickets_in_pool.value
    pool = [create_item(world, "Win Ticket") for _ in range(ticket_count)]
    pool.extend(create_item(world, world.random.choice(FILLER_ITEMS))
                for _ in range(fillable_location_count - ticket_count))
    world.multiworld.itempool += pool
