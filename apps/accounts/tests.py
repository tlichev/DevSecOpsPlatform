from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.admin    = User.objects.create_user('u_admin',    password='testpass123', role='admin')
        self.engineer = User.objects.create_user('u_engineer', password='testpass123', role='engineer')
        self.readonly = User.objects.create_user('u_readonly', password='testpass123', role='readonly')
        self.superuser = User.objects.create_superuser('u_super', password='testpass123')

    def test_admin_is_admin(self):
        self.assertTrue(self.admin.is_admin())

    def test_admin_is_engineer(self):
        self.assertTrue(self.admin.is_engineer())

    def test_engineer_is_not_admin(self):
        self.assertFalse(self.engineer.is_admin())

    def test_engineer_is_engineer(self):
        self.assertTrue(self.engineer.is_engineer())

    def test_readonly_is_not_admin(self):
        self.assertFalse(self.readonly.is_admin())

    def test_readonly_is_not_engineer(self):
        self.assertFalse(self.readonly.is_engineer())

    def test_superuser_is_admin(self):
        self.assertTrue(self.superuser.is_admin())

    def test_superuser_is_engineer(self):
        self.assertTrue(self.superuser.is_engineer())

    def test_default_role_is_readonly(self):
        u = User.objects.create_user('u_default', password='testpass123')
        self.assertEqual(u.role, User.ROLE_READONLY)

    def test_role_badge_admin_color(self):
        self.assertEqual(self.admin.get_role_display_badge(), 'danger')

    def test_role_badge_engineer_color(self):
        self.assertEqual(self.engineer.get_role_display_badge(), 'primary')

    def test_role_badge_readonly_color(self):
        self.assertEqual(self.readonly.get_role_display_badge(), 'secondary')


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user   = User.objects.create_user('loginuser', password='testpass123', role='engineer')
        self.url    = reverse('accounts:login')

    def test_login_page_renders(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_login_success_redirects(self):
        resp = self.client.post(self.url, {'username': 'loginuser', 'password': 'testpass123'})
        self.assertRedirects(resp, '/', fetch_redirect_response=False)

    def test_login_wrong_password_stays_on_page(self):
        resp = self.client.post(self.url, {'username': 'loginuser', 'password': 'wrongpass'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username or password')

    def test_login_nonexistent_user(self):
        resp = self.client.post(self.url, {'username': 'nobody', 'password': 'testpass123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username or password')

    def test_authenticated_user_redirected_away_from_login(self):
        self.client.login(username='loginuser', password='testpass123')
        resp = self.client.get(self.url)
        self.assertRedirects(resp, '/', fetch_redirect_response=False)

    def test_logout_redirects_to_login(self):
        self.client.login(username='loginuser', password='testpass123')
        resp = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)


class ProfileViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user   = User.objects.create_user(
            'profileuser', email='orig@example.com',
            password='testpass123', role='engineer',
        )
        self.url = reverse('accounts:profile')

    def test_profile_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp, f'/accounts/login/?next={self.url}',
            fetch_redirect_response=False,
        )

    def test_profile_page_renders_authenticated(self):
        self.client.login(username='profileuser', password='testpass123')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_profile_update_email(self):
        self.client.login(username='profileuser', password='testpass123')
        resp = self.client.post(self.url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'updated@example.com',
        })
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.first_name, 'Test')


class PasswordChangeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user   = User.objects.create_user('pwuser', password='oldpass123', role='engineer')
        self.url    = reverse('accounts:password_change')

    def test_password_change_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp, f'/accounts/login/?next={self.url}',
            fetch_redirect_response=False,
        )

    def test_password_change_page_renders(self):
        self.client.login(username='pwuser', password='oldpass123')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_password_change_wrong_old_password(self):
        self.client.login(username='pwuser', password='oldpass123')
        resp = self.client.post(self.url, {
            'old_password': 'notmypassword',
            'new_password1': 'newpass999',
            'new_password2': 'newpass999',
        })
        self.assertEqual(resp.status_code, 200)


class UserListViewTest(TestCase):
    def setUp(self):
        self.client   = Client()
        self.admin    = User.objects.create_user('admin_lv', password='testpass123', role='admin')
        self.engineer = User.objects.create_user('eng_lv',   password='testpass123', role='engineer')
        self.url      = reverse('accounts:user_list')

    def test_user_list_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp, f'/accounts/login/?next={self.url}',
            fetch_redirect_response=False,
        )

    def test_user_list_requires_admin(self):
        self.client.login(username='eng_lv', password='testpass123')
        resp = self.client.get(self.url)
        self.assertRedirects(resp, '/', fetch_redirect_response=False)

    def test_user_list_accessible_as_admin(self):
        self.client.login(username='admin_lv', password='testpass123')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
