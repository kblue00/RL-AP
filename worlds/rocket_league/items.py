from BaseClasses import Item, ItemClassification

from . import locations


BASE_ITEM_ID = 12_346_000
ITEM_NAME_TO_ID = {
    "Win Ticket": BASE_ITEM_ID + 1,
    "Victory": BASE_ITEM_ID + 2,
    "Boost": BASE_ITEM_ID + 3,
    "Ball Cam": BASE_ITEM_ID + 4,
    "Jump/Flip": BASE_ITEM_ID + 5,
    "Air Roll": BASE_ITEM_ID + 6,
    "Brake": BASE_ITEM_ID + 7,
    "What a Save!": BASE_ITEM_ID + 101,
    "Nice Shot!": BASE_ITEM_ID + 102,
    "This is Rocket League!": BASE_ITEM_ID + 103,
    "Calculated.": BASE_ITEM_ID + 104,
    "Incoming!": BASE_ITEM_ID + 105,
    "Great Pass!": BASE_ITEM_ID + 106,
    "Scoreboard Trap": BASE_ITEM_ID + 201,
    "Ball Cam Trap": BASE_ITEM_ID + 202,
    "Jump Trap": BASE_ITEM_ID + 203,
    "Boost Trap": BASE_ITEM_ID + 204,
    "Spin Trap": BASE_ITEM_ID + 205,
}

TRAP_ITEMS = tuple(name for name in ITEM_NAME_TO_ID if name.endswith(" Trap"))
FILLER_ITEMS = tuple(name for name in ITEM_NAME_TO_ID
                     if name not in {
                         "Win Ticket", "Victory", "Boost", "Ball Cam", "Jump/Flip", "Air Roll", "Brake",
                         *TRAP_ITEMS,
                     })


def create_item(world, name: str) -> Item:
    if name == "Win Ticket":
        classification = ItemClassification.progression
        code = ITEM_NAME_TO_ID[name]
    elif name in {"Victory", "Boost", "Ball Cam", "Jump/Flip", "Brake"}:
        classification = ItemClassification.progression
        code = ITEM_NAME_TO_ID[name]
    elif name == "Air Roll":
        classification = ItemClassification.useful
        code = ITEM_NAME_TO_ID[name]
    elif name in TRAP_ITEMS:
        classification = ItemClassification.trap
        code = ITEM_NAME_TO_ID[name]
    else:
        classification = ItemClassification.filler
        code = ITEM_NAME_TO_ID[name]
    return Item(name, classification, code, world.player)


def create_item_pool(world) -> None:
    fillable_location_count = locations.count_fillable_locations(world.options)
    ticket_count = world.options.win_tickets_in_pool.value
    ability_items = ("Boost", "Ball Cam", "Jump/Flip", "Air Roll", "Brake") \
        if world.options.ability_unlocks.value else ()
    pool = [create_item(world, "Win Ticket") for _ in range(ticket_count)]
    pool.extend(create_item(world, name) for name in ability_items)
    filler_slots = fillable_location_count - ticket_count - len(ability_items)
    trap_count = (filler_slots * world.options.trap_percentage.value + 50) // 100
    trap_names = (
        "Scoreboard Trap", "Ball Cam Trap", "Jump Trap", "Boost Trap", "Spin Trap",
    )
    trap_weights = (
        world.options.scoreboard_trap_weight.value,
        world.options.ball_cam_trap_weight.value,
        world.options.jump_trap_weight.value,
        world.options.boost_trap_weight.value,
        world.options.spin_trap_weight.value,
    )
    weighted_traps = [name for name, weight in zip(trap_names, trap_weights) for _ in range(weight)]
    pool.extend(create_item(world, world.random.choice(weighted_traps)) for _ in range(trap_count))
    pool.extend(create_item(world, world.random.choice(FILLER_ITEMS))
                for _ in range(filler_slots - trap_count))
    world.multiworld.itempool += pool
