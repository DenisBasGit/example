class DetailNftTokenSerializer(serializers.ModelSerializer):
    creator = ProfileArtworkSerializer()
    owner = ProfileArtworkSerializer()
    is_mine = serializers.BooleanField(default=False)
    tags = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = NftToken
        fields = [
            "uuid",
            "title",
            "description",
            "tags",
            "cover_image",
            "nft_file",
            "creator",
            "owner",
            "is_listed",
            "is_minted",
            "is_hidden",
            "price",
            "is_mine",
        ]

    @staticmethod
    def get_tags(instance: NftToken) -> List[str]:
        """Return list of related tags"""
        return list(instance.tags.values_list("name", flat=True))

    @staticmethod
    def get_price(instance: NftToken) -> Optional[Decimal]:
        if not instance.is_listed:
            return None
        if not hasattr(instance, "last_price"):
            price_history = (
                PriceHistory.objects.filter(token=instance).order_by("-created").first()
            )
            return price_history.price if price_history else None
        return instance.last_price
