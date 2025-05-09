from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import Task, Category, Tag, UserProfile
from tasks.serializers import (
    UserSerializer, UserRegistrationSerializer, UserProfileSerializer,
    CategorySerializer, TagSerializer, TaskSerializer, ChangePasswordSerializer
)
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

User = get_user_model()

class UserSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', email='test@example.com', first_name='Test', last_name='User')
        cls.profile = UserProfile.objects.create(user=cls.user)

    def test_user_serializer_fields(self):
        serializer = UserSerializer(instance=cls.user)
        self.assertEqual(serializer.data['id'], cls.user.id)
        self.assertEqual(serializer.data['username'], cls.user.username)
        self.assertEqual(serializer.data['email'], cls.user.email)
        self.assertEqual(serializer.data['first_name'], cls.user.first_name)
        self.assertEqual(serializer.data['last_name'], cls.user.last_name)
        self.assertIn('profile', serializer.data)

class UserRegistrationSerializerTests(TestCase):
    def test_user_registration_serializer_valid_data(self):
        data = {'username': 'newuser', 'email': 'new@example.com', 'password': 'securepassword'}
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_user_registration_serializer_create_user(self):
        data = {'username': 'newuser', 'email': 'new@example.com', 'password': 'securepassword'}
        serializer = UserRegistrationSerializer(data=data)
        serializer.is_valid()
        user = serializer.save()
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('securepassword'))

class UserProfileSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser')
        cls.profile = UserProfile.objects.create(user=cls.user)
        cls.image_file = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")
        cls.profile.profile_picture = cls.image_file
        cls.profile.save()

    def test_user_profile_serializer_fields(self):
        serializer = UserProfileSerializer(instance=cls.profile)
        self.assertIn('profile_picture', serializer.data)

class CategorySerializerTests(TestCase):
    def test_category_serializer_valid_data(self):
        data = {'name': 'Work'}
        serializer = CategorySerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_category_serializer_create(self):
        data = {'name': 'Personal'}
        serializer = CategorySerializer(data=data)
        serializer.is_valid()
        category = serializer.save()
        self.assertEqual(category.name, 'Personal')
        self.assertEqual(Category.objects.count(), 1)

class TagSerializerTests(TestCase):
    def test_tag_serializer_valid_data(self):
        data = {'name': 'Important'}
        serializer = TagSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_tag_serializer_create(self):
        data = {'name': 'Urgent'}
        serializer = TagSerializer(data=data)
        serializer.is_valid()
        tag = serializer.save()
        self.assertEqual(tag.name, 'Urgent')
        self.assertEqual(Tag.objects.count(), 1)

class TaskSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser')
        cls.category = Category.objects.create(name='Home')
        cls.tag1 = Tag.objects.create(name='Shopping')
        cls.tag2 = Tag.objects.create(name='Weekend')
        cls.task = Task.objects.create(
            user=cls.user, title='Buy groceries', category=cls.category
        )
        cls.task.tags.add(cls.tag1, cls.tag2)

    def test_task_serializer_fields(self):
        serializer = TaskSerializer(instance=cls.task)
        self.assertEqual(serializer.data['title'], 'Buy groceries')
        self.assertEqual(serializer.data['category_name'], 'Home')
        self.assertIn('tags_names', serializer.data)
        self.assertEqual(len(serializer.data['tags_names']), 2)
        self.assertIn('Shopping', serializer.data['tags_names'])
        self.assertIn('Weekend', serializer.data['tags_names'])
        self.assertEqual(serializer.data['user'], cls.user.id)

    def test_task_serializer_validate_due_date(self):
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)
        serializer = TaskSerializer(data={'due_date': yesterday})
        self.assertFalse(serializer.is_valid())
        self.assertIn('due_date', serializer.errors)

        serializer = TaskSerializer(data={'due_date': today + timezone.timedelta(days=1)})
        self.assertTrue(serializer.is_valid())

    def test_task_serializer_create(self):
        data = {
            'title': 'New Task',
            'description': 'Description of new task',
            'due_date': str(timezone.now().date() + timezone.timedelta(days=2)),
            'priority': 'low',
            'status': 'pending',
            'category': cls.category.id,
            'tags': [cls.tag1.id]
        }
        serializer = TaskSerializer(data=data, context={'request': None})
        serializer.is_valid()
        task = serializer.save(user=cls.user)
        self.assertEqual(task.title, 'New Task')
        self.assertEqual(task.category, cls.category)
        self.assertEqual(task.tags.count(), 1)
        self.assertIn(cls.tag1, task.tags.all())

    def test_task_serializer_update(self):
        data = {'title': 'Updated Task', 'status': 'in_progress', 'tags': [cls.tag2.id]}
        serializer = TaskSerializer(instance=cls.task, data=data, partial=True, context={'request': None})
        serializer.is_valid()
        updated_task = serializer.save()
        self.assertEqual(updated_task.title, 'Updated Task')
        self.assertEqual(updated_task.status, 'in_progress')
        self.assertEqual(updated_task.tags.count(), 1)
        self.assertIn(cls.tag2, updated_task.tags.all())

class ChangePasswordSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='oldpassword')

    def test_change_password_serializer_valid_data(self):
        data = {'old_password': 'oldpassword', 'new_password': 'newsecurepassword'}
        serializer = ChangePasswordSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['old_password'], 'oldpassword')
        self.assertEqual(serializer.validated_data['new_password'], 'newsecurepassword')

    def test_change_password_serializer_invalid_old_password(self):
        data = {'old_password': 'wrongpassword', 'new_password': 'newsecurepassword'}
        serializer = ChangePasswordSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('old_password', serializer.errors)