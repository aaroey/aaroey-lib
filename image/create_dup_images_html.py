import abc
import base64
import collections
import dataclasses
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

  @abc.abstractmethod
  def hash_types(self) -> tuple[str, ...]:
    ...

  @abc.abstractmethod
  def compute_hashes(self, file_path: str, file_bytes: bytes) -> dict[str, str]:
    ...

  @abc.abstractmethod
  def key_fn(self, file: utils.ImageFileMeta):
    ...


def compute_md5(file_bytes: bytes):
  """Calculates the MD5 hash of a file."""
  hash_md5 = hashlib.md5()
  hash_md5.update(file_bytes)
  return hash_md5.hexdigest()


class DeduperMd5(Deduper):

  def hash_types(self):
    return ('md5',)

  def compute_hashes(self, file_path: str, file_bytes: bytes):
    hashes = {}
    try:
      md5 = compute_md5(file_bytes)
      hashes['md5'] = md5
    except Exception as e:
      print(f'\033[91m=> Failed to compute md5 of {file_path}: {e}\033[0m')
    return hashes

  def key_fn(self, file: utils.ImageFileMeta):
    return file.relative_path


@dataclasses.dataclass(frozen=True, kw_only=True)
class SimhashConfig:
  tsize: int  # Thumbnail size.
  gscale_bits: int

  @property
  def name(self) -> str:
    size = self.tsize**2
    return f'simhash{size}x{self.gscale}'

  @property
  def gscale(self) -> int:
    return 2**self.gscale_bits


class DeduperSimhash:

  def __init__(self):
    # yapf: disable
    self.cfgs = [
        SimhashConfig(tsize=tsize, gscale_bits=gscale_bits)
        for tsize, gscale_bits in (
            (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), # 4 grayscale
            (4, 1), (5, 1), (6, 1), (7, 1), (8, 1), # 2 grayscale
        )
    ]
    # yapf: enable

  def hash_types(self):
    return tuple(cfg.name for cfg in self.cfgs)

  def compute_hashes(self, file_path: str, file_bytes: bytes):
    hashes = {}
    try:
      # img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
      nparr = np.frombuffer(file_bytes, np.uint8)
      orimg = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
      if orimg is None:
        raise ValueError(f"Could not read image from: {file_path}")

      for cfg in self.cfgs:
        img = cv2.resize(orimg, (cfg.tsize, cfg.tsize))

        # Convert to 4-level grayscale (0, 64, 128, 192)
        # img = img // 64
        m1 = np.min(img)
        m2 = np.max(img)
        img = (img - m1) // ((m2 - m1) // cfg.gscale)

        # Convert the NxN matrix to a binary string. E.g. 8x8 with 4 grayscale
        # will be converted to 128bit binary string.
        binary_string = ''.join(
            format(i, f'0{cfg.gscale_bits}b') for i in img.flatten()
        )
        integer_representation = int(binary_string, 2)
        hashes[cfg.name] = hex(integer_representation)
    except Exception as e:
      print(f'\033[91m=> Failed to simhash {file_path}: {e}\033[0m')
    return hashes

  def key_fn(self, file: utils.ImageFileMeta):
    return -file.w, -file.h, -file.size, file.relative_path


def maybe_move(
    hash_to_metas: dict[str, list[utils.ImageFileMeta]],
    deduper: Deduper,
    src_root_dir: str,
    dst_root_dir: str | None,
):
  for files in hash_to_metas.values():
    files.sort(key=deduper.key_fn)

  if not dst_root_dir:
    return hash_to_metas

  if not os.path.exists(dst_root_dir):
    os.makedirs(dst_root_dir)

  updated_hash_to_metas = {}
  for key, files in hash_to_metas.items():
    moved_files = [files[0]]  # This is the best file, don't move it.
    for file in files[1:]:
      src_path = os.path.join(src_root_dir, file.relative_path)
      dst_path = os.path.join(dst_root_dir, file.relative_path)
      dst_dir = os.path.dirname(dst_path)
      if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
      utils.move(src_path, dst_path)
      moved_files.append(dataclasses.replace(file, relative_path=dst_path))

    updated_hash_to_metas[key] = moved_files
  return updated_hash_to_metas


