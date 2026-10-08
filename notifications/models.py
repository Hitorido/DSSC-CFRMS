from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Persistent, user-specific notification record.

    Distinct from Django messages (django.contrib.messages):
    - Django messages: ephemeral, survive one redirect, shown to the acting user
    - Notification: stored in the database, shown to the recipient on any
      future visit until they read it

    Primary use case: REQUESTER receives a notification when their reservation
    is approved or rejected by STAFF/ADMIN.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='The user who receives and owns this notification.',
    )
    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        help_text=(
            'The reservation this notification relates to. '
            'SET_NULL preserves notification history if the reservation is deleted.'
        ),
    )
    message = models.TextField(
        help_text='The human-readable notification text shown to the recipient.',
    )
    is_read = models.BooleanField(
        default=False,
        help_text='False until the recipient explicitly reads this notification.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when this notification was created.',
    )

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            # Supports the common queries:
            # - a user's full notification list   (filter by recipient)
            # - a user's unread notifications     (filter by recipient + is_read)
            # - ordered by time                   (order by created_at)
            models.Index(
                fields=['recipient', 'is_read', 'created_at'],
                name='notif_recip_read_ts_idx',
            ),
        ]

    def __str__(self):
        read_status = 'read' if self.is_read else 'unread'
        return (
            f"Notification for {self.recipient.username} "
            f"[{read_status}]: {self.message[:60]}"
        )
