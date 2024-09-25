import abc
import base64
import collections
import hashlib
import dataclasses
import json
import os
import typing

import cv2
import numpy as np
from PIL import Image

import utils


@typing.runtime_checkable
class Deduper(typing.Protocol):
  @property
  @abc.abstractmethod
  def name(self) -> str:
    ...

  @abc.abstractmethod
  def compute_hash(self, file_path) -> str | None:
    ...

  @abc.abstractmethod
  def key_fn(self, file: utils.ImageFileMeta):
    ...


def compute_md5(file_path):
  """Calculates the MD5 hash of a file."""
  hash_md5 = hashlib.md5()
  with open(file_path, 'rb') as f:
    for chunk in iter(lambda: f.read(4096), b''):
      hash_md5.update(chunk)
  return hash_md5.hexdigest()


class DeduperMd5:
  name: str = 'md5'

  def compute_hash(self, file_path):
    try:
      md5 = compute_md5(file_path)
    except Exception as e:
      print(f'\033[91m=> Failed to compute md5 of {file_path}: {e}\033[0m')
      return None

  def key_fn(self, file: utils.ImageFileMeta):
    return file.relative_path


class DeduperSimhash:
  name: str = 'simhash64x4'

  def compute_hash(self, file_path):
    try:
      img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
      if img is None:
        raise ValueError(f"Could not read image from: {file_path}")
      img = cv2.resize(img, (8, 8))  # Resize to 8x8

      # Convert to 4-level grayscale (0, 64, 128, 192)
      m1 = np.min(img)
      m2 = np.max(img)
      img = (img-m1)//((m2-m1)//4)
      # img = img // 64

      # Convert the 8x8 matrix to a 128-bit binary string
      binary_string = ''.join(format(i, '02b') for i in img.flatten())
      integer_representation = int(binary_string, 2)
      return hex(integer_representation)
    except Exception as e:
      print(f'\033[91m=> Failed to simhash {file_path}: {e}\033[0m')
      return None

  def key_fn(self, file: utils.ImageFileMeta):
    return -file.w, -file.h, -file.size, file.relative_path


def maybe_move(
        hash_to_files: dict[str, utils.ImageFileMeta],
        deduper: Deduper,
        src_root_dir: str,
        dst_root_dir: str | None
):
  for files in hash_to_files.values():
    files.sort(key=deduper.key_fn)

  if not dst_root_dir:
    return hash_to_files

  if not os.path.exists(dst_root_dir):
    os.makedirs(dst_root_dir)

  updated_hash_to_files = {}
  for key, files in hash_to_files.items():
    moved_files = [files[0]]  # This is the best file, don't move it.
    for file in files[1:]:
      src_path = os.path.join(src_root_dir, file.relative_path)
      dst_path = os.path.join(dst_root_dir, file.relative_path)
      dst_dir = os.path.dirname(dst_path)
      if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
      utils.move(src_path, dst_path)
      moved_files.append(dataclasses.replace(file, relative_path=dst_path))

    updated_hash_to_files[key] = moved_files
  return updated_hash_to_files


def dedup_files(src_root_dir: str, dst_root_dir: str | None, mode: str):
  """Walks through the directory, computes MD5s, and generates the HTML."""
  if mode == 'md5':
    deduper = DeduperMd5()
  elif mode == 'sim':
    deduper = DeduperSimhash()
  else:
    raise ValueError(f'Invalid mode: {mode}')

  hash_json = os.path.join(src_root_dir, f'hash_{deduper.name}.json')
  file_to_hash_loaded = dict()  # Maps (str, int) to hash str
  if os.path.exists(hash_json):
    with open(hash_json, 'r') as f:
      file_to_hash_loaded = json.load(f)

  # Compute the hash values.
  file_to_hash_new = dict()  # Maps (str, int) to hash str
  hash_to_files = collections.defaultdict(list)
  num_processed = 0
  for cur_path, _, files in os.walk(src_root_dir):
    for filename in files:
      num_processed += 1
      if num_processed % 1000 == 0:
        print(f'\033[93m=> Processed {num_processed} files.\033[0m')

      if utils.should_skip(filename):
        continue
      fullpath = os.path.join(cur_path, filename)
      size = os.path.getsize(fullpath)
      # Add file size to key to reduce the chance of collisions when loading the
      # hash file after an image is removed and a new image is added with the
      # same name.
      key = f'{fullpath.encode("utf-8")}:{size}'
      if key in file_to_hash_loaded:
        hash_value = file_to_hash_loaded[key]
      else:
        hash_value = deduper.compute_hash(fullpath)

      if hash_value is None:  # Skip if failed to get the hash, maybe non image.
        continue

      try:
        with Image.open(fullpath) as img:
          width, height = img.size
      except Exception as e:
        print(f'\033[91m=> Failed to get image size for {fullpath}\033[0m')
        continue

      file_to_hash_new[key] = hash_value
      relative_path = os.path.relpath(fullpath, src_root_dir)
      hash_to_files[hash_value].append(
          utils.ImageFileMeta(relative_path=relative_path,
                              size=size, w=width, h=height))

  # Move the duplicates with largest filename to dst_root_dir.
  updated_hash_to_files = maybe_move(hash_to_files, deduper,
                                     src_root_dir, dst_root_dir)

  # Generate the html for comparison.
  html = utils.generate_html(updated_hash_to_files, scale_image_by_width=True)
  html_file = os.path.join(src_root_dir, f'image_mapping_{deduper.name}.html')
  with open(html_file, 'w') as f:
    f.write(html)

  # Save the hash to avoid recomputation next time.
  with open(hash_json, 'w') as f:
    json.dump(file_to_hash_new, f, indent=2)


if __name__ == '__main__':
  # src_root_dir = '/Users/laigd/Documents/images/eee/selected-未筛选'
  src_root_dir = '/Users/laigd/Documents/images/eee/网页'
  # src_root_dir = '/tmp/md5test'

  dst_root_dir = '/Users/laigd/.Trash/2'
  # dst_root_dir = None

  mode = 'md5'
  mode = 'sim'

  dedup_files(src_root_dir=src_root_dir, dst_root_dir=dst_root_dir, mode=mode)
