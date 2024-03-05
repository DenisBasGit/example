# Models.py

class Post(models.Model):
    """
    Post model
    """

    class VisibilityChoices(models.TextChoices):
        PUBLIC = "public"
        PRIVATE = "private"

    author = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(blank=True, default="", max_length=2200)
    content = models.TextField(blank=True)
    status = models.CharField(
        _("Status"), max_length=17, choices=StatusPostChoice.choices, default=StatusPostChoice.PROCEED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views_quantity = models.PositiveIntegerField(default=0)
    favorites_quantity = models.PositiveIntegerField(default=0)
    likes_quantity = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    tags = models.ManyToManyField("Tag", blank=True)  # type: ignore
    categories = models.ManyToManyField("users.Category", blank=True)
    is_commenting_allowed = models.BooleanField(default=True)
    visibility = models.CharField(
        max_length=25,
        choices=VisibilityChoices.choices,
        default=VisibilityChoices.PRIVATE,
    )
    is_reported = models.BooleanField(
        default=False, help_text="Indicates whether the post has violated community rules"
    )

    objects = NotDeletedManager()

    def __str__(self):
        return f"#{self.pk} {self.title}"


class Tag(models.Model):
    """Hashtag model"""

    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class PostMedia(models.Model):
    """Post Media model"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="linked_media")
    type = models.CharField(_("Type"), choices=ContentTypeChoices.choices, max_length=5)
    original = models.FileField(_("Original content"), upload_to=postImageFile)
    formatted_path = models.FileField(_("Formatted path"), null=True, default=None, upload_to=postFormattedPath)
    preview_path = models.FileField(_("Preview path"), null=True, default=None, upload_to=postPreviewPath)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# manager.py
class NotDeletedQuerySet(models.QuerySet):
    """
    QuerySet that filters out objects which are marked as deleted.
    """

    def alive(self):
        return self.filter(is_deleted=False, is_reported=False, author__is_deleted=False)

    def most_popular(self):
        """
        Order queryset from bigger post like/view quantity
        :return:
        """
        # Calculate the ratio of likes to view
        safe_views = Case(When(views_quantity=0, then=1), default=F("views_quantity"), output_field=FloatField())

        likes_to_views_weight = 0.5
        likes_weight = 0.5

        return (
            self.alive()
            .annotate(
                likes_to_views_ratio=F("likes_quantity") / safe_views,
                combined_score=(likes_to_views_weight * F("likes_to_views_ratio"))
                + (likes_weight * F("likes_quantity")),
            )
            .order_by(
                "-combined_score",
                "-views_quantity",
            )
        )

    def public(self):
        return self.most_popular().filter(
            visibility=self.model.VisibilityChoices.PUBLIC, status=StatusPostChoice.PUBLISHED
        )

    def private_for_user(self, user: "User"):
        return self.most_popular().filter(visibility=self.model.VisibilityChoices.PRIVATE, author=user)

    def visible_for_user(self, user: "User"):
        """
        Get posts that are visible for the given user:
        - All public posts
        - All private posts authored by the given user
        """
        return self.public() | self.private_for_user(user)

    def with_comments_count(self):
        """
        Count comments for post

        """
        return self.annotate(
            comments_quantity=Count(
                "comments",
                filter=Q(comments__is_deleted=False, comments__is_reported=False, comments__author__is_deleted=False),
            )
        )


class NotDeletedManager(models.Manager):
    """
    Manager that uses the NotDeletedQuerySet to filter out deleted objects.
    """

    def get_queryset(self) -> NotDeletedQuerySet:
        return NotDeletedQuerySet(self.model, using=self._db).alive()

    def visible_for_user(self, user):
        return self.get_queryset().visible_for_user(user)

    def public(self):
        return self.get_queryset().public()
