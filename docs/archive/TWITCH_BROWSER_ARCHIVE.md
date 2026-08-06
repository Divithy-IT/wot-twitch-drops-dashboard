# Archiwum: przeglądarka Twitch na VPS

## Status

Funkcjonalność została wycofana z produkcji 2026-08-06. Jej kompletny kod i
konfigurację zachowuje tag `archive-wot-twitch-browser-2026-08-06`.

## Cel i architektura

Opcjonalna usługa Compose `browser` uruchamiała ręcznie obsługiwaną sesję
Mozilla Firefox dla Twitcha. Kontener zawierał Firefox, Xvfb, Openbox, x11vnc,
websockify i noVNC. Nginx udostępniał noVNC wyłącznie lokalnie przez
`127.0.0.1:8767` i publiczną ścieżkę `/wot/browser/`, chronioną istniejącą
sesją administratora WoT. Backend wykonywał tylko healthcheck oraz ręczne
start/stop/restart; nie automatyzował logowania, oglądania ani odbierania
nagród.

Kod archiwalny obejmuje `browser/Dockerfile`, skrypty startowe i supervisor,
usługę `browser` w Compose, fragment nginx, endpointy backendu, scheduler,
widok React oraz testy.

## Odtworzenie

1. Pobierz tag: `git checkout archive-wot-twitch-browser-2026-08-06`.
2. Uzupełnij bieżący `.env` o wymagane zmienne poniżej, bez commitowania go.
3. Wklej archiwalny fragment `deploy/nginx/wot.conf` do vhosta, sprawdź
   `nginx -t` i przeładuj nginx.
4. Zbuduj oraz uruchom tylko usługę: `docker compose up -d --build browser`.
5. Sprawdź healthcheck kontenera i dostęp administratora do `/wot/browser/`.

Wymagane zmienne: `BROWSER_MANAGER_URL`, `BROWSER_MANAGER_SECRET` oraz
`BROWSER_BIND_PORT`. Wartości sekretów, cookies, tokenów i profili nie należą
do repozytorium ani do tego dokumentu.

## Wynik diagnostyki i powód wycofania

Twitch odrzucał ręczne logowanie po `POST /protected_login` odpowiedzią HTTP
400 z `error_code: 5025`. Formularz ładował się normalnie, a komunikat
„Your browser is not currently supported” pojawiał się po zatwierdzeniu danych.
Ten sam wynik wystąpił w Chromium i Firefoxie, w kontenerze oraz w niezależnej
sesji Firefoxa uruchomionej bezpośrednio na hoście VPS. Nie wdrożono ani nie
poszukiwano obejść zabezpieczeń Twitcha. Z uwagi na niepraktyczność runtime
został usunięty.

## Usunięte elementy produkcyjne

- kontener i obraz `wot-drops-browser`;
- wolumeny profili Firefox i Chromium oraz dane sesyjne;
- port lokalny `127.0.0.1:8767`;
- ścieżki nginx `/wot/browser/` i `/_wot_browser_auth`;
- usługa Compose, endpointy, scheduler, widok panelu i testy browsera.

Panel WoT, backend, PostgreSQL, OAuth, wykrywanie wydarzeń oraz strona
`/wot/` pozostają niezależne od archiwalnej funkcjonalności.
