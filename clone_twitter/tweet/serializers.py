from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import serializers
from tweet.models import Tweet, Reply, Retweet, UserLike

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'user_id',
            'profile_img',
        ]

class TweetWriteSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, max_length=500)
    media = serializers.FileField(required=False)

    def validate(self, data):
        content = data.get('content', '')
        media = data.get('media', None)
        if not content and not media:
            raise serializers.ValidationError("neither content nor media")
        return data

    def create(self, validated_data):
        tweet_type = 'GENERAL'
        author = self.context['request'].user
        content = validated_data.get('content', '')
        media = validated_data.get('media', None)

        tweet = Tweet.objects.create(tweet_type=tweet_type, author=author, content=content, media=media)

        return tweet


class TweetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tweet
        exclude = ['created_at']

    author = UserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    retweets = serializers.SerializerMethodField()
    user_retweet = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    user_like = serializers.SerializerMethodField()

    def get_replies(self, tweet):
        return tweet.replied_by.all().count()

    def get_retweets(self, tweet):
        return tweet.retweeted_by.all().count() + tweet.quoted_by.all().count()

    def get_user_retweet(self, tweet):
        me = self.context['request'].user
        if me.is_anonymous:
            return False
        user_retweet = tweet.retweeted_by.filter(user=me).count()
        return user_retweet == 1

    def get_likes(self, tweet):
        return tweet.liked_by.all().count()

    def get_user_like(self, tweet):
        me = self.context['request'].user
        if me.is_anonymous:
            return False
        user_like = tweet.liked_by.filter(user=me).count()
        return user_like == 1


class TweetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tweet
        exclude = ['created_at']

    author = UserSerializer(read_only=True)
    retweets = serializers.SerializerMethodField()
    user_retweet = serializers.SerializerMethodField()
    quotes = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    user_like = serializers.SerializerMethodField()
    replied_tweet = serializers.SerializerMethodField()
    replying_tweets = serializers.SerializerMethodField()

    def get_retweets(self, tweet):
        return tweet.retweeted_by.all().count()

    def get_user_retweet(self, tweet):
        me = self.context['request'].user
        if me.is_anonymous:
            return False
        user_retweet = tweet.retweeted_by.filter(user=me).count()
        return user_retweet == 1

    def get_quotes(self, tweet):
        return tweet.quoted_by.all().count()

    def get_likes(self, tweet):
        return tweet.liked_by.all().count()

    def get_user_like(self, tweet):
        me = self.context['request'].user
        if me.is_anonymous:
            return False
        user_like = tweet.liked_by.filter(user=me).count()
        return user_like == 1

    def get_replied_tweet(self, tweet):
        if tweet.tweet_type != 'REPLY':
            return None
        replied = tweet.replying_to.select_related('replied').get(replying=tweet)
        request = self.context['request']
        replied_tweet = TweetSerializer(replied.replied, context={'request': request})
        return replied_tweet.data

    def get_replying_tweets(self, tweet):
        replying = tweet.replied_by.select_related('replying').all()
        if not replying:
            return []
        replying = [x.replying for x in replying]
        request = self.context['request']
        replying_tweets = TweetSerializer(replying, context={'request': request}, many=True)
        return replying_tweets.data


class ReplySerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    content = serializers.CharField(required=False, max_length=500)
    media = serializers.FileField(required=False)

    def validate(self, data):
        content = data.get('content', '')
        media = data.get('media', None)
        if not content and not media:
            raise serializers.ValidationError("neither content nor media")
        return data


    def create(self, validated_data):
        tweet_id = validated_data.get('id')
        try:
            replied = Tweet.objects.get(id=tweet_id)
        except Tweet.DoesNotExist:
            return False

        tweet_type = 'REPLY'
        author = self.context['request'].user
        reply_to = replied.author.user_id
        content = validated_data.get('content', '')
        media = validated_data.get('media', None)

        replying = Tweet.objects.create(tweet_type=tweet_type, author=author, reply_to=reply_to, content=content, media=media)
        reply = Reply.objects.create(replied=replied, replying=replying)

        return True


class RetweetSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)

    def create(self, validated_data):
        tweet_id = validated_data.get('id')
        try:
            retweeted = Tweet.objects.get(id=tweet_id)
        except Tweet.DoesNotExist:
            return False

        me = self.context['request'].user
        tweet_type = 'RETWEET'
        author = retweeted.author
        retweeting_user = me.user_id
        content = retweeted.content
        media = retweeted.media
        written_at = retweeted.written_at

        exist = retweeted.retweeted_by.filter(user=me)
        if not exist:
            retweeting = Tweet.objects.create(tweet_type=tweet_type, author=author, retweeting_user=retweeting_user, content=content, media=media, written_at=written_at)
            retweet = Retweet.objects.create(retweeted=retweeted, retweeting=retweeting, user=me)
        else:
            false = Retweet.objects.create(retweeted=retweeted, retweeting=retweeted, user=me)

        return True


class LikeSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)

    def create(self, validated_data):
        tweet_id = validated_data.get('id')
        try:
            liked = Tweet.objects.get(id=tweet_id)
        except Tweet.DoesNotExist:
            return False

        me = self.context['request'].user
        user_like = UserLike.objects.create(user=me, liked=liked)

        return True


class HomeSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    tweets = serializers.SerializerMethodField()

    def get_user(self, me):
        serializer = UserSerializer(me)
        return serializer.data

    def get_tweets(self, me):
        follows = me.follower.select_related('following').all()

        q = Q()
        for follow in follows:
            q |= (Q(author=follow.following) & ~Q(tweet_type='RETWEET'))                    # tweets written(or replied, quoted) by my following user
            q |= (Q(retweeting_user=follow.following.user_id) & Q(tweet_type='RETWEET'))    # tweets retweeted by my following user
        q |= (Q(author=me) & ~Q(tweet_type='RETWEET'))                                      # tweets written(or replied, quoted) by me
        q |= (Q(retweeting_user=me.user_id) & Q(tweet_type='RETWEET'))                      # tweets retweeted by me

        tweets = Tweet.objects.filter(q).order_by('-created_at')
        request = self.context['request']
        serializer = TweetSerializer(tweets, many=True, context={'request': request})
        return serializer.data
