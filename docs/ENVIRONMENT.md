# Environment Variables Documentation

This document describes all environment variables used in the Atria platform.

## Core Settings

### Django Configuration

| Variable                 | Description                           | Default          | Required |
| ------------------------ | ------------------------------------- | ---------------- | -------- |
| `DEBUG`                  | Enable debug mode                     | `0`              | Yes      |
| `SECRET_KEY`             | Django secret key                     | None             | Yes      |
| `ALLOWED_HOSTS`          | Comma-separated list of allowed hosts | None             | Yes      |
| `DJANGO_SETTINGS_MODULE` | Python path to settings module        | `atria.settings` | Yes      |

### Database Configuration

| Variable       | Description             | Default | Required |
| -------------- | ----------------------- | ------- | -------- |
| `DATABASE_URL` | Database connection URL | None    | Yes      |
| `DB_PASSWORD`  | Database password       | None    | Yes      |

## Security Settings

### HTTPS Configuration

| Variable                | Description              | Default | Required |
| ----------------------- | ------------------------ | ------- | -------- |
| `SECURE_SSL_REDIRECT`   | Force HTTPS redirect     | `1`     | No       |
| `SESSION_COOKIE_SECURE` | Secure session cookies   | `1`     | No       |
| `CSRF_COOKIE_SECURE`    | Secure CSRF cookies      | `1`     | No       |
| `CSRF_TRUSTED_ORIGINS`  | Trusted origins for CSRF | None    | Yes      |

## Integration Settings

### Payment Processing

| Variable               | Description          | Default | Required |
| ---------------------- | -------------------- | ------- | -------- |
| `PAYPAL_CLIENT_ID`     | PayPal API client ID | None    | No       |
| `PAYPAL_CLIENT_SECRET` | PayPal API secret    | None    | No       |

### Storage

| Variable               | Description          | Default | Required |
| ---------------------- | -------------------- | ------- | -------- |
| `DROPBOX_OAUTH2_TOKEN` | Dropbox OAuth2 token | None    | No       |

## Example Configurations

### Development

```bash
DEBUG=1
SECRET_KEY=your-dev-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://atria:development@localhost:5432/atria
SECURE_SSL_REDIRECT=0
SESSION_COOKIE_SECURE=0
CSRF_COOKIE_SECURE=0
CSRF_TRUSTED_ORIGINS=http://localhost:8000
```

### Production

```bash
DEBUG=0
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgres://user:password@host:5432/dbname?sslmode=require
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

## Setting Up Environment Variables

### Local Development

1. Copy `.env.example` to `.env`
2. Generate a new secret key
3. Update variables as needed

### Production Deployment

1. Use your platform's secret management system
2. Never commit production secrets to version control
3. Regularly rotate sensitive credentials

## Best Practices

1. **Security**

    - Use strong, unique values for secrets
    - Regularly rotate sensitive credentials
    - Keep production secrets separate from development

2. **Organization**

    - Group related variables together
    - Use clear, descriptive names
    - Document any custom variables

3. **Development**

    - Use `.env.example` as a template
    - Keep development values simple
    - Document required variables

4. **Production**
    - Use production-grade secret management
    - Enable all security features
    - Regularly audit configuration
