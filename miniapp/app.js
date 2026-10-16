(() => {
    "use strict";

    const telegram = window.Telegram?.WebApp ?? null;
    const initData = telegram?.initData ?? "";
    const telegramUser =
        telegram?.initDataUnsafe?.user ?? null;

    const elements = {
        greeting: document.querySelector("#greeting"),
        planName: document.querySelector("#planName"),
        statusPill: document.querySelector("#statusPill"),
        expiresAt: document.querySelector("#expiresAt"),
        trafficValue:
            document.querySelector("#trafficValue"),
        connectButton:
            document.querySelector("#connectButton"),
        connectionPageButton:
            document.querySelector(
                "#connectionPageButton"
            ),
        plansList: document.querySelector("#plansList"),
        currentOrderCard:
            document.querySelector(
                "#currentOrderCard"
            ),
        currentOrderTitle:
            document.querySelector(
                "#currentOrderTitle"
            ),
        currentOrderBadge:
            document.querySelector(
                "#currentOrderBadge"
            ),
        currentOrderPrice:
            document.querySelector(
                "#currentOrderPrice"
            ),
        currentOrderMessage:
            document.querySelector(
                "#currentOrderMessage"
            ),
        profileName:
            document.querySelector("#profileName"),
        profileUsername:
            document.querySelector("#profileUsername"),
        profileTelegramId:
            document.querySelector("#profileTelegramId"),
        profileSubscriptionStatus:
            document.querySelector(
                "#profileSubscriptionStatus"
            ),
        planSheetBackdrop:
            document.querySelector(
                "#planSheetBackdrop"
            ),
        planSheetClose:
            document.querySelector(
                "#planSheetClose"
            ),
        planSheetTitle:
            document.querySelector(
                "#planSheetTitle"
            ),
        planSheetDuration:
            document.querySelector(
                "#planSheetDuration"
            ),
        planSheetPrice:
            document.querySelector(
                "#planSheetPrice"
            ),
        planSheetStatus:
            document.querySelector(
                "#planSheetStatus"
            ),
        createOrderButton:
            document.querySelector(
                "#createOrderButton"
            ),
        screens: Array.from(
            document.querySelectorAll("[data-screen]")
        ),
        navItems: Array.from(
            document.querySelectorAll(".nav-item")
        ),
        toast: document.querySelector("#toast"),
    };

    let toastTimer = null;
    let selectedPlan = null;
    let orderSubmitting = false;
    let planSheetTimer = null;
    let orderPollTimer = null;
    let currentOrder = null;

    function setConnectionButtonsDisabled(disabled) {
        elements.connectButton.disabled = disabled;
        elements.connectionPageButton.disabled = disabled;
    }

    function showToast(message) {
        elements.toast.textContent = message;
        elements.toast.classList.add("visible");

        window.clearTimeout(toastTimer);

        toastTimer = window.setTimeout(() => {
            elements.toast.classList.remove("visible");
        }, 2600);
    }

    function hapticNotification(
        type = "success"
    ) {
        try {
            telegram?.HapticFeedback
                ?.notificationOccurred(type);
        } catch {
            // Виброотклик поддерживается
            // не во всех клиентах Telegram.
        }
    }

    function hapticImpact(
        style = "light"
    ) {
        try {
            telegram?.HapticFeedback
                ?.impactOccurred(style);
        } catch {
            // Без вибрации приложение
            // всё равно продолжит работать.
        }
    }

    function hapticSelection() {
        try {
            telegram?.HapticFeedback
                ?.selectionChanged();
        } catch {
            // Старые клиенты Telegram
            // могут не поддерживать этот отклик.
        }
    }

    function formatDate(value) {
        if (!value) {
            return "Не указано";
        }

        let date;

        if (typeof value === "number") {
            date = new Date(
                value > 10_000_000_000
                    ? value
                    : value * 1000
            );
        } else {
            date = new Date(value);
        }

        if (Number.isNaN(date.getTime())) {
            return "Не указано";
        }

        return new Intl.DateTimeFormat(
            "ru-RU",
            {
                day: "2-digit",
                month: "long",
                year: "numeric",
            }
        ).format(date);
    }

    function formatPrice(value) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "—";
        }

        return new Intl.NumberFormat(
            "ru-RU",
            {
                style: "currency",
                currency: "RUB",
                maximumFractionDigits: 0,
            }
        ).format(number);
    }

    async function api(path) {
        const response = await fetch(
            path,
            {
                method: "GET",
                headers: {
                    "Accept": "application/json",
                    "X-Telegram-Init-Data": initData,
                },
                cache: "no-store",
                credentials: "same-origin",
            }
        );

        let payload = null;

        try {
            payload = await response.json();
        } catch {
            payload = null;
        }

        if (!response.ok) {
            const error = new Error(
                payload?.detail
                || payload?.message
                || `HTTP ${response.status}`
            );

            error.status = response.status;
            throw error;
        }

        return payload;
    }

    function renderGuest() {
        elements.planName.textContent =
            "Откройте приложение из Telegram";

        elements.statusPill.textContent =
            "Вне Telegram";

        elements.statusPill.className =
            "status-pill inactive";

        elements.expiresAt.textContent = "—";
        elements.trafficValue.textContent = "∞";
        setConnectionButtonsDisabled(true);

        elements.plansList.replaceChildren();

        const item = document.createElement("div");
        item.className = "plan-item";

        const text = document.createElement("div");
        text.className = "plan-title";
        text.textContent =
            "Тарифы появятся после входа через бота";

        item.append(text);
        elements.plansList.append(item);
    }

    function renderProfile(raw) {
        const profile =
            raw?.profile
            ?? raw?.data
            ?? raw
            ?? {};

        const user =
            profile.user ?? {};

        const subscription =
            profile.subscription ?? {};

        const vpn =
            profile.vpn
            ?? profile.connection
            ?? {};

        const status = String(
            subscription.status
            ?? profile.subscription_status
            ?? "unknown"
        ).toLowerCase();

        const active = status === "active";

        const plan =
            subscription.plan?.title
            ?? subscription.plan?.code
            ?? subscription.plan_name
            ?? subscription.name
            ?? subscription.plan_code
            ?? profile.plan_name
            ?? "Без активного тарифа";

        const expiry =
            subscription.expires_at
            ?? subscription.expiry_time
            ?? profile.expires_at
            ?? profile.expiry_time
            ?? vpn.expiry_time;

        elements.planName.textContent =
            String(plan).replaceAll("_", " ");

        elements.expiresAt.textContent =
            formatDate(expiry);

        elements.trafficValue.textContent =
            vpn?.traffic?.display
            ?? (
                vpn?.traffic?.unlimited === false
                    ? "Лимит"
                    : "∞"
            );

        elements.statusPill.textContent =
            active ? "Активна" : "Неактивна";

        elements.statusPill.className =
            active
                ? "status-pill active"
                : "status-pill inactive";

        const vpnEnabled =
            vpn.enabled !== false
            && profile.enabled !== false;

        setConnectionButtonsDisabled(
            !(active && vpnEnabled)
        );

        const fullName = [
            user.first_name,
            user.last_name,
        ]
            .filter(Boolean)
            .join(" ");

        elements.profileName.textContent =
            fullName || "Пользователь Telegram";

        elements.profileUsername.textContent =
            user.username
                ? `@${user.username}`
                : "Не указан";

        elements.profileTelegramId.textContent =
            user.telegram_id ?? "—";

        elements.profileSubscriptionStatus.textContent =
            active ? "Активна" : "Неактивна";
    }

    function renderPlans(raw) {
        const plans =
            Array.isArray(raw)
                ? raw
                : raw?.plans
                ?? raw?.items
                ?? raw?.data?.plans
                ?? [];

        elements.plansList.replaceChildren();

        if (!plans.length) {
            const item = document.createElement("div");
            item.className = "plan-item";

            const text = document.createElement("div");
            text.className = "plan-title";
            text.textContent =
                "Тарифы временно недоступны";

            item.append(text);
            elements.plansList.append(item);
            return;
        }

        for (const plan of plans) {
            const item = document.createElement("div");
            item.className = "plan-item";

            const left = document.createElement("div");

            const title = document.createElement("div");
            title.className = "plan-title";
            title.textContent =
                plan.name
                ?? plan.title
                ?? plan.code
                ?? "Тариф";

            const duration = document.createElement("div");
            duration.className = "plan-duration";

            const durationValue =
                Number(
                    plan.duration?.value
                    ?? plan.duration_months
                    ?? plan.months
                    ?? plan.duration_days
                    ?? plan.days
                );

            const durationUnit =
                plan.duration?.unit
                ?? (
                    plan.duration_days
                    || plan.days
                        ? "day"
                        : "month"
                );

            if (
                Number.isFinite(durationValue)
                && durationValue > 0
            ) {
                duration.textContent =
                    durationUnit === "day"
                        ? `${durationValue} дн. · безлимит`
                        : `${durationValue} мес. · безлимит`;
            } else {
                duration.textContent =
                    "Безлимитный трафик";
            }

            const price = document.createElement("div");
            price.className = "plan-price";
            const amountMinor =
                Number(
                    plan.price?.amount_minor
                );

            const priceValue =
                Number.isFinite(amountMinor)
                    ? amountMinor / 100
                    : (
                        plan.price_rub
                        ?? plan.price
                        ?? plan.amount
                    );

            price.textContent =
                formatPrice(priceValue);

            const selectPlan = () => {
                elements.plansList
                    .querySelectorAll(".plan-item")
                    .forEach((planItem) => {
                        planItem.classList.remove(
                            "selected"
                        );
                    });

                item.classList.add("selected");

                openPlanSheet(plan);

                hapticImpact("light");
            };

            item.setAttribute("role", "button");
            item.tabIndex = 0;
            item.dataset.planCode =
                plan.code ?? "";

            item.addEventListener(
                "click",
                selectPlan
            );

            item.addEventListener(
                "keydown",
                (event) => {
                    if (
                        event.key === "Enter"
                        || event.key === " "
                    ) {
                        event.preventDefault();
                        selectPlan();
                    }
                }
            );

            left.append(title, duration);
            item.append(left, price);
            elements.plansList.append(item);
        }
    }

    function orderStatusText(status) {
        const labels = {
            pending: "Ожидает оплаты",
            paid: "Оплачен",
            failed: "Ошибка",
            cancelled: "Отменён",
            refunded: "Возврат",
        };

        return labels[status] ?? "Неизвестно";
    }

    function orderStatusMessage(status) {
        const messages = {
            pending: "Ожидает подтверждения",
            paid: "Подписка активирована",
            failed: "Оплата не завершена",
            cancelled: "Заказ отменён",
            refunded: "Средства возвращены",
        };

        return messages[status] ?? "Статус неизвестен";
    }

    function renderCurrentOrder(order) {
        currentOrder = order ?? null;

        if (!order) {
            elements.currentOrderCard.hidden =
                true;
            return;
        }

        const status =
            order.status ?? "unknown";

        const amountMinor = Number(
            order?.price?.amount_minor
        );

        elements.currentOrderTitle.textContent =
            order?.plan?.title
            ?? "Заказ KAD VPN";

        elements.currentOrderBadge.textContent =
            orderStatusText(status);

        elements.currentOrderBadge.className =
            "current-order-badge";

        elements.currentOrderBadge.classList.add(
            status
        );

        elements.currentOrderPrice.textContent =
            Number.isFinite(amountMinor)
                ? formatPrice(amountMinor / 100)
                : "—";

        elements.currentOrderMessage.textContent =
            orderStatusMessage(status);

        elements.currentOrderCard.hidden =
            false;
    }

    async function refreshProfile() {
        try {
            const raw = await api(
                "/api/v1/me"
            );

            renderProfile(raw);
        } catch {
            // Заказ уже обновлён. Неудача обновления
            // профиля не должна ломать приложение.
        }
    }

    function stopOrderPolling() {
        window.clearTimeout(
            orderPollTimer
        );

        orderPollTimer = null;
    }

    async function pollCurrentOrder() {
        stopOrderPolling();

        try {
            const raw = await api(
                "/api/v1/orders/current"
            );

            const order =
                raw?.order ?? null;

            const previousStatus =
                currentOrder?.status;

            renderCurrentOrder(order);

            if (
                order?.status === "paid"
                && previousStatus === "pending"
            ) {
                setPlanSheetStatus(
                    (
                        "Оплата подтверждена. "
                        + "Подписка обновлена."
                    ),
                    "success"
                );

                elements.createOrderButton.disabled =
                    true;

                elements.createOrderButton.textContent =
                    "Оплата подтверждена";

                showToast(
                    "Подписка активирована"
                );

                hapticNotification("success");

                await refreshProfile();
            }

            if (order?.status === "pending") {
                orderPollTimer =
                    window.setTimeout(
                        pollCurrentOrder,
                        3000
                    );
            }
        } catch {
            orderPollTimer =
                window.setTimeout(
                    pollCurrentOrder,
                    6000
                );
        }
    }

    function startOrderPolling() {
        stopOrderPolling();

        orderPollTimer =
            window.setTimeout(
                pollCurrentOrder,
                2500
            );
    }

    async function loadCurrentOrder() {
        try {
            const raw = await api(
                "/api/v1/orders/current"
            );

            const order =
                raw?.order ?? null;

            renderCurrentOrder(order);

            if (order?.status === "pending") {
                startOrderPolling();
            }
        } catch {
            renderCurrentOrder(null);
        }
    }

    function setPlanSheetStatus(
        message,
        type = ""
    ) {
        elements.planSheetStatus.textContent =
            message;

        elements.planSheetStatus.classList.remove(
            "success",
            "error"
        );

        if (type) {
            elements.planSheetStatus.classList.add(
                type
            );
        }

        elements.planSheetStatus.hidden =
            !message;
    }

    function formatDuration(plan) {
        const value = Number(
            plan?.duration?.value
        );

        const unit =
            plan?.duration?.unit;

        if (
            !Number.isFinite(value)
            || value <= 0
        ) {
            return "—";
        }

        if (unit === "day") {
            return `${value} дн.`;
        }

        return `${value} мес.`;
    }

    function openPlanSheet(plan) {
        window.clearTimeout(planSheetTimer);

        selectedPlan = plan;
        orderSubmitting = false;

        const amountMinor = Number(
            plan?.price?.amount_minor
        );

        elements.planSheetTitle.textContent =
            plan?.title ?? "Выбранный тариф";

        elements.planSheetDuration.textContent =
            formatDuration(plan);

        elements.planSheetPrice.textContent =
            Number.isFinite(amountMinor)
                ? formatPrice(amountMinor / 100)
                : "—";

        elements.createOrderButton.disabled =
            false;

        elements.createOrderButton.textContent =
            "Создать заказ";

        setPlanSheetStatus("");

        if (currentOrder?.status === "pending") {
            const samePlan = (
                currentOrder?.plan?.code
                === plan?.code
            );

            elements.createOrderButton.disabled =
                true;

            if (samePlan) {
                elements.createOrderButton.textContent =
                    "Ожидает оплаты";

                setPlanSheetStatus(
                    (
                        "Этот заказ уже создан "
                        + "и ожидает подтверждения оплаты."
                    ),
                    "success"
                );
            } else {
                elements.createOrderButton.textContent =
                    "Есть активный заказ";

                setPlanSheetStatus(
                    (
                        "Сначала завершите текущий заказ: "
                        + (
                            currentOrder?.plan?.title
                            ?? "выбранный тариф"
                        )
                    ),
                    "error"
                );
            }

            startOrderPolling();
        }

        elements.planSheetBackdrop.hidden =
            false;

        document.body.classList.add(
            "sheet-open"
        );

        window.requestAnimationFrame(() => {
            elements.planSheetBackdrop
                .classList.add("visible");
        });

        window.setTimeout(() => {
            elements.createOrderButton.focus();
        }, 220);
    }

    function closePlanSheet() {
        if (orderSubmitting) {
            return;
        }

        elements.planSheetBackdrop
            .classList.remove("visible");

        document.body.classList.remove(
            "sheet-open"
        );

        planSheetTimer = window.setTimeout(
            () => {
                elements.planSheetBackdrop.hidden =
                    true;
            },
            190
        );
    }

    async function postApi(
        path,
        payload
    ) {
        const response = await fetch(
            path,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                    "X-Telegram-Init-Data":
                        telegram?.initData ?? "",
                },
                body: JSON.stringify(payload),
                cache: "no-store",
            }
        );

        let data = null;

        try {
            data = await response.json();
        } catch {
            data = null;
        }

        if (!response.ok) {
            const detail = data?.detail;

            const message =
                typeof detail === "string"
                    ? detail
                    : (
                        detail?.message
                        ?? "Не удалось создать заказ"
                    );

            throw new Error(message);
        }

        return data;
    }

    async function createSelectedOrder() {
        if (
            !selectedPlan?.code
            || orderSubmitting
        ) {
            return;
        }

        orderSubmitting = true;

        elements.createOrderButton.disabled =
            true;

        elements.createOrderButton.textContent =
            "Создаём заказ...";

        setPlanSheetStatus(
            "Сохраняем выбранный тариф."
        );

        let succeeded = false;

        try {
            const response = await postApi(
                "/api/v1/orders",
                {
                    plan_code: selectedPlan.code,
                }
            );

            const order = response?.order;

            if (!order) {
                throw new Error(
                    "Backend не вернул данные заказа"
                );
            }

            succeeded = true;

            const message =
                response.created === true
                    ? (
                        "Заказ создан и ожидает "
                        + "подключения оплаты."
                    )
                    : (
                        "Такой заказ уже существует "
                        + "и ожидает оплаты."
                    );

            renderCurrentOrder(order);
            startOrderPolling();

            setPlanSheetStatus(
                message,
                "success"
            );

            elements.createOrderButton.textContent =
                "Ожидает оплаты";

            showToast(
                response.created === true
                    ? "Заказ создан"
                    : "Заказ уже ожидает оплаты"
            );

            hapticNotification("success");
        } catch (error) {
            setPlanSheetStatus(
                error?.message
                    ?? "Не удалось создать заказ",
                "error"
            );

            elements.createOrderButton.textContent =
                "Попробовать снова";

            hapticNotification("error");
        } finally {
            orderSubmitting = false;

            if (!succeeded) {
                elements.createOrderButton.disabled =
                    false;
            }
        }
    }

    async function copyConnection() {
        setConnectionButtonsDisabled(true);

        try {
            const raw = await api(
                "/api/v1/connection"
            );

            const url =
                raw?.connection?.subscription_url
                ?? raw?.subscription_url;

            if (!url) {
                throw new Error(
                    "Ссылка подключения недоступна"
                );
            }

            await navigator.clipboard.writeText(url);

            showToast(
                "Ссылка скопирована. Не пересылайте её другим людям."
            );

            hapticNotification("success");
        } catch {
            showToast(
                "Не удалось скопировать ссылку подключения"
            );

            hapticNotification("error");
        } finally {
            setConnectionButtonsDisabled(false);
        }
    }

    async function load() {
        if (telegramUser?.first_name) {
            elements.greeting.textContent =
                `Привет, ${telegramUser.first_name}`;
        }

        if (!initData) {
            renderGuest();
            return;
        }

        try {
            const [profile, plans] =
                await Promise.all([
                    api("/api/v1/me"),
                    api("/api/v1/plans"),
                ]);

            renderProfile(profile);
            renderPlans(plans);
        } catch {
            elements.planName.textContent =
                "Не удалось загрузить профиль";

            elements.statusPill.textContent =
                "Ошибка";

            elements.statusPill.className =
                "status-pill inactive";

            elements.connectButton.disabled = true;

            showToast(
                "Ошибка связи с сервером"
            );
        }
    }

    function initialiseTelegram() {
        if (!telegram) {
            return;
        }

        telegram.ready();
        telegram.expand();

        hapticNotification("success");

        try {
            telegram.setHeaderColor("#080a10");
            telegram.setBackgroundColor("#080a10");
        } catch {
            // Старый клиент Telegram просто проигнорирует
            // косметику. Переживём и это.
        }
    }

    function showScreen(
        requestedScreen,
        {
            updateUrl = true,
            feedback = true,
        } = {}
    ) {
        const availableScreens =
            new Set(
                elements.screens.map(
                    (screen) => screen.dataset.screen
                )
            );

        const screenName =
            availableScreens.has(requestedScreen)
                ? requestedScreen
                : "home";

        elements.screens.forEach((screen) => {
            screen.classList.toggle(
                "active",
                screen.dataset.screen === screenName
            );
        });

        elements.navItems.forEach((button) => {
            button.classList.toggle(
                "active",
                button.dataset.page === screenName
            );
        });

        if (updateUrl) {
            const url = new URL(
                window.location.href
            );

            if (screenName === "home") {
                url.searchParams.delete("screen");
            } else {
                url.searchParams.set(
                    "screen",
                    screenName
                );
            }

            window.history.replaceState(
                {},
                "",
                url
            );
        }

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });

        if (feedback) {
            hapticSelection();
        }
    }

    function initialiseNavigation() {
        elements.navItems.forEach((button) => {
            button.addEventListener(
                "click",
                () => {
                    showScreen(
                        button.dataset.page
                    );
                }
            );
        });

        const requestedScreen =
            new URLSearchParams(
                window.location.search
            ).get("screen");

        showScreen(
            requestedScreen || "home",
            {
                updateUrl: false,
                feedback: false,
            }
        );
    }

    function initialiseNetwork() {
        const canvas =
            document.querySelector("#network");

        const context =
            canvas.getContext("2d");

        const points = [];
        const count = 34;

        function resize() {
            const ratio =
                Math.min(
                    window.devicePixelRatio || 1,
                    2
                );

            canvas.width =
                window.innerWidth * ratio;

            canvas.height =
                window.innerHeight * ratio;

            canvas.style.width =
                `${window.innerWidth}px`;

            canvas.style.height =
                `${window.innerHeight}px`;

            context.setTransform(
                ratio,
                0,
                0,
                ratio,
                0,
                0
            );
        }

        function createPoints() {
            points.length = 0;

            for (let index = 0; index < count; index++) {
                points.push({
                    x: Math.random() * window.innerWidth,
                    y: Math.random() * window.innerHeight,
                    vx: (Math.random() - 0.5) * 0.17,
                    vy: (Math.random() - 0.5) * 0.17,
                });
            }
        }

        function draw() {
            context.clearRect(
                0,
                0,
                window.innerWidth,
                window.innerHeight
            );

            for (const point of points) {
                point.x += point.vx;
                point.y += point.vy;

                if (
                    point.x < 0
                    || point.x > window.innerWidth
                ) {
                    point.vx *= -1;
                }

                if (
                    point.y < 0
                    || point.y > window.innerHeight
                ) {
                    point.vy *= -1;
                }

                context.beginPath();
                context.arc(
                    point.x,
                    point.y,
                    1.15,
                    0,
                    Math.PI * 2
                );

                context.fillStyle =
                    "rgba(157, 139, 255, 0.48)";

                context.fill();
            }

            for (
                let first = 0;
                first < points.length;
                first++
            ) {
                for (
                    let second = first + 1;
                    second < points.length;
                    second++
                ) {
                    const dx =
                        points[first].x
                        - points[second].x;

                    const dy =
                        points[first].y
                        - points[second].y;

                    const distance =
                        Math.hypot(dx, dy);

                    if (distance > 105) {
                        continue;
                    }

                    context.beginPath();
                    context.moveTo(
                        points[first].x,
                        points[first].y
                    );

                    context.lineTo(
                        points[second].x,
                        points[second].y
                    );

                    context.strokeStyle =
                        `rgba(120, 101, 230, ${
                            (1 - distance / 105) * 0.15
                        })`;

                    context.lineWidth = 0.65;
                    context.stroke();
                }
            }

            window.requestAnimationFrame(draw);
        }

        resize();
        createPoints();
        draw();

        window.addEventListener(
            "resize",
            () => {
                resize();
                createPoints();
            },
            {
                passive: true,
            }
        );
    }

    elements.connectButton.addEventListener(
        "click",
        copyConnection
    );

    elements.connectionPageButton.addEventListener(
        "click",
        copyConnection
    );

    elements.createOrderButton.addEventListener(
        "click",
        createSelectedOrder
    );

    elements.planSheetClose.addEventListener(
        "click",
        closePlanSheet
    );

    elements.planSheetBackdrop.addEventListener(
        "click",
        (event) => {
            if (
                event.target
                === elements.planSheetBackdrop
            ) {
                closePlanSheet();
            }
        }
    );

    document.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key === "Escape"
                && !elements.planSheetBackdrop.hidden
            ) {
                closePlanSheet();
            }
        }
    );

    initialiseTelegram();
    initialiseNavigation();
    loadCurrentOrder();
    initialiseNetwork();
    load();
})();
