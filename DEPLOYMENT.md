# Wdrożenie na VPS

## Bezpieczne przygotowanie

Nie zmieniaj innych kontenerów ani serwerów gier. Repozytorium wiąże aplikację wyłącznie do `127.0.0.1:8765`; baza jest w wewnętrznej sieci Docker. Przed zmianą nginx utwórz kopię konkretnego pliku vhost, np. `sudo cp /etc/nginx/sites-available/gry.conf /etc/nginx/sites-available/gry.conf.bak-$(date +%F-%H%M)`.

1. Sklonuj repozytorium do np. `/opt/wot-twitch-drops-dashboard`.
2. Skopiuj `.env.example` do `.env`, ustaw losowe hasło PostgreSQL i sekrety.
3. Wygeneruj klucz sesji: `openssl rand -hex 32`.
4. Wygeneruj klucz tokenów: `docker run --rm python:3.12-slim sh -c "pip -q install cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"`.
5. `docker compose up -d --build` i sprawdź healthcheck.
6. Wklej zawartość `deploy/nginx/wot.conf` do istniejącego bloku HTTPS `server`.
7. `sudo nginx -t && sudo systemctl reload nginx`.
8. Wejdź na `/wot/` i utwórz administratora.

## Backup i przywracanie

Backup logiczny: `docker compose exec -T db pg_dump -U wot -Fc wot > backups/wot.dump`. Przechowuj kopię poza VPS i testuj odtworzenie. Restore do pustej bazy: `docker compose exec -T db pg_restore -U wot -d wot --clean --if-exists < backups/wot.dump` (operacja destrukcyjna — wykonaj tylko po dodatkowym backupie).

## Aktualizacja bez utraty danych

Wykonaj backup, pobierz zmiany przez `git pull --ff-only`, zbuduj obraz, uruchom migrację w jednorazowym kontenerze, a potem podmień tylko usługę `app`. Wolumen `postgres_data` pozostaje nietknięty. Do rollbacku użyj poprzedniego tagu Git; nie cofaj migracji bez sprawdzenia jej procedury `downgrade`.

## Sekrety wymagające działania użytkownika

Użytkownik sam tworzy aplikację Twitch, wpisuje sekret do `.env` i wykonuje OAuth. Repozytorium, CI i logi nie przechowują tych wartości. Rzeczywiste wdrożenie na `gry.lemanczyk-it.pl` wymaga dostępu SSH do VPS, którego ten projekt nie zakłada.
