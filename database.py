"""Слой доступа к данным: работа с SQLite."""
import sqlite3
from datetime import date
from typing import List, Optional, Tuple

from models import Category, Transaction, INCOME, EXPENSE

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    kind  TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    UNIQUE (name, kind)
);
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    amount_kop  INTEGER NOT NULL CHECK (amount_kop > 0),
    category_id INTEGER NOT NULL REFERENCES categories (id),
    note        TEXT NOT NULL DEFAULT '',
    op_date     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
    category_id INTEGER PRIMARY KEY REFERENCES categories (id),
    limit_kop   INTEGER NOT NULL CHECK (limit_kop > 0)
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions (op_date);
"""

DEFAULT_CATEGORIES = [
    ("Зарплата", INCOME), ("Стипендия", INCOME), ("Подработка", INCOME),
    ("Подарки", INCOME), ("Прочие доходы", INCOME),
    ("Продукты", EXPENSE), ("Транспорт", EXPENSE), ("Жильё и связь", EXPENSE),
    ("Развлечения", EXPENSE), ("Здоровье", EXPENSE), ("Одежда", EXPENSE),
    ("Образование", EXPENSE), ("Прочие расходы", EXPENSE),
]


class Database:
    """Инкапсулирует соединение с SQLite и SQL-запросы."""

    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._seed_categories()

    def _seed_categories(self) -> None:
        count = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            self.conn.executemany(
                "INSERT INTO categories (name, kind) VALUES (?, ?)",
                DEFAULT_CATEGORIES)
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- категории ----
    def list_categories(self, kind: Optional[str] = None) -> List[Category]:
        sql, args = "SELECT id, name, kind FROM categories", ()
        if kind:
            sql, args = sql + " WHERE kind = ?", (kind,)
        rows = self.conn.execute(sql + " ORDER BY id", args).fetchall()
        return [Category(r["id"], r["name"], r["kind"]) for r in rows]

    def get_category(self, category_id: int) -> Optional[Category]:
        r = self.conn.execute(
            "SELECT id, name, kind FROM categories WHERE id = ?",
            (category_id,)).fetchone()
        return Category(r["id"], r["name"], r["kind"]) if r else None

    # ---- операции ----
    def add_transaction(self, kind: str, amount_kop: int, category_id: int,
                        note: str, op_date: date) -> int:
        cur = self.conn.execute(
            "INSERT INTO transactions (kind, amount_kop, category_id, note, op_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (kind, amount_kop, category_id, note, op_date.isoformat()))
        self.conn.commit()
        return cur.lastrowid

    def delete_transaction(self, tx_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_transactions(self, date_from: Optional[date] = None,
                          date_to: Optional[date] = None,
                          limit: Optional[int] = None) -> List[Transaction]:
        sql = ("SELECT t.id, t.kind, t.amount_kop, t.category_id, c.name AS cname, "
               "t.note, t.op_date FROM transactions t "
               "JOIN categories c ON c.id = t.category_id WHERE 1 = 1")
        args: list = []
        if date_from:
            sql += " AND t.op_date >= ?"
            args.append(date_from.isoformat())
        if date_to:
            sql += " AND t.op_date <= ?"
            args.append(date_to.isoformat())
        sql += " ORDER BY t.op_date DESC, t.id DESC"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        rows = self.conn.execute(sql, args).fetchall()
        return [Transaction(r["id"], r["kind"], r["amount_kop"], r["category_id"],
                            r["cname"], r["note"], date.fromisoformat(r["op_date"]))
                for r in rows]

    # ---- агрегаты ----
    def sum_by_kind(self, kind: str, date_from: Optional[date] = None,
                    date_to: Optional[date] = None) -> int:
        sql = "SELECT COALESCE(SUM(amount_kop), 0) FROM transactions WHERE kind = ?"
        args: list = [kind]
        if date_from:
            sql += " AND op_date >= ?"
            args.append(date_from.isoformat())
        if date_to:
            sql += " AND op_date <= ?"
            args.append(date_to.isoformat())
        return int(self.conn.execute(sql, args).fetchone()[0])

    def sum_by_category(self, kind: str, date_from: date,
                        date_to: date) -> List[Tuple[int, str, int]]:
        rows = self.conn.execute(
            "SELECT c.id, c.name, SUM(t.amount_kop) AS total "
            "FROM transactions t JOIN categories c ON c.id = t.category_id "
            "WHERE t.kind = ? AND t.op_date BETWEEN ? AND ? "
            "GROUP BY c.id, c.name ORDER BY total DESC",
            (kind, date_from.isoformat(), date_to.isoformat())).fetchall()
        return [(r["id"], r["name"], int(r["total"])) for r in rows]

    # ---- бюджеты ----
    def set_budget(self, category_id: int, limit_kop: int) -> None:
        self.conn.execute(
            "INSERT INTO budgets (category_id, limit_kop) VALUES (?, ?) "
            "ON CONFLICT(category_id) DO UPDATE SET limit_kop = excluded.limit_kop",
            (category_id, limit_kop))
        self.conn.commit()

    def delete_budget(self, category_id: int) -> None:
        self.conn.execute("DELETE FROM budgets WHERE category_id = ?", (category_id,))
        self.conn.commit()

    def list_budgets(self) -> dict:
        rows = self.conn.execute("SELECT category_id, limit_kop FROM budgets").fetchall()
        return {r["category_id"]: r["limit_kop"] for r in rows}
