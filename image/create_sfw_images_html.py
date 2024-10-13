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
from nudenet import NudeDetector

_DEBUG = False


def should_skip(filename: str):
  for suffix in ('.jpeg', '.jpg', '.png', '.webp'):
    if filename.lower().endswith(suffix):
      return False
  if _DEBUG:
    print(f'\033[93m=> Skipping {filename}\033[0m')
  return True


def gen_html(
    src_root_dir: str, dir_suffix: str, html_suffix: str,
    meta_dict: dict[str, list[utils.ImageFileMeta]]
):
  html_dir = os.path.join(src_root_dir, f'score_html-{dir_suffix}')
  if not os.path.exists(html_dir):
    os.makedirs(html_dir)

  html = utils.generate_html(
      grouped_images=meta_dict,
      cell_width=400,
      check_first_image_path=False,
      num_images_in_group_to_show_thres=1,
  )
  html_file_path = os.path.join(html_dir, f'image_score-{html_suffix}.html')
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
            html_suffix=f'{cur_meta_key}-{html_index}',
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
        html_suffix=f'{cur_meta_key}-{html_index}',
        meta_dict=meta_dict,
    )


class Predictor(Protocol):

  @property
  @abc.abstractmethod
  def name(self) -> str:
    ...

  @abc.abstractmethod
  def run(self, imgs: list[str]) -> dict[str, Any]:
    ...

  @abc.abstractmethod
  def score_and_update(self, info: _FileInfo) -> None:
    ...


_CLASS_WEIGHT = dict(porn=1000, hentai=100, sexy=10, drawings=1, neutral=.1)


@utils.make_dataclass()
class NsfwPredictor(Predictor):
  key: str
  img_dim: int
  model: Any = dataclasses.field(init=False)

  def __post_init__(self):
    from nsfw_detector import predict
    self.model = predict.load_model(
        f'/Users/laigd/Workspace/nsfw_model/models/{self.key}'
    )

  @property
  def name(self) -> str:
    return self.key

  def run(self, imgs):
    return predict.classify(self.model, imgs, self.img_dim)

  def score_and_update(self, info: _FileInfo):
    k, max_value = max(info.metrics.items(), key=lambda item: item[1])
    info.score = max_value * _CLASS_WEIGHT[k]
    info.meta_key = f'score-{info.score}'


@utils.make_dataclass(frozen=True)
class NudePredictor(Predictor):
  src_root_dir: str = None
  dst_root_dir: str = None
  detector = NudeDetector()

  def __post_init__(self):
    assert bool(self.src_root_dir) == bool(
        self.dst_root_dir
    ), f'{self.src_root_dir=}, {self.dst_root_dir=}'

  @property
  def name(self) -> str:
    return 'nudenet'

  def run(self, imgs):
    res = self.detector.detect_batch(imgs)
    return {k: v for k, v in zip(imgs, res)}

  def score_and_update(self, info: _FileInfo):
    image = None
    if self.dst_root_dir:
      image = cv2.imread(info.fullpath)

    score = 0
    has_porn, has_breast, has_sexy, has_face = [False] * 4
    for metric in info.metrics:
      cls = metric['class']
      sc = metric['score']
      if image is not None:
        # If in debug mode, draw the bounding boxes.
        self._draw_box(image, metric['box'], f'{cls}: {sc}')

      if cls in (
          'FEMALE_GENITALIA_EXPOSED', 'ANUS_EXPOSED', 'BUTTOCKS_EXPOSED'
      ):
        score += (1 + sc) * 100
        has_porn = True
      elif cls in ('FEMALE_BREAST_EXPOSED',):
        score += (1 + sc) * 10
        has_breast = True
      elif cls in (
          'FEMALE_GENITALIA_COVERED', 'ANUS_COVERED', 'BUTTOCKS_COVERED'
      ):
        score += (1 + sc) * 5
        has_sexy = True
      elif cls in ('FACE_FEMALE',):
        score += (1 + sc) * 1
        has_face = True
      else:
        score += sc

    info.score = score
    if has_porn:
      info.meta_key = '4-porn'
    elif has_breast:
      info.meta_key = '3-breast'
    elif has_sexy:
      info.meta_key = '2-sexy'
    elif has_face:
      info.meta_key = '1-face'
    else:
      info.meta_key = '0-neutral'

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
  if _DEBUG:
    for info in all_infos:
      print(f'\033[93m=> {info}\033[0m')
  all_infos.sort()

  write_htmls(all_infos, imgs_per_row, predictor.name)


if __name__ == '__main__':
  print(f'\033[92m=> Need to run in vadtf env and in nsfw_model/ dir.\033[0m')
  print(
      f'\033[93m=> Also need to fix nsfw_model code to support batching.\033[0m'
  )

  src_root_dir = '/Users/laigd/Documents/images/eee/网页'
  src_root_dir = '/tmp/nsfw-test'

  mode = 'nsfw'
  mode = 'nude'

  if mode == 'nsfw':
    # yapf: disable
    key = 'nsfw.299x299.h5'; img_dim = 299
    key = 'nsfw_mobilenet2.224x224.h5'; img_dim = 224
    # yapf: enable
    predictor = NsfwPredictor(key=key, img_dim=img_dim)
  elif mode == 'nude':
    predictor = NudePredictor(
        src_root_dir=src_root_dir, dst_root_dir='/tmp/nsfw-moved'
    )

  first_n = 999999999
  first_n = 300

  run(predictor, src_root_dir=src_root_dir, first_n=first_n, imgs_per_row=7)
