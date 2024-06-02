from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Apartment, Task
from .serializers import ApartmentSerializer, TaskSerializer
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import models
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from datetime import timedelta



@swagger_auto_schema(
    method='post',
    request_body=ApartmentSerializer,
    responses={201: ApartmentSerializer()},
    operation_description="Добавить новое объявление"
)
@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('city', openapi.IN_QUERY, description="City", type=openapi.TYPE_STRING),
        openapi.Parameter('last_sent_date', openapi.IN_QUERY, description="Last sent date", type=openapi.FORMAT_DATETIME),
        openapi.Parameter('reporters', openapi.IN_QUERY, description="List of reporters", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
        openapi.Parameter('sizes', openapi.IN_QUERY, description="List of sizes", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
        openapi.Parameter('min_price', openapi.IN_QUERY, description="Minimum price", type=openapi.TYPE_NUMBER),
        openapi.Parameter('max_price', openapi.IN_QUERY, description="Maximum price", type=openapi.TYPE_NUMBER),
        openapi.Parameter('districts', openapi.IN_QUERY, description="List of districts", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
        openapi.Parameter('property_types', openapi.IN_QUERY, description="List of property types", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING)),
        openapi.Parameter('rooms', openapi.IN_QUERY, description="List of rooms", type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER)),
    ],
    responses={200: ApartmentSerializer(many=True)},
    operation_description="Получить список объявлений"
)
@api_view(['POST', 'GET'])
def apartment_create_list(request):
    if request.method == 'POST':
        serializer = ApartmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'GET':
        city = request.query_params.get('city')
        last_sent_date = request.query_params.get('last_sent_date')
        reporters = request.query_params.getlist('reporters')
        sizes = request.query_params.getlist('sizes')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        districts = request.query_params.getlist('districts')
        property_types = request.query_params.getlist('property_types')

        rooms = request.query_params.getlist('rooms')

        allowed_minutes_ago = timezone.now() - timedelta(minutes=30)

        if last_sent_date:
            last_sent_date = parse_datetime(last_sent_date)
            if last_sent_date is not None:
                if last_sent_date.tzinfo is None:
                    last_sent_date = timezone.make_aware(
                        last_sent_date, timezone.get_current_timezone())

                if last_sent_date < allowed_minutes_ago:
                    last_sent_date = allowed_minutes_ago
            else:
                return Response({'error': 'Invalid date format'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            last_sent_date = allowed_minutes_ago

        try:
            apartments = Apartment.objects.filter(city__iexact=city)
            if last_sent_date:
                apartments = apartments.filter(insertedAt__gt=last_sent_date)
            if reporters:
                apartments = apartments.filter(reporter__in=reporters)
            if sizes:
                size_query = models.Q()
                for size_range in sizes:
                    if size_range.startswith('<'):
                        try:
                            max_size = int(size_range[1:])
                            size_query |= models.Q(size__lt=max_size)
                        except ValueError:
                            continue
                    elif size_range.startswith('>'):
                        try:
                            min_size = int(size_range[1:])
                            size_query |= models.Q(size__gt=min_size)
                        except ValueError:
                            continue
                    else:
                        try:
                            min_size, max_size = map(
                                int, size_range.split('-'))
                            size_query |= models.Q(size__gte=min_size,
                                                   size__lte=max_size)
                        except ValueError:
                            continue
                apartments = apartments.filter(size_query)
            if min_price:
                apartments = apartments.filter(price__gte=min_price)
            if max_price:
                apartments = apartments.filter(price__lte=max_price)
            if districts:
                apartments = apartments.filter(district__in=districts)
            if property_types:
                apartments = apartments.filter(type__in=property_types)
            if rooms:
                apartments = apartments.filter(rooms__in=rooms)
            apartments = apartments.order_by('insertedAt')

            serializer = ApartmentSerializer(apartments, many=True)
            return Response(serializer.data)
        except Exception:
            return Response({'error': 'Server error'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def apartment_detail(request, pk):
    try:
        apartment = Apartment.objects.get(pk=pk)
    except Apartment.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = ApartmentSerializer(apartment)
    return Response(serializer.data)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    @action(detail=False, methods=['delete'], url_path='delete-by-user-id')
    def delete_by_user_id(self, request):
        user_id = request.query_params.get('user_id')
        if user_id:
            task = get_object_or_404(Task, user_id=user_id)
            task.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'user_id is required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='filter-by-user-id')
    def filter_by_user_id(self, request):
        user_id = request.query_params.get('user_id')
        if user_id:
            tasks = Task.objects.filter(user_id=user_id)
            serializer = TaskSerializer(tasks, many=True)
            return Response(serializer.data)
        return Response({'detail': 'Отсутствует user_id.'},
                        status=status.HTTP_400_BAD_REQUEST)
