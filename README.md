<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/412c9678-5bec-4ace-9916-4077b8904c49" width="250"></td>
    <td><img src="https://github.com/user-attachments/assets/cd12d23d-0c9a-4a71-a600-71659f74cb9b" width="250"></td>
    <td><img src="https://github.com/user-attachments/assets/06acb6ae-9022-4358-86b2-50b2d4219ed5" width="250"></td>
  </tr>
</table>

# Common Ground

> A small community forum for thoughtful conversations, creative work, and projects in progress.

**Founded:** September 26, 2026  
**Created by:** Arkhyp Danylov · [GitHub](https://github.com/arhkypGitProject) · [LinkedIn](https://www.linkedin.com/in/arkhyp-danylov-23b3243ba/)

**Language / Язык / Język / Мова:** [English](#english) · [Русский](#русский) · [Polski](#polski) · [Українська](#українська)

---

## English

### Project goal

Common Ground is a lightweight forum prototype built around one idea: make it easier to share unfinished work, ask useful questions, and discuss ideas without turning disagreement into a personal argument. The interface is deliberately focused on conversations rather than account dashboards or social-media feeds.

The project is also a compact example of a server-rendered web application implemented with Python's standard library. It can be started locally without installing a web framework or a database server.

### Features

- Browse discussion topics grouped into Discussions, Projects, Questions, and Off-topic.
- Search the topic list by text and narrow it by category or by the built-in Popular and New labels.
- Create an account, log in, and log out.
- Create topics and post replies while signed in.
- Add up to eight hashtags to a topic. Hashtags appear on topic cards and discussion pages; selecting one opens the topic list filtered by that hashtag.
- Browse the member directory and open public member profiles.
- Edit the signed-in user's profile bio. A bio can contain up to 280 characters.
- Use English-language, responsive pages on desktop and mobile.

### Requirements

- Python 3.10 or newer.
- No third-party Python packages are required. The server uses `http.server`, `sqlite3`, and other modules from the Python standard library.
- An up-to-date browser with JavaScript enabled for interactive topic search, category filters, tabs, and the new-topic dialog.

### Run locally

Open PowerShell or another terminal in the project directory and run:

```powershell
python main.py
```

On Windows, the Python launcher can also be used:

```powershell
py -3 main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. Stop the server with `Ctrl+C`.

At startup, the application creates or updates `forum.sqlite3` in the project directory. This database stores accounts, profile bios, topics, hashtags, and replies. Keep the database file if this data should remain available between restarts. Do not commit a database containing real user information.

### How the application works

#### Request handling and pages

`main.py` runs Python's `ThreadingHTTPServer` and routes requests through `ForumHandler`. HTML is rendered from files in `templates/`; CSS and JavaScript are served from `static/`. Topic cards and account-dependent page fragments are assembled on the server, while the browser's JavaScript handles interactive filtering and the topic dialog.

The main routes are:

| Route | Purpose |
| --- | --- |
| `/` | Topic feed, text search, category filters, and Popular/New tabs |
| `/topic/<id>` | A discussion with its messages, hashtags, and reply form |
| `/register` | Account creation |
| `/login` | Sign in; accepts a local `next` destination |
| `/logout` | End the current session |
| `/members` | Directory of registered accounts |
| `/profile` | The signed-in user's profile and bio editor |
| `/profile?user=<username>` | Public profile for a member |
| `/about` | Project description and community principles |

#### Accounts and sessions

Usernames must be 3–32 characters long, contain only ASCII letters, digits, periods, underscores, or hyphens, and are unique without regard to letter case. Passwords must contain 8–1,024 characters. Passwords are not stored as plain text: the server creates a random salt for each account and derives a PBKDF2-HMAC-SHA256 hash using 310,000 iterations. Login checks the result with a constant-time comparison.

After registration or login, the server issues a random session token in a cookie with `HttpOnly`, `SameSite=Lax`, and `Path=/` attributes, plus a separate `HttpOnly`, `SameSite=Strict` CSRF cookie. Both cookies and the server-side session expire after eight hours. State-changing forms carry an unpredictable token that the server checks against the cookie and active session. Successful authentication rotates both tokens. Logging out removes the session and expires both cookies. Login and registration are limited to eight attempts per client IP per 15 minutes. Visitors can read topics and public profiles, but must sign in to create topics, reply, or edit a profile.

POST requests are limited to 64 KiB and form-encoded content. Topic titles are limited to 160 characters, topic/reply bodies to 10,000, hashtag input to 300, and profile bios to 280 characters. Responses use a restrictive Content Security Policy and headers against clickjacking, MIME sniffing, and referrer leakage. Connections time out after 10 seconds; the local server accepts up to 64 concurrent workers and queues up to 32 connections.

#### Topics, replies, and hashtags

Topic creation and replies are accepted only for signed-in users. The topic form accepts hashtags separated by spaces or commas. The parser removes an optional leading `#`, converts tags to lowercase, removes duplicates, ignores invalid values, and keeps at most eight tags. Each tag may contain letters, digits, underscores, or hyphens and must be no longer than 32 characters.

Hashtags are shown as `#tag` links. Selecting a link opens the home page with that tag entered into the search field. Text search, category selection, and the Popular/New tabs work in the browser and can be combined.

#### Profiles and member directory

The member directory reads registered accounts from SQLite. Each member has a public profile showing their username, join month, and bio. A signed-in member may edit only their own bio. The server limits bios to 280 characters and escapes user-provided text before rendering it as HTML.

### Project structure

```text
.
├── .github/workflows/tests.yml  # GitHub Actions on Windows and Linux
├── .gitignore                   # Local databases, secrets, caches, and environments
├── main.py                 # HTTP routes, authentication, rendering, and SQLite forum storage
├── render.yaml             # Always-on Render service and persistent disk configuration
├── static/
│   ├── app.js               # Client-side search, filters, tabs, and topic dialog
│   └── style.css            # Responsive visual styles
├── templates/
│   ├── index.html           # Topic feed
│   ├── topic.html           # Topic discussion
│   ├── login.html           # Sign-in form
│   ├── register.html        # Registration form
│   ├── members.html         # Member directory
│   ├── profile.html         # Member profile
│   └── about.html           # Project and community description
└── tests/
    └── test_app.py          # HTTP and security regression tests
```

### Data persistence and current limitations

This project is currently a learning/demo forum, not a production-ready community service. Persistence is intentionally limited in the current implementation:

- Accounts, password hashes, registration dates, bios, topics, hashtags, and replies are stored in SQLite and survive a server restart.
- The forum starts empty. New topics and replies are persisted to the configured SQLite database.
- Session records are also held in memory. A server restart signs everyone out, even if the browser still has a session cookie.
- Local defaults are `127.0.0.1:8000`. `render.yaml` configures Render to bind to its public port, use HTTPS, secure cookies, and a persistent disk in Frankfurt.
- SQLite on a Render disk is a single-instance setup; attached disks prevent zero-downtime deploys. Email verification and moderation tools are not implemented. Local development cookies omit `Secure`; Render enables it.

Before scaling beyond one Render instance, move forum data to managed PostgreSQL and sessions to shared persistent storage. Add email verification, moderation, operational backups, deployment monitoring, and a production-grade distributed rate limiter. The current CSRF defense and in-memory IP rate limit are useful safeguards, but do not replace a security review. Review privacy and moderation requirements as well.

### Development notes

There is no package installation step or build process. Run the standard-library test suite with `python -m unittest discover -s tests -v`. GitHub Actions runs the suite on Windows and Linux with Python 3.10–3.14. Make changes in `main.py`, the relevant template, or files under `static/`, then restart the server and verify the affected page in a browser.

### Publish on GitHub

Create an empty repository on GitHub, then connect this local repository and push the current branch:

```powershell
git remote add origin https://github.com/<owner>/<repository>.git
git add .
git commit -m "Prepare forum project"
git push -u origin HEAD
```

The project `.gitignore` excludes the local SQLite database, Python bytecode, virtual environments, and secret files. Review `git status` before committing. No license file has been added; choose a license before presenting the project as open source.

### Deploy as a live forum

GitHub Pages serves static files and cannot run this Python backend. The included `render.yaml` is a Render Blueprint for a continuously running Python web service with managed HTTPS and a 1 GB persistent disk for SQLite. After pushing the repository to GitHub, create a Blueprint in the Render Dashboard and connect this repository. The service uses the paid `0.5c-512mb` plan; Render charges for compute and disk. Automatic deploys wait for the GitHub Actions checks to pass. The persistent disk keeps accounts and forum content across restarts, but supports only one service instance and may cause brief downtime during deploys.

---

## Русский

**Дата основания:** 26 сентября 2026 года  
**Автор:** Arkhyp Danylov · [GitHub](https://github.com/arhkypGitProject) · [LinkedIn](https://www.linkedin.com/in/arkhyp-danylov-23b3243ba/)

### Цель проекта

Common Ground — лёгкий прототип форума, созданный вокруг простой идеи: дать людям удобное место, чтобы показывать незавершённую работу, задавать полезные вопросы и обсуждать идеи, не превращая разногласия в личный конфликт. Интерфейс сосредоточен на содержательных разговорах, а не на панелях управления или бесконечной ленте социальных сетей.

Проект также показывает, как устроено небольшое серверное веб-приложение на стандартной библиотеке Python. Его можно запустить локально без веб-фреймворка и отдельного сервера базы данных.

### Возможности

- Просмотр тем по разделам: Discussions, Projects, Questions и Off-topic.
- Поиск по тексту тем, фильтрация по разделам и вкладкам Popular/New.
- Регистрация, вход и выход из аккаунта.
- Создание тем и публикация ответов после входа.
- Добавление до восьми хэштегов к теме. Они видны в карточке и обсуждении; нажатие на тег открывает ленту с фильтром по нему.
- Каталог зарегистрированных участников и публичные страницы профилей.
- Редактирование биографии собственного профиля. Максимальная длина — 280 символов.
- Англоязычный адаптивный интерфейс для компьютеров и мобильных устройств.

### Требования

- Python версии 3.10 или новее.
- Сторонние Python-пакеты не нужны. Сервер использует `http.server`, `sqlite3` и другие модули стандартной библиотеки.
- Современный браузер с включённым JavaScript для интерактивного поиска, фильтров, вкладок и окна создания темы.

### Запуск локально

Откройте PowerShell или другой терминал в папке проекта и выполните:

```powershell
python main.py
```

В Windows также можно запустить через Python Launcher:

```powershell
py -3 main.py
```

Откройте в браузере [http://127.0.0.1:8000](http://127.0.0.1:8000). Для остановки сервера нажмите `Ctrl+C`.

При локальном запуске приложение создаёт или обновляет `forum.sqlite3` в папке проекта. В базе хранятся аккаунты, биографии, темы, хэштеги и ответы. Не добавляйте в Git базу с реальными пользовательскими данными.

### Как работает приложение

#### Обработка запросов и страницы

Файл `main.py` запускает `ThreadingHTTPServer` из стандартной библиотеки Python и обрабатывает запросы через `ForumHandler`. HTML-шаблоны находятся в `templates/`, CSS и JavaScript — в `static/`. Карточки тем и фрагменты страниц, зависящие от авторизации, формируются сервером; клиентский JavaScript отвечает за динамические фильтры и окно создания темы.

Основные маршруты:

| Маршрут | Назначение |
| --- | --- |
| `/` | Лента тем, текстовый поиск, фильтр разделов и вкладки Popular/New |
| `/topic/<id>` | Обсуждение, сообщения, хэштеги и форма ответа |
| `/register` | Создание аккаунта |
| `/login` | Вход; поддерживает локальный параметр `next` для возврата к нужной странице |
| `/logout` | Завершение текущей сессии |
| `/members` | Каталог зарегистрированных аккаунтов |
| `/profile` | Профиль вошедшего пользователя и форма изменения биографии |
| `/profile?user=<username>` | Публичный профиль участника |
| `/about` | Описание проекта и принципы сообщества |

#### Аккаунты и сессии

Имя пользователя должно содержать от 3 до 32 символов и состоять только из латинских букв ASCII, цифр, точек, подчёркиваний или дефисов. Имена уникальны без учёта регистра. Длина пароля — от 8 до 1 024 символов. Пароли не сохраняются открытым текстом: для каждого аккаунта создаётся случайная соль, после чего вычисляется хэш PBKDF2-HMAC-SHA256 с 310 000 итерациями. При входе сравнение выполняется за постоянное время.

После регистрации или входа сервер выдаёт случайный токен сессии в cookie с атрибутами `HttpOnly`, `SameSite=Lax` и `Path=/`, а также отдельную CSRF-cookie с `HttpOnly` и `SameSite=Strict`. Обе cookie и серверная сессия истекают через восемь часов. Формы, изменяющие данные, содержат непредсказуемый токен; сервер сверяет его с cookie и активной сессией. После успешного входа токены меняются. При выходе сервер удаляет сессию и отзывает обе cookie. Для входа и регистрации действует ограничение: не более восьми попыток с одного IP за 15 минут. Гости могут читать темы и публичные профили, но для создания темы, ответа или изменения профиля нужно войти.

Размер POST-запроса ограничен 64 КиБ, принимаются только данные форм. Заголовок темы ограничен 160 символами, текст темы и ответа — 10 000, поле хэштегов — 300, биография — 280 символами. Сервер устанавливает Content Security Policy и заголовки защиты от встраивания во фрейм, MIME-sniffing и утечки referrer. Тайм-аут соединения — 10 секунд; локальный сервер обслуживает до 64 потоков параллельно и ставит в очередь до 32 соединений.

#### Темы, ответы и хэштеги

Создавать темы и отвечать на них могут только вошедшие пользователи. Хэштеги вводятся через пробел или запятую. Обработчик удаляет необязательный начальный символ `#`, приводит тег к нижнему регистру, удаляет повторы, пропускает некорректные значения и оставляет не более восьми тегов. Тег может содержать буквы, цифры, подчёркивания и дефисы; максимальная длина — 32 символа.

Хэштеги отображаются как ссылки вида `#tag`. Нажатие на ссылку открывает главную страницу с этим тегом в строке поиска. Текстовый поиск, выбор раздела и вкладки Popular/New работают в браузере и могут использоваться одновременно.

#### Профили и каталог участников

Список участников загружается из SQLite. Публичный профиль показывает имя, месяц регистрации и биографию. Вошедший пользователь может редактировать только собственную биографию. Сервер ограничивает её 280 символами и экранирует пользовательский текст перед вставкой в HTML.

### Структура проекта

```text
.
├── .github/workflows/tests.yml  # GitHub Actions для Windows и Linux
├── .gitignore                   # Локальные базы, секреты, кэши и окружения
├── main.py                 # HTTP-маршруты, авторизация и SQLite-хранилище форума
├── render.yaml             # Render web service и постоянный диск
├── static/
│   ├── app.js               # Поиск, фильтры, вкладки и окно создания темы
│   └── style.css            # Адаптивные стили
├── templates/
│   ├── index.html           # Лента тем
│   ├── topic.html           # Страница обсуждения
│   ├── login.html           # Форма входа
│   ├── register.html        # Форма регистрации
│   ├── members.html         # Каталог участников
│   ├── profile.html         # Профиль участника
│   └── about.html           # Описание проекта и сообщества
└── tests/
    └── test_app.py          # HTTP-тесты и проверки безопасности
```

### Хранение данных и текущие ограничения

Сейчас это учебный/демонстрационный форум, а не готовый к промышленной эксплуатации сервис. Постоянно сохраняется только часть данных:

- Аккаунты, хэши паролей, даты регистрации, биографии, темы, хэштеги и ответы хранятся в SQLite и переживают перезапуск.
- Форум запускается без тем; новые темы и ответы сохраняются в настроенную SQLite-базу.
- Сессии также хранятся в памяти. Перезапуск сервера завершает все входы, даже если в браузере осталась cookie.
- Локальный режим использует `127.0.0.1:8000`. `render.yaml` настраивает публичный порт Render, HTTPS, `Secure` cookies и постоянный диск во Frankfurt.
- Диск Render работает с одним экземпляром и может вызвать короткую недоступность при deploy. Подтверждения почты и инструментария модерации пока нет. В локальном HTTP-режиме cookies намеренно не имеют `Secure`.

Перед масштабированием за пределы одного экземпляра нужно перенести данные в managed PostgreSQL, а сессии — в общее постоянное хранилище. Также нужны подтверждение почты, модерация, резервное копирование, мониторинг и распределённый production rate limiter. Текущие CSRF-защита и лимит попыток по IP полезны, но не заменяют аудит безопасности. Учтите требования приватности и модерации.

### Заметки для разработки

Установка пакетов и сборка не требуются. Запуск тестов: `python -m unittest discover -s tests -v`. GitHub Actions запускает тесты на Windows и Linux с Python 3.10–3.14. Изменяйте `main.py`, соответствующий шаблон или файлы в `static/`, затем перезапускайте сервер и проверяйте затронутые страницы в браузере.

### Публикация на GitHub

Создайте на GitHub пустой репозиторий и подключите его к локальному:

```powershell
git remote add origin https://github.com/<владелец>/<репозиторий>.git
git add .
git commit -m "Prepare forum project"
git push -u origin HEAD
```

Файл `.gitignore` исключает локальную SQLite-базу, Python bytecode, виртуальные окружения и файлы секретов. Перед коммитом проверьте `git status`. Файл лицензии не добавлен: выберите её, прежде чем объявлять проект открытым исходным кодом.

### Постоянный хостинг форума

GitHub Pages размещает только статические файлы и не может запустить Python backend. Файл `render.yaml` — Blueprint для постоянно работающего Python-сервиса на Render с HTTPS и диском 1 GB для SQLite. После публикации репозитория подключите его в Render Dashboard как Blueprint. План `0.5c-512mb` и диск платные; стоимость начисляет Render. CI должен пройти перед автоматическим deploy. Диск сохраняет аккаунты и обсуждения, но разрешает только один экземпляр сервиса и может вызывать короткий перерыв во время обновления.

---

## Polski

**Data założenia:** 26 września 2026 r.  
**Autor:** Arkhyp Danylov · [GitHub](https://github.com/arhkypGitProject) · [LinkedIn](https://www.linkedin.com/in/arkhyp-danylov-23b3243ba/)

### Cel projektu

Common Ground to lekki prototyp forum oparty na prostej idei: ułatwić dzielenie się niedokończoną pracą, zadawanie przydatnych pytań i rozmowę o pomysłach bez zamieniania różnicy zdań w osobisty konflikt. Interfejs skupia się na rozmowach, a nie na rozbudowanych panelach użytkownika czy nieskończonym strumieniu treści.

Projekt jest również niewielkim przykładem serwerowej aplikacji WWW napisanej przy użyciu biblioteki standardowej Pythona. Można uruchomić go lokalnie bez frameworka WWW i osobnego serwera bazy danych.

### Funkcje

- Przeglądanie tematów w kategoriach Discussions, Projects, Questions i Off-topic.
- Wyszukiwanie tekstowe oraz filtrowanie według kategorii i kart Popular/New.
- Rejestracja, logowanie i wylogowanie.
- Tworzenie tematów i publikowanie odpowiedzi po zalogowaniu.
- Dodawanie do ośmiu hashtagów do tematu. Hashtagi są widoczne na kartach i stronach dyskusji; kliknięcie otwiera listę przefiltrowaną według wybranego hashtagu.
- Katalog zarejestrowanych uczestników i publiczne profile.
- Edycja biografii własnego profilu. Maksymalna długość wynosi 280 znaków.
- Responsywny interfejs w języku angielskim, działający na komputerach i urządzeniach mobilnych.

### Wymagania

- Python 3.10 lub nowszy.
- Nie są wymagane zewnętrzne pakiety Pythona. Serwer korzysta z `http.server`, `sqlite3` i innych modułów biblioteki standardowej.
- Aktualna przeglądarka z włączonym JavaScriptem, potrzebnym do interaktywnego wyszukiwania, filtrów, kart i okna tworzenia tematu.

### Uruchomienie lokalne

Otwórz PowerShell lub inny terminal w katalogu projektu i uruchom:

```powershell
python main.py
```

W systemie Windows możesz również użyć programu Python Launcher:

```powershell
py -3 main.py
```

Otwórz w przeglądarce adres [http://127.0.0.1:8000](http://127.0.0.1:8000). Zatrzymaj serwer skrótem `Ctrl+C`.

Przy lokalnym uruchomieniu aplikacja tworzy lub aktualizuje `forum.sqlite3` w katalogu projektu. Baza przechowuje konta, biografie, tematy, hashtagi i odpowiedzi. Nie dodawaj do repozytorium bazy zawierającej prawdziwe dane użytkowników.

### Jak działa aplikacja

#### Obsługa żądań i strony

Plik `main.py` uruchamia `ThreadingHTTPServer` z biblioteki standardowej Pythona, a żądania obsługuje klasa `ForumHandler`. Szablony HTML znajdują się w `templates/`, a CSS i JavaScript w `static/`. Karty tematów i fragmenty zależne od zalogowania są generowane po stronie serwera. JavaScript w przeglądarce obsługuje interaktywne filtrowanie i okno tworzenia tematu.

Najważniejsze trasy:

| Trasa | Zastosowanie |
| --- | --- |
| `/` | Lista tematów, wyszukiwanie, filtrowanie kategorii i karty Popular/New |
| `/topic/<id>` | Dyskusja, wiadomości, hashtagi i formularz odpowiedzi |
| `/register` | Tworzenie konta |
| `/login` | Logowanie; obsługuje lokalny parametr `next` |
| `/logout` | Zakończenie bieżącej sesji |
| `/members` | Katalog zarejestrowanych kont |
| `/profile` | Profil zalogowanej osoby i edycja biografii |
| `/profile?user=<username>` | Publiczny profil uczestnika |
| `/about` | Opis projektu i zasady społeczności |

#### Konta i sesje

Nazwa użytkownika musi mieć od 3 do 32 znaków i może zawierać wyłącznie litery ASCII, cyfry, kropki, podkreślenia lub łączniki; unikalność jest sprawdzana bez rozróżniania wielkości liter. Hasło musi mieć od 8 do 1 024 znaków. Hasła nie są przechowywane jako zwykły tekst: dla każdego konta generowana jest losowa sól, a następnie obliczany jest skrót PBKDF2-HMAC-SHA256 z 310 000 iteracji. Podczas logowania wynik jest porównywany w stałym czasie.

Po rejestracji lub logowaniu serwer ustawia losowy token sesji w cookie z atrybutami `HttpOnly`, `SameSite=Lax` i `Path=/`, a także osobne cookie CSRF z `HttpOnly` i `SameSite=Strict`. Oba pliki cookie i sesja serwera wygasają po ośmiu godzinach. Formularze zmieniające dane zawierają nieprzewidywalny token, który serwer sprawdza względem cookie i aktywnej sesji. Po poprawnym uwierzytelnieniu tokeny są zmieniane. Wylogowanie usuwa sesję i wygasza oba pliki cookie. Logowanie i rejestracja są ograniczone do ośmiu prób z jednego adresu IP na 15 minut. Goście mogą czytać tematy i publiczne profile, ale tworzenie tematów, odpowiadanie i edycja profilu wymagają zalogowania.

Żądania POST są ograniczone do 64 KiB i muszą być zakodowane jako formularz. Tytuł tematu ma limit 160 znaków, treść tematu i odpowiedzi 10 000, pole hashtagów 300, a biografia 280 znaków. Serwer ustawia restrykcyjną Content Security Policy oraz nagłówki chroniące przed osadzaniem w ramce, MIME-sniffingiem i ujawnianiem referrera. Połączenie ma limit czasu 10 sekund; lokalny serwer obsługuje do 64 równoległych wątków i kolejkę do 32 połączeń.

#### Tematy, odpowiedzi i hashtagi

Tematy i odpowiedzi mogą publikować tylko zalogowane osoby. Hashtagi można rozdzielać spacjami lub przecinkami. Parser usuwa opcjonalny początkowy `#`, zamienia tagi na małe litery, usuwa duplikaty, pomija niepoprawne wartości i zachowuje maksymalnie osiem tagów. Tag może zawierać litery, cyfry, podkreślenia i łączniki, a jego długość nie może przekraczać 32 znaków.

Hashtagi są wyświetlane jako linki `#tag`. Kliknięcie otwiera stronę główną z wybranym tagiem wpisanym w wyszukiwarkę. Wyszukiwanie tekstowe, wybór kategorii i karty Popular/New działają w przeglądarce i można je łączyć.

#### Profile i katalog uczestników

Katalog uczestników pobiera dane z SQLite. Publiczny profil pokazuje nazwę użytkownika, miesiąc dołączenia i biografię. Zalogowana osoba może zmieniać wyłącznie własną biografię. Serwer ogranicza ją do 280 znaków i ucieka znaki specjalne przed umieszczeniem tekstu w HTML.

### Struktura projektu

```text
.
├── .github/workflows/tests.yml  # GitHub Actions dla Windows i Linux
├── .gitignore                   # Lokalne bazy, sekrety, cache i środowiska
├── main.py                 # Trasy HTTP, uwierzytelnianie i forum przechowywane w SQLite
├── render.yaml             # Konfiguracja usługi Render i trwałego dysku
├── static/
│   ├── app.js               # Wyszukiwanie, filtry, karty i okno tworzenia tematu
│   └── style.css            # Responsywne style
├── templates/
│   ├── index.html           # Lista tematów
│   ├── topic.html           # Strona dyskusji
│   ├── login.html           # Formularz logowania
│   ├── register.html        # Formularz rejestracji
│   ├── members.html         # Katalog uczestników
│   ├── profile.html         # Profil uczestnika
│   └── about.html           # Opis projektu i społeczności
└── tests/
    └── test_app.py          # Testy HTTP i regresji bezpieczeństwa
```

### Trwałość danych i obecne ograniczenia

To obecnie projekt edukacyjny/demo, a nie gotowa usługa produkcyjna. W aktualnej wersji tylko część danych jest trwale zapisywana:

- Konta, skróty haseł, daty rejestracji, biografie, tematy, hashtagi i odpowiedzi są przechowywane w SQLite i przetrwają restart.
- Forum uruchamia się bez tematów; nowe tematy i odpowiedzi są zapisywane w skonfigurowanej bazie SQLite.
- Sesje również są przechowywane w pamięci. Restart serwera wyloguje wszystkich, nawet jeśli przeglądarka nadal ma cookie.
- Lokalny tryb domyślnie używa `127.0.0.1:8000`. `render.yaml` konfiguruje publiczny port Render, HTTPS, cookie `Secure` i trwały dysk we Frankfurcie.
- Dysk Render działa z jedną instancją i może powodować krótką niedostępność podczas wdrożenia. Weryfikacja e-mail i narzędzia moderacji nie są jeszcze dostępne. Lokalne cookie HTTP celowo nie używają `Secure`.

Przed skalowaniem poza jedną instancję przenieś dane do zarządzanego PostgreSQL, a sesje do współdzielonego trwałego magazynu. Dodaj weryfikację e-mail, moderację, kopie zapasowe, monitoring i produkcyjny rozproszony rate limiter. Obecna ochrona CSRF i limit prób według IP są przydatne, ale nie zastępują audytu bezpieczeństwa. Uwzględnij wymagania prywatności i moderacji.

### Uwagi dla programistów

Nie ma kroku instalacji zależności ani procesu budowania. Uruchom testy poleceniem `python -m unittest discover -s tests -v`. GitHub Actions testuje Windows i Linux z Pythonem 3.10–3.14. Zmieniaj `main.py`, odpowiedni szablon albo pliki w `static/`, uruchom ponownie serwer i sprawdź zmienioną stronę w przeglądarce.

### Publikacja na GitHubie

Utwórz puste repozytorium na GitHubie, a następnie połącz je z lokalnym:

```powershell
git remote add origin https://github.com/<właściciel>/<repozytorium>.git
git add .
git commit -m "Prepare forum project"
git push -u origin HEAD
```

Projektowy `.gitignore` pomija lokalną bazę SQLite, bytecode Pythona, środowiska wirtualne i pliki z sekretami. Przed commitem sprawdź `git status`. Nie dodano pliku licencji; wybierz licencję przed przedstawieniem projektu jako open source.

### Stały hosting forum

GitHub Pages hostuje wyłącznie pliki statyczne i nie uruchomi backendu Python. `render.yaml` opisuje stale działającą usługę Python na Render z HTTPS i dyskiem 1 GB dla SQLite. Po opublikowaniu repozytorium na GitHubie utwórz Blueprint w Render Dashboard i połącz repozytorium. Plan `0.5c-512mb` oraz dysk są płatne; opłaty nalicza Render. Automatyczne wdrożenie czeka na pozytywne wyniki GitHub Actions. Dysk zachowuje konta i forum po restarcie, ale obsługuje tylko jedną instancję i może powodować krótką przerwę podczas wdrożenia.

---

## Українська

**Дата заснування:** 26 вересня 2026 року  
**Автор:** Arkhyp Danylov · [GitHub](https://github.com/arhkypGitProject) · [LinkedIn](https://www.linkedin.com/in/arkhyp-danylov-23b3243ba/)

### Мета проєкту

Common Ground — легкий прототип форуму з простою метою: створити зручне місце, де можна показувати незавершену роботу, ставити корисні запитання й обговорювати ідеї, не перетворюючи незгоду на особистий конфлікт. Інтерфейс зосереджений на змістовних розмовах, а не на панелях керування чи нескінченній стрічці соцмережі.

Проєкт також демонструє, як працює невеликий серверний вебзастосунок на стандартній бібліотеці Python. Його можна запустити локально без вебфреймворку та окремого сервера бази даних.

### Можливості

- Перегляд тем у розділах Discussions, Projects, Questions і Off-topic.
- Текстовий пошук, фільтрування за розділами та вкладками Popular/New.
- Реєстрація, вхід і вихід з облікового запису.
- Створення тем і відповідей після входу.
- Додавання до восьми хештегів до теми. Вони відображаються в картці та обговоренні; натискання відкриває стрічку з фільтром за цим хештегом.
- Каталог зареєстрованих учасників і публічні сторінки профілів.
- Редагування біографії власного профілю. Максимальна довжина — 280 символів.
- Адаптивний англомовний інтерфейс для комп’ютерів і мобільних пристроїв.

### Вимоги

- Python версії 3.10 або новішої.
- Сторонні пакети Python не потрібні. Сервер використовує `http.server`, `sqlite3` та інші модулі стандартної бібліотеки.
- Сучасний браузер із JavaScript для інтерактивного пошуку, фільтрів, вкладок і вікна створення теми.

### Локальний запуск

Відкрийте PowerShell або інший термінал у каталозі проєкту та виконайте:

```powershell
python main.py
```

У Windows також можна скористатися Python Launcher:

```powershell
py -3 main.py
```

Відкрийте в браузері [http://127.0.0.1:8000](http://127.0.0.1:8000). Щоб зупинити сервер, натисніть `Ctrl+C`.

Під час локального запуску застосунок створює або оновлює `forum.sqlite3` у каталозі проєкту. У базі зберігаються акаунти, біографії, теми, хештеги й відповіді. Не додавайте до Git базу з реальними даними користувачів.

### Як працює застосунок

#### Обробка запитів і сторінки

Файл `main.py` запускає `ThreadingHTTPServer` зі стандартної бібліотеки Python, а запити обробляє `ForumHandler`. HTML-шаблони розташовані в `templates/`, CSS і JavaScript — у `static/`. Картки тем і фрагменти сторінок, що залежать від авторизації, формуються на сервері. JavaScript у браузері відповідає за інтерактивне фільтрування та вікно створення теми.

Основні маршрути:

| Маршрут | Призначення |
| --- | --- |
| `/` | Стрічка тем, текстовий пошук, фільтр розділів і вкладки Popular/New |
| `/topic/<id>` | Обговорення, повідомлення, хештеги та форма відповіді |
| `/register` | Створення облікового запису |
| `/login` | Вхід; підтримує локальний параметр `next` |
| `/logout` | Завершення поточної сесії |
| `/members` | Каталог зареєстрованих акаунтів |
| `/profile` | Профіль користувача, який увійшов, і редагування біографії |
| `/profile?user=<username>` | Публічний профіль учасника |
| `/about` | Опис проєкту та принципів спільноти |

#### Облікові записи та сесії

Ім’я користувача має містити від 3 до 32 символів і складатися лише з латинських літер ASCII, цифр, крапок, підкреслень або дефісів; унікальність перевіряється без урахування регістру. Пароль має містити від 8 до 1 024 символів. Паролі не зберігаються у відкритому вигляді: для кожного облікового запису створюється випадкова сіль, а потім обчислюється хеш PBKDF2-HMAC-SHA256 із 310 000 ітерацій. Під час входу результат порівнюється за сталий час.

Після реєстрації або входу сервер видає випадковий токен сесії в cookie з атрибутами `HttpOnly`, `SameSite=Lax` і `Path=/`, а також окрему CSRF-cookie з `HttpOnly` і `SameSite=Strict`. Обидві cookie та серверна сесія завершуються через вісім годин. Форми, що змінюють дані, містять непередбачуваний токен; сервер перевіряє його за cookie та активною сесією. Після успішної авторизації токени змінюються. Під час виходу сервер видаляє сесію й відкликає обидві cookie. Для входу й реєстрації дозволено не більше восьми спроб з однієї IP-адреси за 15 хвилин. Гості можуть читати теми та публічні профілі, але для створення теми, відповіді чи редагування профілю потрібно ввійти.

POST-запити обмежені розміром 64 КіБ і мають містити дані форми. Заголовок теми обмежений 160 символами, текст теми й відповіді — 10 000, поле хештегів — 300, біографія — 280 символами. Сервер встановлює сувору Content Security Policy та заголовки проти вбудовування у фрейм, MIME-sniffing і витоку referrer. Тайм-аут з’єднання — 10 секунд; локальний сервер обслуговує до 64 потоків паралельно та ставить у чергу до 32 з’єднань.

#### Теми, відповіді та хештеги

Створювати теми й відповідати можуть лише користувачі, які ввійшли. Хештеги можна розділяти пробілами або комами. Обробник прибирає необов’язковий початковий `#`, переводить теги в нижній регістр, видаляє повтори, пропускає некоректні значення та залишає не більше восьми тегів. Тег може містити літери, цифри, підкреслення й дефіси; максимальна довжина — 32 символи.

Хештеги відображаються як посилання `#tag`. Натискання відкриває головну сторінку з цим тегом у полі пошуку. Текстовий пошук, вибір розділу та вкладки Popular/New працюють у браузері й можуть комбінуватися.

#### Профілі та каталог учасників

Каталог учасників читає дані зареєстрованих акаунтів із SQLite. Публічний профіль показує ім’я користувача, місяць реєстрації та біографію. Користувач, який увійшов, може редагувати лише власну біографію. Сервер обмежує її до 280 символів і екранує введений текст перед вставленням у HTML.

### Структура проєкту

```text
.
├── .github/workflows/tests.yml  # GitHub Actions для Windows і Linux
├── .gitignore                   # Локальні бази, секрети, кеш і середовища
├── main.py                 # HTTP-маршрути, авторизація та SQLite-сховище форуму
├── render.yaml             # Налаштування Render і постійного диска
├── static/
│   ├── app.js               # Пошук, фільтри, вкладки та вікно створення теми
│   └── style.css            # Адаптивні стилі
├── templates/
│   ├── index.html           # Стрічка тем
│   ├── topic.html           # Сторінка обговорення
│   ├── login.html           # Форма входу
│   ├── register.html        # Форма реєстрації
│   ├── members.html         # Каталог учасників
│   ├── profile.html         # Профіль учасника
│   └── about.html           # Опис проєкту та спільноти
└── tests/
    └── test_app.py          # HTTP-тести та перевірки безпеки
```

### Збереження даних і поточні обмеження

Наразі це навчальний/демонстраційний форум, а не готовий до промислового використання сервіс. У поточній реалізації постійно зберігається лише частина даних:

- Облікові записи, хеші паролів, дати реєстрації, біографії, теми, хештеги та відповіді зберігаються в SQLite і переживають перезапуск.
- Форум запускається порожнім; нові теми й відповіді записуються до налаштованої SQLite-бази.
- Сесії також зберігаються в пам’яті. Перезапуск сервера виведе всіх користувачів, навіть якщо cookie залишилася в браузері.
- Локально сервер за замовчуванням використовує `127.0.0.1:8000`. `render.yaml` налаштовує публічний порт Render, HTTPS, cookie `Secure` і постійний диск у Франкфурті.
- Диск Render працює з одним екземпляром і може спричинити коротку перерву під час deploy. Підтвердження пошти й інструментів модерації поки немає. Локальні HTTP-cookie навмисно не мають `Secure`.

Перед масштабуванням за межі одного екземпляра перенесіть дані до керованого PostgreSQL, а сесії — до спільного постійного сховища. Додайте підтвердження пошти, модерацію, резервні копії, моніторинг і виробничий розподілений rate limiter. Поточний CSRF-захист і ліміт спроб за IP корисні, але не замінюють аудит безпеки. Врахуйте вимоги щодо приватності й модерації.

### Нотатки для розробки

Встановлювати пакети чи виконувати збірку не потрібно. Запуск тестів: `python -m unittest discover -s tests -v`. GitHub Actions перевіряє Windows і Linux з Python 3.10–3.14. Змінюйте `main.py`, відповідний шаблон або файли в `static/`, перезапускайте сервер і перевіряйте змінену сторінку в браузері.

### Публікація на GitHub

Створіть порожній репозиторій на GitHub, а потім під’єднайте його до локального:

```powershell
git remote add origin https://github.com/<власник>/<репозиторій>.git
git add .
git commit -m "Prepare forum project"
git push -u origin HEAD
```

`.gitignore` виключає локальну SQLite-базу, Python bytecode, віртуальні середовища та файли із секретами. Перед комітом перевірте `git status`. Файл ліцензії не додано: оберіть ліцензію, перш ніж оголошувати проєкт відкритим.

### Постійний хостинг форуму

GitHub Pages розміщує лише статичні файли й не запускає Python backend. `render.yaml` описує постійно працюючий Python-сервіс на Render з HTTPS і диском 1 GB для SQLite. Після публікації репозиторію на GitHub створіть Blueprint у Render Dashboard і під’єднайте репозиторій. План `0.5c-512mb` і диск платні; оплату стягує Render. Автоматичний deploy очікує на успішні перевірки GitHub Actions. Диск зберігає акаунти та форум після перезапуску, але підтримує лише один екземпляр і може спричиняти коротку перерву під час deploy.
