import abc
import base64
import collections
from collections import OrderedDict
import hashlib
import dataclasses
import json
import os
import typing
from typing import Any, Protocol

import cv2
import numpy as np
from PIL import Image

import utils

_DEBUG = False


def should_skip(filename: str):
  for suffix in ('.jpeg', '.jpg', '.png'):  # TODO(laigd): '.webp' has issues.
    if filename.lower().endswith(suffix):
      return False
  if _DEBUG:
    print(f'\033[93m=> Skipping {filename}\033[0m')
  return True


def gen_html(
    src_root_dir: str,
    dir_suffix: str,
    html_name: str,
    meta_dict: dict[str, list[utils.ImageFileMeta]],
):
  html_dir = os.path.join(src_root_dir, f'score_html-{dir_suffix}')
  if not os.path.exists(html_dir):
    os.makedirs(html_dir)

  html = utils.generate_html(
      grouped_images=meta_dict,
      cell_width=200,
      check_first_image_path=False,
      num_images_in_group_to_show_thres=1,
  )
  html_file_path = os.path.join(html_dir, f'{html_name}.html')
  with open(html_file_path, 'w') as f:
    f.write(html)


@utils.make_dataclass()
class _FileInfo:
  fullpath: str
  size: int
  key: str  # Key of the prediction cache.
  metrics: Any = None
  score: float = 0  # Nsfw score, used for grouping.
  meta_key: str = ''  # Key of the html group, used for grouping

  def to_meta(self):
    return utils.ImageFileMeta(
        relative_path=self.fullpath,
        size=self.size,
        meta=(self.metrics, self.score),
    )

  def __lt__(self, rhs):
    key = lambda info: (info.meta_key, info.score, info.size)
    return key(self) < key(rhs)


def write_htmls(
    all_infos: list[_FileInfo], imgs_per_row: int, predictor_name: str
):
  if _DEBUG:
    for info in all_infos:
      print(f'\033[93m=> {info}\033[0m')
  all_infos.sort()

  html_index = 0
  cur_row = None
  cur_meta_key = None
  num_row_elems = imgs_per_row + 1
  meta_dict = collections.defaultdict(list)
  for info in all_infos:
    if num_row_elems >= imgs_per_row or info.meta_key != cur_meta_key:
      if len(meta_dict) >= 100 or (meta_dict and info.meta_key != cur_meta_key):
        # Each html contains at most 100 rows.
        gen_html(
            src_root_dir,
            dir_suffix=predictor_name,
            html_name=f'{cur_meta_key}-{html_index:03}',
            meta_dict=meta_dict,
        )
        meta_dict.clear()
        html_index += 1

      # Starts a new row.
      row_key = f'{info.meta_key}-{info.score}'
      cur_row = meta_dict[row_key]
      cur_meta_key = info.meta_key
      num_row_elems = 0

    cur_row.append(info.to_meta())
    num_row_elems += 1

  if meta_dict:
    gen_html(
        src_root_dir,
        dir_suffix=predictor_name,
        html_name=f'{cur_meta_key}-{html_index:03}',
        meta_dict=meta_dict,
    )


class Predictor(Protocol):

  @property
  @abc.abstractmethod
  def name(self) -> str:
    """Name of the predictor. Used for json and html file names."""

  @abc.abstractmethod
  def run(self, imgs: list[str]) -> dict[str, Any]:
    """Run prediction and return the prediction result to save to json."""

  @abc.abstractmethod
  def score_and_update(self, info: _FileInfo) -> None:
    """Update info's metrics/score/meta_key, and maybe other information."""


_HAS_FACE = 4
_CLASS_WEIGHT_NUDENET = (
    # Tier 1
    ('ANUS_EXPOSED', 1024, '99-porn'),
    ('FEMALE_GENITALIA_EXPOSED', 1024, '99-porn'),
    # Tier 2
    ('BUTTOCKS_EXPOSED', 512, '89-butt'),
    ('ANUS_COVERED', 256, '79-anus_covered'),
    ('FEMALE_GENITALIA_COVERED', 128, '69-genitalia_covered'),
    # Tier 3
    ('BUTTOCKS_COVERED', 64, '59-butt_covered'),
    ('MALE_GENITALIA_EXPOSED', 32, '49-genitalia_male'),
    # Tier 4
    ('FEMALE_BREAST_EXPOSED', 16, '39-breast'),
    ('FEMALE_BREAST_COVERED', 8, '29-breast_covered'),
    # Tier 5
    ('FACE_FEMALE', _HAS_FACE, '19-face'),
    # Tier 6
    ('ARMPITS_EXPOSED', 1, '09-armpits'),
    ('ARMPITS_COVERED', 1, '09-armpits_covered'),
    ('BELLY_EXPOSED', 1, '09-belly'),
    ('BELLY_COVERED', 1, '09-belly_covered'),
    ('FEET_EXPOSED', 1, '09-feet'),
    ('FEET_COVERED', 1, '09-feet_covered'),
    ('FACE_MALE', 1, '09-face_male'),
    ('MALE_BREAST_EXPOSED', 1, '09-breast_male'),
)


def _create_nude_predictor():
  print(f'\033[93m=> Remember to: pip install nudenet \033[0m')
  from nudenet import NudeDetector
  return NudeDetector()


