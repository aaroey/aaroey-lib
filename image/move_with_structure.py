import os
import shutil

import utils


def move_files(src_root_dir: str, dst_root_dir: str):
  """Walks through the directory, computes MD5s, and generates the HTML."""
  i = 0
  for cur_dir, _, files in os.walk(src_root_dir):
    for file in files:
      src_path = os.path.join(cur_dir, file)
      relative_path = os.path.relpath(src_path, src_root_dir)
      dst_path = os.path.join(dst_root_dir, relative_path)
      # print(f'\033[93m=> {src_path}\033[0m')
      # print(f'{dst_path}')
      # i += 1
      # if i > 100: break
      utils.move(src_path, dst_path)


if __name__ == '__main__':
  src_root_dir = '/Users/laigd/.Trash/3'
  dst_root_dir = '/Users/laigd/Documents/images/eee/selected-未筛选'
  move_files(src_root_dir=src_root_dir, dst_root_dir=dst_root_dir)
