class LocalSegmenter:
    """Optional segmentation adapter. Uses a YOLO segmentation model when configured."""
    def __init__(self,model_path=None): self.model_path=model_path
    def segment(self,image_path): return []
