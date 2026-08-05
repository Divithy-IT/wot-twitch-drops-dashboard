# Architektura

Przeglądarka komunikuje się przez istniejący nginx pod `/wot`. Nginx przekazuje ruch do `127.0.0.1:8765`, gdzie FastAPI serwuje API i build React. PostgreSQL jest dostępny tylko w prywatnej sieci Compose. Alembic uruchamia migracje przed startem aplikacji.

Moduły backendu: `auth` (administrator/sesje/CSRF), `twitch_oauth` (Authorization Code, walidacja, szyfrowanie), `campaigns` (CRUD, status, nagrody, postęp, SSE), `notifications` (atom deduplikacji), `system` (health/logi). Frontend korzysta z BrowserRouter z bazą `/wot`.

Status kampanii jest obliczany z czasu UTC, a prezentowany przez `Intl.DateTimeFormat` w `Europe/Warsaw`. Dane źródłowe zachowują typ, URL i datę aktualizacji. Brak Redisa zmniejsza pamięć i liczbę usług; pojedynczy proces jest właściwy dla jednego użytkownika.

Moduł oglądania używa wyłącznie oficjalnego iframe Twitch z wymaganym parametrem `parent`. Nie steruje odtwarzaniem i nie automatyzuje sesji.

Moduł `official_sources` odpytuje oficjalny polski sitemap WoT co 6 godzin, używa identyfikującego User-Agentu, ETag/Last-Modified i cache w PostgreSQL. Wyniki trafiają do `detected_events`, nigdy bezpośrednio do kampanii. APScheduler co 5 minut sprawdza zapisane kanały Twitch i deduplikuje powiadomienie dla konkretnego czasu rozpoczęcia transmisji.

Osobny kontener bez uprawnień roota zawiera oficjalny Google Chrome, Xvfb, Openbox, x11vnc i noVNC. Wewnętrzny,
chroniony losowym sekretem manager pozwala backendowi wyłącznie sprawdzić i ręcznie zmienić stan
procesu Chromium. Backend nie ma dostępu do Docker socket. Nginx używa `auth_request` do sprawdzania
istniejącej sesji administratora przed każdym żądaniem noVNC i WebSocket.
