"""Слой интерфейса на Flet (версия 1.0)."""
from datetime import date

import flet as ft

from models import INCOME, EXPENSE, Transaction
from services import FinanceService, ValidationError, format_money

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль",
          "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


class FinanceApp:
    """Собирает экраны приложения и обрабатывает действия пользователя."""

    def __init__(self, page: ft.Page, service: FinanceService):
        self.page = page
        self.service = service
        today = date.today()
        self.year, self.month = today.year, today.month
        self.screen = 0
        self.content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=10)

    # ------------------------------------------------------------ переключение темы
    def toggle_theme(self, e) -> None:
        """Переключает тему приложения между светлой и темной."""
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            e.control.icon = ft.Icons.DARK_MODE_OUTLINED
            e.control.tooltip = "Включить темную тему"
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            e.control.icon = ft.Icons.LIGHT_MODE_OUTLINED
            e.control.tooltip = "Включить светлую тему"
        self.page.update()
        
    # ------------------------------------------------------------ каркас
    def build(self) -> None:
        page = self.page
        page.title = "ФинУчёт"
        # Устанавливаем темную тему по умолчанию
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
        
        # Добавляем AppBar с кнопкой переключения темы в правом углу
        page.appbar = ft.AppBar(
            title=ft.Text("ФинУчёт"),
            center_title=True,
            actions=[
                ft.IconButton(
                    icon=ft.Icons.LIGHT_MODE_OUTLINED,
                    tooltip="Включить светлую тему",
                    on_click=self.toggle_theme,
                )
            ],
        )
        page.navigation_bar = ft.NavigationBar(
            selected_index=0,
            on_change=self.on_nav,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, label="Главная"),
                ft.NavigationBarDestination(icon=ft.Icons.LIST_ALT, label="Операции"),
                ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART_OUTLINE, label="Статистика"),
                ft.NavigationBarDestination(icon=ft.Icons.SAVINGS_OUTLINED, label="Бюджет"),
            ],
        )
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.Icons.ADD, on_click=self.open_add_dialog)
        page.add(ft.SafeArea(content=self.content, expand=True))
        self.refresh()

    def on_nav(self, e) -> None:
        self.screen = int(e.control.selected_index)
        self.refresh()

    def refresh(self) -> None:
        views = [self._home_view, self._operations_view,
                 self._stats_view, self._budget_view]
        self.content.controls = [self._month_bar()] + views[self.screen]()
        self.page.update()

    def _shift_month(self, delta: int) -> None:
        index = self.year * 12 + (self.month - 1) + delta
        self.year, self.month = index // 12, index % 12 + 1
        self.refresh()

    def _month_bar(self) -> ft.Control:
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT,
                              on_click=lambda _: self._shift_month(-1)),
                ft.Text(f"{MONTHS[self.month - 1]} {self.year}", size=18,
                        weight=ft.FontWeight.BOLD),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT,
                              on_click=lambda _: self._shift_month(1)),
            ])

    # ------------------------------------------------------------ виджеты
    @staticmethod
    def _stat_card(title: str, value_kop: int, color: str) -> ft.Control:
        return ft.Card(expand=True, content=ft.Container(
            padding=12,
            content=ft.Column(spacing=4, controls=[
                ft.Text(title, size=12),
                ft.Text(format_money(value_kop), size=16,
                        weight=ft.FontWeight.BOLD, color=color)])))

    def _tx_tile(self, tx: Transaction, deletable: bool) -> ft.Control:
        is_income = tx.kind == INCOME
        sign = "+" if is_income else "-"
        color = ft.Colors.GREEN if is_income else ft.Colors.RED
        subtitle = tx.op_date.strftime("%d.%m.%Y") + (f" · {tx.note}" if tx.note else "")
        trailing = [ft.Text(f"{sign}{format_money(tx.amount_kop)}", color=color,
                            weight=ft.FontWeight.BOLD)]
        if deletable:
            trailing.append(ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=lambda _, tid=tx.id: self._delete(tid)))
        return ft.ListTile(
            leading=ft.Icon(ft.Icons.ARROW_DOWNWARD if is_income else ft.Icons.ARROW_UPWARD,
                            color=color),
            title=ft.Text(tx.category_name),
            subtitle=ft.Text(subtitle),
            trailing=ft.Row(trailing, tight=True))

    # ------------------------------------------------------------ экраны
    def _home_view(self) -> list:
        summary = self.service.month_summary(self.year, self.month)
        balance_color = ft.Colors.RED if self.service.balance() < 0 else ft.Colors.TEAL
        controls = [
            ft.Card(content=ft.Container(padding=16, content=ft.Column(spacing=4, controls=[
                ft.Text("Общий баланс"),
                ft.Text(format_money(self.service.balance()), size=30,
                        weight=ft.FontWeight.BOLD, color=balance_color)]))),
            ft.Row(controls=[
                self._stat_card("Доходы за месяц", summary["income"], ft.Colors.GREEN),
                self._stat_card("Расходы за месяц", summary["expense"], ft.Colors.RED)]),
            ft.Text("Последние операции", size=16, weight=ft.FontWeight.BOLD),
        ]
        recent = self.service.recent(5)
        if recent:
            controls += [self._tx_tile(t, False) for t in recent]
        else:
            controls.append(ft.Text("Операций пока нет. Нажмите «+», чтобы добавить."))
        return controls

    def _operations_view(self) -> list:
        items = self.service.operations(self.year, self.month)
        if not items:
            return [ft.Text("За выбранный месяц операций нет.")]
        return [self._tx_tile(t, True) for t in items]

    def _stats_view(self) -> list:
        rows = self.service.expense_by_category(self.year, self.month)
        if not rows:
            return [ft.Text("Нет расходов за выбранный месяц.")]
        total = sum(r[1] for r in rows)
        controls = [ft.Text(f"Всего расходов: {format_money(total)}", size=16,
                            weight=ft.FontWeight.BOLD)]
        for name, kop, share in rows:
            controls.append(ft.Column(spacing=2, controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Text(name),
                    ft.Text(f"{format_money(kop)} ({share * 100:.0f}%)")]),
                ft.ProgressBar(value=share)]))
        return controls

    def _budget_view(self) -> list:
        controls = [ft.Text("Месячные лимиты расходов", size=16,
                            weight=ft.FontWeight.BOLD)]
        for st in self.service.budget_statuses(self.year, self.month):
            if st.limit_kop:
                text = f"Потрачено {format_money(st.spent_kop)} из {format_money(st.limit_kop)}"
                color = ft.Colors.RED if st.exceeded else ft.Colors.TEAL
                sub = ft.Column(spacing=4, controls=[
                    ft.Text(text),
                    ft.ProgressBar(value=min(st.ratio, 1.0), color=color)])
            else:
                sub = ft.Text("Лимит не задан")
            controls.append(ft.ListTile(
                title=ft.Text(st.category_name), subtitle=sub,
                trailing=ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda _, s=st: self.open_limit_dialog(s))))
        return controls

    # ------------------------------------------------------------ действия
    def _delete(self, tx_id: int) -> None:
        self.service.delete_operation(tx_id)
        self.refresh()

    def _notify(self, text: str) -> None:
        self.page.show_dialog(ft.SnackBar(content=ft.Text(text)))

    def open_add_dialog(self, e=None) -> None:
        kind = ft.Dropdown(
            label="Тип операции", value=EXPENSE,
            options=[ft.DropdownOption(key=EXPENSE, text="Расход"),
                     ft.DropdownOption(key=INCOME, text="Доход")])
        category = ft.Dropdown(label="Категория")
        amount = ft.TextField(label="Сумма, ₽", keyboard_type=ft.KeyboardType.NUMBER)
        note = ft.TextField(label="Комментарий (необязательно)")
        op_date = ft.TextField(label="Дата (ДД.ММ.ГГГГ)",
                               value=date.today().strftime("%d.%m.%Y"))
        error = ft.Text(color=ft.Colors.RED, visible=False)

        def fill_categories(_=None) -> None:
            cats = self.service.categories(kind.value)
            category.options = [ft.DropdownOption(key=str(c.id), text=c.name) for c in cats]
            category.value = str(cats[0].id) if cats else None
            self.page.update()

        def save(_) -> None:
            try:
                self.service.add_operation(kind.value, amount.value, category.value,
                                           note.value, op_date.value)
            except ValidationError as exc:
                error.value, error.visible = str(exc), True
                self.page.update()
                return
            self.page.pop_dialog()
            self.refresh()
            self._notify("Операция сохранена")

        kind.on_select = fill_categories
        cats = self.service.categories(EXPENSE)
        category.options = [ft.DropdownOption(key=str(c.id), text=c.name) for c in cats]
        category.value = str(cats[0].id) if cats else None

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Новая операция"),
            content=ft.Column(tight=True, width=320, scroll=ft.ScrollMode.AUTO,
                              controls=[kind, category, amount, note, op_date, error]),
            actions=[ft.TextButton("Отмена", on_click=lambda _: self.page.pop_dialog()),
                     ft.Button("Сохранить", on_click=save)]))

    def open_limit_dialog(self, status) -> None:
        limit = ft.TextField(
            label="Лимит на месяц, ₽ (пусто — снять лимит)",
            value=f"{status.limit_kop / 100:.2f}" if status.limit_kop else "",
            keyboard_type=ft.KeyboardType.NUMBER)
        error = ft.Text(color=ft.Colors.RED, visible=False)

        def save(_) -> None:
            try:
                self.service.set_limit(status.category_id, limit.value)
            except ValidationError as exc:
                error.value, error.visible = str(exc), True
                self.page.update()
                return
            self.page.pop_dialog()
            self.refresh()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text(f"Лимит: {status.category_name}"),
            content=ft.Column(tight=True, width=320, controls=[limit, error]),
            actions=[ft.TextButton("Отмена", on_click=lambda _: self.page.pop_dialog()),
                     ft.Button("Сохранить", on_click=save)]))
