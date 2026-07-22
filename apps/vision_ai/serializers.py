from rest_framework import serializers

from apps.vision_ai.models import OCRTextBlock, VisionAnalysis, VisionDetection, VisionFrame, VisionInsight


class VisionDetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisionDetection
        fields = "__all__"


class OCRTextBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = OCRTextBlock
        fields = "__all__"


class VisionInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisionInsight
        fields = "__all__"


class VisionFrameSerializer(serializers.ModelSerializer):
    detections = VisionDetectionSerializer(many=True, read_only=True)
    ocr_blocks = OCRTextBlockSerializer(many=True, read_only=True)

    class Meta:
        model = VisionFrame
        fields = "__all__"


class VisionAnalysisSerializer(serializers.ModelSerializer):
    frames = VisionFrameSerializer(many=True, read_only=True)
    insights = VisionInsightSerializer(many=True, read_only=True)

    class Meta:
        model = VisionAnalysis
        fields = "__all__"
        read_only_fields = (
            "status", "completed_providers", "failed_providers", "scene_type", "summary",
            "features", "products", "extracted_text", "confidence", "raw_results",
            "started_at", "finished_at", "error_message",
        )

    def validate(self, attrs):
        if not attrs.get("scene") and not attrs.get("uploaded_image"):
            raise serializers.ValidationError("Provide either scene or uploaded_image.")
        organization = attrs.get("organization")
        scene = attrs.get("scene")
        if scene and organization and scene.organization_id != organization.id:
            raise serializers.ValidationError("The selected scene belongs to another organization.")
        return attrs
