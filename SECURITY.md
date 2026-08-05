# Security Policy

Problemy bezpieczeństwa zgłaszaj prywatnie przez GitHub Security Advisory („Report a vulnerability”), bez publikowania sekretów i danych użytkownika w issue.

## Założenia

- tokeny OAuth są szyfrowane Fernet i odszyfrowywane wyłącznie w pamięci serwera;
- hasła administratora: Argon2id; sesja: podpisane cookie HTTP-only, Secure w HTTPS, SameSite=Lax;
- mutacje wymagają nagłówka CSRF zgodnego z cookie; logowanie ma limit prób;
- SQLAlchemy i Pydantic zapewniają parametryzację oraz walidację; React domyślnie koduje tekst;
- CSP, `nosniff`, polityka referrera i uprawnień ograniczają powierzchnię ataku;
- baza i aplikacja nie otwierają portów publicznych; aplikacja działa jako użytkownik bez roota;
- sekrety nie są logowane i `.env` jest ignorowany przez Git.

Rotuj `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, hasło bazy i Twitch Client Secret po podejrzeniu wycieku. Zmiana klucza Fernet wymaga wcześniej kontrolowanej re-encryptacji lub ponownego OAuth. Aktualizuj obrazy i zależności regularnie. nginx powinien zapewniać TLS, HSTS oraz własne ograniczenia dostępu do hosta.

Znane ograniczenie MVP: limit logowania jest pamięciowy (wystarczający dla pojedynczego procesu). Konfiguracja Discord/SMTP ma przygotowany model ustawień i deduplikację, ale transporty nie są włączone bez dalszej konfiguracji; nie należy deklarować wysyłki, dopóki nie zostanie przetestowana na konkretnych danych użytkownika.
