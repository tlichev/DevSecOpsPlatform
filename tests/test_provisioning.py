import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.provisioning.models import ConfigTemplate
from apps.provisioning.jinja_renderer import render_template


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("provadmin", "admin@test.com", "testpass123!")


@pytest.fixture
def auth_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def vlan_template(db, admin_user):
    return ConfigTemplate.objects.create(
        name="VLAN Config",
        template_type="vlan",
        body="{% for vlan in vlans %}\nvlan {{ vlan.id }}\n name {{ vlan.name }}\n{% endfor %}",
        created_by=admin_user,
    )


class TestJinjaRenderer:
    def test_render_simple_template(self):
        tmpl = "hostname {{ name }}"
        result = render_template(tmpl, {"name": "R1"})
        assert result == "hostname R1"

    def test_render_loop(self):
        tmpl = "{% for v in vlans %}vlan {{ v }}\n{% endfor %}"
        result = render_template(tmpl, {"vlans": [10, 20, 99]})
        assert "vlan 10" in result
        assert "vlan 20" in result

    def test_missing_variable_raises(self):
        from pytest import raises
        with raises(ValueError, match="Missing variable"):
            render_template("hostname {{ missing_var }}", {})

    def test_syntax_error_raises(self):
        from pytest import raises
        with raises(ValueError, match="syntax"):
            render_template("{% for x in items %}", {})


@pytest.mark.django_db
class TestConfigTemplateAPI:
    def test_list_templates(self, auth_client, vlan_template):
        resp = auth_client.get("/api/provisioning/templates/")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_create_template(self, auth_client):
        payload = {
            "name": "OSPF Template",
            "template_type": "routing",
            "body": "router ospf {{ pid }}\n router-id {{ rid }}",
        }
        resp = auth_client.post("/api/provisioning/templates/", payload, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "OSPF Template"

    def test_preview_template(self, auth_client, vlan_template):
        resp = auth_client.post(
            f"/api/provisioning/templates/{vlan_template.pk}/preview/",
            {"variables": {"vlans": [{"id": 10, "name": "USERS"}, {"id": 20, "name": "SERVERS"}]}},
            format="json",
        )
        assert resp.status_code == 200
        assert "vlan 10" in resp.data["rendered"]

    def test_preview_with_missing_var(self, auth_client, vlan_template):
        resp = auth_client.post(
            f"/api/provisioning/templates/{vlan_template.pk}/preview/",
            {"variables": {}},
            format="json",
        )
        assert resp.status_code == 400
