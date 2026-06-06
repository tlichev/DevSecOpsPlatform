import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.monitoring.models import Alert


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("monitoradmin", "monitor@test.com", "testpass123!")


@pytest.fixture
def auth_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.mark.django_db
class TestAlertManagerWebhook:
    WEBHOOK_URL = "/api/monitoring/webhook/alertmanager/"

    SAMPLE_PAYLOAD = {
        "version": "4",
        "groupKey": "{}:{alertname=\"InterfaceDown\"}",
        "status": "firing",
        "receiver": "django_webhook",
        "groupLabels": {"alertname": "InterfaceDown"},
        "commonLabels": {"alertname": "InterfaceDown", "severity": "critical"},
        "commonAnnotations": {"summary": "Interface down"},
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "InterfaceDown",
                    "instance": "192.168.100.1:161",
                    "severity": "critical",
                    "ifDescr": "GigabitEthernet0/0",
                },
                "annotations": {"summary": "Interface GigabitEthernet0/0 down"},
                "startsAt": "2024-01-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": "abc123def456",
            }
        ],
    }

    def test_webhook_creates_alert(self, api_client):
        resp = api_client.post(self.WEBHOOK_URL, self.SAMPLE_PAYLOAD, format="json")
        assert resp.status_code == 200
        assert resp.data["received"] == 1
        assert Alert.objects.filter(fingerprint="abc123def456").exists()

    def test_webhook_updates_existing_alert(self, api_client, db):
        api_client.post(self.WEBHOOK_URL, self.SAMPLE_PAYLOAD, format="json")
        api_client.post(self.WEBHOOK_URL, self.SAMPLE_PAYLOAD, format="json")
        assert Alert.objects.filter(fingerprint="abc123def456").count() == 1

    def test_webhook_resolved_status(self, api_client, db):
        resolved_payload = dict(self.SAMPLE_PAYLOAD)
        resolved_payload["alerts"] = [{
            **self.SAMPLE_PAYLOAD["alerts"][0],
            "status": "resolved",
            "fingerprint": "resolved123",
        }]
        resp = api_client.post(self.WEBHOOK_URL, resolved_payload, format="json")
        assert resp.status_code == 200
        alert = Alert.objects.get(fingerprint="resolved123")
        assert alert.status == "resolved"

    def test_list_alerts(self, auth_client, db):
        Alert.objects.create(
            alert_name="TestAlert",
            severity="warning",
            status="firing",
            fingerprint="test-fingerprint-1",
        )
        resp = auth_client.get("/api/monitoring/alerts/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_acknowledge_alert(self, auth_client, db):
        alert = Alert.objects.create(
            alert_name="AckTest",
            severity="info",
            status="firing",
            fingerprint="ack-fingerprint",
        )
        resp = auth_client.patch(f"/api/monitoring/alerts/{alert.pk}/acknowledge/")
        assert resp.status_code == 200
        alert.refresh_from_db()
        assert alert.acknowledged is True