def compute_hashes(
    src_root_dir: str, hash_type_to_deduper: dict[str, Deduper],
    file_key_to_hash_loaded: dict[str, dict[str, str]]
):
  """Compute the hash values for all known hash types."""
  # Maps hash_type to {(file_path, file_size): hash_value}
  file_key_to_hash_new = collections.defaultdict(dict)
  # Maps hash_type to {hash_value: list[ImageFileMeta]}
  hash_to_metas = collections.defaultdict(lambda: collections.defaultdict(list))

  num_processed = 0
  for cur_path, _, files in os.walk(src_root_dir):
    for filename in files:
      num_processed += 1
      if num_processed % 1000 == 0:
        print(f'\033[93m=> Processed {num_processed} files.\033[0m')

      fullpath = os.path.join(cur_path, filename)
      size = os.path.getsize(fullpath)
      if utils.should_skip(fullpath, size):
        continue

      # Add file size to key to reduce the chance of collisions when loading the
      # hash file after an image is removed and a new image is added with the
      # same name.
      key = f'{fullpath.encode("utf-8")}:{size}'
      # Get from loaded or {}.
      hash_values = file_key_to_hash_loaded.get(key, {})
      file_bytes = open(fullpath, 'rb').read()
      failed_dedupers = []  # Avoid running the same deduper multiple times.

      for hash_type, deduper in hash_type_to_deduper.items():
        if deduper in failed_dedupers:
          continue
        if hash_type not in hash_values:
          # print(f'\033[93m=> Handling type {hash_type} for {fullpath}\033[0m')
          hashes = deduper.compute_hashes(fullpath, file_bytes)
          if hashes:
            hash_values.update(hashes)
          else:
            failed_dedupers.append(deduper)

      file_key_to_hash_new[key] = hash_values

      if len(hash_values) != len(hash_type_to_deduper):
        # Skip if failed to get all hashes, maybe non image.
        continue

      try:
        with Image.open(fullpath) as img:
          width, height = img.size
      except Exception as e:
        print(f'\033[91m=> Failed to get image size for {fullpath}\033[0m')
        continue

      relative_path = os.path.relpath(fullpath, src_root_dir)
      for hash_type, hash_val in hash_values.items():
        hash_to_metas[hash_type][hash_val].append(
            utils.ImageFileMeta(
                relative_path=relative_path, size=size, w=width, h=height
            )
        )
  return file_key_to_hash_new, hash_to_metas


def dedup_files(
    src_root_dir: str,
    dst_root_dir: str | None,
    hash_type_to_move: str | None = None
):
  """Walks through the directory, computes MD5s, and generates the HTML."""
  all_dedupers = (DeduperMd5(), DeduperSimhash())
  hash_type_to_deduper = {}
  for deduper in all_dedupers:
    for hash_type in deduper.hash_types():
      assert hash_type not in hash_type_to_deduper, f'{hash_type} already exists.'
      hash_type_to_deduper[hash_type] = deduper

  file_json_hash = os.path.join(src_root_dir, f'hash_all.json')
  # Maps (file_path, file_size) to {hash_type: hash_value} dict.
  file_key_to_hash_loaded = collections.defaultdict(dict)
  if os.path.exists(file_json_hash):
    with open(file_json_hash, 'r') as f:
      file_key_to_hash_loaded = json.load(f)

  # Computes the hashes.
  file_key_to_hash_new, hash_to_metas = compute_hashes(
      src_root_dir, hash_type_to_deduper, file_key_to_hash_loaded
  )

  # Save the hash to avoid recomputation next time.
  with open(file_json_hash, 'w') as f:
    json.dump(file_key_to_hash_new, f, indent=2)

  # Move the duplicates with largest filename to dst_root_dir.
  if hash_type_to_move is not None:
    updated_hash_to_metas = maybe_move(
        hash_to_metas[hash_type_to_move],
        hash_type_to_deduper[hash_type_to_move], src_root_dir, dst_root_dir
    )
    hash_to_metas[hash_type_to_move] = updated_hash_to_metas

  # Generate the htmls for comparison.
  for hash_type, deduper in hash_type_to_deduper.items():
    html = utils.generate_html(
        hash_to_metas[hash_type], scale_image_by_width=True
    )
    html_file = os.path.join(src_root_dir, f'image_mapping_{hash_type}.html')
    with open(html_file, 'w') as f:
      f.write(html)


if __name__ == '__main__':
  src_root_dir = '/Users/laigd/Documents/images/eee/网页'

  dst_root_dir = '/Users/laigd/.Trash/2'
  dst_root_dir = None

  hash_type_to_move = None

  dedup_files(
      src_root_dir=src_root_dir,
      dst_root_dir=dst_root_dir,
      hash_type_to_move=hash_type_to_move
  )
