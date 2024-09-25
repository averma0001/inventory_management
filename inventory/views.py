from rest_framework import viewsets, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from .models import Item
from .serializers import ItemSerializer
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import logging

logger = logging.getLogger(__name__)


class RegisterViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def register(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email")

        if User.objects.filter(username=username).exists():
            logger.warning(f"Attempt to register with existing username: {username}")
            return Response(
                {"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        User.objects.create(
            username=username, password=make_password(password), email=email
        )
        logger.info(f"User created successfully: {username}")
        return Response(
            {"message": "User created successfully"}, status=status.HTTP_201_CREATED
        )


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    lookup_field = "id"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if Item.objects.filter(name=serializer.validated_data["name"]).exists():
            logger.warning(
                f"Attempt to create existing item: {serializer.validated_data['name']}"
            )
            return Response(
                {"error": "Item already exists"}, status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        logger.info(f"Item created successfully: {serializer.data['name']}")
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def retrieve(self, request, *args, **kwargs):
        item_id = kwargs.get("id")
        cache_key = f"item_{item_id}"

        item = cache.get(cache_key)
        if not item:
            item = get_object_or_404(Item, id=item_id)
            item_data = ItemSerializer(item).data
            cache.set(cache_key, item_data)
            logger.info(f"Fetched item {item_id} from database and cached it")
        else:
            logger.info(f"Fetched item {item_id} from cache")
            item_data = item

        return Response(item_data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        cache_key = f"item_{instance.id}"
        cache.delete(cache_key)
        logger.info(f"Cache for item {instance.id} deleted due to update")

        self.perform_update(serializer)

        logger.info(f"Item updated successfully: {instance.id}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        cache_key = f"item_{instance.id}"
        cache.delete(cache_key)
        logger.info(f"Cache for item {instance.id} deleted due to deletion")

        self.perform_destroy(instance)
        logger.info(f"Item deleted successfully: {instance.id}")
        return Response({"message": "item deleted"}, status=status.HTTP_204_NO_CONTENT)
