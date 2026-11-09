"""Слой бизнес-логики: проверка данных и расчёт показателей."""
import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from database import Database
from models import BudgetStatus, Category, Transaction, INCOME, EXPENSE

MAX_AMOUNT_KOP = 10_000_000_000      # 100 млн руб. — верхняя граница суммы
MAX_NOTE_LENGTH = 100


class ValidationError(ValueError):
    """Ошибка проверки введённых пользователем данных."""


def parse_amount(text: Optional[str]) -> int:
    """Преобразует строку вида «1 250,50» в копейки (125050)."""
    cleaned = (text or "").replace("\u00a0", "").replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        raise ValidationError("Введите сумму")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValidationError("Сумма должна быть числом")
    if not value.is_finite():
        raise ValidationError("Сумма должна быть числом")
    if value <= 0:
        raise ValidationError("Сумма должна быть больше нуля")
    if value.as_tuple().exponent < -2:
        raise ValidationError("Допускается не более двух знаков после запятой")
    kop = int(value * 100)
    if kop > MAX_AMOUNT_KOP:
        raise ValidationError("Сумма слишком велика")
    return kop


def parse_date(text: Optional[str]) -> date:
    """Разбирает дату в формате ДД.ММ.ГГГГ."""
    try:
        return datetime.strptime((text or "").strip(), "%d.%m.%Y").date()
    except ValueError:
        raise ValidationError("Дата должна быть в формате ДД.ММ.ГГГГ")


def format_money(kop: int) -> str:
    """Форматирует сумму в копейках: 125050 -> «1 250,50 ₽»."""
    sign = "-" if kop < 0 else ""
    rub, cents = divmod(abs(kop), 100)
    return f"{sign}{rub:,}".replace(",", " ") + f",{cents:02d} ₽"


def month_range(year: int, month: int) -> Tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


class FinanceService:
    """Фасад бизнес-логики, используемый слоем интерфейса."""

    def __init__(self, db: Database):
        self.db = db

    def categories(self, kind: Optional[str] = None) -> List[Category]:
        return self.db.list_categories(kind)

    def add_operation(self, kind: str, amount_text: str, category_id,
                      note: str, date_text: str) -> int:
        if kind not in (INCOME, EXPENSE):
            raise ValidationError("Выберите тип операции")
        amount = parse_amount(amount_text)
        try:
            cat = self.db.get_category(int(category_id))
        except (TypeError, ValueError):
            cat = None
        if cat is None:
            raise ValidationError("Выберите категорию")
        if cat.kind != kind:
            raise ValidationError("Категория не соответствует типу операции")
        note = (note or "").strip()
        if len(note) > MAX_NOTE_LENGTH:
            raise ValidationError(f"Комментарий не длиннее {MAX_NOTE_LENGTH} символов")
        return self.db.add_transaction(kind, amount, cat.id, note, parse_date(date_text))

    def delete_operation(self, tx_id: int) -> bool:
        return self.db.delete_transaction(tx_id)

    def operations(self, year: int, month: int) -> List[Transaction]:
        start, end = month_range(year, month)
        return self.db.list_transactions(start, end)

    def recent(self, count: int = 5) -> List[Transaction]:
        return self.db.list_transactions(limit=count)

    def balance(self) -> int:
        return self.db.sum_by_kind(INCOME) - self.db.sum_by_kind(EXPENSE)

    def month_summary(self, year: int, month: int) -> dict:
        start, end = month_range(year, month)
        income = self.db.sum_by_kind(INCOME, start, end)
        expense = self.db.sum_by_kind(EXPENSE, start, end)
        return {"income": income, "expense": expense, "balance": income - expense}

    def expense_by_category(self, year: int, month: int) -> List[Tuple[str, int, float]]:
        start, end = month_range(year, month)
        rows = self.db.sum_by_category(EXPENSE, start, end)
        total = sum(r[2] for r in rows)
        return [(name, kop, kop / total if total else 0.0) for _, name, kop in rows]

    def set_limit(self, category_id: int, limit_text: str) -> None:
        if not (limit_text or "").strip():
            self.db.delete_budget(category_id)
            return
        self.db.set_budget(category_id, parse_amount(limit_text))

    def budget_statuses(self, year: int, month: int) -> List[BudgetStatus]:
        start, end = month_range(year, month)
        spent = {cid: kop for cid, _, kop in
                 self.db.sum_by_category(EXPENSE, start, end)}
        limits = self.db.list_budgets()
        result = []
        for cat in self.db.list_categories(EXPENSE):
            result.append(BudgetStatus(cat.id, cat.name, limits.get(cat.id, 0),
                                       spent.get(cat.id, 0)))
        return result
