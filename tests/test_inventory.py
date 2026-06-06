import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.inventory.models import Device, DiscoveryJob


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(username="testadmin", password="testpass123!", email="admin@test.com")
    return user


@pytest.fixture
def auth_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def device(db, admin_user):
    return Device.objects.create(
        hostname="test-router-01",
        ip_address="192.168.100.1",
        device_type="router",
        vendor="cisco",
        status="online",
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestDeviceAPI:
    def test_list_devices_unauthenticated(self, api_client):
        resp = api_client.get("/api/inventory/devices/")
        assert resp.status_code == 401

    def test_list_devices_authenticated(self, auth_client, device):
        resp = auth_client.get("/api/inventory/devices/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_create_device(self, auth_client):
        payload = {
            "hostname": "sw1",
            "ip_address": "192.168.100.11",
            "device_type": "switch",
            "vendor": "cisco",
        }
        resp = auth_client.post("/api/inventory/devices/", payload, format="json")
        assert resp.status_code == 201
        assert resp.data["hostname"] == "sw1"

    def test_create_device_duplicate_ip(self, auth_client, device):
        payload = {
            "hostname": "another-router",
            "ip_address": "192.168.100.1",  # same IP as fixture
            "device_type": "router",
            "vendor": "cisco",
        }
        resp = auth_client.post("/api/inventory/devices/", payload, format="json")
        assert resp.status_code == 400

    def test_get_device_detail(self, auth_client, device):
        resp = auth_client.get(f"/api/inventory/devices/{device.pk}/")
        assert resp.status_code == 200
        assert resp.data["hostname"] == device.hostname

    def test_update_device(self, auth_client, device):
        resp = auth_client.patch(
            f"/api/inventory/devices/{device.pk}/",
            {"os_version": "15.9(3)M6"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["os_version"] == "15.9(3)M6"

    def test_delete_device(self, auth_client, device):
        resp = auth_client.delete(f"/api/inventory/devices/{device.pk}/")
        assert resp.status_code == 204
        assert not Device.objects.filter(pk=device.pk).exists()

    def test_filter_by_status(self, auth_client, device):
        resp = auth_client.get("/api/inventory/devices/?status=online")
        assert resp.status_code == 200
        for item in resp.data["results"]:
            assert item["status"] == "online"

    def test_search_by_hostname(self, auth_client, device):
        resp = auth_client.get("/api/inventory/devices/?search=test-router")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1


@pytest.mark.django_db
class TestDiscoveryAPI:
    def test_start_discovery_job(self, auth_client):
        # Does not actually run (Celery not running in test), just verifies job creation
        resp = auth_client.post(
            "/api/inventory/discovery/",
            {"subnet": "192.168.100.0/24"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["subnet"] == "192.168.100.0/24"
        assert resp.data["status"] in ["pending", "running"]

    def test_list_discovery_jobs(self, auth_client):
        resp = auth_client.get("/api/inventory/discovery/")
        assert resp.status_code == 200
