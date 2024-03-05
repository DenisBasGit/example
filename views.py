# views.py
class UploadPostAPIView(GenericAPIView):
    """Upload post api view"""

    queryset = Post.objects.all()
    serializer_class = PostContentsSerializer
    permission_classes = [IsAuthenticated]
    service_class = PostCreationService

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Upload media with createting post"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.service_class.create(serializer.validated_data, self.request.user)  # type: ignore
        return Response({"post": instance.id}, status=status.HTTP_201_CREATED)

# serializers.py
class PostMediaContentSerializer(serializers.ModelSerializer):
    """Post media serializer"""

    content_type: str

    class Meta:
        model = PostMedia
        fields = ["original"]

    default_error_messages = {
        "unsupported_extension": _("Unsupported extension format."),
    }

    image_validators = [
        FileSizeValidator(settings.IMAGE_MAX_SIZE),
        ImageResolutionValidator(settings.IMAGE_MIN_RESOLUTION_WIDTH, settings.IMAGE_MIN_RESOLUTION_HEIGHT),
    ]
    video_validators = [FileSizeValidator(settings.VIDEO_MAX_SIZE)]
    clip_validators = [
        VideoResolutionValidator(
            settings.VIDEO_HORIZONTAL_MIN_RESOLUTION_WIDTH,
            settings.VIDEO_HORIZONTAL_MIN_RESOLUTION_HEIGHT,
            settings.VIDEO_HORIZONTAL_MAX_RESOLUTION_WIDTH,
            min_width_vertical=settings.VIDEO_VERTICAL_MIN_RESOLUTION_WIDTH,
            min_height_vertical=settings.VIDEO_VERTICAL_MIN_RESOLUTION_HEIGHT,
            max_width_vertical=settings.VIDEO_VERTICAL_MAX_RESOLUTION_HEIGHT,
        ),
        VideoDurationValidator(settings.VIDEO_MAX_TIMELINE),
    ]

    def get_type_of_content(self, file) -> str:
        extension = Path(file.name).suffix[1:].lower()
        if extension in settings.IMAGE_ALLOWED_FORMAT:  # Image format
            return ContentTypeChoices.IMAGE
        elif extension in settings.VIDEO_ALLOWED_FORMAT:
            return ContentTypeChoices.VIDEO
        else:
            raise serializers.ValidationError(
                self.default_error_messages["unsupported_extension"], code="unsupported_extension"
            )

    def validate_original(self, value) -> Dict[str, Any]:
        errors = []
        self.content_type = self.get_type_of_content(value)
        if self.content_type == ContentTypeChoices.IMAGE:
            for validators in self.image_validators:
                try:
                    validators(value)  # type: ignore
                except serializers.ValidationError as exc:
                    errors.append(exc.detail[0])  # type: ignore
                except DjangoValidationError as exc:
                    errors.append(get_error_detail(exc)[0])
        else:
            for validators in self.video_validators:
                try:
                    validators(value)
                except serializers.ValidationError as exc:
                    errors.append(exc.detail[0])  # type: ignore
                except DjangoValidationError as exc:
                    errors.append(get_error_detail(exc)[0])
            with VideoFileClip(value.temporary_file_path()) as clip:
                for validators in self.clip_validators:
                    try:
                        validators(clip)  # type: ignore
                    except serializers.ValidationError as exc:
                        errors.append(exc.detail[0])  # type: ignore
                    except DjangoValidationError as exc:
                        errors.append(get_error_detail(exc)[0])
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data["type"] = self.content_type
        return data


class PostContentsSerializer(serializers.Serializer):
    content = ListUploadMediaField(child=PostMediaContentSerializer())

    default_errors_messages = {
        "content_video_invalid": _("Unable to upload more than 1 video."),
        "mix_content_error": _("Unable to upload video and image together."),
        "max_content_items": _("Content items cannot be bigger than %s items.") % settings.MAX_CONTENT_ITEMS,
    }

    def validate(self, data: Dict[str, Any]):
        content_types = [content["type"] for content in data["content"]]
        if ContentTypeChoices.IMAGE in content_types and ContentTypeChoices.VIDEO in content_types:
            raise serializers.ValidationError(
                {"content": self.default_errors_messages["mix_content_error"]}, "mix_content_error"
            )
        elif ContentTypeChoices.VIDEO in content_types and len(content_types) > 1:
            raise serializers.ValidationError(
                {"content": self.default_errors_messages["content_video_invalid"]}, "content_video_invalid"
            )
        elif len(content_types) > settings.MAX_CONTENT_ITEMS:
            raise serializers.ValidationError(
                {"content": self.default_errors_messages["max_content_items"]}, "max_content_items"
            )
        return data

# service.py
class PostCreationService:
    @classmethod
    def _create(cls, data: Dict) -> Post:
        post = Post.objects.create(**data)
        return post

    @classmethod
    @transaction.atomic
    def create(cls, data: Dict, author: "User") -> Post:
        """
        Create post and add media
        Args:
            data: Content Data
            author: Author of User

        Returns: Post

        """
        content = data.pop("content")
        data["author"] = author
        post = cls._create(data)
        if content:
            PostMediaService.create(post, content)
        return post
