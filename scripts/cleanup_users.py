"""
Скрипт для удаления пользователей из базы данных, которых нет в users_dump.csv.
Сравнивает список пользователей в БД со списком в CSV и удаляет тех, кого нет в файле.
"""

import asyncio
import csv

from sqlalchemy import select, delete

from src.database.core import SessionFactory
from src.database.models import User


async def cleanup_users():
    """Удаляет пользователей из БД, которых нет в CSV файле."""

    csv_file = "users_dump.csv"

    # Читаем ID всех пользователей из CSV
    csv_user_ids = set()

    print(f"Читаю файл {csv_file}...")

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_user_ids.add(int(row["id"]))

    print(f"Найдено пользователей в CSV: {len(csv_user_ids)}")

    # Получаем всех пользователей из БД
    async with SessionFactory() as session:
        print("Получаю список пользователей из базы данных...")

        result = await session.execute(select(User.id))
        db_user_ids = {row[0] for row in result.all()}

        print(f"Найдено пользователей в БД: {len(db_user_ids)}")

        # Находим пользователей, которые есть и в БД, и в CSV
        users_to_delete = []
        for db_user in db_user_ids:
            if db_user not in csv_user_ids:
                users_to_delete.append(db_user)

        if not users_to_delete:
            print(
                "✓ Нет пользователей для удаления. Нет совпадений между БД и CSV файлом."
            )
            return

        print(
            f"\nПользователи для удаления (есть И в БД, И в CSV): {len(users_to_delete)}"
        )

        # Запрашиваем подтверждение
        confirmation = input(
            f"\nВы уверены, что хотите удалить {len(users_to_delete)} пользователей? (yes/no): "
        )

        if confirmation.lower() != "yes":
            print("Операция отменена.")
            return

        # Удаляем пользователей
        print("Удаляю пользователей...")

        stmt = delete(User).where(User.id.in_(users_to_delete))
        result = await session.execute(stmt)
        await session.commit()

        print(f"✓ Успешно удалено {result.rowcount} пользователей")


if __name__ == "__main__":
    asyncio.run(cleanup_users())
