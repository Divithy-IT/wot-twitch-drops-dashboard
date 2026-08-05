# Changelog

## 0.3.2 — 2026-08-05

- zastąpiono Chrome oficjalnym Mozilla Firefox po odrzuceniu logowania przez mechanizm zgodności Twitcha;
- zachowano ręczną, trwałą sesję noVNC w nowym, odseparowanym wolumenie profilu;
- nie zastosowano podmiany User-Agent ani automatyzacji logowania.

## 0.3.1 — 2026-08-05

- zastąpiono niewspieraną przez Twitch kompilację Debian Chromium oficjalnym Google Chrome;
- włączono programowy WebGL przez SwiftShader i zachowano trwały profil przeglądarki;
- usunięto flagi blokujące aktualizacje komponentów multimedialnych.

## 0.3.0 — 2026-08-05

- trwała sesja Chromium z Xvfb/noVNC i osobnym wolumenem profilu;
- chroniony sesją administratora adres `/wot/browser/`;
- status, kontrola CSRF, monitoring awarii i limity 1 GiB/1 CPU;
- priorytetowe kanały WoT oraz przypomnienie o ręcznym sprawdzeniu Drops Inventory.

## 0.2.0 — 2026-08-05

- oficjalne źródła WoT, cache i synchronizacja co 6 godzin;
- propozycje wydarzeń z zatwierdzaniem, odrzucaniem i oznaczaniem duplikatów;
- kalendarz 30 dni, obserwowane kanały i ręczne potwierdzanie Drops źródłem;
- powiadomienia o nowych informacjach i transmisjach oraz zaszyfrowany Discord webhook;
- migracja `0002` i testy ekstrakcji, deduplikacji, timeoutów, akceptacji i kalendarza.

## 0.1.0 — 2026-08-05

- pierwsze publiczne MVP: administrator, kampanie i nagrody, ręczny postęp, OAuth Twitch;
- responsywny pulpit, SSE/polling i oficjalny Twitch Embed;
- PostgreSQL/Alembic, Docker Compose, nginx, testy i GitHub Actions;
- dokumentacja ograniczeń Twitch API, bezpieczeństwa, backupu i wdrożenia.
