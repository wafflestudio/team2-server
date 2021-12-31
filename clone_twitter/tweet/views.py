from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from tweet.models import Tweet
from tweet.serializers import TweetWriteSerializer, ReplySerializer


class TweetPostView(APIView):      # write & delete tweet
    permission_classes = (permissions.IsAuthenticated, )

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'content': openapi.Schema(type=openapi.TYPE_STRING, description='content'),
            'media': openapi.Schema(type=openapi.TYPE_FILE, description='media'),
        }
    ))

    def post(self, request):
        serializer = TweetWriteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_201_CREATED, data='successfully write tweet')

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='tweet_id'),
        }
    ))

    def delete(self, request):
        me = request.user
        tweet_id = request.data.get('id', None)
        if tweet_id is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='you have specify tweet you want to delete')
        try:
            tweet = Tweet.objects.get(id=tweet_id)
        except Tweet.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data='no such tweet exists')
        if (tweet.tweet_type != 'RETWEET' and tweet.author != me) or (tweet.tweet_type == 'RETWEET' and tweet.retweeting_user != me.user_id):
            return Response(status=status.HTTP_403_FORBIDDEN, data='you can delete only your tweets')
        tweet.delete()
        return Response(status=status.HTTP_200_OK, data='successfully delete tweet')


# class TweetDetailView(APIView):     # open thread of the tweet
#     permission_classes = (permissions.AllowAny, )


class ReplyView(APIView):       # reply tweet
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='tweet_id'),
            'content': openapi.Schema(type=openapi.TYPE_STRING, description='content'),
            'media': openapi.Schema(type=openapi.TYPE_FILE, description='media'),
        }
    ))
    def post(self, request):
        serializer = ReplySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            success = serializer.save()
            if not success:
                return Response(status=status.HTTP_404_NOT_FOUND, data='no such tweet exists')
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_201_CREATED, data='successfully reply tweet')