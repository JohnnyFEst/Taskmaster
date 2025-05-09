from django.contrib import admin
from .models import Task, Category, UserProfile

admin.site.register(Task)
admin.site.register(Category)
admin.site.register(UserProfile)