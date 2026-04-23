# BooruHub

**Live Demo:** [http://79.137.184.53:8080/](http://79.137.184.53:8080/)

---

## Features

- **Multi-source Search**: Aggregate results from Danbooru, e621, Rule34, and others simultaneously.
- **Universal Tag Mapping**: Define your own "Unitags" that translate automatically to specific tags on each booru site.
- **Advanced Blacklist**: Powerful client-side and server-side filtering.
- **Secure Store**: All API keys are stored **encrypted (AES-256)** on the backend.
- **Full Localization**: Seamlessly switch between **English** and **Russian** languages.

## Disclaimer

**18+ only.** This project aggregates content from adult-oriented imageboards. No third-party content is hosted or stored by this application. Use at your own risk and according to the laws of your jurisdiction.

## Security Setup

Copy `.env.example` to `.env` and generate fresh values before exposing the stack anywhere outside local development.

- `JWT_SECRET` must be a random secret at least 32 characters long.
- `ENCRYPTION_KEY` must be a dedicated Fernet key and should not reuse the JWT secret.
- `ENCRYPTION_KEY_FALLBACKS` can hold previous encryption keys during rotation so existing stored API keys remain decryptable.
- In the default Docker stack only `nginx` is published; `db` and `backend` stay on the internal Docker network.

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.s
