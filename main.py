"""Точка входа приложения «ФинУчёт»."""
import os
#ошибка скачивания флет
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
#ошибка скачивания флет
import flet as ft

from database import Database
from services import FinanceService
from ui import FinanceApp


def main(page: ft.Page) -> None:
    # В собранном приложении Flet задаёт каталог постоянного хранилища
    storage = os.getenv("FLET_APP_STORAGE_DATA", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(storage, exist_ok=True)
    db = Database(os.path.join(storage, "finance.db"))
    FinanceApp(page, FinanceService(db)).build()


if __name__ == "__main__":
    ft.run(main)

