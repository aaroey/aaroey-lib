import abc
import base64
import collections
from collections import OrderedDict
import hashlib
import dataclasses
import json
import os
import typing

import cv2
import numpy as np
from PIL import Image

import utils
from nsfw_detector import predict

_DEBUG = False


def should_skip(filename: str):
  for suffix in ('.jpg', '.png', '.webp'):
    if filename.lower().endswith(suffix):
      return False
  if _DEBUG:
    print(f'\033[93m=> Skipping {filename}\033[0m')
  return True


@utils.make_dataclass()
class _FileInfo:
  fullpath: str
  size: int
  w: int
  h: int
  key: str
  res: dict[str, float] = None
  nsfw: bool = None
  score: float = 0

  def to_meta(self):
    return utils.ImageFileMeta(
        relative_path=self.fullpath,
        size=self.size,
        w=self.w,
        h=self.h,
        meta=dict(**self.res, nsfw=self.nsfw, score=self.score)
    )

  def meta_key(self):
    return f'{"NOT-safe" if self.nsfw else "safe"}-{self.score}'


def is_nsfw(metrics: dict[str, float]) -> tuple[bool, float]:
  mhentai, mporn, msexy = metrics['hentai'], metrics['porn'], metrics['sexy']
  thentai, tporn, tsexy = .1, .1, .1  # Metric thresholds.
  score = mhentai + mporn
  if mhentai > thentai or mporn > tporn:
    return True, score
  return False, score


def gen_html(
    src_root_dir: str, meta_dict: dict[str, list[utils.ImageFileMeta]]
):
  html_dir = os.path.join(src_root_dir, 'nsfw_score_html')
  if not os.path.exists(html_dir):
    os.makedirs(html_dir)

  html = utils.generate_html(
      grouped_images=meta_dict, cell_width=200, check_first_image_path=False
  )
  key = next(iter(meta_dict))
  html_file_path = os.path.join(html_dir, f'image_score-{key}.html')
  with open(html_file_path, 'w') as f:
    f.write(html)


def run(src_root_dir: str, first_n: int = 999999999, imgs_per_row: int = 10):
  model_key = 'nsfw_mobilenet2.224x224.h5'
  model = predict.load_model(f'./{model_key}')
  predict_result_json_file_path = os.path.join(
      src_root_dir, f'prediction_result-{model_key}.json'
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
      try:
        with Image.open(fullpath) as img:
          width, height = img.size
      except Exception as e:
        print(f'\033[91m=> Failed to get image size for {fullpath}\033[0m')
        continue

      key = f'{fullpath.encode("utf-8")}:{size}'
      info = _FileInfo(fullpath=fullpath, size=size, key=key, w=width, h=height)
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
    prediction_result = predict.classify(model, file_paths_to_predict)
    for info in infos_to_predict:
      predict_result_new[info.key] = prediction_result[info.fullpath]
  utils.dump_json(predict_result_json_file_path, predict_result_new)

  for info in all_infos:
    info.res = predict_result_new[info.key]
    info.nsfw, info.score = is_nsfw(info.res)

  print(f'\033[93m=> Generating htmls...\033[0m')
  if _DEBUG:
    for info in all_infos:
      print(f'\033[93m=> {info}\033[0m')
  all_infos.sort(key=lambda info: (info.nsfw, info.score, info.size))

  cur_nsfw = None
  cur_row = None
  num_row_elems = imgs_per_row + 1
  meta_dict = collections.defaultdict(list)
  for info in all_infos:
    if num_row_elems >= imgs_per_row or info.nsfw != cur_nsfw:
      if len(meta_dict) >= 100:
        # Each html contains at most 100 rows.
        gen_html(src_root_dir, meta_dict)
        meta_dict.clear()

      # Starts a new row.
      row_key = info.meta_key()
      cur_nsfw = info.nsfw
      cur_row = meta_dict[row_key]
      num_row_elems = 0

    cur_row.append(info.to_meta())
    num_row_elems += 1

  if meta_dict:
    gen_html(src_root_dir, meta_dict)


if __name__ == '__main__':
  print(f'\033[92m=> Need to run in vadtf env and in nsfw_model/ dir.\033[0m')
  print(
      f'\033[93m=> Also need to fix nsfw_model code to support batching.\033[0m'
  )

  src_root_dir = '/Users/laigd/Documents/images/eee/网页'
  # src_root_dir = '/tmp/nsfw-test'

  run(src_root_dir=src_root_dir, imgs_per_row=7)
