from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import TaskViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet)

urlpatterns = [
     path('apartments/', views.apartment_create_list,
          name='apartment-create-list'),
     path('apartments/<int:pk>/', views.apartment_detail,
          name='apartment-detail'),
     path('', include(router.urls)),
     path('tasks/delete-by-user-id/',
          TaskViewSet.as_view({'delete': 'delete_by_user_id'}),
          name='delete-task-by-user-id'),
]
