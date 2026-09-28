"""Local YOLOX + DWPose ONNX inference; outputs COCO body keypoints in pixels.

Pre/post-processing follows IDEA-Research/DWPose's Apache-2.0 ONNX reference.
Only CPU providers are used, leaving ComfyUI's GPU allocation untouched.
"""
from pathlib import Path
import threading
import numpy as np


def find_models(roots):
    names = ("yolox_l.onnx", "dw-ll_ucoco_384.onnx")
    roots = [Path(root) for root in roots]
    found = []
    for name in names:
        match = next((p for root in roots if root.is_dir()
                      for p in root.rglob(name) if p.is_file()), None)
        if match is None:
            raise FileNotFoundError(f"Missing {name}. Place both pose models in models/dwpose; see README.")
        found.append(match)
    return found


def nms(boxes, scores, threshold=.45):
    order = np.argsort(-scores)
    keep = []
    areas = np.prod(np.maximum(0, boxes[:, 2:] - boxes[:, :2] + 1), axis=1)
    while order.size:
        i = order[0]
        keep.append(int(i))
        others = order[1:]
        intersection = np.prod(np.maximum(0, np.minimum(boxes[i, 2:], boxes[others, 2:])
                                          - np.maximum(boxes[i, :2], boxes[others, :2]) + 1), axis=1)
        overlap = intersection / np.maximum(areas[i] + areas[others] - intersection, 1e-8)
        order = others[overlap <= threshold]
    return keep


class PoseDetector:
    def __init__(self, roots):
        try:
            import cv2
            import onnxruntime as ort
        except ImportError as error:
            raise RuntimeError("Image import requires onnxruntime and opencv-python-headless; see requirements-pose.txt.") from error
        self.cv2 = cv2
        det, pose = find_models(roots)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        self.detector = ort.InferenceSession(str(det), options, providers=["CPUExecutionProvider"])
        self.pose = ort.InferenceSession(str(pose), options, providers=["CPUExecutionProvider"])
        self.lock = threading.Lock()

    def __call__(self, rgb):
        with self.lock:
            return self._detect(rgb)

    def _detect(self, rgb):
        cv2 = self.cv2
        # DWPose's released ONNX demo expects OpenCV BGR for both networks.
        bgr = np.ascontiguousarray(rgb[..., ::-1])
        height, width = bgr.shape[:2]
        ratio = min(640 / height, 640 / width)
        resized = cv2.resize(bgr, (max(1, int(width * ratio)), max(1, int(height * ratio))))
        padded = np.full((640, 640, 3), 114, dtype=np.float32)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        output = self.detector.run(None, {self.detector.get_inputs()[0].name:
                                         padded.transpose(2, 0, 1)[None].copy()})[0][0]
        grids, strides = [], []
        for stride in (8, 16, 32):
            y, x = np.mgrid[:640 // stride, :640 // stride]
            grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
            strides.append(np.full((x.size, 1), stride))
        stride = np.concatenate(strides)
        center = (output[:, :2] + np.concatenate(grids)) * stride
        size = np.exp(np.clip(output[:, 2:4], -20, 20)) * stride
        boxes = np.concatenate((center - size / 2, center + size / 2), axis=1) / ratio
        scores = output[:, 4] * output[:, 5]  # COCO class 0: person
        valid = scores > .3
        boxes, scores = boxes[valid], scores[valid]
        keep = nms(boxes, scores)[:8]
        # Stable person numbers: left to right, rather than model confidence order.
        keep.sort(key=lambda i: float(boxes[i, 0] + boxes[i, 2]))
        people = []
        for i in keep:
            bbox = boxes[i]
            center = (bbox[:2] + bbox[2:]) / 2
            scale = (bbox[2:] - bbox[:2]) * 1.25
            if np.min(scale) < 2:
                continue
            h, w = self.pose.get_inputs()[0].shape[2:]
            aspect = w / h
            if scale[0] > scale[1] * aspect:
                scale[1] = scale[0] / aspect
            else:
                scale[0] = scale[1] * aspect
            affine = np.array([[w / scale[0], 0, w / 2 - center[0] * w / scale[0]],
                               [0, h / scale[1], h / 2 - center[1] * h / scale[1]]], dtype=np.float32)
            crop = cv2.warpAffine(bgr, affine, (w, h), flags=cv2.INTER_LINEAR).astype(np.float32)
            crop = (crop - np.array([123.675, 116.28, 103.53], np.float32)) / np.array([58.395, 57.12, 57.375], np.float32)
            sx, sy = self.pose.run(None, {self.pose.get_inputs()[0].name: crop.transpose(2, 0, 1)[None].copy()})
            xy = np.stack((sx[0].argmax(axis=-1), sy[0].argmax(axis=-1)), axis=-1) / 2
            xy = xy / [w, h] * scale + center - scale / 2
            confidence = np.minimum(sx[0].max(axis=-1), sy[0].max(axis=-1))
            points = np.column_stack((xy[:17], np.clip(confidence[:17], 0, 1)))
            if (points[5:17, 2] >= .3).sum() < 4:
                continue
            clipped = np.clip(bbox, [0, 0, 0, 0], [width, height, width, height])
            people.append({"index": len(people), "bbox": clipped.tolist(), "score": float(scores[i]),
                           "keypoints": points.tolist()})
        return people
