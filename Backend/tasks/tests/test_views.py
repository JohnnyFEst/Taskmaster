from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from tasks.models import Task, Category, Tag
import json
from django.core import mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class UserRegistrationViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.registration_url = reverse('user-register')

    def test_user_registration_success(self):
        data = {'username': 'newuser', 'email': 'new@example.com', 'password': 'securepassword'}
        response = self.client.post(self.registration_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['username'], 'newuser')
        self.assertEqual(response.data['email'], 'new@example.com')
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_registration_duplicate_username(self):
        User.objects.create_user(username='existinguser', email='exist@example.com', password='password')
        data = {'username': 'existinguser', 'email': 'new@example.com', 'password': 'securepassword'}
        response = self.client.post(self.registration_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_user_registration_duplicate_email(self):
        User.objects.create_user(username='existinguser', email='exist@example.com', password='password')
        data = {'username': 'newuser', 'email': 'exist@example.com', 'password': 'securepassword'}
        response = self.client.post(self.registration_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

class LoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='testuser', password='testpassword')

    def test_login_success(self):
        data = {'username': 'testuser', 'password': 'testpassword'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', response.data)
        self.assertIn('access', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')

    def test_login_invalid_credentials(self):
        data = {'username': 'testuser', 'password': 'wrongpassword'}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)

class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.logout_url = reverse('logout')
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        refresh = RefreshToken.for_user(self.user)
        self.refresh_token = str(refresh)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_logout_success(self):
        data = {'refresh_token': self.refresh_token}
        response = self.client.post(self.logout_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

    def test_logout_invalid_token(self):
        data = {'refresh_token': 'invalid_token'}
        response = self.client.post(self.logout_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class UserProfileViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.profile_url = reverse('user-profile')
        self.user = User.objects.create_user(username='testuser', password='testpassword', email='test@example.com', first_name='Test', last_name='User')
        self.client.force_authenticate(user=self.user)

    def test_get_user_profile(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')

    def test_update_user_profile(self):
        data = {'first_name': 'Updated', 'last_name': 'User'}
        response = self.client.patch(self.profile_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

class ChangePasswordViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.change_password_url = reverse('change-password')
        self.user = User.objects.create_user(username='testuser', password='oldpassword')
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        data = {'old_password': 'oldpassword', 'new_password': 'newpassword'}
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword'))

    def test_change_password_invalid_old_password(self):
        data = {'old_password': 'wrongpassword', 'new_password': 'newpassword'}
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword'))

class TaskViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.task_list_url = reverse('task-list')
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(name='Test Category')
        self.tag = Tag.objects.create(name='Test Tag')
        self.task1 = Task.objects.create(user=self.user, title='Task 1', category=self.category)
        self.task1.tags.add(self.tag)
        self.task2 = Task.objects.create(user=self.user, title='Task 2')
        self.task_detail_url = reverse('task-detail', args=[self.task1.id])

    def test_get_task_list(self):
        response = self.client.get(self.task_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_task(self):
        data = {'title': 'New Task', 'category': self.category.id, 'tags': [self.tag.id]}
        response = self.client.post(self.task_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.count(), 3)
        self.assertEqual(Task.objects.get(id=response.data['id']).user, self.user)
        self.assertEqual(Task.objects.get(id=response.data['id']).category, self.category)
        self.assertEqual(Task.objects.get(id=response.data['id']).tags.count(), 1)
        self.assertEqual(Task.objects.get(id=response.data['id']).tags.first(), self.tag)

    def test_get_task_detail(self):
        response = self.client.get(self.task_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Task 1')

    def test_update_task(self):
        data = {'title': 'Updated Task'}
        response = self.client.patch(self.task_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Task.objects.get(id=self.task1.id).title, 'Updated Task')

    def test_delete_task(self):
        response = self.client.delete(self.task_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Task.objects.count(), 1)

class CategoryViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category_list_url = reverse('category-list')
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.category1 = Category.objects.create(name='Category 1')
        self.category2 = Category.objects.create(name='Category 2')
        self.category_detail_url = reverse('category-detail', args=[self.category1.id])

    def test_get_category_list(self):
        response = self.client.get(self.category_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_category(self):
        data = {'name': 'New Category'}
        response = self.client.post(self.category_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 3)
        self.assertEqual(Category.objects.get(id=response.data['id']).name, 'New Category')

    def test_get_category_detail(self):
        response = self.client.get(self.category_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Category 1')

    def test_update_category(self):
        data = {'name': 'Updated Category'}
        response = self.client.put(self.category_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Category.objects.get(id=self.category1.id).name, 'Updated Category')

    def test_delete_category(self):
        response = self.client.delete(self.category_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Category.objects.count(), 1)

class TagViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tag_list_url = reverse('tag-list')
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.tag1 = Tag.objects.create(name='Tag 1')
        self.tag2 = Tag.objects.create(name='Tag 2')
        self.tag_detail_url = reverse('tag-detail', args=[self.tag1.id])

    def test_get_tag_list(self):
        response = self.client.get(self.tag_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_tag(self):
        data = {'name': 'New Tag'}
        response = self.client.post(self.tag_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.count(), 3)
        self.assertEqual(Tag.objects.get(id=response.data['id']).name, 'New Tag')

    def test_get_tag_detail(self):
        response = self.client.get(self.tag_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Tag 1')

    def test_update_tag(self):
        data = {'name': 'Updated Tag'}
        response = self.client.put(self.tag_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Tag.objects.get(id=self.tag1.id).name, 'Updated Tag')

    def test_delete_tag(self):
        response = self.client.delete(self.tag_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Tag.objects.count(), 1)

class ForgotPasswordViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.forgot_password_url = reverse('forgot-password')
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='oldpassword')
        self.frontend_url = settings.FRONTEND_URL

    def test_forgot_password_valid_email(self):
        data = {'email': 'test@example.com'}
        response = self.client.post(self.forgot_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])
        self.assertIn(f'{self.frontend_url}/reset-password', mail.outbox[0].body)

    def test_forgot_password_invalid_email(self):
        data = {'email': 'nonexistent@example.com'}
        response = self.client.post(self.forgot_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('se ha enviado un correo electrónico', response.data['message'])

    def test_forgot_password_no_email(self):
        response = self.client.post(self.forgot_password_url,json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Se requiere un correo electrónico', response.data['error'])

class ResetPasswordViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.reset_password_url = reverse('reset-password')
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='oldpassword')
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def test_reset_password_success(self):
        data = {
            'uidb64': self.uidb64,
            'token': self.token,
            'new_password': 'newsecurepassword',
            'confirm_password': 'newsecurepassword'
        }
        response = self.client.post(self.reset_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Contraseña restablecida con éxito', response.data['message'])
        self.assertTrue(self.user.check_password('newsecurepassword'))

    def test_reset_password_password_mismatch(self):
        data = {
            'uidb64': self.uidb64,
            'token': self.token,
            'new_password': 'newsecurepassword',
            'confirm_password': 'differentpassword'
        }
        response = self.client.post(self.reset_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Las contraseñas no coinciden', response.data['error'])

    def test_reset_password_invalid_token(self):
        data = {
            'uidb64': self.uidb64,
            'token': 'invalid-token',
            'new_password': 'newsecurepassword',
            'confirm_password': 'newsecurepassword'
        }
        response = self.client.post(self.reset_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Enlace de restablecimiento de contraseña inválido', response.data['error'])

    def test_reset_password_invalid_uidb64(self):
        data = {
            'uidb64': 'invalid-uidb64',
            'token': self.token,
            'new_password': 'newsecurepassword',
            'confirm_password': 'newsecurepassword'
        }
        response = self.client.post(self.reset_password_url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Enlace de restablecimiento de contraseña inválido', response.data['error'])