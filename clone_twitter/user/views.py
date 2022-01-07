import json
import rest_framework.pagination
from tweet.serializers import custom_paginator
import user.paginations
from django.db.models.expressions import Case, When
from django.contrib.auth import authenticate
from user.utils import unique_random_id_generator, unique_random_email_generator
from django.shortcuts import get_object_or_404, redirect
from rest_framework import status, permissions, viewsets
from rest_framework.views import Response, APIView
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from user.serializers import UserCreateSerializer, UserInfoSerializer, UserLoginSerializer, FollowSerializer, UserFollowSerializer, UserFollowingSerializer, UserProfileSerializer, UserSearchInfoSerializer, jwt_token_of, UserRecommendSerializer
from django.db import IntegrityError
from django.db.models import Q, Count
from user.models import Follow, User, SocialAccount, ProfileMedia
import requests
from twitter.settings import get_secret, FRONT_URL
# Create your views here.

class PingPongView(APIView):
    permission_classes = (permissions.AllowAny,)

    swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'ping': openapi.Schema(type=openapi.TYPE_STRING, description='ping'),
        }
    ))

    def get(self, request):
        return Response(data={'ping': 'pong'}, status=status.HTTP_200_OK)

class EmailSignUpView(APIView):   #signup with email
    permission_classes = (permissions.AllowAny, )
    # parser_classes = [JSONParser]

    @swagger_auto_schema(request_body=openapi.Schema(  #TODO check format
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_STRING, description='user_id'),
            'email': openapi.Schema(type=openapi.FORMAT_EMAIL, description='email'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description='password'),
            'username': openapi.Schema(type=openapi.TYPE_STRING, description='username'),
            'profile_img': openapi.Schema(type=openapi.TYPE_FILE, description='profile_img'),
            'header_img': openapi.Schema(type=openapi.TYPE_FILE, description='header_img'),
            'bio': openapi.Schema(type=openapi.TYPE_STRING, description='bio'),
            'birth_date': openapi.Schema(type=openapi.FORMAT_DATETIME, description='birth_date'),
        }
    ))

    def post(self, request, *args, **kwargs):

        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user, jwt_token = serializer.save()
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT, data={"message": "unexpected db error"})
        return Response({'token': jwt_token, 'user_id': user.user_id}, status=status.HTTP_201_CREATED)

class UserLoginView(APIView): #login with user_id
    permission_classes = (permissions.AllowAny, )

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_STRING, description='user_id'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description='password'),
        }
    ))

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        user_id = serializer.validated_data['user_id']
        return Response({'success': True, 'token': token, 'user_id': user_id}, status=status.HTTP_200_OK)

# TODO: Logout.. expire token and add blacklist.. ?

class UserDeactivateView(APIView): # deactivate
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request):
        me = request.user
        password = request.data.get('password', None)
        if hasattr(me, 'social_account'):
            return Response({'message': "social login user cannot deactivate account via this api"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(user_id=me.user_id, password=password)

        if user is None:
            return Response({'message': "password is wrong"}, status=status.HTTP_401_UNAUTHORIZED)

        retweets = user.retweets.select_related('retweeting').all()
        for retweet in retweets:
            retweet.retweeting.delete()

        user.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)

class UserFollowView(APIView): # TODO: refactor to separate views.. maybe using viewset
    permission_classes = (permissions.IsAuthenticated,)  # later change to Isauthenticated

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_STRING, description='user_id'),
        }
    ))

    def post(self, request):
        serializer = FollowSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            follow_relation = serializer.save()
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT, data={'message':'user already follows followee'})
        return Response(status=status.HTTP_201_CREATED) #TODO: recommend user

class UserUnfollowView(APIView):
    permission_classes = (permissions.IsAuthenticated,)  # later change to Isauthenticated

    @swagger_auto_schema(request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_STRING, description='user_id'),
        }
    ))

    def delete(self, request, user_id=None):  # unfollow/{target_id}/
        target_id = user_id
        if target_id is None:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message':'you have specify user you want to unfollow'})
        try:
            following = User.objects.get(user_id=target_id)
            follow_relation = Follow.objects.get(follower=request.user, following=following)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such user exists'})
        except Follow.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'you can unfollow only currently following user'})
        follow_relation.delete()
        return Response(status=status.HTTP_200_OK, data='successfully unfollowed')

class FollowListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = UserFollowSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = user.paginations.FollowListPagination

    # GET /api/v1/follow_list/{lookup}/follower/
    @action(detail=True, methods=['GET'])
    def follower(self, request, pk=None):
        user = get_object_or_404(User, user_id=pk)
        followers = Follow.objects.filter(following=user).order_by('-created_at')
        page = self.paginate_queryset(followers)

        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(followers, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # GET /api/v1/follow_list/{lookup}/following/
    @action(detail=True, methods=['GET'])
    def following(self, request, pk=None):
        user = get_object_or_404(User, user_id=pk)
        followings = Follow.objects.filter(follower=user).order_by('-created_at')
        page = self.paginate_queryset(followings)

        if page is not None:
            serializer = UserFollowingSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = UserFollowingSerializer(followings, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserInfoViewSet(viewsets.GenericViewSet):
    serializer_class = UserInfoSerializer
    permission_classes = (permissions.AllowAny,)

    # GET /user/{user_user_id}/
    def retrieve(self, request, pk=None):
        if pk == 'me':
            user = request.user
        else:
            user = get_object_or_404(User, user_id=pk)

        serializer = self.get_serializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # PATCH /user/id/
    @action(detail=False, methods=['patch'], name='Id')
    def id(self, request):
        user = request.user

        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    # GET /user/{user_id}/profile/
    @action(detail=True, methods=['get'], url_path='profile', url_name='profile')
    def profile(self, request, pk=None):
        if pk == 'me':
            user = request.user
        else:
            user = get_object_or_404(User, user_id=pk)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # PATCH /user/profile/
    @action(detail=False, methods=['patch'], url_path='profile', url_name='profile')
    def patch_profile(self, request):
        user = request.user

        serializer = UserProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

# Social Login : Kakao

KAKAO_KEY = get_secret("CLIENT_ID")
REDIRECT_URI = get_secret("REDIRECT_URI")

# get authorization code from kakao auth server
class KaKaoSignInView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        kakao_auth_url = "https://kauth.kakao.com/oauth/authorize?response_type=code"
        response = redirect(f'{kakao_auth_url}&client_id={KAKAO_KEY}&redirect_uri={REDIRECT_URI}')
        return response

# get access token from kakao api server
class KakaoCallbackView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        # 1. get token
        code = request.GET.get("code") # TODO tell front (request / query param)
        kakao_token_url = "https://kauth.kakao.com/oauth/token"
        data = {
            'grant_type': 'authorization_code',
            'client_id': KAKAO_KEY,
            'redirect_uri': REDIRECT_URI,
            'code': code,
            # 'client_secret': '', # Not required but.. for security
        }
        response = requests.post(kakao_token_url, data=data).json()
        access_token = response.get("access_token")
        if not access_token:
            url = FRONT_URL + "oauth/callback/kakao/?code=null" + "&message=failed to get access_token"
            response = redirect(url)
            return response
            #return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'failed to get access_token'})

        # 2. get user information
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        user_info_response = requests.get(user_info_url, headers={"Authorization": f"Bearer ${access_token}"},).json()
        kakao_id = user_info_response.get("id")
        if not kakao_id:
            url = FRONT_URL + "oauth/callback/kakao/?code=null" + "&message=failed to get kakao_id"
            response = redirect(url)
            return response
            # return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'failed to get kakao_id'})

        user_info = user_info_response["kakao_account"]
        profile = user_info["profile"]
        nickname = profile['nickname']
        profile_img_url = profile.get("profile_image_url")
        is_default_image = profile.get("is_default_image", True)
        email = user_info.get("email", None)

        # 3. connect kakao account - user
        # user signed up with kakao -> enable kakao login (Q. base login?)
        # case 1. user who has signed up with kakao account trying to login
        kakao_account = SocialAccount.objects.filter(account_id=kakao_id)
        if kakao_account:
            user = kakao_account.first().user
            token = jwt_token_of(user)
            url = FRONT_URL + "oauth/callback/kakao/?code=" + token + "&user_id=" + user.user_id
            response = redirect(url)
            return response
            # return Response({'success': True, 'token': token, 'user_id': user.user_id}, status=status.HTTP_200_OK)

        # case 2. new user signup with kakao (might use profile info)
        else:  #TODO exception duplicate email
            random_id = unique_random_id_generator()
            fake_email = unique_random_email_generator()

            if email and User.objects.filter(email=email).exists():
                url = FRONT_URL + "oauth/callback/kakao/?code=null" + "&message=duplicate email"
                response = redirect(url)
                return response

            user = User(user_id=random_id, email=email, username=nickname)
            user.set_unusable_password()  # user signed up with kakao can only login via kakao login
            user.save()

            if not is_default_image:
                profile_media = ProfileMedia(image_url=profile_img_url)
            else:
                profile_media = ProfileMedia()
            profile_media.user = user
            profile_media.save()

            kakao_account = SocialAccount.objects.create(account_id=kakao_id, type='kakao', user=user)
            token = jwt_token_of(user)
            url = FRONT_URL + "oauth/callback/kakao/?code=" + token + "&user_id=" + user.user_id
            response = redirect(url)

            return response
            # return Response({'token': token, 'user_id': user.user_id}, status=status.HTTP_201_CREATED)

# UNLINK_REDIRECT_URI = get_secret("UNLINK")
ADMIN_KEY = get_secret("ADMIN_KEY")

class KakaoUnlinkView(APIView): # deactivate
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request):
        me = request.user
        if not hasattr(me, 'social_account'):  # TODO add account type checking after google social login
            return Response({'message': "normal user cannot deactivate account via this api"}, status=status.HTTP_400_BAD_REQUEST)

        kakao_id = me.social_account.account_id
        # 2. unlink kakao account
        kakao_unlink_url = "https://kapi.kakao.com/v1/user/unlink"
        data = {
            'target_id_type': 'user_id',
            'target_id': kakao_id,
        }
        auth_header = "KakaoAK " + ADMIN_KEY
        user_unlink_response = requests.post(kakao_unlink_url, data=data, headers={"Authorization": auth_header,
                                             "Content-Type": "application/x-www-form-urlencoded"}).json()
        unlinked_user_id = user_unlink_response.get("id")

        if not unlinked_user_id:
            return Response({'message': "failed to get unlinked user_id"}, status=status.HTTP_400_BAD_REQUEST)
        # 3. delete related social account object
        kakao_account = SocialAccount.objects.get(account_id=kakao_id)
        me = kakao_account.user

        # delete related retweets
        retweets = me.retweets.select_related('retweeting').all()
        for retweet in retweets:
            retweet.retweeting.delete()

        me.delete()
        return Response({'success':True, 'user_id':unlinked_user_id}, status=status.HTTP_200_OK)

class UserRecommendView(APIView):  # recommend random ? users who I don't follow
    queryset = User.objects.all().reverse()
    permission_classes = (permissions.IsAuthenticated,)

    # GET /api/v1/recommend/  TODO: Q. request.user? or specify..?
    def get(self, request):
        me = request.user
        unfollowing_users = self.queryset.exclude(Q(following__follower=me) | Q(pk=me.pk))[:3]

        if unfollowing_users.count() < 3:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "not enough users to recommend"})

        serializer = UserRecommendSerializer(unfollowing_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class FollowRecommendView(APIView):  # recommend random ? users who I don't follow
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    # GET /api/v1/follow/{pk}/recommend/  tmp
    def get(self, request, pk=None):
        me = request.user
        try:
            new_following = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={'message': 'no such user exists'})

        followings = User.objects.filter(following__follower=new_following)
        recommending_users = followings.exclude(Q(following__follower=me) | Q(pk=me.pk))[:3]

        if recommending_users.count() < 3:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': "not enough users to recommend"})

        serializer = UserRecommendSerializer(recommending_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SearchPeopleView(APIView):
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    
    # GET /api/v1/search/people/
    # include 
    def get(self, request):
        if not request.query_params:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'no query provided'})
        search_keywords = request.query_params['query'].split()

        sorted_queryset = \
            User.objects.all() \
            .annotate(num_keywords_included=sum([Case(When(Q(username__icontains=keyword) | Q(user_id__icontains=keyword) | Q(bio__icontains=keyword), then=1), default=0) for keyword in search_keywords]), num_keywords_in_username=sum([Case(When(Q(username__icontains=keyword), then=1), default=0) for keyword in search_keywords]), num_followers=Count('following')) \
            .filter(num_keywords_included__gte=1) \
            .order_by('-num_keywords_in_username', '-num_keywords_included', '-num_followers')

        people_list = [x for x in sorted_queryset]
        people, previous_page, next_page = custom_paginator(people_list, 20, request)
        serializer = UserSearchInfoSerializer(people, many=True, context={'request': request})
        data = serializer.data

        pagination_info = dict()
        pagination_info['previous'] = previous_page
        pagination_info['next'] = next_page

        data.append(pagination_info)
        return Response(data, status=status.HTTP_200_OK)