@utils.make_dataclass(frozen=True)
class NudePredictor(Predictor):
  # src_root_dir and dst_root_dir is used for debugging purposes. Need to be set
  # together. When set, it'll copy the images from src_root_dir to dst_root_dir
  # and add bounding boxes to the copies.
  src_root_dir: str = None
  dst_root_dir: str = None

  _detector: Any = dataclasses.field(default_factory=_create_nude_predictor)
  _class_weight_map = {k: w for k, w, _ in _CLASS_WEIGHT_NUDENET}

  def __post_init__(self):
    assert bool(self.src_root_dir) == bool(
        self.dst_root_dir
    ), f'{self.src_root_dir=}, {self.dst_root_dir=}'

  @property
  def name(self) -> str:
    return 'nudenet'

  def run(self, imgs):
    res = self._detector.detect_batch(imgs)
    return {k: v for k, v in zip(imgs, res)}

  def score_and_update(self, info: _FileInfo):
    image = None
    if self.dst_root_dir:
      image = cv2.imread(info.fullpath)

    score = 0
    classes = 0
    for metric in info.metrics:
      cls = metric['class']
      sc = metric['score']
      if image is not None:
        # If in debug mode, draw the bounding boxes.
        self._draw_box(image, metric['box'], f'{cls}: {sc}')
      weight = self._class_weight_map[cls]
      score += (1 + sc) * weight
      classes |= weight
    info.score = score

    meta_key = 'face-' if (classes & _HAS_FACE) else ''
    for name, weight, key in _CLASS_WEIGHT_NUDENET:
      if classes & weight:
        meta_key += key
        break
    info.meta_key = meta_key or '00-neutral'

    # If in debug mode, dump the image with bounding boxes.
    if image is not None:
      dst_path = utils.move_with_roots(
          self.src_root_dir,
          self.dst_root_dir,
          os.path.relpath(info.fullpath, self.src_root_dir),
          move_fn=lambda *args: None  # Don't move, just get the path.
      )
      info.fullpath = dst_path
      cv2.imwrite(dst_path, image)

  def _draw_box(
      self,
      cv2_img,
      box,
      note,  # Description of the box.
      color=(0, 255, 0),
      thickness=2,
      font_scale=1.0,
      text_color=(0, 0, 0),
  ):
    x, y, w, h = box
    cv2.rectangle(cv2_img, (x, y), (x + w, y + h), color, thickness)

    # Calculate text size and position
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(note, font, font_scale, 1)
    text_x = int(x + (w - text_size[0]) / 2)  # Center text horizontally
    text_y = y + h + text_size[1] + 5  # Position below the box

    # Draw background rectangle for the note
    cv2.rectangle(
        cv2_img, (text_x - 2, text_y - text_size[1] - 2),
        (text_x + text_size[0] + 2, text_y + 2), color, -1
    )  # Filled rectangle

    # Add the note text
    cv2.putText(
        cv2_img, note, (text_x, text_y), font, font_scale, text_color, 1,
        cv2.LINE_AA
    )


def run(
    predictor: Predictor,
    *,
    src_root_dir: str,
    first_n: int = 999999999,
    imgs_per_row: int = 10
):
  predict_result_json_file_path = os.path.join(
      src_root_dir, f'prediction_result-{predictor.name}.json'
  )
  # Maps (file_path, file_size) to {metric_name: metric_value}.
  predict_result_loaded = utils.load_json_or(
      predict_result_json_file_path, collections.defaultdict(dict)
  )
  predict_result_new = collections.defaultdict(dict)

  print(f'\033[93m=> Getting all image file paths...\033[0m')
  all_infos = []
  infos_to_predict = []
  num_files = 0

  for cur_path, _, files in os.walk(src_root_dir):
    if num_files > first_n:
      break
    for filename in files:
      if should_skip(filename):
        continue

      fullpath = os.path.join(cur_path, filename)
      size = os.path.getsize(fullpath)
      key = f'{fullpath.encode("utf-8")}:{size}'
      info = _FileInfo(fullpath=fullpath, size=size, key=key)
      all_infos.append(info)

      if key in predict_result_loaded:
        predict_result_new[key] = predict_result_loaded[key]
      else:
        infos_to_predict.append(info)

      num_files += 1
      if num_files > first_n:
        break

  print(f'\033[93m=> Running predictions...\033[0m')
  file_paths_to_predict = [info.fullpath for info in infos_to_predict]
  if _DEBUG:
    print(f'\033[93m=> {file_paths_to_predict}\033[0m')
  if file_paths_to_predict:
    prediction_result = predictor.run(file_paths_to_predict)
    for info in infos_to_predict:
      predict_result_new[info.key] = prediction_result[info.fullpath]
  utils.dump_json(predict_result_json_file_path, predict_result_new)

  for info in all_infos:
    info.metrics = predict_result_new[info.key]
    predictor.score_and_update(info)

  print(f'\033[93m=> Generating htmls...\033[0m')
  write_htmls(all_infos, imgs_per_row, predictor.name)


if __name__ == '__main__':
  src_root_dir = '/Users/laigd/Documents/images/eee/网页'
  src_root_dir = '/tmp/nsfw-test'
  predictor = NudePredictor(
      src_root_dir=src_root_dir, dst_root_dir='/tmp/nsfw-moved'
  )

  first_n = 999999999
  first_n = 100000

  run(predictor, src_root_dir=src_root_dir, first_n=first_n, imgs_per_row=7)
