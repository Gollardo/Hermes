from enum import StrEnum


class OnboardingExpenseGroup(StrEnum):
    HOUSING = "housing"
    CAR = "car"
    TRANSPORT = "transport"
    CHILDREN = "children"
    FAMILY = "family"
    PETS = "pets"
    HEALTH = "health"
    SPORT = "sport"
    EDUCATION = "education"
    WORK = "work"
    BUSINESS = "business"
    TRAVEL = "travel"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"


class CategoryTemplateLanguage(StrEnum):
    RU = "ru"
    EN = "en"


ONBOARDING_EXPENSE_CATEGORIES: dict[OnboardingExpenseGroup, tuple[str, tuple[str, ...]]] = {
    OnboardingExpenseGroup.HOUSING: (
        "🏠 Жильё",
        (
            "Аренда / ипотека",
            "Коммунальные услуги",
            "Ремонт",
            "Мебель и интерьер",
            "Хозяйственные расходы",
        ),
    ),
    OnboardingExpenseGroup.CAR: (
        "🚗 Автомобиль",
        ("Топливо", "Обслуживание и ремонт", "Страхование", "Парковка и дороги", "Автотовары"),
    ),
    OnboardingExpenseGroup.TRANSPORT: (
        "🚌 Транспорт",
        (
            "Общественный транспорт",
            "Такси",
            "Каршеринг",
            "Велосипед / самокат",
            "Междугородний транспорт",
        ),
    ),
    OnboardingExpenseGroup.CHILDREN: (
        "👶 Дети",
        ("Образование", "Одежда и обувь", "Здоровье", "Досуг и кружки", "Товары для детей"),
    ),
    OnboardingExpenseGroup.FAMILY: (
        "👨‍👩‍👧 Семья и близкие",
        (
            "Подарки",
            "Помощь родственникам",
            "Семейные мероприятия",
            "Совместный досуг",
            "Семейные покупки",
        ),
    ),
    OnboardingExpenseGroup.PETS: (
        "🐕 Домашние животные",
        ("Корм", "Ветеринария", "Уход", "Товары для животных", "Услуги для животных"),
    ),
    OnboardingExpenseGroup.HEALTH: (
        "❤️ Здоровье",
        (
            "Врачи и клиники",
            "Лекарства",
            "Стоматология",
            "Анализы и диагностика",
            "Медицинское страхование",
        ),
    ),
    OnboardingExpenseGroup.SPORT: (
        "🏃 Спорт и активность",
        (
            "Фитнес и спортзалы",
            "Спортивные секции",
            "Спортивный инвентарь",
            "Спортивная одежда",
            "Активный отдых",
        ),
    ),
    OnboardingExpenseGroup.EDUCATION: (
        "🎓 Учёба и развитие",
        ("Образование", "Онлайн-курсы", "Книги и материалы", "Языки", "Профессиональное развитие"),
    ),
    OnboardingExpenseGroup.WORK: (
        "💼 Работа и карьера",
        (
            "Рабочее оборудование",
            "Профессиональные сервисы",
            "Командировки",
            "Рабочая связь",
            "Карьерные расходы",
        ),
    ),
    OnboardingExpenseGroup.BUSINESS: (
        "🧑‍💻 Бизнес и самозанятость",
        (
            "Товары и материалы",
            "Подрядчики и сотрудники",
            "Реклама и продвижение",
            "Сервисы и оборудование",
            "Налоги и сборы",
        ),
    ),
    OnboardingExpenseGroup.TRAVEL: (
        "✈️ Путешествия",
        ("Транспорт", "Проживание", "Питание", "Развлечения и экскурсии", "Туристические расходы"),
    ),
    OnboardingExpenseGroup.ENTERTAINMENT: (
        "🎬 Отдых и развлечения",
        ("Кафе и рестораны", "Кино и мероприятия", "Игры", "Хобби", "Ночная жизнь"),
    ),
    OnboardingExpenseGroup.SHOPPING: (
        "🛍️ Покупки и личные вещи",
        ("Одежда", "Обувь", "Электроника", "Красота и уход", "Личные товары"),
    ),
}

DEFAULT_INCOME_CATEGORIES = ("Зарплата", "Аванс", "Бизнес", "Процент банка", "Прочее")


ENGLISH_INCOME_CATEGORIES = ("Salary", "Advance payment", "Business", "Bank interest", "Other")

ENGLISH_EXPENSE_CATEGORIES: dict[OnboardingExpenseGroup, tuple[str, tuple[str, ...]]] = {
    OnboardingExpenseGroup.HOUSING: (
        "🏠 Housing",
        (
            "Rent / mortgage",
            "Utilities",
            "Repairs",
            "Furniture and interiors",
            "Household expenses",
        ),
    ),
    OnboardingExpenseGroup.CAR: (
        "🚗 Car",
        ("Fuel", "Maintenance and repairs", "Insurance", "Parking and tolls", "Car supplies"),
    ),
    OnboardingExpenseGroup.TRANSPORT: (
        "🚌 Transport",
        ("Public transport", "Taxis", "Car sharing", "Bicycle / scooter", "Intercity transport"),
    ),
    OnboardingExpenseGroup.CHILDREN: (
        "👶 Children",
        (
            "Education",
            "Clothing and footwear",
            "Health",
            "Activities and clubs",
            "Children’s supplies",
        ),
    ),
    OnboardingExpenseGroup.FAMILY: (
        "👨\u200d👩\u200d👧 Family and loved ones",
        ("Gifts", "Support for relatives", "Family events", "Shared leisure", "Family purchases"),
    ),
    OnboardingExpenseGroup.PETS: (
        "🐕 Pets",
        ("Food", "Veterinary care", "Grooming", "Pet supplies", "Pet services"),
    ),
    OnboardingExpenseGroup.HEALTH: (
        "❤️ Health",
        (
            "Doctors and clinics",
            "Medicines",
            "Dental care",
            "Tests and diagnostics",
            "Health insurance",
        ),
    ),
    OnboardingExpenseGroup.SPORT: (
        "🏃 Sports and activity",
        (
            "Fitness and gyms",
            "Sports clubs",
            "Sports equipment",
            "Sportswear",
            "Outdoor activities",
        ),
    ),
    OnboardingExpenseGroup.EDUCATION: (
        "🎓 Education and development",
        (
            "Education",
            "Online courses",
            "Books and materials",
            "Languages",
            "Professional development",
        ),
    ),
    OnboardingExpenseGroup.WORK: (
        "💼 Work and career",
        (
            "Work equipment",
            "Professional services",
            "Business trips",
            "Work communications",
            "Career expenses",
        ),
    ),
    OnboardingExpenseGroup.BUSINESS: (
        "🧑\u200d💻 Business and self-employment",
        (
            "Goods and materials",
            "Contractors and staff",
            "Advertising and promotion",
            "Services and equipment",
            "Taxes and fees",
        ),
    ),
    OnboardingExpenseGroup.TRAVEL: (
        "✈️ Travel",
        ("Transport", "Accommodation", "Food", "Entertainment and excursions", "Travel expenses"),
    ),
    OnboardingExpenseGroup.ENTERTAINMENT: (
        "🎬 Leisure and entertainment",
        ("Cafés and restaurants", "Cinema and events", "Games", "Hobbies", "Nightlife"),
    ),
    OnboardingExpenseGroup.SHOPPING: (
        "🛍️ Shopping and personal items",
        ("Clothing", "Footwear", "Electronics", "Beauty and care", "Personal items"),
    ),
}
