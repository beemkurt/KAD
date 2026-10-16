from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.config import get_settings
from app.payments import (
    PaymentError,
    confirm_test_payment,
    get_latest_pending_order,
)
from app.provisioning import (
    ProvisioningError,
    ProvisioningService,
)
from app.xui import XUIClient, XUIError


router = Router()

settings = get_settings()
xui = XUIClient(settings)
provisioning = ProvisioningService(settings, xui)


def is_admin(telegram_id: int) -> bool:
    return telegram_id == settings.telegram_admin_id


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть KAD",
                    web_app=WebAppInfo(
                        url="https://app.kaditsolution.site"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Проверить тестовый заказ",
                    callback_data="order_review",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Получить тестовый VPN",
                    callback_data="vpn_create",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Моя подписка",
                    callback_data="vpn_status",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Удалить тестовый VPN",
                    callback_data="vpn_delete",
                )
            ],
        ]
    )


def delete_confirmation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data="vpn_delete_confirm",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="vpn_delete_cancel",
                ),
            ]
        ]
    )


def order_confirmation(
    public_id: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить тестовую оплату",
                    callback_data=(
                        f"order_pay:{public_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Открыть KAD",
                    web_app=WebAppInfo(
                        url=(
                            "https://"
                            "app.kaditsolution.site"
                            "?screen=home"
                        )
                    ),
                )
            ],
        ]
    )


def open_kad_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть KAD",
                    web_app=WebAppInfo(
                        url=(
                            "https://"
                            "app.kaditsolution.site"
                            "?screen=home"
                        )
                    ),
                )
            ]
        ]
    )


def format_order_price(
    amount_minor: object,
    currency: object,
) -> str:
    try:
        amount = int(amount_minor or 0)
    except (TypeError, ValueError):
        amount = 0

    rubles = amount / 100

    if rubles.is_integer():
        value = f"{int(rubles):,}".replace(
            ",",
            " ",
        )
    else:
        value = (
            f"{rubles:,.2f}"
            .replace(",", " ")
        )

    return f"{value} {currency or 'RUB'}"


def format_expiry(expiry_time: object) -> str:
    try:
        value = int(expiry_time or 0)
    except (TypeError, ValueError):
        return "неизвестно"

    if value <= 0:
        return "без ограничения"

    moment = datetime.fromtimestamp(
        value / 1000,
        tz=timezone.utc,
    )

    return moment.strftime("%d.%m.%Y %H:%M UTC")


async def send_subscription(
    message: Message,
    state: dict[str, object],
    *,
    heading: str,
) -> None:
    url = state.get("subscription_url")

    if not url:
        await message.answer(
            "Подписочная ссылка не найдена.",
            reply_markup=main_menu(),
        )
        return

    total_bytes = int(state.get("total_bytes") or 0)

    traffic_value = (
        "∞"
        if total_bytes == 0
        else f"{total_bytes // 1024 // 1024} МБ"
    )

    await message.answer(
        f"<b>{html.escape(heading)}</b>\n\n"
        f"Статус: активна\n"
        f"Трафик: {traffic_value}\n"
        f"Действует до: "
        f"{format_expiry(state.get('expiry_time'))}\n\n"
        f"<b>Ссылка для подключения:</b>\n"
        f"<code>{html.escape(str(url))}</code>\n\n"
        "Эта ссылка является ключом доступа. "
        "Не пересылай её другим людям.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def reject_non_admin(
    callback: CallbackQuery,
) -> bool:
    user = callback.from_user

    if is_admin(user.id):
        return False

    await callback.answer(
        "Бот пока находится в закрытом режиме.",
        show_alert=True,
    )

    return True


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    user = message.from_user

    if user is None:
        return

    if not is_admin(user.id):
        await message.answer(
            "KAD VPN сейчас находится "
            "в режиме технической настройки."
        )
        return

    await message.answer(
        "<b>KAD VPN</b>\n\n"
        "Backend, база и сервер 3x-ui подключены.\n"
        "Доступно закрытое меню тестирования.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@router.message(Command("ping"))
async def ping_handler(message: Message) -> None:
    user = message.from_user

    if user is None or not is_admin(user.id):
        return

    await message.answer("Бот работает.")


@router.callback_query(
    F.data == "order_review"
)
async def review_order(
    callback: CallbackQuery,
) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer()

    order = get_latest_pending_order()

    if order is None:
        if callback.message:
            await callback.message.answer(
                "Заказов, ожидающих оплаты, нет.",
                reply_markup=main_menu(),
            )
        return

    username = order.get("username")
    first_name = order.get("first_name")

    user_label = (
        f"@{username}"
        if username
        else (
            str(first_name)
            if first_name
            else str(order["telegram_id"])
        )
    )

    if callback.message:
        await callback.message.answer(
            "<b>Тестовый заказ</b>\n\n"
            f"Пользователь: "
            f"{html.escape(user_label)}\n"
            f"Тариф: "
            f"{html.escape(str(order['plan_title']))}\n"
            f"Сумма: "
            f"{html.escape(format_order_price(
                order['amount_minor'],
                order['currency'],
            ))}\n"
            "Статус: ожидает оплаты",
            parse_mode="HTML",
            reply_markup=order_confirmation(
                str(order["public_id"])
            ),
        )


