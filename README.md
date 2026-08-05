# WoT Twitch Drops Dashboard

Lekki, polskojęzyczny panel dla jednego administratora, który porządkuje kampanie Twitch Drops gry World of Tanks. Działa pod podkatalogiem `/wot`, pokazuje terminy w `Europe/Warsaw`, ręczny/źródłowy postęp, nagrody, status OAuth, historię zdarzeń i oficjalny Twitch Embed.

> Ważne: publiczne Twitch Helix API **nie udostępnia widzowi** listy kampanii Drops ani dokładnego postępu oglądania. `Get Drops Entitlements` jest przeznaczone dla organizacji będącej właścicielem gry. Aplikacja nie zgaduje danych: kampanie pochodzą z publicznych źródeł lub wpisów ręcznych, a postęp jest wyraźnie oznaczony jako ręczny/szacunkowy/oficjalny.

## Funkcje

- aktywne, nadchodzące (30 dni) i zakończone kampanie;
- nagrody, kwalifikujące kanały, źródło i czas pozostały;
- ręczny postęp, automatyczne oznaczanie zdobytych progów;
- bezpieczny administrator: Argon2id, HTTP-only cookie, CSRF, limit prób, unieważnienie sesji;
- Twitch OAuth Authorization Code bez pytania o hasło, tokeny szyfrowane w PostgreSQL;
- SSE co 30 s i fallback polling co 60 s;
- oficjalny Twitch Embed lub otwarcie streamu w nowej karcie;
- wykrywanie nowych oficjalnych informacji z polskiej mapy aktualności `worldoftanks.eu` co 6 godzin;
- kolejka „Wykryte wydarzenia” z pewnością, źródłem, zatwierdzaniem, odrzucaniem i deduplikacją;
- kalendarz 30 dni i obserwowane kanały z metadanymi Twitch API;
- log zdarzeń i model deduplikacji powiadomień;
- FastAPI + React + PostgreSQL oraz opcjonalna trwała sesja Chromium/noVNC;
- Docker Compose, healthchecki, migracje Alembic, nginx i CI.

## Podgląd

Interfejs jest ciemnym, responsywnym centrum operacyjnym z kartami kampanii, dużymi paskami postępu i kolorowymi statusami. Po uruchomieniu wejdź na `https://gry.lemanczyk-it.pl/wot/`. Zrzutu nie dołączono, ponieważ nie wdrożono aplikacji na wskazanym VPS bez danych dostępowych i sekretów produkcyjnych.

## Wymagania i instalacja

- Linux VPS, Docker Engine z Compose v2;
- istniejący nginx obsługujący `gry.lemanczyk-it.pl`;
- aplikacja Twitch Developer (opcjonalnie dla OAuth).

```bash
git clone https://github.com/Divithy-IT/wot-twitch-drops-dashboard.git
cd wot-twitch-drops-dashboard
cp .env.example .env
# wpisz unikalne sekrety; nigdy ich nie commituj
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8766/api/health
```

Pierwsze wejście wyświetli formularz utworzenia administratora. Hasło musi mieć co najmniej 12 znaków.

## Twitch Developer Application

1. W konsoli Twitch Developer utwórz aplikację typu **Confidential**.
2. Dodaj dokładny OAuth Redirect URL: `https://gry.lemanczyk-it.pl/wot/api/oauth/twitch/callback`.
3. W `.env` ustaw `TWITCH_CLIENT_ID` i `TWITCH_CLIENT_SECRET`.
4. Uruchom ponownie wyłącznie tę aplikację: `docker compose up -d --build app`.
5. W Ustawieniach kliknij „Połącz Twitch” i zaloguj się w oficjalnym oknie Twitch.

Integracja prosi o pusty zakres OAuth — identyfikacja użytkownika i publiczne dane streamów nie wymagają dodatkowych uprawnień. Token jest walidowany zgodnie z wymaganiami Twitcha. Brak API postępu oznacza, że konto OAuth nie daje aplikacji dostępu do ekwipunku widza.

## Konfiguracja i wdrożenie

Pełna instrukcja, backup, rollback i aktualizacja: [DEPLOYMENT.md](DEPLOYMENT.md). Gotowy fragment nginx: [deploy/nginx/wot.conf](deploy/nginx/wot.conf). Po wklejeniu wykonaj `sudo nginx -t`, a dopiero potem `sudo systemctl reload nginx`. Nie zastępuj istniejącego vhosta ani konfiguracji certyfikatu.

## Aktualizacja

```bash
git fetch --all --prune
git pull --ff-only
docker compose pull db
docker compose build --pull app
docker compose run --rm app alembic upgrade head
docker compose up -d app
```

## Backup

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U wot -Fc wot > "backups/wot-$(date +%F-%H%M).dump"
```

Profil Chromium znajduje się wyłącznie w nazwanym wolumenie `wot-drops_chromium_profile` i nie trafia
do repozytorium ani backupu PostgreSQL. Sekrety istnieją wyłącznie w `.env`.

## Diagnostyka

- `502` nginx: sprawdź `docker compose ps` i `curl http://127.0.0.1:8765/api/health`.
- OAuth `redirect_mismatch`: URI w Twitch musi być identyczny łącznie z `/wot` i HTTPS.
- Twitch Embed error: `TWITCH_EMBED_PARENT`/host musi odpowiadać domenie HTTPS.
- brak kampanii: dodaj oficjalnie ogłoszoną kampanię ręcznie, wpisując URL źródła.
- token wygasł: użyj „Połącz ponownie”; aplikacja nie zapisuje tokenów w logach.

## Dane i ograniczenia

`source_type` rozróżnia `twitch`, `wargaming` i `manual`; `progress_source` rozróżnia `official`, `manual` i `estimated`. W obecnym MVP widz nie może uzyskać postępu oficjalnego z Twitch API, więc UI domyślnie używa `manual`. Oficjalny stan odebrania należy potwierdzić na [Twitch Drops Inventory](https://www.twitch.tv/drops/inventory).

Automatyczna synchronizacja korzysta wyłącznie z oficjalnej mapy `https://worldoftanks.eu/sitemap-news-pl-1.xml` oraz — jeżeli portal zwróci normalną treść — publicznych metadanych nowych artykułów. Portal może zwrócić stronę ochronną; aplikacja jej nie omija. W takim przypadku zachowuje URL, datę z sitemap i tytuł techniczny, oznacza niższą pewność i pozostawia daty wydarzenia, nagrody oraz czas oglądania puste.

Dokumenty: [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md). Licencja: MIT.

## Trwała przeglądarka VPS

Serwis `browser` uruchamia zwykłe Chromium w Xvfb, udostępnione przez noVNC pod `/wot/browser/`.
Dostęp jest chroniony istniejącą sesją administratora; port noVNC jest związany wyłącznie z
`127.0.0.1:8767`. Kontener ma limit 1 GiB RAM i 1 CPU, nie ma dostępu do Docker socket ani
katalogów innych usług. Logowanie do Twitcha, uruchomienie transmisji i odbieranie nagród wykonuje
użytkownik ręcznie. Panel nie odczytuje DOM, cookies ani prywatnej zawartości Twitcha.
