import random
import uuid
from datetime import datetime, timezone

try:
    from faker import Faker  # type: ignore
except Exception:  # pragma: no cover - fallback when pip install is unavailable
    class Faker:  # lightweight compatibility fallback
        _companies = [
            "Nexa Retail Group",
            "Urban Cart Ventures",
            "BlueMarket Traders",
            "Savanna Commerce Ltd",
            "Metro Supplies Co",
            "Prime Shelf Brands",
            "Hilltop Distribution",
            "Green Basket Wholesale",
        ]
        _phrases = [
            "Scaling smart retail experiences",
            "Modern supply chain for daily essentials",
            "Reliable wholesale for growing stores",
            "Quality products, delivered consistently",
        ]
        _first = ["Amina", "John", "Grace", "Kevin", "Fatma", "Brian", "Lucy", "David"]
        _last = ["Otieno", "Mwangi", "Njeri", "Kariuki", "Ali", "Kamau", "Wanjiku", "Chebet"]
        _words = ["smart", "pure", "nova", "fresh", "urban", "elite", "prime", "daily"]
        _colors = ["Red", "Blue", "Green", "Silver", "Black", "White", "Golden"]

        def company(self):
            return random.choice(self._companies)

        def catch_phrase(self):
            return random.choice(self._phrases)

        def name(self):
            return f"{random.choice(self._first)} {random.choice(self._last)}"

        def email(self):
            return f"{self.word()}.{self.word()}@example.com"

        def address(self):
            return f"{random.randint(10, 999)} Market Street, Nairobi"

        def word(self):
            return random.choice(self._words)

        def color_name(self):
            return random.choice(self._colors)

        def text(self, max_nb_chars=200):
            base = "Quality marketplace product suitable for everyday shopping needs. "
            return (base * 8)[:max_nb_chars]

        def image_url(self):
            return f"https://picsum.photos/seed/{uuid.uuid4().hex[:8]}/600/400"

        def uuid4(self):
            return str(uuid.uuid4())


fake = Faker()

DEFAULT_CATEGORIES = [
    "Electronics",
    "Home & Garden",
    "Beauty & Wellness",
    "Groceries",
    "Fashion",
    "Office Supplies",
    "Sports & Outdoors",
]


def generate_fake_marketplace_data(
    *,
    category_count: int = 7,
    vendor_count: int = 7,
    user_count: int = 14,
    product_count: int = 100,
    shop_id: str = "seed-shop-1",
):
    now = datetime.now(timezone.utc).isoformat()

    categories = []
    chosen_categories = DEFAULT_CATEGORIES[:category_count]
    if len(chosen_categories) < category_count:
        while len(chosen_categories) < category_count:
            chosen_categories.append(fake.word().title())

    for index, name in enumerate(chosen_categories, start=1):
        categories.append({
            "id": f"seed-category-{index}",
            "name": name,
            "description": fake.catch_phrase(),
            "shop_id": shop_id,
            "created_at": now,
        })

    vendors = []
    for index in range(1, vendor_count + 1):
        vendors.append({
            "id": f"seed-vendor-{index}",
            "name": fake.company(),
            "description": fake.catch_phrase(),
            "shop_id": shop_id,
            "created_at": now,
        })

    users = []
    for index in range(1, user_count + 1):
        role = random.choice(["customer", "supplier"])
        users.append({
            "id": f"seed-user-{index}",
            "name": fake.name(),
            "email": fake.email(),
            "address": fake.address(),
            "password_hash": fake.uuid4(),
            "role": role,
            "shop_id": shop_id if role == "supplier" else None,
            "created_at": now,
        })

    products = []
    for index in range(1, product_count + 1):
        category = random.choice(categories)
        vendor = random.choice(vendors)
        price = round(random.uniform(50, 3500), 2)
        stock = random.randint(5, 250)
        name = f"{fake.word().title()} {fake.color_name()}"
        products.append({
            "id": f"seed-product-{index}",
            "name": name,
            "price": price,
            "unit_price": price,
            "stock": stock,
            "stock_quantity": stock,
            "category": category["name"],
            "category_id": category["id"],
            "vendor_id": vendor["id"],
            "vendor": vendor["name"],
            "description": fake.text(max_nb_chars=200),
            "image": fake.image_url(),
            "image_url": fake.image_url(),
            "shop_id": shop_id,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })

    suppliers = [
        {
            "id": f"seed-supplier-{i+1}",
            "name": vendor["name"],
            "phone": f"07{random.randint(10,99)}{random.randint(100000,999999)}",
            "notes": "Auto-seeded from Faker vendor",
            "shop_id": shop_id,
            "created_at": now,
        }
        for i, vendor in enumerate(vendors)
    ]

    return {
        "categories": categories,
        "vendors": vendors,
        "users": users,
        "products": products,
        "suppliers": suppliers,
    }
