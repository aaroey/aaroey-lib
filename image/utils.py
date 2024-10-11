import collections
import dataclasses
import hashlib
import json
import os
import random
import re
import shutil
import string
from urllib.parse import quote


def should_skip(filename: str):
  for suffix in (
      '.ds_store', '.py', '.html', '.json', '.txt', '.mp4', '.avi', '.mov'
  ):
    if filename.lower().endswith(suffix):
      return True
  return False


@dataclasses.dataclass(frozen=True, kw_only=True)
class ImageFileMeta:
  relative_path: str
  size: int
  w: int
  h: int


def generate_html(
    grouped_images: dict[str, list[ImageFileMeta]],
    scale_image_by_width: bool = False
):
  """Generates an HTML table with image links grouped by hash of the image."""
  html = """
  <!DOCTYPE html>
  <html>
  <head>
  <title>File Hash Mappings</title>
  </head>
  <body>
  <h1>File Hash Mappings</h1>
  <table>
  <thead>
    <tr>
      <th>Hash value</th>
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
    assert not first_file.relative_path.startswith('/')

    for file in file_list:
      width = 100
      if scale_image_by_width:
        width *= file.w / first_file.w
      html += f'<img src="{quote(file.relative_path)}" width="{int(width)}px" data-meta="{file.w} x {file.h}; {file.size}" /> '
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
