from rest_framework import viewsets, permissions, generics, status, exceptions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Task, Category, Tag, UserProfile
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserProfileSerializer,
    ChangePasswordSerializer, TaskSerializer, CategorySerializer, TagSerializer
)
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
import json
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, CharFilter, DateFilter
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class TaskFilter(FilterSet):
    title = CharFilter(field_name='title', lookup_expr='icontains')
    description = CharFilter(field_name='description', lookup_expr='icontains')
    status = CharFilter(field_name='status', lookup_expr='exact')
    priority = CharFilter(field_name='priority', lookup_expr='exact')
    category = CharFilter(field_name='category_id', lookup_expr='exact') # Filtrar por ID de categoría
    due_date = DateFilter(field_name='due_date', lookup_expr='exact')
    due_date_after = DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_before = DateFilter(field_name='due_date', lookup_expr='lte')

    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'priority', 'category', 'due_date', 'due_date_after', 'due_date_before']

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get('username')
        email = serializer.validated_data.get('email')

        errors = {}
        if User.objects.filter(username=username).exists():
            errors['username'] = ['Este nombre de usuario ya existe']
        if User.objects.filter(email=email).exists():
            errors['email'] = ['Este correo electrónico ya está registrado']

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

class LoginView(generics.GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer # Usamos UserSerializer aquí
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.request.user
        old_password = serializer.validated_data.get('old_password')
        new_password = serializer.validated_data.get('new_password')
        if not user.check_password(old_password):
            return Response({'error': 'Contraseña antigua incorrecta'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        return Response({'message': 'Contraseña actualizada con éxito'}, status=status.HTTP_200_OK)

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter

    def get_queryset(self):
        user = self.request.user
        logger.error(f"Tipo de self.request.user: {type(user)}")
        logger.error(f"Valor de self.request.user: {user}")
        logger.error(f"ID de self.request.user: {user.id if hasattr(user, 'id') else None}")
        logger.error(f"Username de self.request.user: {user.username if hasattr(user, 'username') else None}")
        return Task.objects.filter(user=user)

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise exceptions.PermissionDenied("No tienes permiso para editar esta tarea.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise exceptions.PermissionDenied("No tienes permiso para eliminar esta tarea.")
        instance.delete()

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def forgot_password(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        if not email:
            return Response({'error': 'Se requiere un correo electrónico.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'message': 'Se ha enviado un correo electrónico con instrucciones para restablecer tu contraseña.'}, status=status.HTTP_200_OK)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uidb64={uidb64}&token={token}"

        subject = 'Restablecimiento de contraseña'
        message = f'Por favor, haz clic en el siguiente enlace para restablecer tu contraseña: {reset_url}'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]

        send_mail(subject, message, from_email, recipient_list)

        return Response({'message': 'Se ha enviado un correo electrónico con instrucciones para restablecer tu contraseña.'}, status=status.HTTP_200_OK)

    except json.JSONDecodeError:
        return Response({'error': 'Formato JSON inválido.'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Ocurrió un error inesperado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def reset_password(request):
    try:
        data = json.loads(request.body)
        uidb64 = data.get('uidb64')
        token = data.get('token')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if not all([uidb64, token, new_password, confirm_password]):
            return Response({'error': 'Todos los campos son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'error': 'Las contraseñas no coinciden.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            return Response({'message': 'Contraseña restablecida con éxito', 'access_token': access_token}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Enlace de restablecimiento de contraseña inválido o expirado.'}, status=status.HTTP_400_BAD_REQUEST)
    except json.JSONDecodeError:
        return Response({'error': 'Formato JSON inválido.'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Ocurrió un error inesperado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)