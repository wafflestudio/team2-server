from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from tweet.models import Tweet, Retweet, UserLike
from tweet.serializers import TweetWriteSerializer, ReplySerializer, RetweetSerializer, TweetDetailSerializer, LikeSerializer, HomeSerializer, QuoteSerializer


class TweetPostView(APIView):      # write tweet
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
        return Response(status=status.HTTP_201_CREATED, data={'message': 'successfully write tweet'})


class TweetDetailView(APIView):     # open thread of the tweet
    permission_classes = (permissions.AllowAny, )

    def get(self, request, pk):
        tweet = get_object_or_404(Tweet, pk=pk)

        if tweet.tweet_type == 'RETWEET':
            tweet = tweet.retweeting.all()[0].retweeted

        serializer = TweetDetailSerializer(tweet, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, pk):
        me = request.user
        if me.is_anonymous:
            return Response(status=status.HTTP_403_FORBIDDEN, data={'message': 'login first'})
        tweet = get_object_or_404(Tweet, pk=pk)
        if (tweet.tweet_type != 'RETWEET' and tweet.author != me) or (tweet.tweet_type == 'RETWEET' and tweet.retweeting_user != me.user_id):
            return Response(status=status.HTTP_403_FORBIDDEN, data={'message': 'you can delete only your tweets'})

        retweets = tweet.retweeted_by.select_related('retweeting').all()
        for retweet in retweets:
            retweet.retweeting.delete()

        tweet.delete()
        return Response(status=status.HTTP_200_OK, data={'message': 'successfully delete tweet'})

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
                return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such tweet exists'})
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_201_CREATED, data={'message': 'successfully reply tweet'})


class RetweetView(APIView):       # do retweet
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='tweet_id'),
        }
    ))

    def post(self, request):
        serializer = RetweetSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            success = serializer.save()
            if not success:
                return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such tweet exists'})
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT, data={'message': 'you already retweeted this tweet'})
        return Response(status=status.HTTP_201_CREATED, data={'message': 'successfully do retweet'})


class RetweetCancelView(APIView):     # cancel retweet
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, pk):
        me = request.user
        source_tweet = get_object_or_404(Tweet, pk=pk)

        try:
            retweeting = source_tweet.retweeted_by.get(user=me).retweeting
        except Retweet.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'you have not retweeted this tweet'})
        retweeting.delete()
        return Response(status=status.HTTP_200_OK, data={'message': 'successfully cancel retweet'})


class QuoteView(APIView):            # quote-retweet
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
        serializer = QuoteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            success = serializer.save()
            if not success:
                return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such tweet exists'})
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_201_CREATED, data={'message': 'successfully quote and retweet'})


class LikeView(APIView):       # do like
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='tweet_id'),
        }
    ))

    def post(self, request):
        serializer = LikeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            success = serializer.save()
            if not success:
                return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such tweet exists'})
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT, data={'message': 'you already liked this tweet'})
        return Response(status=status.HTTP_201_CREATED, data={'message': 'successfully like'})


class UnlikeView(APIView):      # cancel like
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, pk):
        me = request.user
        tweet = get_object_or_404(Tweet, pk=pk)

        try:
            user_like = tweet.liked_by.get(user=me)
        except UserLike.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'you have not liked this tweet'})
        user_like.delete()
        return Response(status=status.HTTP_200_OK, data={'message': 'successfully cancel like'})


class HomeView(APIView):        # home
    permission_classes = (permissions.IsAuthenticated, )

    def get(self, request):
        me = request.user
        serializer = HomeSerializer(me, context={'request': request})
        return Response(serializer.data)
