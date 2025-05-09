from django.http import HttpResponse

def home(request):
    return HttpResponse("¡Bienvenido a TaskMaster desde la API!")