@router.callback_query(
    F.data.startswith("order_pay:")
)
async def pay_test_order(
    callback: CallbackQuery,
) -> None:
    if await reject_non_admin(callback):
        return

    public_id = (
        callback.data
        or ""
    ).partition(":")[2]

    if not public_id:
        await callback.answer(
            "Некорректный заказ.",
            show_alert=True,
        )
        return

    await callback.answer(
        "Подтверждаю оплату..."
    )

    try:
        result = await confirm_test_payment(
            public_id,
            xui=xui,
            default_inbound_id=(
                settings.xui_inbound_id
            ),
        )

    except (PaymentError, XUIError) as exc:
        logging.exception(
            "Не удалось подтвердить оплату"
        )

        if callback.message:
            await callback.message.answer(
                "Не удалось подтвердить оплату.\n"
                f"Причина: {html.escape(str(exc))}",
                parse_mode="HTML",
                reply_markup=main_menu(),
            )
        return

    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        heading = (
            "Оплата уже была подтверждена"
            if result["already_paid"]
            else "Оплата подтверждена"
        )

        await callback.message.answer(
            f"<b>{heading}</b>\n\n"
            f"Тариф: "
            f"{html.escape(str(result['plan_title']))}\n"
            f"Действует до: "
            f"{format_expiry(result['expires_at'])}\n\n"
            "Заказ получил статус paid, "
            "срок VPN обновлён.",
            parse_mode="HTML",
            reply_markup=open_kad_keyboard(),
        )


@router.callback_query(F.data == "vpn_create")
async def create_vpn(callback: CallbackQuery) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer("Создаю подписку...")

    try:
        result = await provisioning.provision_test_client(
            telegram_id=callback.from_user.id,
            duration_minutes=1440,
        )
    except (XUIError, ProvisioningError):
        logging.exception(
            "Не удалось создать тестового клиента"
        )

        if callback.message:
            await callback.message.answer(
                "Не удалось создать VPN-подписку. "
                "Ошибка записана в журнал."
            )
        return

    heading = (
        "Тестовая подписка создана"
        if result.get("created")
        else "Тестовая подписка уже существует"
    )

    if callback.message:
        await send_subscription(
            callback.message,
            result,
            heading=heading,
        )


@router.callback_query(F.data == "vpn_status")
async def vpn_status(callback: CallbackQuery) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer()

    state = provisioning.get_state(
        callback.from_user.id
    )

    if state is None or not state.get("subscription_url"):
        if callback.message:
            await callback.message.answer(
                "Тестовая подписка пока не создана.",
                reply_markup=main_menu(),
            )
        return

    if callback.message:
        await send_subscription(
            callback.message,
            state,
            heading="Текущая тестовая подписка",
        )


@router.callback_query(F.data == "vpn_delete")
async def delete_vpn(callback: CallbackQuery) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer()

    state = provisioning.get_state(
        callback.from_user.id
    )

    if state is None or not state.get("xui_email"):
        if callback.message:
            await callback.message.answer(
                "Удалять нечего. "
                "Тестовая подписка не найдена.",
                reply_markup=main_menu(),
            )
        return

    if callback.message:
        await callback.message.answer(
            "Удалить тестовую VPN-подписку "
            "из базы и 3x-ui?",
            reply_markup=delete_confirmation(),
        )


@router.callback_query(
    F.data == "vpn_delete_confirm"
)
async def delete_vpn_confirm(
    callback: CallbackQuery,
) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer("Удаляю...")

    try:
        deleted = await provisioning.purge_test_client(
            callback.from_user.id
        )
    except XUIError:
        logging.exception(
            "Не удалось удалить тестового клиента"
        )

        if callback.message:
            await callback.message.answer(
                "Не удалось удалить клиента из 3x-ui."
            )
        return

    if callback.message:
        await callback.message.answer(
            (
                "Тестовая подписка удалена."
                if deleted
                else "Подписка уже отсутствует."
            ),
            reply_markup=main_menu(),
        )


@router.callback_query(
    F.data == "vpn_delete_cancel"
)
async def delete_vpn_cancel(
    callback: CallbackQuery,
) -> None:
    if await reject_non_admin(callback):
        return

    await callback.answer("Удаление отменено.")

    if callback.message:
        await callback.message.answer(
            "Подписка сохранена.",
            reply_markup=main_menu(),
        )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    if settings.telegram_admin_id <= 0:
        raise RuntimeError(
            "TELEGRAM_ADMIN_ID не настроен"
        )

    bot = Bot(
        token=(
            settings.telegram_bot_token
            .get_secret_value()
        )
    )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    bot_info = await bot.get_me()

    logging.info(
        "Подключён бот @%s, ID %s",
        bot_info.username,
        bot_info.id,
    )

    logging.info(
        "Администратор: Telegram ID %s",
        settings.telegram_admin_id,
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=(
                dispatcher.resolve_used_update_types()
            ),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
