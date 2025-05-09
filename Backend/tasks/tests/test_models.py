from django.test import TestCase
from django.contrib.auth import get_user_model
from tasks.models import Task, Category, Tag, UserProfile
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date

User = get_user_model()

class UserModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpassword')

    def test_user_creation(self):
        self.assertTrue(isinstance(self.user, User))
        self.assertEqual(self.user.username, 'testuser')
        self.assertTrue(self.user.check_password('testpassword'))
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_user_str_method(self):
        self.assertEqual(str(self.user), 'testuser')

    def test_user_profile_picture(self):
        image_file = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")
        self.user.profile_picture = image_file
        self.user.save()
        self.assertTrue(self.user.profile_picture.name.startswith('profile_pics/'))

class CategoryModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Trabajo')

    def test_category_creation(self):
        self.assertTrue(isinstance(cls.category, Category))
        self.assertEqual(cls.category.name, 'Trabajo')

    def test_category_name_unique(self):
        with self.assertRaises(Exception):
            Category.objects.create(name='Trabajo')

    def test_category_str_method(self):
        self.assertEqual(str(cls.category), 'Trabajo')

class TagModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name='Urgente')

    def test_tag_creation(self):
        self.assertTrue(isinstance(cls.tag, Tag))
        self.assertEqual(cls.tag.name, 'Urgente')

    def test_tag_name_unique(self):
        with self.assertRaises(Exception):
            Tag.objects.create(name='Urgente')

    def test_tag_str_method(self):
        self.assertEqual(str(cls.tag), 'Urgente')

class UserProfileModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='profileuser', password='testpassword')
        cls.user_profile = UserProfile.objects.create(user=cls.user)

    def test_user_profile_creation(self):
        self.assertTrue(isinstance(cls.user_profile, UserProfile))
        self.assertEqual(cls.user_profile.user.username, 'profileuser')

    def test_user_profile_one_to_one_relation(self):
        retrieved_profile = UserProfile.objects.get(user=cls.user)
        self.assertEqual(retrieved_profile, cls.user_profile)
        self.assertEqual(cls.user.profile, cls.user_profile)

    def test_user_profile_str_method(self):
        self.assertEqual(str(cls.user_profile), 'profileuser')

    def test_user_profile_picture(self):
        image_file = SimpleUploadedFile("profile_test.jpg", b"file_content", content_type="image/jpeg")
        cls.user_profile.profile_picture = image_file
        cls.user_profile.save()
        self.assertTrue(cls.user_profile.profile_picture.name.startswith('profile_pics/'))

class TaskModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='taskuser', password='testpassword')
        cls.category = Category.objects.create(name='Personal')
        cls.tag1 = Tag.objects.create(name='Importante')
        cls.tag2 = Tag.objects.create(name='Hoy')
        cls.task = Task.objects.create(
            user=cls.user,
            title='Hacer la compra',
            description='Comprar leche, pan y huevos',
            due_date=date(2025, 5, 10),
            priority='high',
            status='pending',
            category=cls.category,
        )
        cls.task.tags.add(cls.tag1, cls.tag2)

    def test_task_creation(self):
        self.assertTrue(isinstance(cls.task, Task))
        self.assertEqual(cls.task.user, cls.user)
        self.assertEqual(cls.task.title, 'Hacer la compra')
        self.assertEqual(cls.task.description, 'Comprar leche, pan y huevos')
        self.assertEqual(cls.task.due_date, date(2025, 5, 10))
        self.assertEqual(cls.task.priority, 'high')
        self.assertEqual(cls.task.status, 'pending')
        self.assertEqual(cls.task.category, cls.category)
        self.assertEqual(cls.task.tags.count(), 2)
        self.assertIsNotNone(cls.task.created_at)
        self.assertIsNotNone(cls.task.updated_at)

    def test_task_priority_choices(self):
        self.assertIn(cls.task.priority, ['low', 'medium', 'high'])

    def test_task_status_choices(self):
        self.assertIn(cls.task.status, ['pending', 'in_progress', 'completed'])

    def test_task_category_relation(self):
        self.assertEqual(cls.category.tasks.first(), cls.task)

    def test_task_tags_relation(self):
        self.assertIn(cls.tag1, cls.task.tags.all())
        self.assertIn(cls.tag2, cls.task.tags.all())
        self.assertEqual(cls.tag1.tasks.first(), cls.task)
        self.assertEqual(cls.tag2.tasks.first(), cls.task)

    def test_task_str_method(self):
        self.assertEqual(str(cls.task), 'Hacer la compra')