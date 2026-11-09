"""Модели данных приложения «ФинУчёт»."""
from dataclasses import dataclass
from datetime import date

INCOME = "income"      # тип операции: доход
EXPENSE = "expense"    # тип операции: расход


@dataclass
class Category:
    """Категория доходов или расходов."""
    id: int
    name: str
    kind: str


@dataclass
class Transaction:
    """Финансовая операция. Сумма хранится в копейках."""
    id: int
    kind: str
    amount_kop: int
    category_id: int
    category_name: str
    note: str
    op_date: date


@dataclass
class BudgetStatus:
    """Состояние месячного лимита по категории расходов."""
    category_id: int
    category_name: str
    limit_kop: int
    spent_kop: int

    @property
    def ratio(self) -> float:
        """Доля израсходованного лимита (может быть больше 1)."""
        return self.spent_kop / self.limit_kop if self.limit_kop > 0 else 0.0

    @property
    def exceeded(self) -> bool:
        return self.spent_kop > self.limit_kop
