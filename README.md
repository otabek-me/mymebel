# Mebel do'koni

O'zbek tilidagi, mobil qurilmalarga mos mebel katalogi va Django asosidagi maxsus boshqaruv paneli. Xaridor material va qo'shimcha detallarni tanlab narxni ko'radi, telefonini qoldiradi; narx serverda qayta hisoblanib, murojaat panelga saqlanadi.

## Talablar

- Python 3.12 yoki yangiroq
- `pip`
- Node.js va `npm` (faqat Tailwind CSS build qilish uchun)
- SQLite (standart) yoki PostgreSQL

## Mahalliy ishga tushirish (Windows PowerShell)

Loyiha papkasidan:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` ichidagi `SECRET_KEY`, sayt nomi, sotuvchi telefon raqami va ijtimoiy tarmoq havolalarini moslang. Telegram yoki Instagram ko'rsatilmasa, footer'da uning tugmasi chiqmaydi.

```powershell
python manage.py migrate
python manage.py seed_shop
python manage.py createsuperuser
python manage.py runserver
```

Sayt `http://127.0.0.1:8000/`, maxsus panel `http://127.0.0.1:8000/panel/` manzilida ochiladi. `createsuperuser` foydalanuvchisi `is_staff` bo'lgani uchun panelga kira oladi. Django default admin ilovasi va `/admin/` paneli ataylab yoqilmagan.

`seed_shop` qayta ishlatilishi mumkin: mavjud namunaviy yozuvlar va admin kiritgan narxlar ustidan yozilmaydi. Namunaviy mebellarga rasmni panel orqali yuklang.

`seed_shop` demo ko'rinishi uchun uchta gradient/tekstura bannerni ham yaratadi; ular haqiqiy mebel fotosuratlari emas. Haqiqiy fotosuratlarni panel → **Bosh sahifa bannerlari** orqali yuklang. Shu sahifada bosh sahifa matnlari, logotip va ishonch tasmasi matnlarini ham tahrirlash mumkin.

Frontend utility CSS faylini birinchi ishga tushirishda va Tailwind klasslari o'zgarganda build qiling:

```powershell
npm install
npm run build:css
```

Build qilingan `static/css/tailwind.css` sayt va panelda ishlatiladi; mijoz brauzerida Tailwind generator JavaScript talab qilinmaydi.

## PostgreSQL

PostgreSQL drayverini alohida o'rnating:

```powershell
pip install "psycopg[binary]"
```

`.env` ichida `DB_ENGINE=django.db.backends.postgresql` va `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` qiymatlarini belgilang. `DB_ENGINE` bo'sh qolsa SQLite ishlatiladi.

## Sinov va sifat tekshiruvi

```powershell
python manage.py check
python manage.py test shop panel
python manage.py makemigrations --check --dry-run
```

Sinovlar storefront sahifalari, CSRF, telefon tekshiruvi, narx snapshot'i va soxta narxni rad etish, mahsulotga tegishli detallar, spam cheklovi, murojaatni o'chirib bo'lmasligi, rasm konvertatsiyasi hamda staff panel oqimini tekshiradi.

## Production

1. Yangi maxfiy `SECRET_KEY` yarating. `.env` yoki deploy platformasining maxfiy o'zgaruvchilarida saqlang; repoga qo'shmang.
2. `DEBUG=False`, haqiqiy domenlarni `ALLOWED_HOSTS` ga, HTTPS domenini kerak bo'lsa `CSRF_TRUSTED_ORIGINS` ga kiriting.
3. DB sifatida PostgreSQL va fayllar uchun doimiy disk yoki mos media/object storage sozlang. `MEDIA_ROOT` dagi yuklangan fayllarni `DEBUG=False` paytida Django ishlab chiqarish serveri tarqatmaydi — Nginx/object storage orqali xizmat qildiring.
4. Static fayllarni collect qiling va migrate bajaring:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

WhiteNoise static fayllarni gunicorn jarayonidan tarqatadi. HTTPS proxy ortida `SECURE_PROXY_SSL_HEADER` faollashadi; faqat ishonchli TLS proxy bilan ishlating. HSTS yoqilgan holda production'ga o'tishdan oldin domen va HTTPS'ni tekshiring.

Panelga kirish urinishlari va murojaat rate limit'i Django cache orqali yuradi. Standart cache bitta jarayon uchun; bir nechta worker/serverda umumiy throttling kerak bo'lsa Redis kabi umumiy cache backend sozlang. Production'da DB/media backup, log kuzatuvi va `check --deploy` natijalarini ham tekshiring.

## Mijoz oqimi tekshiruv ro'yxati

- [x] Bosh sahifa, katalog, kategoriya va mebel sahifalari ochiladi.
- [x] Material/detal narxi mijoz sahifasida jonli hisoblanadi; server so'ralgan tanlovlarni tekshiradi va jami narxni o'zi hisoblaydi.
- [x] Murojaat telefon formati, CSRF, honeypot va tez-tez yuborish cheklovi bilan tekshiriladi.
- [x] Murojaat va narx/material/detal snapshot'i bazaga saqlanadi; uni panel ro'yxatida ko'rish va statusini o'zgartirish mumkin.
- [x] Staff panel murojaatlar sonini 10 soniyada polling qiladi; yangi murojaat uchun badge va toast ko'rsatadi.
- [x] Murojaatni UI, URL, view yoki model/queryset orqali o'chirib bo'lmaydi.

Interaktiv AJAX va rasm oqimlari `python manage.py test shop panel` bilan ham tekshiriladi.
