import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from auth_settings import AuthSettings

logger = logging.getLogger('calllens.auth')


async def send_magic_link(settings: AuthSettings, email: str, url: str, purpose: str) -> None:
    if settings.email_mode.lower() == 'log':
        logger.info('MAGIC LINK for %s (%s): %s', email, purpose, url)
        return
    if settings.email_mode.lower() != 'smtp':
        raise RuntimeError('EMAIL_MODE должен быть log или smtp')
    config = ConnectionConfig(
        MAIL_USERNAME=settings.smtp_user,
        MAIL_PASSWORD=settings.smtp_password,
        MAIL_FROM=settings.smtp_from,
        MAIL_PORT=settings.smtp_port,
        MAIL_SERVER=settings.smtp_host,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    message = MessageSchema(
        subject='CallLens: ссылка для входа',
        recipients=[email],
        body=f'Откройте ссылку для входа в CallLens: {url}',
        subtype=MessageType.plain,
    )
    await FastMail(config).send_message(message)
