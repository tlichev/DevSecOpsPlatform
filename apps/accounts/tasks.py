import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task(name='accounts.send_otp_email', queue='default',
             autoretry_for=(Exception,), max_retries=2, retry_backoff=5)
def send_otp_email(user_id: int, code: str):
    """Send a 6-digit OTP code to the user's email address."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('send_otp_email: user %s not found', user_id)
        return

    if not user.email:
        logger.warning('send_otp_email: user %s has no email address', user.username)
        return

    platform_url = getattr(settings, 'PLATFORM_URL', 'http://localhost:8000')
    subject = f'[NetOps Platform] Your verification code: {code}'

    html_body = render_to_string('emails/otp_code.html', {
        'user':         user,
        'code':         code,
        'platform_url': platform_url,
        'expiry_mins':  10,
    })
    text_body = (
        f'Your NetOps Platform verification code is: {code}\n\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not attempt to log in, please contact your administrator immediately.\n'
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send()
    logger.info('send_otp_email: sent to %s', user.email)
