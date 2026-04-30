"""
Скрипт для импорта пользователей из users_dump.csv в базу данных.
Импортируются только пользователи с заполненным referral_source.
"""

import asyncio
import csv
from datetime import datetime

from src.database.core import SessionFactory
from src.database.models import User


async def import_users():
    """Импортирует пользователей из CSV файла в базу данных."""

    csv_file = "users_with_touched_at.csv"

    # Читаем CSV файл
    users_to_import = []
    skipped_count = 0
    skipped_by_date_count = 0
    cutoff_date = datetime(2025, 12, 31, 0, 0, 0)

    print(f"Читаю файл {csv_file}...")

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Парсим created_at
            created_at = datetime.fromisoformat(row["created_at"])

            # Пропускаем пользователей с датой created_at <= 31.12.2025
            if created_at <= cutoff_date:
                skipped_by_date_count += 1
                continue

            source = row.get("referral_source")
            touched_at = (
                datetime.fromisoformat(row["touched_at"])
                if row.get("touched_at")
                else None
            )

            user = User(
                id=int(row["id"]),
                username=row["username"] if row["username"] else None,
                full_name=row["full_name"] if row["full_name"] else None,
                touched_at=touched_at,
                source=source,
                created_at=created_at,
                updated_at=created_at,
            )
            users_to_import.append(user)

    print(f"Найдено пользователей для импорта: {len(users_to_import)}")
    print(f"Пропущено пользователей без referral_source: {skipped_count}")
    print(
        f"Пропущено пользователей по дате (created_at <= 31.12.2025): {skipped_by_date_count}"
    )

    if not users_to_import:
        print("Нет пользователей для импорта.")
        return

    # Импортируем в базу данных
    async with SessionFactory() as session:
        print("Начинаю импорт в базу данных...")

        # Проверяем и добавляем/обновляем пользователей
        for user in users_to_import:
            # Проверяем, существует ли пользователь
            existing_user = await session.get(User, user.id)

            if existing_user:
                # Обновляем существующего пользователя
                existing_user.username = user.username
                existing_user.full_name = user.full_name
                existing_user.source = user.source
                existing_user.updated_at = datetime.now()
            else:
                # Добавляем нового пользователя
                session.add(user)

        await session.commit()

        print(f"✓ Успешно импортировано/обновлено {len(users_to_import)} пользователей")


if __name__ == "__main__":
    asyncio.run(import_users())
