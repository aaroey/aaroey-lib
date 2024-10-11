import os
import random
import re
import shutil
import string
from PIL import Image

import utils


def fake_move_fn(src, dst):
  print(f'\033[93m=> {src}\033[0m')


def cleanup_images(
        src_root_dir,
        dst_root_dir,
        size_threshold=20 * 1024,
        delete_regex_patterns=None,
        keep_dir_structture=True,
):  # size in bytes
  """Walks through a directory and moves files that meet certain criteria.

  Args:
    src_root_dir: The path to the source directory.
    dst_root_dir: The path to the destination directory.
    size_threshold: The size threshold in bytes (default: 20KB).
    regex_pattern: Regular expression patterns to match filenames (optional).
  """

  if not os.path.exists(dst_root_dir):
    os.makedirs(dst_root_dir)

  regexes = [re.compile(p) for p in (delete_regex_patterns or ())]
  move_fn = utils.move
  # move_fn = fake_move_fn

  for cur_path, _, files in os.walk(src_root_dir):
    for filename in files:
      if utils.should_skip(filename):
        continue

      src_path = os.path.join(cur_path, filename)

      if keep_dir_structture:
        relative_path = os.path.relpath(src_path, src_root_dir)
        dst_dir = os.path.join(dst_root_dir, os.path.dirname(relative_path))
        if not os.path.exists(dst_dir):
          os.makedirs(dst_dir)
        dst_path = os.path.join(dst_dir, filename)
      else:
        # Use a random file name to avoid overwriting the same file.
        suffix = ''.join(random.choices(
            string.ascii_letters + string.digits, k=16))
        parts = filename.split('.')
        name = '.'.join(parts[:-1])
        ext = parts[-1]
        dst_path = os.path.join(dst_root_dir, f'{name}.{suffix}.{ext}')

      try:
        # Check file size
        if os.path.getsize(src_path) < size_threshold:
          move_fn(src_path, dst_path)
          continue  # Move to the next file if size condition is met

        # Regex check (if provided)
        moved = False
        for r in regexes:
          if r.match(filename):
            move_fn(src_path, dst_path)
            moved = True
            break  # Move if regex matches
        if moved:
          continue

        # Check if it's an image. If it is, check dimensions or other image-specific criteria
        try:
          img = Image.open(src_path)
          img.verify()  # Verify that it's a valid image
          img.close()
        except (IOError, OSError) as e:  # Handle cases where PIL can't open the file as an image
          move_fn(src_path, dst_path)
          continue

      except Exception as e:  # Catch general errors
        print(f"Error processing {src_path}: {e}")


# To run:
# vadjx
# python cleanup.py
cleanup_images(
    # src_root_dir='/Users/laigd/Documents/images/eee/网页',
    src_root_dir='/Users/laigd/.Trash/1',
    dst_root_dir='/Users/laigd/.Trash/2',
    size_threshold=20 * 1024,
    delete_regex_patterns=(
        # Don't remove gif! Small gif should be handled by size-based rule!
        # r'.*\.gif$',
        r'.*_avatar_.*\.jpg$',
        r'.*\.php$',
        r'^js(.[123].)?$',
        r'^f(\(1\))?\.txt$',
    ),
    keep_dir_structture=False,
)
