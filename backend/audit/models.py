from django.db import models


class AuditLog(models.Model):
    institute = models.ForeignKey("institutes.Institute", null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey("accounts.User", null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=64)
    # Allowlisted summaries only; never store passwords, tokens or request payloads.
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
