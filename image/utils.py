import collections
import dataclasses
import hashlib
import json
import os
import random
import re
import shutil
import string
import sys
from typing import Any
from urllib.parse import quote


def load_json_or(path: str, default_value: Any):
  loaded = default_value
  if os.path.exists(path):
    with open(path, 'r') as f:
      loaded = json.load(f)
  return loaded


def dump_json(path: str, value: Any):
  with open(path, 'w') as f:
    json.dump(value, f, indent=2)


def make_dataclass(*args, **kwargs):
  v = sys.version_info
  ver = f'{v.major}.{v.minor}.{v.micro}'
  print(f'\033[93m=> python {ver=}\033[0m')
  assert v.major == 3
  if v.minor <= 9:
    return dataclasses.dataclass(*args, **kwargs)
  return dataclasses.dataclass(*args, kw_only=True, **kwargs)


def should_skip(filename: str, size: int = None):
  # yapf: disable
  for suffix in (
      '.ds_store',  # System files
      '.html', '.json', '.py',  # Developer files
      '.avi', '.mov', '.mp4',  # Videos
      '.txt',  # Notes
      '.webp',  # opencv-python / cv2 can't read webp
  ):
    # yapf: enable
    if filename.lower().endswith(suffix):
      return True
  if size is not None and size > 10 * 2**20:  # Ignore large files.
    return True
  return False


@make_dataclass(frozen=True)
class ImageFileMeta:
  relative_path: str
  size: int
  w: int
  h: int
  meta: dict[str, Any] = dataclasses.field(default_factory=dict)


def generate_html(
    grouped_images: dict[str, list[ImageFileMeta]],
    cell_width: int = 100,
    scale_image_by_width: bool = False,
    check_first_image_path: bool = True,
):
  """Generates an HTML table with image links grouped by hash of the image."""
  html = """
  <!DOCTYPE html>
  <html>
  <head>
  <title>File Group Mappings</title>
  </head>
  <body>
  <h1>File Group Mappings</h1>
  <table>
  <thead>
    <tr>
      <th>Group Name</th>
      <th>Files</th>
    </tr>
  </thead>
  <tbody>
  """

  for key, file_list in grouped_images.items():
    if len(file_list) == 1:
      continue  # Don't show groups that only have one file.
    html += f'<tr><td>{key}</td><td>'

    # First file must not be moved, i.e. its path must be relative!
    first_file = file_list[0]
    if check_first_image_path:
      assert not first_file.relative_path.startswith('/')

    for file in file_list:
      width = cell_width
      if scale_image_by_width:
        width *= file.w / first_file.w
      html += f'<img src="{quote(file.relative_path)}" width="{int(width)}px" data-meta="{file.meta}" /> '
    html += '</td></tr>'

  html += """
  </tbody>
  </table>
  </body>
  </html>
  """
  return html


def move(src, dst):
  assert not os.path.exists(dst), f'{dst} already exist'
  shutil.move(src, dst)
