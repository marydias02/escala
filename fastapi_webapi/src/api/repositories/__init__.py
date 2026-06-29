from api.repositories.item_repository import ItemRepository


async def declare_tables():
    await ItemRepository().declare_table()

    # WRITE MORE DECLARATIONS HERE
