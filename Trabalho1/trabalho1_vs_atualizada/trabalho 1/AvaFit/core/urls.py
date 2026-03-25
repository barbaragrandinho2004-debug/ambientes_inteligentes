"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from avafit.views import home, ver_stats, ver_config, atualizar_dados, login_view, logout_google





urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('login/', login_view, name='login'), 
    path('', home, name='home'),
    path('atualizar/', atualizar_dados, name='atualizar'),
    path('stats/', ver_stats, name='stats'),
    path('config/', ver_config, name='config'), 
    path('logout/', logout_google, name='logout_google'),



] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
